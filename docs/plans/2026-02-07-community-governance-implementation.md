# 社群治理系統 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a decentralized community governance system where PRO users act as review nodes to maintain community health through content reporting, voting, violation tracking, and transparent audit logs.

**Architecture:**
- Database: PostgreSQL with new tables for violations, reports, votes, and activity logs
- API: FastAPI routers under `/api/routers/governance.py` for all governance endpoints
- Frontend: HTML/JS under `/web/governance/` for reporting, review queue, and activity logs
- Integration: Leverages existing PRO verification system and forum infrastructure

**Tech Stack:**
- Python 3.11+, FastAPI, PostgreSQL, Pydantic
- Frontend: Vanilla JS with Fetch API
- Testing: pytest with coverage

**Prerequisites:**
- Existing forum system at `/api/routers/forum/` and `/core/database/forum.py`
- Existing PRO membership system at `/core/database/user.py`
- Existing audit log patterns at `/api/routers/audit.py`

---

## Task 1: Database Migration - Create Governance Tables

**Files:**
- Create: `database/migrations/add_governance_tables.sql`

**Step 1: Write the migration SQL file**

Create `database/migrations/add_governance_tables.sql`:

```sql
-- ============================================
-- 社群治理系統 Database Migration
-- Created: 2026-02-07
-- ============================================

-- 1. 用戶違規點數表
CREATE TABLE IF NOT EXISTS user_violation_points (
    user_id TEXT PRIMARY KEY,
    points INTEGER DEFAULT 0,
    last_violation_at TIMESTAMP,
    last_decrement_at TIMESTAMP,

    -- 統計
    total_violations INTEGER DEFAULT 0,
    suspension_count INTEGER DEFAULT 0,

    updated_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_violation_points ON user_violation_points(points DESC);

-- 2. 違規記錄表
CREATE TABLE IF NOT EXISTS user_violations (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    violation_level TEXT NOT NULL,  -- mild/medium/severe/critical
    violation_type TEXT NOT NULL,
    points INTEGER DEFAULT 0,

    -- 觸發來源
    source_type TEXT NOT NULL,      -- 'report', 'admin_action'
    source_id INTEGER,

    -- 處罰結果
    action_taken TEXT,              -- 'warning', 'suspend_3d', 'suspend_7d', etc.
    suspended_until TIMESTAMP,

    processed_by TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_violations_user ON user_violations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_violations_level ON user_violations(violation_level);

-- 3. 內容檢舉表
CREATE TABLE IF NOT EXISTS content_reports (
    id SERIAL PRIMARY KEY,

    -- 被檢舉內容
    content_type TEXT NOT NULL,      -- 'post' 或 'comment'
    content_id INTEGER NOT NULL,

    -- 檢舉者
    reporter_user_id TEXT NOT NULL,
    report_type TEXT NOT NULL,       -- spam/harassment/misinformation/scam/illegal/other
    description TEXT,

    -- 審核狀態
    review_status TEXT DEFAULT 'pending',  -- pending/approved/rejected
    violation_level TEXT,                   -- mild/medium/severe/critical

    -- 處理結果
    action_taken TEXT,                      -- 警告/刪除/停權
    points_assigned INTEGER DEFAULT 0,
    processed_by TEXT,                      -- 審核員 user_id

    -- 投票統計
    approve_count INTEGER DEFAULT 0,        -- 認為違規
    reject_count INTEGER DEFAULT 0,         -- 認為不違規

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(reporter_user_id, content_type, content_id),
    FOREIGN KEY (reporter_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_report_content ON content_reports(content_type, content_id);
CREATE INDEX IF NOT EXISTS idx_report_status ON content_reports(review_status);
CREATE INDEX IF NOT EXISTS idx_report_created ON content_reports(created_at DESC);

-- 4. 審核投票表
CREATE TABLE IF NOT EXISTS report_review_votes (
    id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL,
    reviewer_user_id TEXT NOT NULL,
    vote_type TEXT NOT NULL,                -- 'approve' (違規) / 'reject' (不違規)
    vote_weight FLOAT DEFAULT 1.0,          -- 權重（基於聲望）
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(report_id, reviewer_user_id),
    FOREIGN KEY (report_id) REFERENCES content_reports(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_review_report ON report_review_votes(report_id);
CREATE INDEX IF NOT EXISTS idx_review_user ON report_review_votes(reviewer_user_id);

-- 5. 用戶活動日誌表
CREATE TABLE IF NOT EXISTS user_activity_logs (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,

    -- 活動詳情
    activity_type TEXT NOT NULL,      -- 'post_created', 'comment_liked', 'report_submitted', etc.
    resource_type TEXT,               -- 'post', 'comment', 'user', 'report'
    resource_id INTEGER,

    -- 額外資料（JSON 格式）
    metadata JSONB,                   -- 靈活存儲各種資訊

    -- 結果
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,

    -- 時間與 IP
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_activity ON user_activity_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity_logs(activity_type);

-- 6. 審核聲望表（獨立於一般聲望）
CREATE TABLE IF NOT EXISTS audit_reputation (
    user_id TEXT PRIMARY KEY,
    total_reviews INTEGER DEFAULT 0,
    correct_votes INTEGER DEFAULT 0,      -- 與最終結果一致的投票
    accuracy_rate FLOAT DEFAULT 1.0,      -- 正確率
    reputation_score INTEGER DEFAULT 0,   -- 審核聲望值

    updated_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_reputation ON audit_reputation(reputation_score DESC);

-- ============================================
-- Functions for automated processing
-- ============================================

-- 檢查並處理點數遞減（每30天無違規減1點）
CREATE OR REPLACE FUNCTION decrement_violation_points()
RETURNS TABLE(user_id TEXT, points_deducted INTEGER) AS $$
DECLARE
    record RECORD;
BEGIN
    FOR record IN
        SELECT user_id, points, last_violation_at, last_decrement_at
        FROM user_violation_points
        WHERE points > 0
          AND (last_decrement_at IS NULL OR last_decrement_at < NOW() - INTERVAL '30 days')
          AND (last_violation_at IS NULL OR last_violation_at < NOW() - INTERVAL '30 days')
    LOOP
        UPDATE user_violation_points
        SET points = GREATEST(0, points - 1),
            last_decrement_at = NOW()
        WHERE user_id = record.user_id;

        RETURN NEXT VALUES(record.user_id, 1);
    END LOOP;
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Grant permissions (adjust user as needed)
-- ============================================
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
```

**Step 2: Manually run the migration**

Run: `psql -U your_user -d stock_agent -f database/migrations/add_governance_tables.sql`

Or use the database connection script if available.

**Step 3: Verify tables were created**

Run: `\dt` in psql or query:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('user_violation_points', 'user_violations', 'content_reports', 'report_review_votes', 'user_activity_logs', 'audit_reputation');
```

Expected: 6 tables listed

**Step 4: Commit**

```bash
git add database/migrations/add_governance_tables.sql
git commit -m "feat(governance): add database migration for governance system"
```

---

## Task 2: Database Operations Layer - Core Functions

**Files:**
- Create: `core/database/governance.py`
- Test: `tests/test_governance_db.py`

**Step 1: Write the failing test**

Create `tests/test_governance_db.py`:

```python
import pytest
from core.database.governance import (
    create_report,
    get_pending_reports,
    vote_on_report,
    check_report_consensus,
    add_violation_points,
    get_user_violation_points,
    log_activity,
    get_user_activity_logs
)
from core.database.connection import get_db


@pytest.fixture
def db():
    """Get database connection"""
    yield from get_db()


@pytest.fixture
def test_user(db):
    """Create test user"""
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        ["test_user_001", "testuser"]
    )
    db.commit()
    return "test_user_001"


@pytest.fixture
def test_pro_user(db):
    """Create test PRO user"""
    user_id = "test_pro_001"
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username, membership_tier, membership_expires_at) "
        "VALUES (%s, %s, %s, NOW() + INTERVAL '30 days') "
        "ON CONFLICT (user_id) DO UPDATE SET membership_tier = EXCLUDED.membership_tier",
        [user_id, "testpro", "pro"]
    )
    db.commit()
    return user_id


def test_create_report(db, test_user):
    """Test creating a content report"""
    report = create_report(
        db=db,
        reporter_user_id=test_user,
        content_type="post",
        content_id=123,
        report_type="spam",
        description="Spam content"
    )

    assert report["id"] is not None
    assert report["content_type"] == "post"
    assert report["content_id"] == 123
    assert report["report_type"] == "spam"
    assert report["review_status"] == "pending"


def test_vote_on_report(db, test_user, test_pro_user):
    """Test PRO user voting on a report"""
    # First create a report
    report = create_report(
        db=db,
        reporter_user_id=test_user,
        content_type="post",
        content_id=456,
        report_type="harassment",
        description="Harassing content"
    )

    # PRO user votes
    vote = vote_on_report(
        db=db,
        report_id=report["id"],
        reviewer_user_id=test_pro_user,
        vote_type="approve"
    )

    assert vote["vote_type"] == "approve"
    assert vote["report_id"] == report["id"]


def test_check_consensus(db, test_user, test_pro_user):
    """Test consensus checking mechanism"""
    report = create_report(
        db=db,
        reporter_user_id=test_user,
        content_type="comment",
        content_id=789,
        report_type="scam",
        description="Scam comment"
    )

    # Add 5 approve votes (should trigger consensus)
    for i in range(5):
        pro_user = f"test_pro_{i:03d}"
        # Insert pro users
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, username, membership_tier, membership_expires_at) "
            "VALUES (%s, %s, %s, NOW() + INTERVAL '30 days') "
            "ON CONFLICT DO NOTHING",
            [pro_user, f"pro{i}", "pro"]
        )
        db.commit()

        vote_on_report(db, report["id"], pro_user, "approve")

    result = check_report_consensus(db, report["id"])

    # With 5 approve votes (100%), should have consensus
    assert result["has_consensus"] == True
    assert result["decision"] == "approved"


def test_add_violation_points(db, test_user):
    """Test adding violation points to user"""
    add_violation_points(
        db=db,
        user_id=test_user,
        points=3,
        violation_level="medium",
        violation_type="harassment",
        source_type="report",
        source_id=1
    )

    record = get_user_violation_points(db, test_user)

    assert record["points"] == 3
    assert record["total_violations"] == 1


def test_log_and_retrieve_activity(db, test_user):
    """Test activity logging and retrieval"""
    log_activity(
        db=db,
        user_id=test_user,
        activity_type="report_submitted",
        resource_type="report",
        resource_id=1,
        metadata={"report_type": "spam"}
    )

    logs = get_user_activity_logs(db, test_user, limit=10)

    assert len(logs) > 0
    assert logs[0]["activity_type"] == "report_submitted"
    assert logs[0]["resource_type"] == "report"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_governance_db.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'core.database.governance'"

**Step 3: Write minimal implementation**

Create `core/database/governance.py`:

```python
"""
社群治理系統 - Database Operations Layer

提供所有治理相關的資料庫操作函數
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# ========================
# Constants
# ========================

VIOLATION_LEVELS = {
    "mild": 1,      # 輕微
    "medium": 3,    # 中等
    "severe": 5,    # 嚴重
    "critical": 30  # 極嚴重
}

REPORT_TYPES = ["spam", "harassment", "misinformation", "scam", "illegal", "other"]

VIOLATION_ACTIONS = {
    5: "warning",
    10: "suspend_3d",
    20: "suspend_7d",
    30: "suspend_30d",
    40: "permanent_ban"
}

SUSPENSION_DURATIONS = {
    "suspend_3d": timedelta(days=3),
    "suspend_7d": timedelta(days=7),
    "suspend_30d": timedelta(days=30)
}

# Consensus thresholds
MIN_VOTES_REQUIRED = 3
CONSENSUS_APPROVE_THRESHOLD = 0.70  # 70%
CONSENSUS_REJECT_THRESHOLD = 0.30   # 30%


# ========================
# Report Management
# ========================

def create_report(
    db,
    reporter_user_id: str,
    content_type: str,
    content_id: int,
    report_type: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    創建新的內容檢舉

    Args:
        db: Database connection
        reporter_user_id: 檢舉者用戶 ID
        content_type: 內容類型 ('post' 或 'comment')
        content_id: 內容 ID
        report_type: 檢舉類型
        description: 檢舉說明

    Returns:
        Dict: 創建的檢舉記錄
    """
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Invalid report_type: {report_type}")

    if content_type not in ["post", "comment"]:
        raise ValueError(f"Invalid content_type: {content_type}")

    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            INSERT INTO content_reports
            (reporter_user_id, content_type, content_id, report_type, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (reporter_user_id, content_type, content_id)
            DO NOTHING
            RETURNING *
        """, [reporter_user_id, content_type, content_id, report_type, description])

        result = cursor.fetchone()

        if result is None:
            raise ValueError("Report already exists for this content by this user")

        db.commit()

        # Log the activity
        log_activity(
            db=db,
            user_id=reporter_user_id,
            activity_type="report_submitted",
            resource_type="report",
            resource_id=result["id"],
            metadata={
                "content_type": content_type,
                "content_id": content_id,
                "report_type": report_type
            }
        )

        return dict(result)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating report: {e}")
        raise


def get_pending_reports(
    db,
    limit: int = 50,
    offset: int = 0,
    exclude_user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    獲取待審核的檢舉列表

    Args:
        db: Database connection
        limit: 最多返回數量
        offset: 分頁偏移
        exclude_user_id: 排除特定用戶的檢舉（不能審核自己）

    Returns:
        List[Dict]: 待審核檢舉列表
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT
            r.id,
            r.content_type,
            r.content_id,
            r.report_type,
            r.description,
            r.created_at,
            r.approve_count,
            r.reject_count,
            u.username as reporter_username
        FROM content_reports r
        JOIN users u ON r.reporter_user_id = u.user_id
        WHERE r.review_status = 'pending'
    """

    params = []

    if exclude_user_id:
        # 排除該用戶發表的內容和該用戶提交的檢舉
        query += """
            AND r.reporter_user_id != %s
            AND NOT EXISTS (
                SELECT 1 FROM forum_posts p
                WHERE p.id = r.content_id AND p.user_id = %s AND r.content_type = 'post'
            )
            AND NOT EXISTS (
                SELECT 1 FROM forum_comments c
                WHERE c.id = r.content_id AND c.user_id = %s AND r.content_type = 'comment'
            )
        """
        params.extend([exclude_user_id, exclude_user_id, exclude_user_id])

    query += " ORDER BY r.created_at ASC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_report_by_id(db, report_id: int) -> Optional[Dict[str, Any]]:
    """
    獲取檢舉詳情

    Args:
        db: Database connection
        report_id: 檢舉 ID

    Returns:
        Optional[Dict]: 檢舉詳情
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            r.*,
            u.username as reporter_username
        FROM content_reports r
        JOIN users u ON r.reporter_user_id = u.user_id
        WHERE r.id = %s
    """, [report_id])

    result = cursor.fetchone()
    return dict(result) if result else None


def get_user_reports(
    db,
    user_id: str,
    status: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    獲取用戶提交的檢舉記錄

    Args:
        db: Database connection
        user_id: 用戶 ID
        status: 篩選狀態
        limit: 最多返回數量

    Returns:
        List[Dict]: 檢舉記錄列表
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT *
        FROM content_reports
        WHERE reporter_user_id = %s
    """
    params = [user_id]

    if status:
        query += " AND review_status = %s"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def check_daily_report_limit(db, user_id: str, daily_limit: int = 10) -> bool:
    """
    檢查用戶今日檢舉次數是否超限

    Args:
        db: Database connection
        user_id: 用戶 ID
        daily_limit: 每日限制

    Returns:
        bool: True if under limit, False otherwise
    """
    cursor = db.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM content_reports
        WHERE reporter_user_id = %s
          AND created_at >= CURRENT_DATE
    """, [user_id])

    count = cursor.fetchone()[0]
    return count < daily_limit


# ========================
# Voting System
# ========================

def vote_on_report(
    db,
    report_id: int,
    reviewer_user_id: str,
    vote_type: str
) -> Dict[str, Any]:
    """
    對檢舉進行投票

    Args:
        db: Database connection
        report_id: 檢舉 ID
        reviewer_user_id: 審核員用戶 ID
        vote_type: 投票類型 ('approve' 或 'reject')

    Returns:
        Dict: 投票記錄
    """
    if vote_type not in ["approve", "reject"]:
        raise ValueError(f"Invalid vote_type: {vote_type}")

    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        # Get user's audit reputation for weight calculation
        reputation = get_audit_reputation(db, reviewer_user_id)
        vote_weight = calculate_vote_weight(reputation)

        # Insert vote
        cursor.execute("""
            INSERT INTO report_review_votes
            (report_id, reviewer_user_id, vote_type, vote_weight)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (report_id, reviewer_user_id)
            DO UPDATE SET vote_type = EXCLUDED.vote_type, vote_weight = EXCLUDED.vote_weight
            RETURNING *
        """, [report_id, reviewer_user_id, vote_type, vote_weight])

        vote = dict(cursor.fetchone())

        # Update report counts
        cursor.execute("""
            UPDATE content_reports
            SET approve_count = (
                SELECT COUNT(*) FROM report_review_votes
                WHERE report_id = %s AND vote_type = 'approve'
            ),
            reject_count = (
                SELECT COUNT(*) FROM report_review_votes
                WHERE report_id = %s AND vote_type = 'reject'
            ),
            updated_at = NOW()
            WHERE id = %s
        """, [report_id, report_id, report_id])

        db.commit()

        # Log activity
        log_activity(
            db=db,
            user_id=reviewer_user_id,
            activity_type="vote_cast",
            resource_type="report",
            resource_id=report_id,
            metadata={"vote_type": vote_type, "weight": vote_weight}
        )

        return vote

    except Exception as e:
        db.rollback()
        logger.error(f"Error voting on report: {e}")
        raise


def get_report_votes(db, report_id: int) -> List[Dict[str, Any]]:
    """
    獲取檢舉的所有投票記錄

    Args:
        db: Database connection
        report_id: 檢舉 ID

    Returns:
        List[Dict]: 投票列表
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            v.vote_type,
            v.vote_weight,
            v.created_at,
            u.username
        FROM report_review_votes v
        JOIN users u ON v.reviewer_user_id = u.user_id
        WHERE v.report_id = %s
        ORDER BY v.created_at ASC
    """, [report_id])

    return [dict(row) for row in cursor.fetchall()]


def check_report_consensus(db, report_id: int) -> Dict[str, Any]:
    """
    檢查檢舉是否達成共識

    Args:
        db: Database connection
        report_id: 檢舉 ID

    Returns:
        Dict: {
            "has_consensus": bool,
            "decision": "approved" | "rejected" | "pending",
            "approve_count": int,
            "reject_count": int,
            "total_votes": int,
            "approve_ratio": float
        }
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            approve_count,
            reject_count,
            (approve_count + reject_count) as total_votes
        FROM content_reports
        WHERE id = %s
    """, [report_id])

    result = cursor.fetchone()

    if not result:
        raise ValueError(f"Report {report_id} not found")

    approve_count = result["approve_count"] or 0
    reject_count = result["reject_count"] or 0
    total_votes = result["total_votes"] or 0

    if total_votes < MIN_VOTES_REQUIRED:
        return {
            "has_consensus": False,
            "decision": "pending",
            "approve_count": approve_count,
            "reject_count": reject_count,
            "total_votes": total_votes,
            "approve_ratio": 0
        }

    approve_ratio = approve_count / total_votes if total_votes > 0 else 0

    if approve_ratio >= CONSENSUS_APPROVE_THRESHOLD:
        return {
            "has_consensus": True,
            "decision": "approved",
            "approve_count": approve_count,
            "reject_count": reject_count,
            "total_votes": total_votes,
            "approve_ratio": approve_ratio
        }
    elif approve_ratio <= CONSENSUS_REJECT_THRESHOLD:
        return {
            "has_consensus": True,
            "decision": "rejected",
            "approve_count": approve_count,
            "reject_count": reject_count,
            "total_votes": total_votes,
            "approve_ratio": approve_ratio
        }
    else:
        return {
            "has_consensus": False,
            "decision": "pending",
            "approve_count": approve_count,
            "reject_count": reject_count,
            "total_votes": total_votes,
            "approve_ratio": approve_ratio
        }


def finalize_report(
    db,
    report_id: int,
    decision: str,
    violation_level: Optional[str] = None,
    processed_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    完成檢舉處理，執行相關動作

    Args:
        db: Database connection
        report_id: 檢舉 ID
        decision: 決定 ('approved' 或 'rejected')
        violation_level: 違規等級 (如果 approved)
        processed_by: 處理者用戶 ID

    Returns:
        Dict: 更新後的檢舉記錄
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        report = get_report_by_id(db, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")

        action_taken = None
        points_assigned = 0

        if decision == "approved" and violation_level:
            # Get violation points
            points = VIOLATION_LEVELS.get(violation_level, 1)

            # Get the content author
            author_id = get_content_author(db, report["content_type"], report["content_id"])

            if author_id:
                # Add violation points
                add_violation_points(
                    db=db,
                    user_id=author_id,
                    points=points,
                    violation_level=violation_level,
                    violation_type=report["report_type"],
                    source_type="report",
                    source_id=report_id
                )
                points_assigned = points

                # Check if suspension needed
                violation_record = get_user_violation_points(db, author_id)
                action_taken = determine_suspension_action(violation_record["points"])

                if action_taken:
                    apply_suspension(db, author_id, action_taken)

        # Update report status
        cursor.execute("""
            UPDATE content_reports
            SET
                review_status = %s,
                violation_level = %s,
                action_taken = %s,
                points_assigned = %s,
                processed_by = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """, [decision, violation_level, action_taken, points_assigned, processed_by, report_id])

        result = dict(cursor.fetchone())
        db.commit()

        # Log activity
        log_activity(
            db=db,
            user_id=processed_by or "system",
            activity_type="report_finalized",
            resource_type="report",
            resource_id=report_id,
            metadata={
                "decision": decision,
                "violation_level": violation_level,
                "action_taken": action_taken
            }
        )

        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Error finalizing report: {e}")
        raise


# ========================
# Violation Points System
# ========================

def add_violation_points(
    db,
    user_id: str,
    points: int,
    violation_level: str,
    violation_type: str,
    source_type: str = "report",
    source_id: Optional[int] = None,
    processed_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    為用戶添加違規點數

    Args:
        db: Database connection
        user_id: 用戶 ID
        points: 點數
        violation_level: 違規等級
        violation_type: 違規類型
        source_type: 來源類型
        source_id: 來源 ID
        processed_by: 處理者

    Returns:
        Dict: 更新後的違規記錄
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        # Insert violation record
        cursor.execute("""
            INSERT INTO user_violations
            (user_id, violation_level, violation_type, points, source_type, source_id, processed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, [user_id, violation_level, violation_type, points, source_type, source_id, processed_by])

        violation = dict(cursor.fetchone())

        # Update or insert points record
        cursor.execute("""
            INSERT INTO user_violation_points
            (user_id, points, total_violations, last_violation_at)
            VALUES (%s, %s, 1, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                points = user_violation_points.points + EXCLUDED.points,
                total_violations = user_violation_points.total_violations + 1,
                last_violation_at = NOW(),
                updated_at = NOW()
            RETURNING *
        """, [user_id, points])

        points_record = dict(cursor.fetchone())
        db.commit()

        # Log activity
        log_activity(
            db=db,
            user_id=user_id,
            activity_type="violation_recorded",
            resource_type="violation",
            resource_id=violation["id"],
            metadata={
                "points": points,
                "violation_level": violation_level,
                "violation_type": violation_type,
                "total_points": points_record["points"]
            }
        )

        return points_record

    except Exception as e:
        db.rollback()
        logger.error(f"Error adding violation points: {e}")
        raise


def get_user_violation_points(db, user_id: str) -> Dict[str, Any]:
    """
    獲取用戶違規點數記錄

    Args:
        db: Database connection
        user_id: 用戶 ID

    Returns:
        Dict: 違規點數記錄
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT * FROM user_violation_points WHERE user_id = %s
    """, [user_id])

    result = cursor.fetchone()

    if result:
        return dict(result)
    else:
        # Return default structure for new users
        return {
            "user_id": user_id,
            "points": 0,
            "total_violations": 0,
            "suspension_count": 0,
            "last_violation_at": None,
            "last_decrement_at": None
        }


def get_user_violations(
    db,
    user_id: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    獲取用戶違規記錄列表

    Args:
        db: Database connection
        user_id: 用戶 ID
        limit: 最多返回數量

    Returns:
        List[Dict]: 違規記錄列表
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT *
        FROM user_violations
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, [user_id, limit])

    return [dict(row) for row in cursor.fetchall()]


def determine_suspension_action(points: int) -> Optional[str]:
    """
    根據點數決定處罰行動

    Args:
        points: 累積點數

    Returns:
        Optional[str]: 處罰行動
    """
    if points >= 40:
        return "permanent_ban"
    elif points >= 30:
        return "suspend_30d"
    elif points >= 20:
        return "suspend_7d"
    elif points >= 10:
        return "suspend_3d"
    elif points >= 5:
        return "warning"
    return None


def apply_suspension(db, user_id: str, action: str) -> bool:
    """
    對用戶執行停權

    Args:
        db: Database connection
        user_id: 用戶 ID
        action: 處罰行動

    Returns:
        bool: 成功與否
    """
    if action == "permanent_ban":
        suspended_until = None  # 永久停權
        is_banned = True
    else:
        duration = SUSPENSION_DURATIONS.get(action)
        if not duration:
            return False
        suspended_until = datetime.now() + duration
        is_banned = False

    cursor = db.cursor()

    try:
        cursor.execute("""
            UPDATE users
            SET
                suspended_until = %s,
                is_banned = %s,
                updated_at = NOW()
            WHERE user_id = %s
        """, [suspended_until, is_banned, user_id])

        db.commit()

        # Update suspension count
        cursor.execute("""
            INSERT INTO user_violation_points
            (user_id, suspension_count)
            VALUES (%s, 1)
            ON CONFLICT (user_id)
            DO UPDATE SET
                suspension_count = user_violation_points.suspension_count + 1
        """, [user_id])

        db.commit()

        # Log activity
        log_activity(
            db=db,
            user_id=user_id,
            activity_type="suspension_applied",
            resource_type="user",
            resource_id=None,
            metadata={"action": action, "suspended_until": str(suspended_until)}
        )

        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Error applying suspension: {e}")
        return False


def check_user_suspension(db, user_id: str) -> Dict[str, Any]:
    """
    檢查用戶是否被停權

    Args:
        db: Database connection
        user_id: 用戶 ID

    Returns:
        Dict: {
            "is_suspended": bool,
            "suspended_until": Optional[datetime],
            "is_banned": bool
        }
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            suspended_until,
            is_banned,
            NOW() > suspended_until as suspension_expired
        FROM users
        WHERE user_id = %s
    """, [user_id])

    result = cursor.fetchone()

    if not result:
        return {"is_suspended": False, "suspended_until": None, "is_banned": False}

    is_banned = result["is_banned"] or False
    suspended_until = result["suspended_until"]

    if is_banned:
        return {
            "is_suspended": True,
            "suspended_until": None,
            "is_banned": True
        }

    if suspended_until and suspended_until > datetime.now():
        return {
            "is_suspended": True,
            "suspended_until": suspended_until,
            "is_banned": False
        }

    return {
        "is_suspended": False,
        "suspended_until": None,
        "is_banned": False
    }


# ========================
# Audit Reputation System
# ========================

def get_audit_reputation(db, user_id: str) -> Dict[str, Any]:
    """
    獲取用戶審核聲望

    Args:
        db: Database connection
        user_id: 用戶 ID

    Returns:
        Dict: 審核聲望記錄
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT * FROM audit_reputation WHERE user_id = %s
    """, [user_id])

    result = cursor.fetchone()

    if result:
        return dict(result)
    else:
        return {
            "user_id": user_id,
            "total_reviews": 0,
            "correct_votes": 0,
            "accuracy_rate": 1.0,
            "reputation_score": 0
        }


def calculate_vote_weight(reputation: Dict[str, Any]) -> float:
    """
    計算投票權重

    Args:
        reputation: 審核聲望記錄

    Returns:
        float: 投票權重
    """
    base_weight = 1.0

    # 聲望加成（最多 +10%）
    reputation_bonus = min(reputation["reputation_score"] / 1000, 0.1)

    # 準確率加成（準確率 > 90% 才有加成）
    accuracy_rate = reputation.get("accuracy_rate", 1.0)
    accuracy_bonus = max(0, (accuracy_rate - 0.9) * 0.5)

    return base_weight + reputation_bonus + accuracy_bonus


def update_audit_reputation(
    db,
    user_id: str,
    was_correct: bool
) -> Dict[str, Any]:
    """
    更新審核聲望

    Args:
        db: Database connection
        user_id: 用戶 ID
        was_correct: 投票是否正確

    Returns:
        Dict: 更新後的聲望記錄
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            INSERT INTO audit_reputation
            (user_id, total_reviews, correct_votes, reputation_score)
            VALUES (%s, 1, %s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET
                total_reviews = audit_reputation.total_reviews + 1,
                correct_votes = audit_reputation.correct_votes + %s,
                accuracy_rate = CAST(audit_reputation.correct_votes + %s AS FLOAT) /
                              CAST(audit_reputation.total_reviews + 1 AS FLOAT),
                reputation_score = audit_reputation.reputation_score + %s,
                updated_at = NOW()
            RETURNING *
        """, [
            user_id,
            1 if was_correct else 0,
            1 if was_correct else 0,
            1 if was_correct else 0,
            1 if was_correct else 0,
            1 if was_correct else -1  # 正確+1，錯誤-1
        ])

        result = dict(cursor.fetchone())
        db.commit()

        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating audit reputation: {e}")
        raise


# ========================
# Activity Logging
# ========================

def log_activity(
    db,
    user_id: str,
    activity_type: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    記錄用戶活動日誌

    Args:
        db: Database connection
        user_id: 用戶 ID
        activity_type: 活動類型
        resource_type: 資源類型
        resource_id: 資源 ID
        metadata: 額外資料
        success: 是否成功
        error_message: 錯誤訊息
        ip_address: IP 地址
        user_agent: User Agent

    Returns:
        Dict: 創建的日誌記錄
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        INSERT INTO user_activity_logs
        (user_id, activity_type, resource_type, resource_id, metadata,
         success, error_message, ip_address, user_agent)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, [
        user_id, activity_type, resource_type, resource_id,
        metadata, success, error_message, ip_address, user_agent
    ])

    result = dict(cursor.fetchone())
    db.commit()

    return result


def get_user_activity_logs(
    db,
    user_id: str,
    activity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    獲取用戶活動日誌

    Args:
        db: Database connection
        user_id: 用戶 ID
        activity_type: 活動類型篩選
        limit: 最多返回數量
        offset: 分頁偏移

    Returns:
        List[Dict]: 活動日誌列表
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT * FROM user_activity_logs
        WHERE user_id = %s
    """
    params = [user_id]

    if activity_type:
        query += " AND activity_type = %s"
        params.append(activity_type)

    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


# ========================
# Helper Functions
# ========================

def get_content_author(db, content_type: str, content_id: int) -> Optional[str]:
    """
    獲取內容作者 ID

    Args:
        db: Database connection
        content_type: 內容類型 ('post' 或 'comment')
        content_id: 內容 ID

    Returns:
        Optional[str]: 作者用戶 ID
    """
    cursor = db.cursor()

    if content_type == "post":
        cursor.execute("SELECT user_id FROM forum_posts WHERE id = %s", [content_id])
    elif content_type == "comment":
        cursor.execute("SELECT user_id FROM forum_comments WHERE id = %s", [content_id])
    else:
        return None

    result = cursor.fetchone()
    return result[0] if result else None


def get_report_statistics(db, days: int = 30) -> Dict[str, Any]:
    """
    獲取檢舉統計數據

    Args:
        db: Database connection
        days: 統計天數

    Returns:
        Dict: 統計數據
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '%s days') as total_reports,
            COUNT(*) FILTER (WHERE review_status = 'pending') as pending_reports,
            COUNT(*) FILTER (WHERE review_status = 'approved') as approved_reports,
            COUNT(*) FILTER (WHERE review_status = 'rejected') as rejected_reports,
            AVG(approve_count::FLOAT / GREATEST(approve_count + reject_count, 1))
                FILTER (WHERE approve_count + reject_count > 0) as avg_approve_ratio
        FROM content_reports
    """, [days])

    result = cursor.fetchone()

    return {
        "total_reports": result["total_reports"] or 0,
        "pending_reports": result["pending_reports"] or 0,
        "approved_reports": result["approved_reports"] or 0,
        "rejected_reports": result["rejected_reports"] or 0,
        "avg_approve_ratio": float(result["avg_approve_ratio"] or 0)
    }


def get_top_reviewers(db, limit: int = 10) -> List[Dict[str, Any]]:
    """
    獲取審核排行榜

    Args:
        db: Database connection
        limit: 最多返回數量

    Returns:
        List[Dict]: 排行榜列表
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT
            a.user_id,
            u.username,
            a.total_reviews,
            a.correct_votes,
            a.accuracy_rate,
            a.reputation_score
        FROM audit_reputation a
        JOIN users u ON a.user_id = u.user_id
        ORDER BY a.reputation_score DESC
        LIMIT %s
    """, [limit])

    return [dict(row) for row in cursor.fetchall()]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_governance_db.py -v`

