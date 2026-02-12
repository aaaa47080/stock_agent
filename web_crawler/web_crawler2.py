import argparse
import asyncio
import json
from urllib.parse import urlsplit, urlunsplit

import trafilatura
from playwright.async_api import async_playwright
from summarize_futunn_posts import (
    DEFAULT_SYSTEM_PROMPT,
    create_summary_chain_from_env,
    summarize_articles,
)

MAIN_URL = "https://news.futunn.com/main?chain_id=FBB0EGgLsPxZBN.1klpic0&global_content=%7B%22promote_id%22%3A13766,%22sub_promote_id%22%3A1,%22f%22%3A%22nn%2F%22%7D&lang=zh-cn"
TSM_URL = "https://www.futunn.com/hk/stock/TSM-US/news?global_content=%7B%22promote_id%22%3A13643,%22sub_promote_id%22%3A60%7D"
STOCK_NEWS_TEMPLATE = "https://www.futunn.com/hk/stock/{ticker}-US/news?global_content=%7B%22promote_id%22%3A13643,%22sub_promote_id%22%3A60%7D"

OUT_FILE = "futunn_main_posts.jsonl"
SCROLL_ROUNDS = 0          # 想抓更多就加大
LIMIT = 5               # 只抓一篇就設 1；抓全部就 None
ONLY_POST = True           # True=只抓 /post/；False=也抓 /flash/
PRESET_URLS = {"main": MAIN_URL, "tsm": TSM_URL}


def parse_args():
    parser = argparse.ArgumentParser(description="Crawl futunn news pages with playwright and trafilatura")
    parser.add_argument("--url", default=None, help="Target page to scan for article links (overrides preset)")
    parser.add_argument("--preset", choices=list(PRESET_URLS.keys()), default=None, help="Preset page to crawl when --url is not provided; omit for interactive prompt")
    parser.add_argument("--output", default=OUT_FILE, help="JSONL output file path")
    parser.add_argument(
        "--scroll-rounds",
        type=int,
        default=SCROLL_ROUNDS,
        help="Number of scroll events to trigger lazy loading",
    )
    parser.add_argument("--limit", type=int, default=LIMIT, help="Maximum articles to fetch (<=0 means no limit)")
    parser.add_argument("--include-flash", action="store_true", help="When set also keep /flash/ links")

    parser.add_argument(
        "--summary-output",
        default="futunn_main_summaries.jsonl",
        help="Write batch summaries to this JSONL file",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Do not summarize content during crawling",
    )
    parser.add_argument(
        "--summary-batch-size",
        type=int,
        default=3,
        help="Number of fetched articles per summarize batch",
    )
    parser.add_argument(
        "--summary-max-content-chars",
        type=int,
        default=6000,
        help="Trim content length before sending to LLM",
    )
    parser.add_argument(
        "--summary-system-prompt",
        default=DEFAULT_SYSTEM_PROMPT,
        help="System prompt used by LLM summarizer",
    )
    parser.add_argument(
        "--summary-temperature",
        type=float,
        default=0.2,
        help="LLM temperature for summaries",
    )

    return parser.parse_args()


def build_stock_news_url(target: str) -> str:
    candidate = target.strip()
    if candidate.lower().startswith("http://") or candidate.lower().startswith("https://"):
        return candidate
    ticker = candidate.upper()
    return STOCK_NEWS_TEMPLATE.format(ticker=ticker)


def select_target_url():
    prompt = "請輸入想爬取的美股代號（例如 TSM）或完整 Futunn URL："
    while True:
        entry = input(prompt).strip()
        if not entry:
            print("請輸入有效的代號或 URL。")
            continue
        return build_stock_news_url(entry)

def canonical_url(url: str) -> str:
    sp = urlsplit(url)
    return urlunsplit((sp.scheme, sp.netloc, sp.path, "", ""))


def clean_text(text: str) -> str:
    if not text:
        return ""
    cut_markers = [
        "以上内容仅用作资讯或教育之目的",
        "风险及免责提示",
        "譯文內容由第三人軟體翻譯",
    ]
    for m in cut_markers:
        idx = text.find(m)
        if idx != -1:
            text = text[:idx].strip()
    return text.strip()


def resolve_effective_title(article_title: str, list_title: str) -> str:
    article_title = (article_title or "").strip()
    list_title = (list_title or "").strip()
    generic_titles = {"新聞", "新闻", "News"}
    if not article_title or article_title in generic_titles:
        return list_title or article_title
    return article_title


