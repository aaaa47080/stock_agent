"""
API 入口點 - 供 Gunicorn/Zeabur 部署使用
"""
import sys
import os

# 確保項目根目錄在 Python 路徑中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 從 api_server.py 導入 app
# noqa: E402 — 必須在 sys.path 修改後才能 import
from api_server import app

__all__ = ["app"]
