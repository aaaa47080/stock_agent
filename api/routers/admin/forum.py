"""
Admin Forum Management
Post, comment, and report management endpoints
"""
import asyncio
import logging
from functools import partial
from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import require_admin
from core.database.connection import get_connection
from core.database.governance import finalize_report, get_report_by_id
from .schemas import PostVisibilityRequest, PostPinRequest, ResolveReportRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Forum"])


@router.get("/forum/posts")
async def admin_list_posts(
    search: str = Query(None, max_length=200),
    status: str = Query("all", pattern="^(all|hidden|pinned)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """管理後台 - 列出論壇貼文（含隱藏貼文）"""
    loop = asyncio.get_running_loop()
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                where_clauses = []
                params = []

                if search:
                    where_clauses.append("(p.title ILIKE %s OR u.username ILIKE %s)")
                    like = f"%{search}%"
                    params.extend([like, like])

                if status == "hidden":
                    where_clauses.append("p.is_hidden = 1")
                elif status == "pinned":
                    where_clauses.append("p.is_pinned = 1")

                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                c.execute(f"""
                    SELECT p.id, p.title, p.user_id, u.username, p.category,
                           p.is_hidden, p.is_pinned, p.comment_count, p.view_count,
                           p.push_count, p.boo_count, p.created_at
                    FROM posts p
                    LEFT JOIN users u ON p.user_id = u.user_id
                    {where_sql}
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                rows = c.fetchall()

                c.execute(f"""
                    SELECT COUNT(*)
                    FROM posts p
                    LEFT JOIN users u ON p.user_id = u.user_id
                    {where_sql}
                """, params)
                total = c.fetchone()[0]

                return {
                    "posts": [{
                        "id": r[0], "title": r[1], "user_id": r[2],
                        "username": r[3] or "Unknown", "category": r[4],
                        "is_hidden": bool(r[5]), "is_pinned": bool(r[6]),
                        "comment_count": r[7] or 0, "view_count": r[8] or 0,
                        "push_count": r[9] or 0, "boo_count": r[10] or 0,
                        "created_at": r[11].isoformat() if r[11] else None
                    } for r in rows],
                    "total": total, "page": page, "limit": limit
                }
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


@router.patch("/forum/posts/{post_id}/visibility")
async def admin_toggle_post_visibility(
    post_id: int,
    request: PostVisibilityRequest,
    admin_user: dict = Depends(require_admin)
):
    """隱藏/顯示貼文"""
    loop = asyncio.get_running_loop()
    hidden_int = 1 if request.is_hidden else 0

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_hidden, title FROM posts WHERE id = %s", (post_id,))
                row = c.fetchone()
                if not row:
                    return None
                old_hidden = bool(row[0])

                c.execute("UPDATE posts SET is_hidden = %s WHERE id = %s", (hidden_int, post_id))
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"admin_forum:post_visibility:{post_id}",
                      "hidden" if old_hidden else "visible",
                      "hidden" if request.is_hidden else "visible",
                      admin_user["user_id"]))
                conn.commit()
                return {"old_hidden": old_hidden, "new_hidden": request.is_hidden, "title": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True, **result}


@router.patch("/forum/posts/{post_id}/pin")
async def admin_toggle_post_pin(
    post_id: int,
    request: PostPinRequest,
    admin_user: dict = Depends(require_admin)
):
    """置頂/取消置頂貼文"""
    loop = asyncio.get_running_loop()
    pinned_int = 1 if request.is_pinned else 0

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_pinned, title FROM posts WHERE id = %s", (post_id,))
                row = c.fetchone()
                if not row:
                    return None

                c.execute("UPDATE posts SET is_pinned = %s WHERE id = %s", (pinned_int, post_id))
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"admin_forum:post_pin:{post_id}",
                      "pinned" if row[0] else "unpinned",
                      "pinned" if request.is_pinned else "unpinned",
                      admin_user["user_id"]))
                conn.commit()
                return {"old_pinned": bool(row[0]), "new_pinned": request.is_pinned, "title": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True, **result}


