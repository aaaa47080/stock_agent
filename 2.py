import asyncio
import json
from urllib.parse import urlsplit, urlunsplit

import trafilatura
from playwright.async_api import async_playwright

MAIN_URL = "https://news.futunn.com/main?chain_id=FBB0EGgLsPxZBN.1klpic0&global_content=%7B%22promote_id%22%3A13766,%22sub_promote_id%22%3A1,%22f%22%3A%22nn%2F%22%7D&lang=zh-cn"

OUT_FILE = "futunn_main_posts.jsonl"
SCROLL_ROUNDS = 0          # 想抓更多就加大
LIMIT = 5               # 只抓一篇就設 1；抓全部就 None
ONLY_POST = True           # True=只抓 /post/；False=也抓 /flash/


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


async def collect_main_links(page, scroll_rounds: int = 6, only_post: bool = True):
    await page.goto(MAIN_URL, wait_until="domcontentloaded", timeout=120000)
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
        const href = a.href || "";
        if (onlyPost) {
          if (!href.includes("/post/")) continue;
        } else {
          if (!href.includes('/post/')) continue;
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


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="zh-CN", viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        links = await collect_main_links(page, scroll_rounds=SCROLL_ROUNDS, only_post=ONLY_POST)
        print(f"links found = {len(links)}")

        if LIMIT is not None:
            links = links[:LIMIT]
            print(f"limit -> {LIMIT}")

        if not links:
            print("No links found. Consider increasing SCROLL_ROUNDS or set ONLY_POST=False.")
            await browser.close()
            return

        with open(OUT_FILE, "w", encoding="utf-8") as f:
            for i, it in enumerate(links, 1):
                url = it["url"]
                print(f"[{i}/{len(links)}] fetch:", it.get("title", "")[:60], url)
                art = await fetch_article_via_playwright(context, url)

                # 立即看到成果（抓一篇就停時很有用）
                print("  -> title:", art["title"][:80])
                print("  -> content_len:", len(art["content"] or ""))

                f.write(json.dumps(art, ensure_ascii=False) + "\n")

        print(f"saved -> {OUT_FILE}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