async def collect_main_links(page, main_url: str, scroll_rounds: int = 6, only_post: bool = True):
    await page.goto(main_url, wait_until="domcontentloaded", timeout=120000)
    await page.wait_for_timeout(1500)

    # 滾動讓更多列表載入（/main 可能會 lazy-load）
    for _ in range(scroll_rounds):
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(700)

    js = r"""
    (onlyPost) => {
      const out = [];
      const anchors = Array.from(document.querySelectorAll('a[href]'));

      for (const a of anchors) {
        const className = (a.getAttribute("class") || "").toLowerCase();
        if (className.includes("web_search-hot-news")) {
          continue;
        }
        const href = a.href || "";
        if (onlyPost) {
          if (!href.includes("/post/")) continue;
        } else {
          if (!href.includes("/post/") && !href.includes("/flash/")) continue;
        }

        // 嘗試抓乾淨標題：優先找 h1/h2/h3 或 title-like class
        const titleEl =
          a.querySelector("h1,h2,h3,[class*='title'],[class*='Title']") || a;

        let text = (titleEl.innerText || a.innerText || "").trim();
        // 有些 a 會把來源/時間也塞進 innerText，取第一行通常比較像標題
        text = text.split("\n")[0].trim();

        out.push({ href, title: text });
      }
      return out;
    }
    """

    items = await page.evaluate(js, only_post)

    # 去重 + canonical
    seen = set()
    links = []
    for it in items:
        cu = canonical_url(it["href"])
        if cu in seen:
            continue
        seen.add(cu)
        links.append({"url": cu, "title": it.get("title", "")})

    return links


async def fetch_article_via_playwright(context, url: str):
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(1200)

        html = await page.content()

        # 用 trafilatura 抽正文（不綁死 selector）
        main = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        main = clean_text(main)

        # title：先用 document.title；不行再 fallback
        title = (await page.title()) or ""
        title = title.strip()

        return {"url": url, "title": title, "content": main}
    finally:
        await page.close()


def process_summary_batch(
    pending_rows: list[dict],
    summary_chain,
    summary_max_content_chars: int,
) -> list[str]:
    if not pending_rows:
        return []
    return summarize_articles(summary_chain, pending_rows, max_content_chars=summary_max_content_chars)


async def main():
    args = parse_args()
    if args.url:
        target_url = args.url
    elif args.preset:
        target_url = PRESET_URLS.get(args.preset, MAIN_URL)
    else:
        target_url = select_target_url()
    out_file = args.output
    scroll_rounds = args.scroll_rounds
    limit = args.limit
    if limit is not None and limit <= 0:
        limit = None
    only_post = not args.include_flash
    summary_batch_size = args.summary_batch_size if args.summary_batch_size > 0 else 1
    summary_chain = None
    if not args.skip_summary:
        summary_chain = create_summary_chain_from_env(
            system_prompt=args.summary_system_prompt,
            temperature=args.summary_temperature,
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="zh-CN", viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        print(f"target -> {target_url}")
        links = await collect_main_links(page, target_url, scroll_rounds=scroll_rounds, only_post=only_post)
        print(f"links found = {len(links)}")

        if limit is not None:
            links = links[:limit]
            print(f"limit -> {limit}")

        if not links:
            print("No links found. Consider increasing SCROLL_ROUNDS or try --include-flash")
            await browser.close()
            return

        with open(out_file, "w", encoding="utf-8-sig") as f:
            summary_fp = None
            if not args.skip_summary:
                summary_fp = open(args.summary_output, "w", encoding="utf-8-sig")
            try:
                pending_batch: list[dict] = []

                for i, it in enumerate(links, 1):
                    url = it["url"]
                    art = await fetch_article_via_playwright(context, url)
                    art["title"] = resolve_effective_title(art.get("title", ""), it.get("title", ""))
                    art["_idx"] = i

                    f.write(json.dumps({k: v for k, v in art.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")
                    pending_batch.append(art)

                    should_flush = len(pending_batch) >= summary_batch_size or i == len(links)
                    if not should_flush:
                        continue

                    summaries = []
                    if summary_chain is not None:
                        summaries = process_summary_batch(
                            pending_batch,
                            summary_chain,
                            summary_max_content_chars=args.summary_max_content_chars,
                        )
                    else:
                        summaries = ["(skip summary)"] * len(pending_batch)

                    for item, summary in zip(pending_batch, summaries):
                        fetch_text = item.get("title", "").strip()[:60]
                        one_line_summary = " | ".join(
                            part.strip() for part in summary.splitlines() if part.strip()
                        )
                        print(
                            f"[{item.get('_idx')}/{len(links)}] "
                            f"fetch: {fetch_text} \n"
                            f"summary: {one_line_summary} \n"
                            f"url: {item['url']}"
                            f"\n=================================\n"
                        )
                        if summary_fp is not None:
                            summary_fp.write(
                                json.dumps(
                                    {
                                        "url": item["url"],
                                        "title": item["title"],
                                        "summary": summary,
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                    pending_batch.clear()
            finally:
                if summary_fp is not None:
                    summary_fp.close()

        print(f"saved -> {out_file}")
        if not args.skip_summary:
            print(f"summaries saved -> {args.summary_output}")


if __name__ == "__main__":
    asyncio.run(main())