@router.patch("/forum/comments/{comment_id}/visibility")
async def admin_toggle_comment_visibility(
    comment_id: int,
    request: PostVisibilityRequest,
    admin_user: dict = Depends(require_admin)
):
    """隱藏/顯示留言"""
    loop = asyncio.get_running_loop()
    hidden_int = 1 if request.is_hidden else 0

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_hidden, post_id FROM forum_comments WHERE id = %s", (comment_id,))
                row = c.fetchone()
                if not row:
                    return None

                c.execute("UPDATE forum_comments SET is_hidden = %s WHERE id = %s", (hidden_int, comment_id))
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"admin_forum:comment_visibility:{comment_id}",
                      "hidden" if row[0] else "visible",
                      "hidden" if request.is_hidden else "visible",
                      admin_user["user_id"]))
                conn.commit()
                return {"old_hidden": bool(row[0]), "new_hidden": request.is_hidden, "post_id": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"success": True, **result}


@router.get("/forum/reports")
async def admin_list_reports(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """列出內容舉報"""
    loop = asyncio.get_running_loop()
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT cr.id, cr.content_type, cr.content_id, cr.reporter_user_id,
                           u.username as reporter_username, cr.report_type, cr.description,
                           cr.review_status, cr.approve_count, cr.reject_count, cr.created_at
                    FROM content_reports cr
                    LEFT JOIN users u ON cr.reporter_user_id = u.user_id
                    WHERE cr.review_status = %s
                    ORDER BY cr.created_at DESC
                    LIMIT %s OFFSET %s
                """, (status, limit, offset))
                rows = c.fetchall()

                c.execute("SELECT COUNT(*) FROM content_reports WHERE review_status = %s", (status,))
                total = c.fetchone()[0]

                reports = []
                for r in rows:
                    report = {
                        "id": r[0], "content_type": r[1], "content_id": r[2],
                        "reporter_user_id": r[3], "reporter_username": r[4] or "Unknown",
                        "report_type": r[5], "description": r[6],
                        "review_status": r[7], "approve_count": r[8] or 0,
                        "reject_count": r[9] or 0,
                        "created_at": r[10].isoformat() if r[10] else None,
                        "content_preview": None
                    }
                    # Fetch content preview
                    if r[1] == "post":
                        c.execute("SELECT title FROM posts WHERE id = %s", (r[2],))
                    elif r[1] == "comment":
                        c.execute("SELECT content FROM forum_comments WHERE id = %s", (r[2],))
                    preview_row = c.fetchone()
                    if preview_row:
                        report["content_preview"] = (preview_row[0] or "")[:100]
                    reports.append(report)

                return {"reports": reports, "total": total, "page": page, "limit": limit}
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


@router.post("/forum/reports/{report_id}/resolve")
async def admin_resolve_report(
    report_id: int,
    request: ResolveReportRequest,
    admin_user: dict = Depends(require_admin)
):
    """處理舉報（批准=隱藏內容+違規記點，駁回=不處理）"""
    loop = asyncio.get_running_loop()

    # 1. Get report details
    report = await loop.run_in_executor(None, partial(get_report_by_id, None, report_id))
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.get("review_status") != "pending":
        raise HTTPException(status_code=400, detail="Report already resolved")

    # 2. Finalize via governance system
    _ = await loop.run_in_executor(
        None, partial(finalize_report, None, report_id, request.decision,
                      request.violation_level, admin_user["user_id"])
    )

    # 3. If approved, auto-hide the reported content
    if request.decision == "approved":
        content_type = report.get("content_type")
        content_id = report.get("content_id")

        def _hide_content():
            conn = get_connection()
            try:
                with conn.cursor() as c:
                    if content_type == "post":
                        c.execute("UPDATE posts SET is_hidden = 1 WHERE id = %s", (content_id,))
                    elif content_type == "comment":
                        c.execute("UPDATE forum_comments SET is_hidden = 1 WHERE id = %s", (content_id,))
                    c.execute("""
                        INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                        VALUES (%s, %s, %s, %s)
                    """, (f"admin_forum:report_resolve:{report_id}",
                          "pending", f"{request.decision}:hide_{content_type}:{content_id}",
                          admin_user["user_id"]))
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning(f"Failed to hide content for report {report_id}: {e}")
            finally:
                conn.close()

        await loop.run_in_executor(None, _hide_content)

    return {"success": True, "report_id": report_id, "decision": request.decision,
            "content_hidden": request.decision == "approved"}