Expected: Tests pass

**Step 5: Commit**

```bash
git add core/database/governance.py tests/test_governance_db.py
git commit -m "feat(governance): add database operations layer"
```

---

## Task 3: Pydantic Models for Request/Response

**Files:**
- Create: `core/models/governance.py`
- Test: `tests/test_governance_models.py`

**Step 1: Write the failing test**

Create `tests/test_governance_models.py`:

```python
import pytest
from pydantic import ValidationError
from core.models.governance import (
    ReportCreateRequest,
    ReportResponse,
    VoteRequest,
    ReportDetailResponse,
    ViolationPointsResponse,
    ActivityLogResponse,
    ReviewStatisticsResponse
)


def test_report_create_request_valid():
    """Test valid report creation request"""
    data = {
        "content_type": "post",
        "content_id": 123,
        "report_type": "spam",
        "description": "Spam content test"
    }

    request = ReportCreateRequest(**data)

    assert request.content_type == "post"
    assert request.content_id == 123
    assert request.report_type == "spam"


def test_report_create_request_invalid_type():
    """Test invalid content type"""
    with pytest.raises(ValidationError):
        ReportCreateRequest(
            content_type="invalid",
            content_id=123,
            report_type="spam"
        )


def test_report_create_request_invalid_report_type():
    """Test invalid report type"""
    with pytest.raises(ValidationError):
        ReportCreateRequest(
            content_type="post",
            content_id=123,
            report_type="invalid_type"
        )


def test_vote_request_valid():
    """Test valid vote request"""
    data = {"vote_type": "approve"}
    request = VoteRequest(**data)

    assert request.vote_type == "approve"


def test_vote_request_invalid():
    """Test invalid vote type"""
    with pytest.raises(ValidationError):
        VoteRequest(vote_type="invalid")


def test_violation_points_response():
    """Test violation points response model"""
    data = {
        "user_id": "test_user",
        "points": 5,
        "total_violations": 2,
        "suspension_count": 0,
        "action_required": "warning"
    }

    response = ViolationPointsResponse(**data)

    assert response.points == 5
    assert response.action_required == "warning"


def test_review_statistics_response():
    """Test review statistics response model"""
    data = {
        "total_reports": 100,
        "pending_reports": 10,
        "approved_reports": 60,
        "rejected_reports": 30,
        "avg_approve_ratio": 0.67
    }

    response = ReviewStatisticsResponse(**data)

    assert response.total_reports == 100
    assert response.approved_reports == 60
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_governance_models.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'core.models.governance'"

**Step 3: Write minimal implementation**

Create `core/models/governance.py`:

```python
"""
社群治理系統 - Pydantic Models

定義 API 請求和回應的資料模型
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ========================
# Report Models
# ========================

class ReportCreateRequest(BaseModel):
    """檢舉創建請求"""
    content_type: str = Field(..., description="內容類型: post 或 comment")
    content_id: int = Field(..., gt=0, description="內容 ID")
    report_type: str = Field(..., description="檢舉類型")
    description: Optional[str] = Field(None, max_length=500, description="檢舉說明")

    @validator("content_type")
    def validate_content_type(cls, v):
        if v not in ["post", "comment"]:
            raise ValueError("content_type must be 'post' or 'comment'")
        return v

    @validator("report_type")
    def validate_report_type(cls, v):
        valid_types = ["spam", "harassment", "misinformation", "scam", "illegal", "other"]
        if v not in valid_types:
            raise ValueError(f"report_type must be one of: {', '.join(valid_types)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "content_type": "post",
                "content_id": 123,
                "report_type": "spam",
                "description": "重複貼文"
            }
        }


class ReportResponse(BaseModel):
    """檢舉回應（簡化）"""
    id: int
    content_type: str
    content_id: int
    report_type: str
    review_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReportDetailResponse(ReportResponse):
    """檢舉詳情回應"""
    reporter_username: str
    description: Optional[str]
    violation_level: Optional[str]
    action_taken: Optional[str]
    points_assigned: int
    approve_count: int
    reject_count: int
    processed_by: Optional[str]
    updated_at: datetime

    # Consensus info
    has_consensus: bool = False
    decision: Optional[str] = None

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """檢舉列表回應"""
    reports: List[ReportResponse]
    total: int
    page: int
    page_size: int


# ========================
# Vote Models
# ========================

class VoteRequest(BaseModel):
    """投票請求"""
    vote_type: str = Field(..., description="投票類型: approve (違規) 或 reject (不違規)")

    @validator("vote_type")
    def validate_vote_type(cls, v):
        if v not in ["approve", "reject"]:
            raise ValueError("vote_type must be 'approve' or 'reject'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "vote_type": "approve"
            }
        }


class VoteResponse(BaseModel):
    """投票回應"""
    report_id: int
    vote_type: str
    vote_weight: float
    created_at: datetime

    class Config:
        from_attributes = True


class ConsensusResponse(BaseModel):
    """共識檢查回應"""
    has_consensus: bool
    decision: str  # "approved", "rejected", "pending"
    approve_count: int
    reject_count: int
    total_votes: int
    approve_ratio: float


# ========================
# Violation Models
# ========================

class ViolationPointsResponse(BaseModel):
    """違規點數回應"""
    user_id: str
    points: int
    total_violations: int
    suspension_count: int
    last_violation_at: Optional[datetime]
    action_required: Optional[str]  # warning, suspend_3d, etc.
    suspended_until: Optional[datetime]

    @validator("action_required", pre=True)
    def calculate_action_required(cls, v, values):
        # If already provided, use it
        if v is not None:
            return v
        # Calculate based on points
        points = values.get("points", 0)
        if points >= 40:
            return "permanent_ban"
        elif points >= 30:
            return "suspend_30d"
        elif points >= 20:
            return "suspend_7d"
        elif points >= 10:
            return "suspend_3d"
        elif points >= 5:
            return "warning"
        return None

    class Config:
        from_attributes = True


class ViolationRecordResponse(BaseModel):
    """違規記錄回應"""
    id: int
    violation_level: str
    violation_type: str
    points: int
    action_taken: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ========================
# Activity Log Models
# ========================

class ActivityLogResponse(BaseModel):
    """活動日誌回應"""
    id: int
    activity_type: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    metadata: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityStatsResponse(BaseModel):
    """活動統計回應"""
    user_id: str
    period: str  # "today", "week", "month", "all"
    posts_created: int = 0
    comments_created: int = 0
    likes_received: int = 0
    reports_submitted: int = 0
    reviews_completed: int = 0
    current_points: int = 0


# ========================
# Statistics Models
# ========================

class ReviewStatisticsResponse(BaseModel):
    """審核統計回應"""
    total_reports: int
    pending_reports: int
    approved_reports: int
    rejected_reports: int
    avg_approve_ratio: float

    class Config:
        from_attributes = True


class ReviewerRankResponse(BaseModel):
    """審核排行榜回應"""
    user_id: str
    username: str
    total_reviews: int
    correct_votes: int
    accuracy_rate: float
    reputation_score: int
    rank: int


# ========================
# Audit Records (Transparency)
# ========================

class AuditVoteRecord(BaseModel):
    """審核投票記錄（公開用）"""
    username: str  # 部分遮蔽
    vote_type: str
    vote_weight: float
    created_at: datetime

    class Config:
        from_attributes = True


class AuditRecordResponse(BaseModel):
    """審核記錄回應（公開透明）"""
    report_id: int
    status: str
    violation_level: Optional[str]
    votes: Dict[str, int]  # approve, reject, total
    decision: Optional[str]
    action: Optional[str]
    reviewers: List[AuditVoteRecord]

    class Config:
        from_attributes = True
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_governance_models.py -v`

Expected: Tests pass

**Step 5: Commit**

```bash
git add core/models/governance.py tests/test_governance_models.py
git commit -m "feat(governance): add Pydantic models"
```

---

## Task 4: API Router - Report Management

**Files:**
- Create: `api/routers/governance.py`
- Modify: `api_server.py` (to register the router)
- Test: `tests/test_governance_api.py`

**Step 1: Write the failing test**

Create `tests/test_governance_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from api_server import app
from core.database.connection import get_db


@pytest.fixture
def client():
    """Test client with database"""
    def override_get_db():
        from core.database.connection import get_db
        for db in get_db():
            yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(client):
    """Create and login test user"""
    # Create user
    # Login and get token
    # Return user_id and token
    pass


@pytest.fixture
def test_pro_user(client):
    """Create and login test PRO user"""
    pass


def test_create_report_success(client, test_user):
    """Test successful report creation"""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    response = client.post(
        "/api/governance/reports",
        json={
            "content_type": "post",
            "content_id": 123,
            "report_type": "spam",
            "description": "Test spam"
        },
        headers=headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["content_type"] == "post"
    assert data["report_type"] == "spam"
    assert data["review_status"] == "pending"


def test_create_report_duplicate(client, test_user):
    """Test duplicate report rejection"""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # First report
    client.post(
        "/api/governance/reports",
        json={
            "content_type": "post",
            "content_id": 999,
            "report_type": "spam"
        },
        headers=headers
    )

    # Duplicate report
    response = client.post(
        "/api/governance/reports",
        json={
            "content_type": "post",
            "content_id": 999,
            "report_type": "spam"
        },
        headers=headers
    )

    assert response.status_code == 400


def test_create_report_rate_limit(client, test_user):
    """Test daily report limit"""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # Try to create 11 reports (limit is 10)
    for i in range(11):
        response = client.post(
            "/api/governance/reports",
            json={
                "content_type": "comment",
                "content_id": i,
                "report_type": "spam"
            },
            headers=headers
        )

    # Last request should fail
    assert response.status_code == 429


def test_get_pending_reports_unauthorized(client, test_user):
    """Test that non-PRO users can't access pending reports"""
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    response = client.get(
        "/api/governance/reports/pending",
        headers=headers
    )

    assert response.status_code == 403


