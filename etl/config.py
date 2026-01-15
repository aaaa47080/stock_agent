from pathlib import Path

# ETL Configuration
ETL_ROOT = Path(__file__).resolve().parent

# GPU Allocation
# GPU 0: DeepSeek OCR (VRAM heavy)
# GPU 1: VLM / Embedding (VRAM heavy)
GPU_MAPPING = {
    "dialysis": "0",
    "general": "0",
    "images": "1",
    "jsonl": "0" 
}

# Source Directories
SOURCE_DIRS = {
    "jsonl": Path("/home/danny/AI-agent/RAG_JSONL"),
    "general_pdf": Path("/home/danny/AI-agent/DataSet"),
    "dialysis_pdf": Path("/home/danny/AI-agent/洗腎衛教"),
}

# Logging
LOG_DIR = ETL_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
