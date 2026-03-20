"""
依赖包清理分析脚本
分析项目实际使用的包，生成精简的 requirements.txt
"""

import re
from pathlib import Path
from typing import Set

# 已知的明确未使用的包（通过分析确认）
UNUSED_PACKAGES = {
    "backtrader",  # 未在代码中找到引用
    "gradio",  # UI库，未使用
    "gradio_client",  # Gradio 客户端
    "ipython",  # 开发工具，生产环境不需要
    "ipython_pygments_lexers",
    "ipywidgets",
    "jupyterlab_widgets",
    "widgetsnbextension",
    "jupyter",
    "ffmpy",  # 音频处理，未使用
    "pydub",  # 音频处理，未使用
    "ImageIO",  # 图像处理，未使用（注意大小写）
    "imageio",
    "anywidget",
    "groovy",  # 未找到引用
    "vectorbt",  # 回测库，未使用
    "matplotlib-inline",  # Jupyter 专用
    "tradingpattern",  # 未找到引用
    "hf-xet",  # Hugging Face 工具，未使用
}

# 实际使用的核心包（从 import 分析)
CORE_PACKAGES = {
    # FastAPI 核心
    "fastapi",
    "uvicorn",
    "gunicorn",  # 新增的生产环境依赖
    "starlette",
    "pydantic",
    "pydantic_core",
    "pydantic-settings",
    "python-multipart",
    # ASGI/异步
    "h11",
    "httpcore",
    "httpx",
    "httpx-sse",
    "aiohttp",
    "aiohappyeyeballs",
    "aiosignal",
    "aiofiles",
    "aiosqlite",
    "anyio",
    "sniffio",
    "websockets",
    # 数据库
    "SQLAlchemy",
    "sqlite-vec",
    # LangChain 生态
    "langchain",
    "langchain-core",
    "langchain-community",
    "langchain-openai",
    "langchain-google-genai",
    "langchain-text-splitters",
    "langgraph",
    "langgraph-checkpoint",
    "langgraph-checkpoint-sqlite",
    "langgraph-prebuilt",
    "langgraph-sdk",
    "langsmith",
    # LLM 提供商
    "openai",
    "google-genai",
    "google-generativeai",
    "google-ai-generativelanguage",
    "google-api-core",
    "google-api-python-client",
    "google-auth",
    "google-auth-httplib2",
    # 数据处理
    "pandas",
    "numpy",
    "pandas-ta",  # 技术指标
    "scipy",
    "scikit-learn",
    "seaborn",
    # 图表
    "matplotlib",
    "plotly",
    "contourpy",
    "cycler",
    "fonttools",
    "kiwisolver",
    # 时间处理
    "python-dateutil",
    "pytz",
    "tzdata",
    "tzlocal",
    "dateparser",
    # 工具库
    "requests",
    "requests-toolbelt",
    "click",
    "rich",
    "typer",
    "typer-slim",
    # 缓存
    "cachetools",
    # 环境变量
    "python-dotenv",
    # JSON处理
    "orjson",
    "dirtyjson",
    "jiter",
    # 序列化
    "marshmallow",
    "dataclasses-json",
    # 协议和格式
    "protobuf",
    "proto-plus",
    "googleapis-common-protos",
    "grpcio",
    "grpcio-status",
    # Token 处理
    "tiktoken",
    # 监控日志
    "filelock",
    "fsspec",
    # 网络请求
    "certifi",
    "charset-normalizer",
    "idna",
    "urllib3",
    "httplib2",
    # 压缩
    "brotli",
    "zstandard",
    # 其他工具
    "packaging",
    "Jinja2",
    "MarkupSafe",
    "regex",
    "six",
    "decorator",
    "attrs",
    "frozenlist",
    "multidict",
    "propcache",
    "yarl",
    "tqdm",
    "joblib",
    "threadpoolctl",
    "dill",
    "pillow",
    "pyparsing",
    "tenacity",
    "annotated-types",
    "typing_extensions",
    "typing-inspect",
    "typing-inspection",
    "mypy_extensions",
    "distro",
    "shellingham",
    "tomlkit",
    "PyYAML",
    "markdown-it-py",
    "mdurl",
    "Pygments",
    "pyasn1",
    "pyasn1_modules",
    "rsa",
    "uritemplate",
    "uuid_utils",
    "semantic-version",
    "narwhals",
    "safehttpx",
    "jsonpatch",
    "jsonpointer",
    "filetype",
    "ormsgpack",
    "schedule",
    "xxhash",
    "greenlet",
}


def analyze_imports(project_root: Path) -> Set[str]:
    """分析项目中实际导入的包"""
    imports = set()

    for py_file in project_root.rglob("*.py"):
        # 跳过虚拟环境和缓存
        if any(p in py_file.parts for p in [".venv", "__pycache__", ".git"]):
            continue

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 使用正则表达式提取 import
            import_patterns = [
                r"^import\s+(\w+)",
                r"^from\s+(\w+)",
            ]

            for pattern in import_patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    imports.add(match.group(1))

        except Exception as e:
            print(f"Error reading {py_file}: {e}")

    return imports


def generate_clean_requirements():
    """生成清理后的 requirements.txt"""
    # 定位项目根目录 (脚本在 scripts/ 下)
    project_root = Path(__file__).parent.parent
    req_file = project_root / "requirements.txt"

    if not req_file.exists():
        print(f"❌ 找不到 requirements.txt: {req_file}")
        return

    # 读取现有 requirements
    with open(req_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 分析使用的包
    used_imports = analyze_imports(project_root)

    print("🔍 实际引用的包 (前20个):")
    for imp in sorted(list(used_imports)[:20]):
        print(f"  - {imp}")
    print(f"  ... 共 {len(used_imports)} 个")

    # 清理后的依赖
    clean_lines = []
    removed_packages = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            clean_lines.append(line)
            continue

        # 提取包名
        package_name = line_stripped.split("==")[0].split("[")[0].lower()

        # 检查是否在删除列表中
        if any(unused.lower() in package_name for unused in UNUSED_PACKAGES):
            removed_packages.append(line_stripped)
            print(f"❌ 移除: {line_stripped}")
        else:
            clean_lines.append(line)

    # 写入备份
    backup_file = project_root / "requirements.txt.backup"
    with open(backup_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"\n✅ 原文件备份到: {backup_file}")

    # 写入清理后的文件
    with open(req_file, "w", encoding="utf-8") as f:
        f.writelines(clean_lines)

    print("\n📊 清理总结:")
    print(
        f"  原始包数: {len([line for line in lines if line.strip() and not line.strip().startswith('#')])}"
    )
    print(f"  移除包数: {len(removed_packages)}")
    print(
        f"  保留包数: {len([line for line in clean_lines if line.strip() and not line.strip().startswith('#')])}"
    )

    print("\n🗑️  已移除的包:")
    for pkg in removed_packages:
        print(f"  - {pkg}")


if __name__ == "__main__":
    print("=" * 60)
    print("依赖包清理工具")
    print("=" * 60)
    generate_clean_requirements()
    print("\n✅ 完成！请测试应用是否正常运行。")