def test_get_pending_reports_pro(client, test_pro_user):
    """Test PRO user accessing pending reports"""
    headers = {"Authorization": f"Bearer {test_pro_user['token']}"}

    response = client.get(
        "/api/governance/reports/pending",
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "reports" in data


def test_vote_on_report(client, test_pro_user):
    """Test voting on a report"""
    headers = {"Authorization": f"Bearer {test_pro_user['token']}"}

    # First create a report (using a different user)
    # Then vote on it
    response = client.post(
        "/api/governance/reports/1/vote",
        json={"vote_type": "approve"},
        headers=headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["vote_type"] == "approve"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_governance_api.py::test_create_report_success -v`

Expected: FAIL with 404 or router not found

**Step 3: Write minimal implementation**

Create `api/routers/governance.py`:

```python
"""
社群治理系統 - API Router

提供治理相關的 API 端點
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from core.database.connection import get_db
from core.database.governance import (
    # Reports
    create_report,
    get_pending_reports,
    get_report_by_id,
    get_user_reports,
    check_daily_report_limit,
    finalize_report,
    # Votes
    vote_on_report,
    get_report_votes,
    check_report_consensus,
    # Violations
    get_user_violation_points,
    get_user_violations,
    check_user_suspension,
    # Activity
    get_user_activity_logs,
    # Stats
    get_report_statistics,
    get_top_reviewers,
    # Helpers
    get_content_author
)
from core.database.user import get_user_membership
from core.models.governance import (
    ReportCreateRequest,
    ReportResponse,
    ReportDetailResponse,
    VoteRequest,
    VoteResponse,
    ConsensusResponse,
    ViolationPointsResponse,
    ViolationRecordResponse,
    ActivityLogResponse,
    ReviewStatisticsResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])
security = HTTPBearer()


# ========================
# Dependencies
# ========================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db)
) -> dict:
    """Get current authenticated user"""
    token = credentials.credentials

    # Decode token and get user_id
    # This should integrate with existing auth system
    # For now, assume token contains user_id
    cursor = db.cursor()
    cursor.execute(
        "SELECT user_id, username FROM users WHERE auth_token = %s",
        [token]
    )
    result = cursor.fetchone()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    return {
        "user_id": result[0],
        "username": result[1]
    }


async def require_pro_user(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
) -> dict:
    """Require PRO membership"""
    membership = get_user_membership(db, current_user["user_id"])

    if not membership["is_pro"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires PRO membership"
        )

    return current_user


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# ========================
# Report Management Endpoints
# ========================

@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_report(
    report_data: ReportCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    提交內容檢舉

    - 任何登入用戶可使用
    - 每天最多 10 次檢舉
    - 同一內容只能檢舉一次
    """
    user_id = current_user["user_id"]

    # Check daily limit
    if not check_daily_report_limit(db, user_id, daily_limit=10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily report limit reached (10 reports per day)"
        )

    # Check if user is suspended
    suspension = check_user_suspension(db, user_id)
    if suspension["is_suspended"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended"
        )

    try:
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent")

        report = create_report(
            db=db,
            reporter_user_id=user_id,
            content_type=report_data.content_type,
            content_id=report_data.content_id,
            report_type=report_data.report_type,
            description=report_data.description
        )

        return report

    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already reported this content"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/reports/pending", response_model=List[ReportResponse])
async def get_pending_reports_endpoint(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(require_pro_user),
    db=Depends(get_db)
):
    """
    獲取待審核檢舉列表

    - 僅限 PRO 用戶
    - 排除用戶自己發表的內容和提交的檢舉
    """
    reports = get_pending_reports(
        db=db,
        limit=limit,
        offset=offset,
        exclude_user_id=current_user["user_id"]
    )

    return reports


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
async def get_report_detail(
    report_id: int,
    current_user: dict = Depends(require_pro_user),
    db=Depends(get_db)
):
    """
    獲取檢舉詳情

    - 僅限 PRO 用戶
    - 包含投票統計和共識狀態
    """
    report = get_report_by_id(db, report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    # Get consensus status
    consensus = check_report_consensus(db, report_id)

    # Mask reporter username for privacy (partial masking)
    username = report.get("reporter_username", "")
    if len(username) > 3:
        masked_username = username[:3] + "***" + username[-3:]
    else:
        masked_username = "***"

    report["reporter_username"] = masked_username
    report["has_consensus"] = consensus["has_consensus"]
    report["decision"] = consensus["decision"]

    return report


@router.get("/reports", response_model=List[ReportResponse])
async def get_my_reports(
    status: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    獲取我提交的檢舉記錄

    - 任何登入用戶可查看自己的檢舉
    - 可篩選狀態
    """
    reports = get_user_reports(
        db=db,
        user_id=current_user["user_id"],
        status=status,
        limit=limit
    )

    return reports


# ========================
# Voting Endpoints
# ========================

@router.post("/reports/{report_id}/vote", response_model=VoteResponse, status_code=status.HTTP_201_CREATED)
async def cast_vote(
    report_id: int,
    vote_data: VoteRequest,
    request: Request,
    current_user: dict = Depends(require_pro_user),
    db=Depends(get_db)
):
    """
    對檢舉進行投票

    - 僅限 PRO 用戶
    - 每個檢舉只能投票一次
    - 可以修改投票（toggle）
    """
    # Check if report exists and is pending
    report = get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    if report["review_status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not pending review"
        )

    # Check for conflicts (can't vote on own content)
    author_id = get_content_author(db, report["content_type"], report["content_id"])
    if author_id == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot vote on your own content"
        )

    if report["reporter_user_id"] == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot vote on your own report"
        )

    try:
        vote = vote_on_report(
            db=db,
            report_id=report_id,
            reviewer_user_id=current_user["user_id"],
            vote_type=vote_data.vote_type
        )

        # Check if consensus reached
        consensus = check_report_consensus(db, report_id)

        if consensus["has_consensus"]:
            # Auto-finalize the report
            finalize_report(
                db=db,
                report_id=report_id,
                decision=consensus["decision"],
                violation_level=report["report_type"] if consensus["decision"] == "approved" else None,
                processed_by="system"
            )

            # Update audit reputation for all voters
            votes = get_report_votes(db, report_id)
            final_decision = consensus["decision"]

            for v in votes:
                from core.database.governance import update_audit_reputation
                was_correct = (v["vote_type"] == "approve" and final_decision == "approved") or \
                             (v["vote_type"] == "reject" and final_decision == "rejected")
                update_audit_reputation(db, v["user_id"], was_correct)

        return vote

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/reports/{report_id}/votes")
async def get_report_votes_endpoint(
    report_id: int,
    current_user: dict = Depends(require_pro_user),
    db=Depends(get_db)
):
    """
    獲取檢舉的投票記錄

    - 僅限 PRO 用戶
    - 用戶名部分遮蔽以保護隱私
    """
    votes = get_report_votes(db, report_id)

    # Mask usernames
    for vote in votes:
        username = vote.get("username", "")
        if len(username) > 3:
            vote["username"] = username[:3] + "***" + username[-3:]
        else:
            vote["username"] = "***"

    return {"votes": votes}


@router.get("/my-votes")
async def get_my_votes(
    current_user: dict = Depends(require_pro_user),
    db=Depends(get_db)
):
    """
    獲取我的投票記錄

    - 僅限 PRO 用戶
    - 顯示自己所有的投票歷史
    """
    cursor = db.cursor(cursor_factory=dict_cursor)

    cursor.execute("""
        SELECT
            v.*,
            r.content_type,
            r.content_id,
            r.report_type,
            r.review_status,
            r.violation_level
        FROM report_review_votes v
        JOIN content_reports r ON v.report_id = r.id
        WHERE v.reviewer_user_id = %s
        ORDER BY v.created_at DESC
        LIMIT 100
    """, [current_user["user_id"]])

    return {"votes": cursor.fetchall()}


# ========================
# Violation Points Endpoints
# ========================

@router.get("/my-points", response_model=ViolationPointsResponse)
async def get_my_violation_points(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    獲取我的違規點數

    - 任何登入用戶可查看自己的點數
    - 顯示當前狀態和可能的處罰
    """
    points = get_user_violation_points(db, current_user["user_id"])

    # Check suspension status
    suspension = check_user_suspension(db, current_user["user_id"])

    points["action_required"] = None
    points["suspended_until"] = suspension.get("suspended_until")

    if suspension["is_suspended"]:
        if suspension["is_banned"]:
            points["action_required"] = "permanent_ban"
        else:
            points["action_required"] = "suspended"

    return points


@router.get("/my-violations", response_model=List[ViolationRecordResponse])
async def get_my_violations(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    獲取我的違規記錄

    - 任何登入用戶可查看自己的違規記錄
    """
    violations = get_user_violations(
        db=db,
        user_id=current_user["user_id"],
        limit=limit
    )

    return violations


# ========================
# Activity Log Endpoints
# ========================

@router.get("/my-logs", response_model=List[ActivityLogResponse])
async def get_my_activity_logs(
    activity_type: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    獲取我的活動日誌

    - 任何登入用戶可查看自己的活動日誌
    - 可按活動類型篩選
    """
    logs = get_user_activity_logs(
        db=db,
        user_id=current_user["user_id"],
        activity_type=activity_type,
        limit=limit
    )

    return logs


@router.get("/my-activity-stats")
async def get_my_activity_stats(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    獲取我的活動統計

    - 返回各類活動的統計數據
    """
    from psycopg2.extras import RealDictCursor
    cursor = db.cursor(cursor_factory=RealDictCursor)

    user_id = current_user["user_id"]

    # Get various activity counts
    stats = {
        "user_id": user_id,
        "period": "all",
        "posts_created": 0,
        "comments_created": 0,
        "likes_received": 0,
        "reports_submitted": 0,
        "reviews_completed": 0,
        "current_points": 0
    }

    # Posts created
    cursor.execute(
        "SELECT COUNT(*) FROM forum_posts WHERE user_id = %s",
        [user_id]
    )
    stats["posts_created"] = cursor.fetchone()[0] or 0

    # Comments created
    cursor.execute(
        "SELECT COUNT(*) FROM forum_comments WHERE user_id = %s",
        [user_id]
    )
    stats["comments_created"] = cursor.fetchone()[0] or 0

    # Reports submitted
    cursor.execute(
        "SELECT COUNT(*) FROM content_reports WHERE reporter_user_id = %s",
        [user_id]
    )
    stats["reports_submitted"] = cursor.fetchone()[0] or 0

    # Reviews completed
    cursor.execute(
        "SELECT COUNT(*) FROM report_review_votes WHERE reviewer_user_id = %s",
        [user_id]
    )
    stats["reviews_completed"] = cursor.fetchone()[0] or 0

    # Current points
    points = get_user_violation_points(db, user_id)
    stats["current_points"] = points["points"]

    return stats


# ========================
# Statistics and Public Endpoints
# ========================

@router.get("/statistics", response_model=ReviewStatisticsResponse)
async def get_governance_statistics(
    days: int = 30,
    db=Depends(get_db)
):
    """
    獲取治理系統統計數據

    - 公開端點，不需要登入
    - 用於透明監督
    """
    stats = get_report_statistics(db, days)

    return stats


@router.get("/reviewers/top")
async def get_top_reviewers_endpoint(
    limit: int = 10,
    db=Depends(get_db)
):
    """
    獲取審核排行榜

    - 公開端點
    - 顯示最活躍的審核員
    """
    reviewers = get_top_reviewers(db, limit)

    # Add rank
    for i, reviewer in enumerate(reviewers):
        reviewer["rank"] = i + 1

    return {"reviewers": reviewers}


@router.get("/audit-records/{report_id}")
async def get_audit_record(
    report_id: int,
    db=Depends(get_db)
):
    """
    獲取審核記錄（透明監督）

    - 公開端點
    - 顯示完整的審核記錄（除敏感資訊）
    """
    report = get_report_by_id(db, report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    votes = get_report_votes(db, report_id)

    # Mask usernames in votes
    for vote in votes:
        username = vote.get("username", "")
        if len(username) > 3:
            vote["username"] = username[:3] + "***" + username[-3:]
        else:
            vote["username"] = "***"

    return {
        "report_id": report_id,
        "status": report["review_status"],
        "violation_level": report.get("violation_level"),
        "votes": {
            "approve": report["approve_count"],
            "reject": report["reject_count"],
            "total": report["approve_count"] + report["reject_count"]
        },
        "decision": report.get("review_status"),
        "action": report.get("action_taken"),
        "reviewers": votes
    }
```

**Step 4: Register the router in api_server.py**

Edit `api_server.py` to add the governance router (find where other routers are included):

```python
# Add this import near the top with other router imports
from api.routers import governance

# Add this where routers are registered (search for include_router)
app.include_router(
    governance.router,
    tags=["governance"]
)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_governance_api.py -v`

Expected: Tests pass (may need to adjust auth integration)

**Step 6: Commit**

```bash
git add api/routers/governance.py api_server.py tests/test_governance_api.py
git commit -m "feat(governance): add API router for report management"
```

---

## Task 5: Frontend - Governance Dashboard

**Files:**
- Create: `web/governance/index.html`
- Create: `web/governance/js/governance.js`
- Create: `web/governance/css/governance.css`

**Step 1: Create HTML structure**

Create `web/governance/index.html`:

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>社群治理 - Stock Agent</title>
    <link rel="stylesheet" href="../styles.css">
    <link rel="stylesheet" href="css/governance.css">
</head>
<body>
    <div class="governance-container">
        <!-- Header -->
        <header class="governance-header">
            <h1>🛡️ 社群治理中心</h1>
            <nav class="governance-nav">
                <button class="nav-btn active" data-tab="dashboard">儀表板</button>
                <button class="nav-btn" data-tab="my-reports">我的檢舉</button>
                <button class="nav-btn pro-only" data-tab="review">審核隊列</button>
                <button class="nav-btn" data-tab="my-points">違規記錄</button>
                <button class="nav-btn" data-tab="logs">活動日誌</button>
            </nav>
        </header>

        <!-- Dashboard Tab -->
        <section id="tab-dashboard" class="tab-content active">
            <h2>治理概況</h2>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📊</div>
                    <div class="stat-label">待審核案件</div>
                    <div class="stat-value" id="pending-count">-</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">✅</div>
                    <div class="stat-label">本月已處理</div>
                    <div class="stat-value" id="processed-count">-</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">⚖️</div>
                    <div class="stat-label">處理率</div>
                    <div class="stat-value" id="approval-rate">-</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">👥</div>
                    <div class="stat-label">活躍審核員</div>
                    <div class="stat-value" id="active-reviewers">-</div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="quick-actions">
                <button id="btn-report-content" class="action-btn">
                    🚨 檢舉內容
                </button>
                <button id="btn-start-review" class="action-btn pro-only">
                    🛡️ 開始審核
                </button>
            </div>

            <!-- Recent Activity -->
            <div class="recent-activity">
                <h3>最近活動</h3>
                <div id="recent-activity-list" class="activity-list">
                    <p class="loading">載入中...</p>
                </div>
            </div>
        </section>

        <!-- My Reports Tab -->
        <section id="tab-my-reports" class="tab-content">
            <div class="tab-header">
                <h2>我的檢舉</h2>
                <button id="btn-new-report" class="btn-primary">+ 新增檢舉</button>
            </div>

            <div class="filter-bar">
                <select id="report-status-filter">
                    <option value="">全部狀態</option>
                    <option value="pending">待審核</option>
                    <option value="approved">已通過</option>
                    <option value="rejected">已駁回</option>
                </select>
            </div>

            <div id="my-reports-list" class="reports-list">
                <p class="loading">載入中...</p>
            </div>
        </section>

        <!-- Review Queue Tab (PRO Only) -->
        <section id="tab-review" class="tab-content pro-only">
            <div class="tab-header">
                <h2>🛡️ 內容審核隊列</h2>
                <div class="reviewer-stats">
                    <span>你的審核: <strong id="my-review-count">0</strong></span>
                    <span>準確率: <strong id="my-accuracy">0%</strong></span>
                    <span>聲望排名: <strong id="my-rank">#-</strong></span>
                    <span>投票權重: <strong id="my-weight">1.0x</strong></span>
                </div>
            </div>

            <div id="review-queue" class="review-queue">
                <p class="loading">載入待審核案件...</p>
            </div>

            <!-- Empty State -->
            <div id="review-empty" class="empty-state hidden">
                <p>🎉 目前沒有待審核的案件！</p>
            </div>
        </section>

        <!-- My Points Tab -->
        <section id="tab-my-points" class="tab-content">
            <h2>違規記錄</h2>

            <div class="points-overview">
                <div class="points-card status-ok">
                    <div class="points-label">當前點數</div>
                    <div class="points-value" id="current-points">0</div>
                    <div class="points-status" id="points-status">狀態良好</div>
                </div>
            </div>

            <h3>違規歷史</h3>
            <div id="violations-list" class="violations-list">
                <p class="loading">載入中...</p>
            </div>
        </section>

        <!-- Activity Logs Tab -->
        <section id="tab-logs" class="tab-content">
            <h2>活動日誌</h2>

            <div class="filter-bar">
                <select id="activity-type-filter">
                    <option value="">全部活動</option>
                    <option value="post_created">發文</option>
                    <option value="comment_created">留言</option>
                    <option value="report_submitted">檢舉</option>
                    <option value="vote_cast">審核投票</option>
                    <option value="violation_recorded">違規記錄</option>
                </select>
            </div>

            <div class="activity-stats">
                <div class="mini-stat">
                    <span class="label">本月發文</span>
                    <span class="value" id="stat-posts">0</span>
                </div>
                <div class="mini-stat">
                    <span class="label">本月留言</span>
                    <span class="value" id="stat-comments">0</span>
                </div>
                <div class="mini-stat">
                    <span class="label">檢舉次數</span>
                    <span class="value" id="stat-reports">0</span>
                </div>
                <div class="mini-stat">
                    <span class="label">審核次數</span>
                    <span class="value" id="stat-reviews">0</span>
                </div>
            </div>

            <div id="activity-logs-list" class="activity-logs-list">
                <p class="loading">載入中...</p>
            </div>
        </section>
    </div>

    <!-- Report Modal -->
    <div id="report-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>🚨 檢舉內容</h3>
                <button class="modal-close">&times;</button>
            </div>
            <form id="report-form" class="modal-body">
                <input type="hidden" id="report-content-type" name="content_type">
                <input type="hidden" id="report-content-id" name="content_id">

                <div class="form-group">
                    <label>檢舉類型</label>
                    <select id="report-type" name="report_type" required>
                        <option value="">請選擇...</option>
                        <option value="spam">📢 垃圾內容 - 重複貼文、無意義留言</option>
                        <option value="harassment">😠 騷擾攻擊 - 人身攻擊、惡意標籤</option>
                        <option value="misinformation">📰 錯誤資訊 - 虛假消息、誤導投資</option>
                        <option value="scam">🎭 詐騙行為 - 詐騙錢財、假冒身份</option>
                        <option value="illegal">⚠️ 非法內容 - 違法內容、洗錢</option>
                        <option value="other">📋 其他 - 其他違規行為</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>說明 (選填)</label>
                    <textarea id="report-description" name="description"
                              maxlength="500" placeholder="請詳細說明違規情況..."></textarea>
                    <small class="char-count"><span id="desc-count">0</span>/500</small>
                </div>

                <div class="form-actions">
                    <button type="button" class="btn-secondary modal-close-btn">取消</button>
                    <button type="submit" class="btn-primary">提交檢舉</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Toast Notification -->
    <div id="toast" class="toast hidden">
        <span class="toast-message"></span>
    </div>

    <script src="../config.js"></script>
    <script src="../js/auth.js"></script>
    <script src="js/governance.js"></script>
</body>
</html>
```

**Step 2: Create CSS styles**

Create `web/governance/css/governance.css`:

```css
/* Governance Dashboard Styles */

.governance-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* Header */
.governance-header {
    margin-bottom: 30px;
}

.governance-header h1 {
    font-size: 28px;
    margin-bottom: 20px;
}

.governance-nav {
    display: flex;
    gap: 10px;
    border-bottom: 2px solid #e0e0e0;
}

.nav-btn {
    padding: 12px 24px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 16px;
    color: #666;
    border-bottom: 3px solid transparent;
    transition: all 0.3s;
}

.nav-btn:hover {
    color: #333;
}

.nav-btn.active {
    color: #2563eb;
    border-bottom-color: #2563eb;
}

/* Tab Content */
.tab-content {
    display: none;
}

.tab-content.active {
    display: block;
}

.tab-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.stat-card {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}

.stat-icon {
    font-size: 32px;
    margin-bottom: 10px;
}

.stat-label {
    font-size: 14px;
    color: #666;
    margin-bottom: 5px;
}

.stat-value {
    font-size: 32px;
    font-weight: bold;
    color: #2563eb;
}

/* Quick Actions */
.quick-actions {
    display: flex;
    gap: 15px;
    margin-bottom: 30px;
}

.action-btn {
    padding: 15px 30px;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    cursor: pointer;
    background: #2563eb;
    color: white;
    transition: background 0.3s;
}

.action-btn:hover {
    background: #1d4ed8;
}

/* Activity List */
.activity-list {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 20px;
}

.activity-item {
    padding: 15px 0;
    border-bottom: 1px solid #e0e0e0;
}

.activity-item:last-child {
    border-bottom: none;
}

.activity-time {
    font-size: 12px;
    color: #999;
    margin-bottom: 5px;
}

.activity-content {
    font-size: 14px;
}

/* Reports List */
.reports-list {
    display: grid;
    gap: 15px;
}

.report-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 15px;
}

.report-type {
    font-weight: bold;
    color: #2563eb;
}

.report-status {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
}

.report-status.pending {
    background: #fef3c7;
    color: #92400e;
}

.report-status.approved {
    background: #d1fae5;
    color: #065f46;
}

.report-status.rejected {
    background: #fee2e2;
    color: #991b1b;
}

/* Review Queue */
.reviewer-stats {
    display: flex;
    gap: 20px;
    font-size: 14px;
}

.reviewer-stats span strong {
    color: #2563eb;
}

.review-card {
    background: white;
    border: 2px solid #e0e0e0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
}

.review-card.voted {
    border-color: #2563eb;
}

.review-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 15px;
}

.review-type {
    font-size: 18px;
    font-weight: bold;
}

.review-votes {
    display: flex;
    gap: 10px;
    font-size: 14px;
}

.vote-count.approve {
    color: #dc2626;
}

.vote-count.reject {
    color: #16a34a;
}

.review-content {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 15px;
    font-style: italic;
}

.review-actions {
    display: flex;
    gap: 10px;
}

.vote-btn {
    flex: 1;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    background: white;
    cursor: pointer;
    font-size: 16px;
    transition: all 0.3s;
}

.vote-btn:hover {
    border-color: #2563eb;
}

.vote-btn.approve.selected {
    background: #dc2626;
    color: white;
    border-color: #dc2626;
}

.vote-btn.reject.selected {
    background: #16a34a;
    color: white;
    border-color: #16a34a;
}

/* Points Overview */
.points-overview {
    display: flex;
    justify-content: center;
    margin-bottom: 30px;
}

.points-card {
    width: 300px;
    padding: 30px;
    border-radius: 16px;
    text-align: center;
}

.points-card.status-ok {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
}

.points-card.status-warning {
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: white;
}

.points-card.status-danger {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: white;
}

.points-label {
    font-size: 14px;
    opacity: 0.9;
    margin-bottom: 10px;
}

.points-value {
    font-size: 64px;
    font-weight: bold;
    line-height: 1;
}

.points-status {
    font-size: 18px;
    margin-top: 15px;
}

/* Violations List */
.violations-list {
    display: grid;
    gap: 10px;
}

.violation-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 8px;
}

.violation-level {
    font-weight: bold;
    text-transform: uppercase;
}

.violation-level.mild { color: #f59e0b; }
.violation-level.medium { color: #ef4444; }
.violation-level.severe { color: #dc2626; }
.violation-level.critical { color: #991b1b; }

/* Activity Stats */
.activity-stats {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
}

.mini-stat {
    background: #f8f9fa;
    padding: 15px 20px;
    border-radius: 8px;
    text-align: center;
}

.mini-stat .label {
    font-size: 12px;
    color: #666;
    display: block;
    margin-bottom: 5px;
}

.mini-stat .value {
    font-size: 24px;
    font-weight: bold;
    color: #2563eb;
}

/* Activity Logs */
.activity-logs-list {
    position: relative;
    padding-left: 30px;
}

.activity-logs-list::before {
    content: '';
    position: absolute;
    left: 10px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #e0e0e0;
}

.log-item {
    position: relative;
    padding: 15px 0;
}

.log-item::before {
    content: '';
    position: absolute;
    left: -24px;
    top: 20px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #2563eb;
}

.log-item.activity-type-post_created::before { background: #10b981; }
.log-item.activity-type-report_submitted::before { background: #f59e0b; }
.log-item.activity-type-vote_cast::before { background: #8b5cf6; }
.log-item.activity-type-violation_recorded::before { background: #ef4444; }

.log-time {
    font-size: 12px;
    color: #999;
    margin-bottom: 5px;
}

.log-content {
    font-size: 14px;
}

/* Filter Bar */
.filter-bar {
    margin-bottom: 20px;
}

.filter-bar select {
    padding: 8px 15px;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    font-size: 14px;
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
}

.modal.active {
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-content {
    background: white;
    border-radius: 12px;
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid #e0e0e0;
}

.modal-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #999;
}

.modal-body {
    padding: 20px;
}

.form-group {
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: bold;
}

.form-group input,
.form-group select,
.form-group textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    font-size: 14px;
}

.form-group textarea {
    min-height: 100px;
    resize: vertical;
}

.char-count {
    display: block;
    text-align: right;
    font-size: 12px;
    color: #999;
    margin-top: 5px;
}

.form-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.btn-primary,
.btn-secondary {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
}

.btn-primary {
    background: #2563eb;
    color: white;
}

.btn-secondary {
    background: #e5e7eb;
    color: #374151;
}

/* Toast */
.toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 15px 25px;
    background: #333;
    color: white;
    border-radius: 8px;
    z-index: 2000;
}

.toast.success {
    background: #10b981;
}

.toast.error {
    background: #ef4444;
}

.toast.hidden {
    display: none;
}

/* Utility */
.hidden {
    display: none !important;
}

.loading {
    text-align: center;
    color: #999;
    padding: 40px;
}

.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #999;
}

/* PRO Badge */
.pro-only {
    display: none;
}

.pro-only.show {
    display: flex;
}

.pro-only.show.nav-btn {
    display: inline-block;
}
```

**Step 3: Create JavaScript logic**

Create `web/governance/js/governance.js`:

```javascript
/**
 * Community Governance Dashboard
 * Provides UI for reporting, reviewing, and monitoring governance activities
 */

// State
const state = {
    isPro: false,
    currentTab: 'dashboard',
    reports: [],
    votes: {}, // Track user's votes: { reportId: 'approve'|'reject' }
    reviewerStats: null
};

// API Base URL (from config)
const API_BASE = window.API_BASE || '';

// ========================
// Initialization
// ========================

document.addEventListener('DOMContentLoaded', async () => {
    await checkProStatus();
    initEventListeners();
    loadDashboard();
});

async function checkProStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/user/me`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            state.isPro = data.membership_tier === 'pro' && data.is_pro;

            // Show/hide PRO elements
            document.querySelectorAll('.pro-only').forEach(el => {
                if (state.isPro) {
                    el.classList.add('show');
                }
            });
        }
    } catch (error) {
        console.error('Failed to check PRO status:', error);
    }
}

function initEventListeners() {
    // Tab navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // New report button
    document.getElementById('btn-new-report')?.addEventListener('click', openReportModal);

    // Report modal
    document.querySelectorAll('.modal-close, .modal-close-btn').forEach(btn => {
        btn.addEventListener('click', closeReportModal);
    });

    // Report form
    document.getElementById('report-form')?.addEventListener('submit', submitReport);

    // Character count
    document.getElementById('report-description')?.addEventListener('input', (e) => {
        document.getElementById('desc-count').textContent = e.target.value.length;
    });

    // Status filter
    document.getElementById('report-status-filter')?.addEventListener('change', loadMyReports);

    // Activity filter
    document.getElementById('activity-type-filter')?.addEventListener('change', loadActivityLogs);
}

// ========================
// Tab Navigation
// ========================

function switchTab(tabName) {
    state.currentTab = tabName;

    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });

    // Load content for the tab
    switch (tabName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'my-reports':
            loadMyReports();
            break;
        case 'review':
            if (state.isPro) {
                loadReviewQueue();
            }
            break;
        case 'my-points':
            loadMyPoints();
            break;
        case 'logs':
            loadActivityLogs();
            loadActivityStats();
            break;
    }
}

// ========================
// Dashboard
// ========================

async function loadDashboard() {
    try {
        const [statsRes, logsRes] = await Promise.all([
            fetch(`${API_BASE}/api/governance/statistics`),
            fetch(`${API_BASE}/api/governance/my-logs`, {
                headers: getAuthHeaders()
            })
        ]);

        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById('pending-count').textContent = stats.pending_reports;
            document.getElementById('processed-count').textContent = stats.approved_reports + stats.rejected_reports;
            document.getElementById('approval-rate').textContent = `${(stats.avg_approve_ratio * 100).toFixed(0)}%`;
        }

        if (logsRes.ok) {
            const logs = await logsRes.json();
            renderRecentActivity(logs.slice(0, 5));
        }

    } catch (error) {
        console.error('Failed to load dashboard:', error);
    }
}

function renderRecentActivity(logs) {
    const container = document.getElementById('recent-activity-list');

    if (logs.length === 0) {
        container.innerHTML = '<p class="empty-state">暫無活動記錄</p>';
        return;
    }

    container.innerHTML = logs.map(log => `
        <div class="activity-item">
            <div class="activity-time">${formatTime(log.created_at)}</div>
            <div class="activity-content">${formatActivityMessage(log)}</div>
        </div>
    `).join('');
}

// ========================
// My Reports
// ========================

async function loadMyReports() {
    const container = document.getElementById('my-reports-list');
    const statusFilter = document.getElementById('report-status-filter')?.value;

    container.innerHTML = '<p class="loading">載入中...</p>';

    try {
        let url = `${API_BASE}/api/governance/reports`;
        if (statusFilter) {
            url += `?status=${statusFilter}`;
        }

        const response = await fetch(url, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const reports = await response.json();
            renderMyReports(reports);
        } else {
            container.innerHTML = '<p class="error">載入失敗</p>';
        }
    } catch (error) {
        console.error('Failed to load reports:', error);
        container.innerHTML = '<p class="error">載入失敗</p>';
    }
}

function renderMyReports(reports) {
    const container = document.getElementById('my-reports-list');

    if (reports.length === 0) {
        container.innerHTML = '<p class="empty-state">尚未提交任何檢舉</p>';
        return;
    }

    container.innerHTML = `<div class="reports-list">` + reports.map(report => `
        <div class="report-card">
            <div>
                <div class="report-type">${formatReportType(report.report_type)}</div>
                <div class="report-content">${report.content_type === 'post' ? '文章' : '留言'} #${report.content_id}</div>
                <div class="report-time">${formatTime(report.created_at)}</div>
            </div>
            <div>
                <span class="report-status ${report.review_status}">${formatStatus(report.review_status)}</span>
            </div>
        </div>
    `).join('') + '</div>';
}

// ========================
// Review Queue (PRO)
// ========================

async function loadReviewQueue() {
    if (!state.isPro) return;

    const container = document.getElementById('review-queue');
    const emptyState = document.getElementById('review-empty');

    container.innerHTML = '<p class="loading">載入中...</p>';

    try {
        // Load reviewer stats
        const statsRes = await fetch(`${API_BASE}/api/governance/my-activity-stats`, {
            headers: getAuthHeaders()
        });

        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById('my-review-count').textContent = stats.reviews_completed;
            // Accuracy and rank would come from audit_reputation table
        }

        // Load pending reports
        const reportsRes = await fetch(`${API_BASE}/api/governance/reports/pending`, {
            headers: getAuthHeaders()
        });

        if (reportsRes.ok) {
            const reports = await reportsRes.json();

            if (reports.length === 0) {
                container.classList.add('hidden');
                emptyState.classList.remove('hidden');
            } else {
                container.classList.remove('hidden');
                emptyState.classList.add('hidden');
                renderReviewQueue(reports);
            }
        }
    } catch (error) {
        console.error('Failed to load review queue:', error);
    }
}

function renderReviewQueue(reports) {
    const container = document.getElementById('review-queue');

    container.innerHTML = reports.map(report => {
        const userVote = state.votes[report.id];

        return `
        <div class="review-card ${userVote ? 'voted' : ''}" data-report-id="${report.id}">
            <div class="review-header">
                <div class="review-type">${formatReportType(report.report_type)}</div>
                <div class="review-votes">
                    <span class="vote-count approve">🚫 ${report.approve_count}</span>
                    <span class="vote-count reject">✅ ${report.reject_count}</span>
                </div>
            </div>
            <div class="review-content">
                ${report.description || '無詳細說明'}
            </div>
            <div class="review-actions">
                <button class="vote-btn approve ${userVote === 'approve' ? 'selected' : ''}"
                        onclick="castVote(${report.id}, 'approve')">
                    🚫 違規
                </button>
                <button class="vote-btn reject ${userVote === 'reject' ? 'selected' : ''}"
                        onclick="castVote(${report.id}, 'reject')">
                    ✅ 不違規
                </button>
            </div>
        </div>
    `}).join('');
}

async function castVote(reportId, voteType) {
    try {
        const response = await fetch(`${API_BASE}/api/governance/reports/${reportId}/vote`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ vote_type: voteType })
        });

        if (response.ok) {
            const vote = await response.json();
            state.votes[reportId] = voteType;

            // Update UI
            const card = document.querySelector(`.review-card[data-report-id="${reportId}"]`);
            if (card) {
                card.querySelectorAll('.vote-btn').forEach(btn => btn.classList.remove('selected'));
                card.querySelector(`.vote-btn.${voteType}`).classList.add('selected');
                card.classList.add('voted');
            }

            showToast('投票成功！', 'success');

            // Reload queue after a delay to show consensus updates
            setTimeout(() => loadReviewQueue(), 1000);

        } else {
            const error = await response.json();
            showToast(error.detail || '投票失敗', 'error');
        }
    } catch (error) {
        console.error('Failed to cast vote:', error);
        showToast('投票失敗', 'error');
    }
}

// ========================
// My Points
// ========================

async function loadMyPoints() {
    try {
        const [pointsRes, violationsRes] = await Promise.all([
            fetch(`${API_BASE}/api/governance/my-points`, {
                headers: getAuthHeaders()
            }),
            fetch(`${API_BASE}/api/governance/my-violations`, {
                headers: getAuthHeaders()
            })
        ]);

        if (pointsRes.ok) {
            const points = await pointsRes.json();
            renderPointsOverview(points);
        }

        if (violationsRes.ok) {
            const violations = await violationsRes.json();
            renderViolationsList(violations);
        }
    } catch (error) {
        console.error('Failed to load points:', error);
    }
}

function renderPointsOverview(points) {
    document.getElementById('current-points').textContent = points.points;

    const card = document.querySelector('.points-card');
    const statusEl = document.getElementById('points-status');

    card.classList.remove('status-ok', 'status-warning', 'status-danger');

    if (points.points >= 20) {
        card.classList.add('status-danger');
        statusEl.textContent = points.action_required || '危險';
    } else if (points.points >= 10) {
        card.classList.add('status-warning');
        statusEl.textContent = points.action_required || '警告';
    } else {
        card.classList.add('status-ok');
        statusEl.textContent = '狀態良好';
    }
}

function renderViolationsList(violations) {
    const container = document.getElementById('violations-list');

    if (violations.length === 0) {
        container.innerHTML = '<p class="empty-state">🎉 沒有違規記錄</p>';
        return;
    }

    container.innerHTML = `<div class="violations-list">` + violations.map(v => `
        <div class="violation-item">
            <div>
                <span class="violation-level ${v.violation_level}">${formatViolationLevel(v.violation_level)}</span>
                <span>${formatViolationType(v.violation_type)}</span>
            </div>
            <div>
                <span class="violation-points">+${v.points}點</span>
                <span class="violation-time">${formatTime(v.created_at)}</span>
            </div>
        </div>
    `).join('') + '</div>';
}

// ========================
// Activity Logs
// ========================

async function loadActivityLogs() {
    const container = document.getElementById('activity-logs-list');
    const typeFilter = document.getElementById('activity-type-filter')?.value;

    container.innerHTML = '<p class="loading">載入中...</p>';

    try {
        let url = `${API_BASE}/api/governance/my-logs`;
        if (typeFilter) {
            url += `?activity_type=${typeFilter}`;
        }

        const response = await fetch(url, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const logs = await response.json();
            renderActivityLogs(logs);
        }
    } catch (error) {
        console.error('Failed to load activity logs:', error);
    }
}

async function loadActivityStats() {
    try {
        const response = await fetch(`${API_BASE}/api/governance/my-activity-stats`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const stats = await response.json();
            document.getElementById('stat-posts').textContent = stats.posts_created;
            document.getElementById('stat-comments').textContent = stats.comments_created;
            document.getElementById('stat-reports').textContent = stats.reports_submitted;
            document.getElementById('stat-reviews').textContent = stats.reviews_completed;
        }
    } catch (error) {
        console.error('Failed to load activity stats:', error);
    }
}

function renderActivityLogs(logs) {
    const container = document.getElementById('activity-logs-list');

    if (logs.length === 0) {
        container.innerHTML = '<p class="empty-state">暫無活動記錄</p>';
        return;
    }

    container.innerHTML = logs.map(log => `
        <div class="log-item activity-type-${log.activity_type}">
            <div class="log-time">${formatTime(log.created_at)}</div>
            <div class="log-content">${formatActivityMessage(log)}</div>
        </div>
    `).join('');
}

// ========================
// Report Modal
// ========================

function openReportModal(contentType = null, contentId = null) {
    const modal = document.getElementById('report-modal');

    // Reset form
    document.getElementById('report-form').reset();
    document.getElementById('desc-count').textContent = '0';

    if (contentType && contentId) {
        document.getElementById('report-content-type').value = contentType;
        document.getElementById('report-content-id').value = contentId;
    }

    modal.classList.add('active');
}

function closeReportModal() {
    document.getElementById('report-modal').classList.remove('active');
}

async function submitReport(e) {
    e.preventDefault();

    const form = e.target;
    const data = {
        content_type: form.content_type.value,
        content_id: parseInt(form.content_id.value),
        report_type: form.report_type.value,
        description: form.description.value
    };

    try {
        const response = await fetch(`${API_BASE}/api/governance/reports`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            showToast('檢舉提交成功！', 'success');
            closeReportModal();

            // Reload if on reports tab
            if (state.currentTab === 'my-reports') {
                loadMyReports();
            }
        } else {
            const error = await response.json();
            showToast(error.detail || '提交失敗', 'error');
        }
    } catch (error) {
        console.error('Failed to submit report:', error);
        showToast('提交失敗', 'error');
    }
}

// ========================
// Helpers
// ========================

function getAuthHeaders() {
    // Get token from localStorage or cookie
    const token = localStorage.getItem('auth_token') || getCookie('auth_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function formatTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    // Less than 1 minute
    if (diff < 60000) {
        return '剛剛';
    }

    // Less than 1 hour
    if (diff < 3600000) {
        return `${Math.floor(diff / 60000)} 分鐘前`;
    }

    // Less than 1 day
    if (diff < 86400000) {
        return `${Math.floor(diff / 3600000)} 小時前`;
    }

    // Less than 1 week
    if (diff < 604800000) {
        return `${Math.floor(diff / 86400000)} 天前`;
    }

    // Format date
    return date.toLocaleDateString('zh-TW');
}

function formatReportType(type) {
    const types = {
        'spam': '📢 垃圾內容',
        'harassment': '😠 騷擾攻擊',
        'misinformation': '📰 錯誤資訊',
        'scam': '🎭 詐騙行為',
        'illegal': '⚠️ 非法內容',
        'other': '📋 其他'
    };
    return types[type] || type;
}

function formatStatus(status) {
    const statuses = {
        'pending': '待審核',
        'approved': '已通過',
        'rejected': '已駁回'
    };
    return statuses[status] || status;
}

function formatViolationLevel(level) {
    const levels = {
        'mild': '輕微',
        'medium': '中等',
        'severe': '嚴重',
        'critical': '極嚴重'
    };
    return levels[level] || level;
}

function formatViolationType(type) {
    return formatReportType(type).replace(/[^\u4e00-\u9fa5]/g, '').trim();
}

function formatActivityMessage(log) {
    const messages = {
        'post_created': '發表了一篇文章',
        'comment_created': '發表了一則留言',
        'report_submitted': '提交了內容檢舉',
        'vote_cast': '參與了審核投票',
        'violation_recorded': '收到違規記錄',
        'suspension_applied': '帳號被停權'
    };

    return messages[log.activity_type] || log.activity_type;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const messageEl = toast.querySelector('.toast-message');

    toast.className = `toast ${type}`;
    messageEl.textContent = message;

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// Global function for onclick handlers
window.castVote = castVote;
```

**Step 4: Test the dashboard**

Run: Open `web/governance/index.html` in a browser (or serve via the API server)

Expected: Dashboard renders without JavaScript errors

**Step 5: Commit**

```bash
git add web/governance/
git commit -m "feat(governance): add frontend dashboard"
```

---

## Task 6: Integration - Report Buttons on Forum

**Files:**
- Modify: `web/forum/post.html` (add report button)
- Modify: `web/forum/js/forum.js` (add report integration)

**Step 1: Add report button to post detail page**

Edit `web/forum/post.html` to add report buttons (find the action button section):

```html
<!-- Add this after the like/tip buttons -->
<div class="post-actions">
    <!-- existing buttons... -->

    <button class="btn-report" onclick="openReportModal('post', {{post.id}})">
        🚨 檢舉
    </button>
</div>

<!-- Add similar for comments -->
```

**Step 2: Add report modal to forum pages**

Add the report modal to forum pages that don't have governance dashboard access.

**Step 3: Integrate report function**

Edit `web/forum/js/forum.js` to add report integration:

```javascript
// Add this function
function openReportModal(contentType, contentId) {
    // Check if user is logged in
    if (!getCurrentUser()) {
        showToast('請先登入', 'error');
        return;
    }

    // If governance dashboard exists, redirect there
    // Otherwise, open inline modal
    window.location.href = `/governance/?report=${contentType}:${contentId}`;
}
```

**Step 4: Test report flow**

Run: Navigate to a forum post, click report button

Expected: Redirects to governance dashboard with pre-filled report

**Step 5: Commit**

```bash
git add web/forum/post.html web/forum/js/forum.js
git commit -m "feat(governance): add report buttons to forum"
```

---

## Task 7: Rate Limiting and Security

**Files:**
- Create: `api/routers/governance.py` (add rate limiting)
- Modify: as needed

**Step 1: Add rate limiting to report submission**

The `check_daily_report_limit` function already exists in the database layer. Verify it's being called correctly in the API.

**Step 2: Add IP-based rate limiting for voting**

Add a check in the vote endpoint:

```python
# In governance.py, add this helper
from datetime import datetime, timedelta

async def check_vote_rate_limit(db, user_id: str, limit: int = 30, window_minutes: int = 60):
    """Check if user has exceeded vote rate limit"""
    cursor = db.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM report_review_votes
        WHERE reviewer_user_id = %s
          AND created_at > NOW() - INTERVAL '%s minutes'
    """, [user_id, window_minutes])

    count = cursor.fetchone()[0]
    return count < limit


# Use in vote endpoint
if not await check_vote_rate_limit(db, current_user["user_id"]):
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Vote rate limit exceeded (30 votes per hour)"
    )
```

**Step 3: Add request validation**

Ensure all request inputs are properly validated using Pydantic models (already done).

**Step 4: Test security measures**

Run: Try to submit 11 reports in a day, try to vote more than 30 times in an hour

Expected: Rate limit errors returned

**Step 5: Commit**

```bash
git add api/routers/governance.py
git commit -m "feat(governance): add rate limiting and security measures"
```

---

## Task 8: Background Job - Points Decrement

**Files:**
- Create: `scripts/governance_jobs.py` or integrate into existing job system

**Step 1: Create background job script**

Create `scripts/governance_jobs.py`:

```python
"""
Background jobs for governance system

Run daily to:
- Decrement violation points for users with no recent violations
- Clean up old activity logs
"""

import logging
from core.database.connection import get_db

logger = logging.getLogger(__name__)


def run_daily_maintenance():
    """Run daily maintenance tasks"""
    logger.info("Starting daily governance maintenance...")

    with next(get_db()) as db:
        # Decrement points
        from core.database.governance import decrement_violation_points

        results = decrement_violation_points()
        logger.info(f"Decremented points for {len(list(results))} users")

        # Clean up old logs (older than 90 days)
        cursor = db.cursor()
        cursor.execute("""
            DELETE FROM user_activity_logs
            WHERE created_at < NOW() - INTERVAL '90 days'
        """)
        deleted = cursor.rowcount
        db.commit()
        logger.info(f"Deleted {deleted} old activity logs")

    logger.info("Daily governance maintenance completed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_daily_maintenance()
```

**Step 2: Set up cron job or scheduled task**

Add to crontab or task scheduler:

```
# Run daily at 2 AM
0 2 * * * cd /path/to/stock_agent && python scripts/governance_jobs.py
```

**Step 3: Test the maintenance script**

Run: `python scripts/governance_jobs.py`

Expected: Logs show maintenance completed

**Step 4: Commit**

```bash
git add scripts/governance_jobs.py
git commit -m "feat(governance): add daily maintenance background job"
```

---

## Task 9: Documentation

**Files:**
- Create: `docs/governance.md` (user-facing documentation)
- Update: `README.md` (if needed)

**Step 1: Create user documentation**

Create `docs/governance.md`:

```markdown
# 社群治理系統使用指南

## 概述

社群治理系統是一個去中心化的自我管理機制，讓 PRO 用戶作為審核節點共同維護社群健康。

## 功能

### 1. 檢舉內容

任何登入用戶都可以檢舉不當內容：

- 每天最多 10 次檢舉
- 同一內容只能檢舉一次
- 檢舉類型：垃圾內容、騷擾攻擊、錯誤資訊、詐騙行為、非法內容、其他

### 2. PRO 審核

PRO 用戶可以參與內容審核：

- 最低 3 位 PRO 用戶投票
- 70% 以上投「違規」即判定違規
- 30% 以下投「違規」即判定不違規
- 審核可累積聲望值

### 3. 違規處罰

累積違規點數會導致處罰：

| 點數 | 處罰 |
|------|------|
| 5點 | 警告 |
| 10點 | 停權3天 |
| 20點 | 停權7天 |
| 30點 | 停權30天 |
| 40點 | 永久停權 |

PRO 用戶享有較優惠的處罰標準。

### 4. 活動日誌

所有用戶可以查看自己的活動記錄，包括發文、留言、檢舉、審核等操作。

## 使用方式

### 檢舉內容

1. 在文章或留言旁點擊「🚨 檢舉」按鈕
2. 選擇檢舉類型
3. 填寫說明（選填）
4. 提交檢舉

### 參與審核（PRO）

1. 前往「社群治理中心」
2. 點擊「審核隊列」
3. 查看待審核案件
4. 投票「違規」或「不違規」

### 查看違規記錄

1. 前往「社群治理中心」
2. 點擊「違規記錄」
3. 查看當前點數和違規歷史

## 透明監督

所有審核記錄公開透明，任何人都可以查核：
- 檢舉狀態
- 投票結果
- 處理決定
- 審核員統計

前往治理中心查看統計數據。
```

**Step 2: Update README if needed**

**Step 3: Commit**

```bash
git add docs/governance.md
git commit -m "docs(governance): add user documentation"
```

---

## Task 10: Final Testing and Review

**Step 1: Run all tests**

Run: `pytest tests/test_governance*.py -v --cov=core.database.governance --cov=api.routers.governance`

Expected: All tests pass with good coverage

**Step 2: Manual testing checklist**

- [ ] Can create a report
- [ ] Cannot report same content twice
- [ ] Daily report limit enforced
- [ ] PRO users can access review queue
- [ ] Non-PRO users cannot access review queue
- [ ] Can vote on reports
- [ ] Consensus triggers auto-finalization
- [ ] Points are added correctly
- [ ] Suspension actions work
- [ ] Activity logs are recorded
- [ ] Dashboard displays correctly

**Step 3: Load testing**

Test with multiple concurrent users voting.

**Step 4: Security review**

Check for:
- SQL injection vulnerabilities
- XSS vulnerabilities
- Authorization bypasses
- Rate limit bypasses

**Step 5: Final commit**

```bash
git add .
git commit -m "feat(governance): complete implementation with testing and documentation"
```

---

## Success Criteria

- ✅ All database tables created
- ✅ All API endpoints functional
- ✅ Frontend dashboard working
- ✅ Report flow working (create → vote → finalize)
- ✅ Violation points system working
- ✅ Activity logging working
- ✅ Rate limiting enforced
- ✅ Tests passing with >80% coverage
- ✅ Documentation complete

---

**Total Estimated Time**: 5-7 days

**Next Steps After Implementation**:
1. Deploy to staging environment
2. Conduct beta testing with select users
3. Gather feedback and iterate
4. Deploy to production
