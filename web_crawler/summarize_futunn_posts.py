import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, Optional
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

load_dotenv()

DEFAULT_INPUT = Path(__file__).with_name("futunn_main_posts.jsonl")
DEFAULT_OUTPUT = Path(__file__).with_name("futunn_main_summaries.jsonl")
DEFAULT_SYSTEM_PROMPT = (
    "你是財經新聞摘要助手。請用繁體中文（台灣用語）做精簡摘要，"
    "只根據提供內容，不要補充未提及的資訊。"
)


def derive_api_base(endpoint: str) -> Optional[str]:
    if not endpoint:
        return None
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def derive_deployment_from_endpoint(endpoint: str) -> Optional[str]:
    if not endpoint:
        return None
    parsed = urlsplit(endpoint)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        idx = parts.index("deployments")
    except ValueError:
        return None
    if idx + 1 >= len(parts):
        return None
    name = parts[idx + 1].strip()
    return name or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize each content field in futunn_main_posts.jsonl with Azure OpenAI."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input JSONL file path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSONL file path.")
    parser.add_argument("--max-items", type=int, default=None, help="Maximum number of rows to summarize.")
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=6000,
        help="Trim content to this length before sending to LLM.",
    )
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--llm-endpoint", default=os.getenv("AZURE_OPENAI_LLM_ENDPOINT"))
    parser.add_argument("--llm-api-key", default=os.getenv("AZURE_OPENAI_LLM_API_KEY"))
    parser.add_argument("--deployment-name", default=os.getenv("AZURE_LLM_DEPLOYMENT"))
    parser.add_argument("--model-name", default=os.getenv("AZURE_LLM_MODEL", ""))
    parser.add_argument("--api-version", default=os.getenv("AZURE_LLM_API_VERSION", ""))
    return parser.parse_args()


def build_llm(args: argparse.Namespace) -> AzureChatOpenAI:
    if not args.llm_endpoint:
        raise RuntimeError("Missing --llm-endpoint or AZURE_OPENAI_LLM_ENDPOINT")
    endpoint = derive_api_base(args.llm_endpoint)
    if not endpoint:
        raise RuntimeError("Invalid Azure endpoint; unable to derive base URL")
    if not args.llm_api_key:
        raise RuntimeError("Missing --llm-api-key or AZURE_OPENAI_LLM_API_KEY")
    endpoint_deployment = derive_deployment_from_endpoint(args.llm_endpoint)
    deployment_name = args.deployment_name
    if endpoint_deployment and endpoint_deployment != deployment_name:
        print(
            f"deployment mismatch: env/arg='{deployment_name}', endpoint='{endpoint_deployment}', "
            f"use endpoint deployment '{endpoint_deployment}'"
        )
        deployment_name = endpoint_deployment
    if not deployment_name:
        raise RuntimeError("Missing --deployment-name or AZURE_LLM_DEPLOYMENT")
    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=deployment_name,
        api_version=args.api_version,
        api_key=args.llm_api_key,
        temperature=args.temperature,
        model=args.model_name,
    )


def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8-sig") as fp:
        for line_no, raw in enumerate(fp, 1):
            row = raw.strip()
            if not row:
                continue
            try:
                data = json.loads(row)
            except json.JSONDecodeError:
                print(f"skip malformed json line {line_no}")
                continue
            if isinstance(data, dict):
                yield data


def build_chain(system_prompt: str, llm: AzureChatOpenAI):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                (
                    "請摘要以下新聞，輸出格式固定三行：\n"
                    "1) 核心重點：一句話（30字內）\n"
                    "2) 市場影響：一句話（30字內）\n"
                    "3) 風險提醒：一句話（30字內）\n\n"
                    "標題：{title}\n"
                    "網址：{url}\n"
                    "內文：\n{content}\n"
                ),
            ),
        ]
    )
    return prompt | llm | StrOutputParser()


def truncate_content(content: str, max_chars: int) -> str:
    if max_chars <= 0:
        return content
    return content[:max_chars]


def summarize_articles(chain, rows: list[dict], max_content_chars: int = 6000) -> list[str]:
    summaries: list[str] = []
    for row in rows:
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        content = (row.get("content") or "").strip()
        if not content:
            summary = "1) 核心重點：內容不足\n2) 市場影響：內容不足\n3) 風險提醒：內容不足"
        else:
            summary = chain.invoke(
                {
                    "title": title,
                    "url": url,
                    "content": truncate_content(content, max_content_chars),
                }
            ).strip()
        summaries.append(summary)
    return summaries


def create_summary_chain_from_env(
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    temperature: float = 0.2,
):
    runtime_args = SimpleNamespace(
        llm_endpoint=os.getenv("AZURE_OPENAI_LLM_ENDPOINT"),
        llm_api_key=os.getenv("AZURE_OPENAI_LLM_API_KEY"),
        deployment_name=os.getenv("AZURE_LLM_DEPLOYMENT"),
        model_name=os.getenv("AZURE_LLM_MODEL", ""),
        api_version=os.getenv("AZURE_LLM_API_VERSION", ""),
        temperature=temperature,
    )
    llm = build_llm(runtime_args)
    return build_chain(system_prompt, llm)


def summarize_rows(args: argparse.Namespace) -> None:
    llm = build_llm(args)
    chain = build_chain(args.system_prompt, llm)

    rows = list(read_jsonl(args.input))
    if args.max_items and args.max_items > 0:
        rows = rows[: args.max_items]
    summaries = summarize_articles(chain, rows, max_content_chars=args.max_content_chars)

    with args.output.open("w", encoding="utf-8-sig") as out_fp:
        total = len(rows)
        for idx, (row, summary) in enumerate(zip(rows, summaries), 1):
            url = (row.get("url") or "").strip()
            title = (row.get("title") or "").strip()

            payload = {
                "url": url,
                "title": title,
                "summary": summary,
            }
            out_fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
            print(f"[{idx}/{total}] summarized: {title[:40]}")

    print(f"saved -> {args.output}")


def main() -> None:
    args = parse_args()
    summarize_rows(args)


if __name__ == "__main__":
    main()
