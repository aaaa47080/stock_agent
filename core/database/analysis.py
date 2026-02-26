"""
分析報告資料庫操作
儲存 V4 Agent 產生的分析報告，供前端歷史查詢使用。
"""
import json
from typing import List, Dict, Optional

from .base import DatabaseBase


def save_analysis_report(
    session_id: str,
    user_id: str,
    symbol: str,
    interval: str = "1d",
    report_text: str = "",
    metadata: Optional[Dict] = None,
) -> Optional[int]:
    """
    儲存分析報告。

    Returns:
        新建的 report id，失敗時返回 None。
    """
    row = DatabaseBase.query_one(
        '''
        INSERT INTO analysis_reports (session_id, user_id, symbol, interval, report_text, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        ''',
        (
            session_id,
            user_id,
            symbol.upper(),
            interval,
            report_text,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    return row["id"] if row else None


def get_analysis_reports(user_id: str, limit: int = 20) -> List[Dict]:
    """
    取得使用者的分析報告清單（最新優先）。

    Returns:
        報告清單，每筆含 id, session_id, symbol, interval, report_text, metadata, created_at。
    """
    rows = DatabaseBase.query_all(
        '''
        SELECT id, session_id, symbol, interval, report_text, metadata, created_at
        FROM analysis_reports
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        ''',
        (user_id, limit),
    )
    result = []
    for row in rows:
        created_at = row.get("created_at")
        if created_at and not isinstance(created_at, str):
            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        result.append({
            "id": row["id"],
            "session_id": row["session_id"],
            "symbol": row["symbol"],
            "interval": row["interval"],
            "report_text": row["report_text"],
            "metadata": metadata or {},
            "created_at": created_at,
        })
    return result


def get_analysis_report_by_id(report_id: int) -> Optional[Dict]:
    """取得單一分析報告的完整內容。"""
    row = DatabaseBase.query_one(
        "SELECT * FROM analysis_reports WHERE id = %s",
        (report_id,),
    )
    if not row:
        return None
    created_at = row.get("created_at")
    if created_at and not isinstance(created_at, str):
        created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "symbol": row["symbol"],
        "interval": row["interval"],
        "report_text": row["report_text"],
        "metadata": metadata or {},
        "created_at": created_at,
    }
