"""
Admin Forum Management
Post, comment, and report management endpoints
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, update

from api.deps import require_admin
from core.orm import ForumComment, Post
from core.orm.config_repo import _write_audit_log
from core.orm.governance_repo import governance_repo
from core.orm.session import get_session_factory

from .schemas import PostPinRequest, PostVisibilityRequest, ResolveReportRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Forum"])


@router.get("/forum/posts")
async def admin_list_posts(
    search: str = Query(None, max_length=200),
    status: str = Query("all", pattern="^(all|hidden|pinned)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin),
):
    """管理後台 - 列出論壇貼文（含隱藏貼文）"""
    offset = (page - 1) * limit

    factory = get_session_factory()
    async with factory() as session:
        where_clauses = []
        params = {}

        if search:
            like = f"%{search}%"
            where_clauses.append("(p.title ILIKE :like OR u.username ILIKE :like)")
            params["like"] = like

        if status == "hidden":
            where_clauses.append("p.is_hidden = 1")
        elif status == "pinned":
            where_clauses.append("p.is_pinned = 1")

        where_clause = (
            (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        )

        post_query = text(
            """
            SELECT p.id, p.title, p.user_id, u.username, p.category,
                   p.is_hidden, p.is_pinned, p.comment_count, p.view_count,
                   p.push_count, p.boo_count, p.created_at
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.user_id
        """
            + where_clause
            + """
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        )

        result = await session.execute(
            post_query, {**params, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()

        count_query = text(
            """
            SELECT COUNT(*)
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.user_id
        """
            + where_clause
        )
        count_result = await session.execute(count_query, params)
        total = count_result.scalar()

        return {
            "success": True,
            "posts": [
                {
                    "id": r[0],
                    "title": r[1],
                    "user_id": r[2],
                    "username": r[3] or "Unknown",
                    "category": r[4],
                    "is_hidden": bool(r[5]),
                    "is_pinned": bool(r[6]),
                    "comment_count": r[7] or 0,
                    "view_count": r[8] or 0,
                    "push_count": r[9] or 0,
                    "boo_count": r[10] or 0,
                    "created_at": r[11].isoformat() if r[11] else None,
                }
                for r in rows
            ],
            "total": total,
            "page": page,
            "limit": limit,
        }


@router.patch("/forum/posts/{post_id}/visibility")
async def admin_toggle_post_visibility(
    post_id: int,
    request: PostVisibilityRequest,
    admin_user: dict = Depends(require_admin),
):
    """隱藏/顯示貼文"""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT is_hidden, title FROM posts WHERE id = :id"), {"id": post_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        old_hidden = bool(row[0])

        await session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_hidden=1 if request.is_hidden else 0)
        )
        await _write_audit_log(
            session,
            f"admin_forum:post_visibility:{post_id}",
            "hidden" if old_hidden else "visible",
            "hidden" if request.is_hidden else "visible",
            admin_user["user_id"],
        )
        await session.commit()

        return {
            "success": True,
            "old_hidden": old_hidden,
            "new_hidden": request.is_hidden,
            "title": row[1],
        }


@router.patch("/forum/posts/{post_id}/pin")
async def admin_toggle_post_pin(
    post_id: int, request: PostPinRequest, admin_user: dict = Depends(require_admin)
):
    """置頂/取消置頂貼文"""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT is_pinned, title FROM posts WHERE id = :id"), {"id": post_id}
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")

        await session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_pinned=1 if request.is_pinned else 0)
        )
        await _write_audit_log(
            session,
            f"admin_forum:post_pin:{post_id}",
            "pinned" if row[0] else "unpinned",
            "pinned" if request.is_pinned else "unpinned",
            admin_user["user_id"],
        )
        await session.commit()

        return {
            "success": True,
            "old_pinned": bool(row[0]),
            "new_pinned": request.is_pinned,
            "title": row[1],
        }


