"""
Admin System Config Management
Configuration and audit log endpoints
"""
from api.utils import run_sync
from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import require_admin
from core.database.connection import get_connection
from core.database.system_config import list_all_configs_with_metadata, set_config
from .schemas import UpdateConfigRequest

router = APIRouter(tags=["Admin - Config"])


@router.get("/config/all")
async def admin_get_all_configs(
    admin_user: dict = Depends(require_admin)
):
    """獲取所有系統設定（依類別分組）"""
    configs = await run_sync(list_all_configs_with_metadata)

    # Group by category
    grouped = {}
    for cfg in configs:
        cat = cfg.get("category", "general")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(cfg)

    return {"success": True, "configs_by_category": grouped}


@router.put("/config/{key}")
async def admin_update_config(
    key: str,
    request: UpdateConfigRequest,
    admin_user: dict = Depends(require_admin)
):
    """更新單一設定值"""
    success = await run_sync(
        lambda: set_config(key, request.value, changed_by=admin_user["user_id"])
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update config")

    return {"success": True, "key": key, "value": request.value}


@router.get("/config/audit")
async def admin_get_config_audit(
    limit: int = Query(50, ge=1, le=200),
    admin_user: dict = Depends(require_admin)
):
    """獲取設定變更歷史"""
    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT config_key, old_value, new_value, changed_by, changed_at
                    FROM config_audit_log
                    ORDER BY changed_at DESC
                    LIMIT %s
                """, (limit,))
                rows = c.fetchall()
                return [{
                    "key": r[0], "old_value": r[1], "new_value": r[2],
                    "changed_by": r[3],
                    "changed_at": r[4].isoformat() if r[4] else None
                } for r in rows]
        finally:
            conn.close()

    logs = await run_sync(_query)
    return {"success": True, "logs": logs}
