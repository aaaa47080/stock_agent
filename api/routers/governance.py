"""
社群治理系統 API (Community Governance System)

提供檢舉管理、審核投票、違規記錄、活動日誌等接口
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.deps import get_current_user, require_admin
from api.middleware.rate_limit import limiter
from api.models import (
    FinalizeReportRequest,
    ReportCreateRequest,
    VoteRequest,
)
from api.utils import logger
from core.orm.governance_repo import (
    DEFAULT_DAILY_REPORT_LIMIT,
    PRO_DAILY_REPORT_LIMIT,
    governance_repo,
)
from core.orm.repositories import user_repo

router = APIRouter(prefix="/api/governance", tags=["Community Governance"])


# ============================================================================
# 檢舉管理 (Report Management)
# ============================================================================


@router.post("/reports")
@limiter.limit("10/hour")  # 每小時最多 10 次檢舉
async def submit_report(
    request: Request,
    report_data: ReportCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    提交內容檢舉

    - **content_type**: 內容類型 ('post' 或 'comment')
    - **content_id**: 內容 ID
    - **report_type**: 檢舉類型 (spam, harassment, misinformation, scam, illegal, other)
    - **description**: 檢舉說明（選填）

    檢舉限制：
    - 免費用戶：每日 5 次
    - Premium 會員：每日 10 次
    - 不能檢舉自己的內容
    - 同一用戶對同一內容只能檢舉一次
    """
    try:
        user_id = current_user["user_id"]

        # Get user's daily limit
        membership = await user_repo.get_membership(user_id)
        is_premium = membership.get("is_premium", False)
        daily_limit = (
            PRO_DAILY_REPORT_LIMIT if is_premium else DEFAULT_DAILY_REPORT_LIMIT
        )
        result = await governance_repo.create_report(
            reporter_user_id=user_id,
            content_type=report_data.content_type,
            content_id=report_data.content_id,
            report_type=report_data.report_type,
            description=report_data.description,
        )

        if not result.get("success"):
            error = result.get("error", "unknown_error")
            if error == "invalid_report_type":
                raise HTTPException(status_code=400, detail="無效的檢舉類型")
            elif error == "cannot_report_own_content":
                raise HTTPException(status_code=400, detail="不能檢舉自己的內容")
            elif error == "daily_limit_exceeded":
                raise HTTPException(
                    status_code=429, detail=f"已達每日檢舉上限 ({daily_limit} 次)"
                )
            elif error == "duplicate_report":
                raise HTTPException(status_code=409, detail="您已經檢舉過此內容")
            elif error == "content_not_found":
                raise HTTPException(status_code=404, detail="找不到要檢舉的內容")
            else:
                raise HTTPException(status_code=500, detail=f"檢舉提交失敗: {error}")

        return {
            "success": True,
            "report_id": result["report_id"],
            "message": "檢舉已提交，等待審核",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit report error: {e}")
        raise HTTPException(status_code=500, detail="提交檢舉失敗，請稍後再試")


@router.get("/report-quota")
async def get_report_quota(current_user: dict = Depends(get_current_user)):
    """
    獲取用戶今日檢舉配額

    回傳：今日已用次數、每日上限、剩餘次數
    """
    try:
        user_id = current_user["user_id"]
        membership = await user_repo.get_membership(user_id)
        is_premium = membership.get("is_premium", False)
        daily_limit = (
            PRO_DAILY_REPORT_LIMIT if is_premium else DEFAULT_DAILY_REPORT_LIMIT
        )
        used_today = await governance_repo.get_daily_report_usage(user_id)

        return {
            "used": used_today,
            "limit": daily_limit,
            "remaining": max(0, daily_limit - used_today),
            "is_premium": is_premium,
        }
    except Exception as e:
        logger.error(f"Get report quota error: {e}")
        raise HTTPException(status_code=500, detail="獲取配額失敗，請稍後再試")


@router.get("/reports/pending")
async def list_pending_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取待審核的檢舉列表（Premium 會員專用）

    - **limit**: 最多返回數量 (1-100)
    - **offset**: 分頁偏移
    """
    try:
        user_id = current_user["user_id"]

        membership = await user_repo.get_membership(user_id)
        if not membership.get("is_premium", False):
            raise HTTPException(status_code=403, detail="此功能僅限 Premium 會員使用")

        reports = await governance_repo.get_pending_reports(
            limit=limit,
            offset=offset,
            exclude_user_id=user_id,
            viewer_user_id=user_id,
        )

        return {"success": True, "reports": reports, "count": len(reports)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List pending reports error: {e}")
        raise HTTPException(status_code=500, detail="獲取待審核列表失敗，請稍後再試")


@router.get("/reports/{report_id}")
async def get_report_detail(
    report_id: int, current_user: dict = Depends(get_current_user)
):
    """
    獲取檢舉詳情

    包含檢舉內容和投票記錄
    """
    try:
        user_id = current_user["user_id"]

        membership = await user_repo.get_membership(user_id)
        is_premium = membership.get("is_premium", False)

        report = await governance_repo.get_report_by_id(report_id)

        if not report:
            raise HTTPException(status_code=404, detail="找不到該檢舉")

        # Get votes for premium members
        votes = None
        if is_premium:
            votes = await governance_repo.get_report_votes(report_id)

        return {"success": True, "report": {**report, "votes": votes}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get report detail error: {e}")
        raise HTTPException(status_code=500, detail="獲取檢舉詳情失敗，請稍後再試")


@router.get("/reports")
async def list_my_reports(
    status: Optional[str] = Query(
        None, description="篩選狀態: pending, approved, rejected"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取我提交的檢舉記錄

    - **status**: 篩選狀態（選填）
    - **limit**: 最多返回數量
    - **offset**: 分頁偏移
    """
    try:
        user_id = current_user["user_id"]

        reports = await governance_repo.get_user_reports(
            user_id=user_id, status=status, limit=limit, offset=offset
        )

        return {"success": True, "reports": reports, "count": len(reports)}

    except Exception as e:
        logger.error(f"List my reports error: {e}")
        raise HTTPException(status_code=500, detail="獲取檢舉記錄失敗，請稍後再試")


# ============================================================================
# 審核投票 (Voting)
# ============================================================================


@router.post("/reports/{report_id}/vote")
@limiter.limit("30/hour")  # 每小時最多 30 次投票
async def vote_on_pending_report(
    report_id: int,
    request: Request,
    vote_data: VoteRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    對檢舉進行投票（Premium 會員專用）

    - **vote_type**: 投票類型
      - 'approve': 認為內容違規，支持檢舉
      - 'reject': 認為內容不違規，拒絕檢舉

    投票規則：
    - 每個 Premium 會員對同一檢舉只能投票一次
    - 投票後不可修改
    - 當投票達到共識時（最少 3 票，70% 同意），自動處理
    """
    try:
        user_id = current_user["user_id"]

        membership = await user_repo.get_membership(user_id)
        if not membership.get("is_premium", False):
            raise HTTPException(status_code=403, detail="投票功能僅限 Premium 會員使用")

        result = await governance_repo.vote_on_report(
            report_id=report_id,
            reviewer_user_id=user_id,
            vote_type=vote_data.vote_type,
            is_premium=True,
        )

        if not result.get("success"):
            error = result.get("error", "unknown_error")
            if error == "invalid_vote_type":
                raise HTTPException(status_code=400, detail="無效的投票類型")
            elif error == "premium_membership_required":
                raise HTTPException(
                    status_code=403, detail="投票功能僅限 Premium 會員使用"
                )
            elif error == "report_not_found":
                raise HTTPException(status_code=404, detail="找不到該檢舉")
            elif error == "report_not_pending":
                raise HTTPException(status_code=400, detail="該檢舉已結案，無法投票")
            elif error == "already_voted":
                raise HTTPException(status_code=409, detail="您已經投過票了")
            else:
                raise HTTPException(status_code=500, detail=f"投票失敗: {error}")

        # Check if consensus is reached after this vote
        consensus = await governance_repo.check_report_consensus(report_id)

        response = {
            "success": True,
            "vote_id": result["vote_id"],
            "message": "投票成功",
        }

        # Include consensus info
        if consensus.get("has_consensus"):
            response["consensus_reached"] = True
            response["decision"] = consensus["decision"]
            response["consensus_message"] = (
                f"已達成共識：{'通過' if consensus['decision'] == 'approved' else '拒絕'}"
            )
        else:
            response["consensus_reached"] = False
            response["current_status"] = {
                "total_votes": consensus.get("total_votes", 0),
                "approve_count": consensus.get("approve_count", 0),
                "reject_count": consensus.get("reject_count", 0),
                "approve_rate": consensus.get("approve_rate", 0),
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vote on report error: {e}")
        raise HTTPException(status_code=500, detail="投票失敗，請稍後再試")


@router.post("/reports/{report_id}/finalize")
async def finalize_report_decision(
    report_id: int,
    request: FinalizeReportRequest,
    current_user: dict = Depends(require_admin),
):
    """
    完成檢舉處理（管理員功能）

    手動設定檢舉的結果，通常在自動共識機制失敗時使用

    - **decision**: 決定 ('approved' 或 'rejected')
    - **violation_level**: 違規等級（當 decision=approved 時必填）
      - mild: 輕微 (1點)
      - medium: 中等 (3點)
      - severe: 嚴重 (5點)
      - critical: 極嚴重 (30點)
    """
    try:
        user_id = current_user["user_id"]

        result = await governance_repo.finalize_report(
            report_id=report_id,
            decision=request.decision,
            violation_level=request.violation_level,
            processed_by=user_id,
        )

        if not result.get("success"):
            error = result.get("error", "unknown_error")
            if error == "invalid_decision":
                raise HTTPException(status_code=400, detail="無效的決定")
            elif error == "report_not_found":
                raise HTTPException(status_code=404, detail="找不到該檢舉")
            else:
                raise HTTPException(status_code=500, detail=f"處理失敗: {error}")

        action_taken = result.get("action_taken")
        action_message = ""
        if action_taken:
            action_map = {
                "warning": "警告",
                "suspend_3d": "暫停3天",
                "suspend_7d": "暫停7天",
                "suspend_30d": "暫停30天",
                "permanent_ban": "永久停權",
            }
            action_message = (
                f"，已執行處罰：{action_map.get(action_taken, action_taken)}"
            )

        return {
            "success": True,
            "message": f"檢舉已{result['decision']}{action_message}",
            "decision": result["decision"],
            "violation_level": result.get("violation_level"),
            "points_assigned": result.get("points_assigned", 0),
            "action_taken": action_taken,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Finalize report error: {e}")
        raise HTTPException(status_code=500, detail="處理檢舉失敗，請稍後再試")


# ============================================================================
# 違規記錄 (Violation Records)
# ============================================================================


@router.get("/violations")
async def get_my_violation_points(current_user: dict = Depends(get_current_user)):
    """
    獲取我的違規點數和記錄

    返回：
    - points: 當前違規點數
    - total_violations: 總違規次數
    - suspension_count: 累計被暫停次數
    - last_violation_at: 最後違規時間
    - action_threshold: 下一步處罰等級（如：10點將暫停3天）
    """
    try:
        user_id = current_user["user_id"]

        points_data = await governance_repo.get_user_violation_points(user_id)
        violations = await governance_repo.get_user_violations(user_id, limit=10)

        # Calculate action threshold
        points = points_data.get("points", 0)
        action_threshold = None
        if points < 5:
            action_threshold = "無（5點將發出警告）"
        elif points < 10:
            action_threshold = "暫停3天（10點）"
        elif points < 20:
            action_threshold = "暫停7天（20點）"
        elif points < 30:
            action_threshold = "暫停30天（30點）"
        elif points < 40:
            action_threshold = "永久停權（40點）"
        else:
            action_threshold = "已達永久停權門檻"

        return {
            "success": True,
            "points": points_data,
            "action_threshold": action_threshold,
            "recent_violations": violations,
        }

    except Exception as e:
        logger.error(f"Get violation points error: {e}")
        raise HTTPException(status_code=500, detail="獲取違規記錄失敗，請稍後再試")


@router.get("/violations/{user_id}")
async def get_user_violations_public(
    user_id: str, current_user: dict = Depends(get_current_user)
):
    """
    獲取指定用戶的違規記錄（公開信息）

    返回公開的違規統計，不包含敏感信息
    """
    try:
        # Only show own violations unless premium member
        requester_id = current_user["user_id"]
        membership = await user_repo.get_membership(requester_id)
        is_premium = membership.get("is_premium", False)

        if user_id != requester_id and not is_premium:
            raise HTTPException(status_code=403, detail="無權查看其他用戶的違規記錄")
        points_data = await governance_repo.get_user_violation_points(user_id)
        violations = await governance_repo.get_user_violations(user_id, limit=20)

        return {
            "success": True,
            "points": points_data.get("points", 0),
            "total_violations": points_data.get("total_violations", 0),
            "suspension_count": points_data.get("suspension_count", 0),
            "violations": violations,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user violations error: {e}")
        raise HTTPException(status_code=500, detail="獲取違規記錄失敗，請稍後再試")


# ============================================================================
# 活動日誌 (Activity Logs)
# ============================================================================


@router.get("/activity-logs")
async def get_my_activity_logs(
    activity_type: Optional[str] = Query(None, description="活動類型篩選"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取我的活動日誌

    - **activity_type**: 篩選活動類型（選填）
    - **limit**: 最多返回數量
    - **offset**: 分頁偏移
    """
    try:
        user_id = current_user["user_id"]

        logs = await governance_repo.get_user_activity_logs(
            user_id=user_id,
            activity_type=activity_type,
            limit=limit,
            offset=offset,
        )

        return {"success": True, "logs": logs, "count": len(logs)}

    except Exception as e:
        logger.error(f"Get activity logs error: {e}")
        raise HTTPException(status_code=500, detail="獲取活動日誌失敗，請稍後再試")


# ============================================================================
# 統計與排行 (Statistics & Leaderboard)
# ============================================================================


@router.get("/statistics")
async def get_governance_statistics(
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    current_user: dict = Depends(get_current_user),
):
    """
    獲取治理系統統計數據

    - **days**: 統計天數（默認30天）

    返回：
    - total_reports: 總檢舉數
    - pending_reports: 待審核數
    - approved_reports: 通過數
    - rejected_reports: 拒絕數
    - total_votes: 總投票數
    - avg_approval_rate: 平均通過率
    """
    try:
        stats = await governance_repo.get_report_statistics(days)

        return {"success": True, "statistics": stats, "period_days": days}

    except Exception as e:
        logger.error(f"Get statistics error: {e}")
        raise HTTPException(status_code=500, detail="獲取統計數據失敗，請稍後再試")


@router.get("/reviewers/leaderboard")
async def get_review_leaderboard(
    limit: int = Query(10, ge=1, le=50), current_user: dict = Depends(get_current_user)
):
    """
    獲取審核員排行榜

    - **limit**: 最多返回數量

    排行依據：聲望分數 > 準確率 > 審核數量
    """
    try:
        reviewers = await governance_repo.get_top_reviewers(limit)

        return {"success": True, "leaderboard": reviewers, "count": len(reviewers)}

    except Exception as e:
        logger.error(f"Get leaderboard error: {e}")
        raise HTTPException(status_code=500, detail="獲取排行榜失敗，請稍後再試")


# ============================================================================
# 審核聲望 (Audit Reputation)
# ============================================================================


@router.get("/reputation")
async def get_my_reputation(current_user: dict = Depends(get_current_user)):
    """
    獲取我的審核聲望

    返回：
    - total_reviews: 總審核次數
    - correct_votes: 正確投票次數
    - accuracy_rate: 準確率
    - reputation_score: 聲望分數
    - vote_weight: 當前投票權重
    """
    try:
        user_id = current_user["user_id"]

        reputation = await governance_repo.get_audit_reputation(user_id)
        vote_weight = governance_repo.calculate_vote_weight(reputation)

        return {
            "success": True,
            "reputation": {**reputation, "vote_weight": vote_weight},
        }

    except Exception as e:
        logger.error(f"Get reputation error: {e}")
        raise HTTPException(status_code=500, detail="獲取聲望失敗，請稍後再試")