@router.patch("/forum/comments/{comment_id}/visibility")
async def admin_toggle_comment_visibility(
    comment_id: int,
    request: PostVisibilityRequest,
    admin_user: dict = Depends(require_admin),
):
    """隱藏/顯示留言"""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT is_hidden, post_id FROM forum_comments WHERE id = :id"),
            {"id": comment_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Comment not found")

        await session.execute(
            update(ForumComment)
            .where(ForumComment.id == comment_id)
            .values(is_hidden=1 if request.is_hidden else 0)
        )
        await _write_audit_log(
            session,
            f"admin_forum:comment_visibility:{comment_id}",
            "hidden" if row[0] else "visible",
            "hidden" if request.is_hidden else "visible",
            admin_user["user_id"],
        )
        await session.commit()

        return {
            "success": True,
            "old_hidden": bool(row[0]),
            "new_hidden": request.is_hidden,
            "post_id": row[1],
        }


@router.get("/forum/reports")
async def admin_list_reports(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin),
):
    """列出內容舉報"""
    offset = (page - 1) * limit

    factory = get_session_factory()
    async with factory() as session:
        query = text(
            """
            SELECT cr.id, cr.content_type, cr.content_id, cr.reporter_user_id,
                   u.username as reporter_username, cr.report_type, cr.description,
                   cr.review_status, cr.approve_count, cr.reject_count, cr.created_at
            FROM content_reports cr
            LEFT JOIN users u ON cr.reporter_user_id = u.user_id
            WHERE cr.review_status = :status
            ORDER BY cr.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        )
        result = await session.execute(
            query, {"status": status, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()

        count_result = await session.execute(
            text("SELECT COUNT(*) FROM content_reports WHERE review_status = :status"),
            {"status": status},
        )
        total = count_result.scalar()

        reports = []
        for r in rows:
            report = {
                "id": r[0],
                "content_type": r[1],
                "content_id": r[2],
                "reporter_user_id": r[3],
                "reporter_username": r[4] or "Unknown",
                "report_type": r[5],
                "description": r[6],
                "review_status": r[7],
                "approve_count": r[8] or 0,
                "reject_count": r[9] or 0,
                "created_at": r[10].isoformat() if r[10] else None,
                "content_preview": None,
            }
            if r[1] == "post":
                preview_result = await session.execute(
                    text("SELECT title FROM posts WHERE id = :id"), {"id": r[2]}
                )
            elif r[1] == "comment":
                preview_result = await session.execute(
                    text("SELECT content FROM forum_comments WHERE id = :id"),
                    {"id": r[2]},
                )
            else:
                preview_result = None
            preview_row = preview_result.fetchone() if preview_result else None
            if preview_row:
                report["content_preview"] = (preview_row[0] or "")[:100]
            reports.append(report)

        return {
            "success": True,
            "reports": reports,
            "total": total,
            "page": page,
            "limit": limit,
        }


@router.post("/forum/reports/{report_id}/resolve")
async def admin_resolve_report(
    report_id: int,
    request: ResolveReportRequest,
    admin_user: dict = Depends(require_admin),
):
    """處理舉報（批准=隱藏內容+違規記點，駁回=不處理）"""
    report = await governance_repo.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.get("review_status") != "pending":
        raise HTTPException(status_code=400, detail="Report already resolved")

    await governance_repo.finalize_report(
        report_id,
        request.decision,
        request.violation_level,
        admin_user["user_id"],
    )

    if request.decision == "approved":
        content_type = report.get("content_type")
        content_id = report.get("content_id")

        factory = get_session_factory()
        async with factory() as session:
            if content_type == "post":
                await session.execute(
                    update(Post).where(Post.id == content_id).values(is_hidden=1)
                )
            elif content_type == "comment":
                await session.execute(
                    update(ForumComment)
                    .where(ForumComment.id == content_id)
                    .values(is_hidden=1)
                )
            await _write_audit_log(
                session,
                f"admin_forum:report_resolve:{report_id}",
                "pending",
                f"{request.decision}:hide_{content_type}:{content_id}",
                admin_user["user_id"],
            )
            await session.commit()

    return {
        "success": True,
        "report_id": report_id,
        "decision": request.decision,
        "content_hidden": request.decision == "approved",
    }
