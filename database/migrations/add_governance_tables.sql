-- ================================================================
-- Community Governance System Database Schema
-- 创建时间: 2026-02-07
-- 用途: 社区治理系统 - 违规点数追踪、内容举报和PRO审核员声望系统
-- ================================================================

-- ================================================================
-- 1. 用户违规点数表 (user_violation_points)
-- 用途: 追踪每个用户的当前违规点数和状态
-- ================================================================

CREATE TABLE IF NOT EXISTS user_violation_points (
    -- 主键 - 用户ID
    user_id TEXT PRIMARY KEY,

    -- 违规点数（默认0）
    points INTEGER DEFAULT 0 NOT NULL,

    -- 最后违规时间（用于判断是否可以递减点数）
    last_violation_at TIMESTAMP WITH TIME ZONE,

    -- 最后递减点数的时间（防止频繁递减）
    last_decrement_at TIMESTAMP WITH TIME ZONE,

    -- 总违规次数（累计）
    total_violations INTEGER DEFAULT 0 NOT NULL,

    -- 累计被暂停次数
    suspension_count INTEGER DEFAULT 0 NOT NULL,

    -- 更新时间
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 外键约束
    CONSTRAINT fk_violation_points_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    -- 约束：点数不能为负
    CONSTRAINT chk_violation_points_non_negative
        CHECK (points >= 0),

    -- 约束：违规次数不能为负
    CONSTRAINT chk_total_violations_non_negative
        CHECK (total_violations >= 0),

    -- 约束：暂停次数不能为负
    CONSTRAINT chk_suspension_count_non_negative
        CHECK (suspension_count >= 0)
);

-- 索引：按点数降序查询（用于查找高违规用户）
CREATE INDEX IF NOT EXISTS idx_violation_points
    ON user_violation_points(points DESC);

-- 索引：按最后违规时间查询（用于点数递减检查）
CREATE INDEX IF NOT EXISTS idx_violation_last_violation
    ON user_violation_points(last_violation_at DESC)
    WHERE last_violation_at IS NOT NULL;

-- ================================================================
-- 2. 用户违规记录表 (user_violations)
-- 用途: 记录每次违规的详细信息
-- ================================================================

CREATE TABLE IF NOT EXISTS user_violations (
    -- 主键
    id SERIAL PRIMARY KEY,

    -- 用户ID
    user_id TEXT NOT NULL,

    -- 违规等级：mild(轻微), medium(中等), severe(严重), critical(极其严重)
    violation_level TEXT NOT NULL
        CHECK (violation_level IN ('mild', 'medium', 'severe', 'critical')),

    -- 违规类型（如：spam, harassment, misinformation, scam, illegal等）
    violation_type TEXT NOT NULL,

    -- 扣除的违规点数
    points INTEGER DEFAULT 0 NOT NULL
        CHECK (points >= 0),

    -- 来源类型：report(举报), admin_action(管理员操作)
    source_type TEXT NOT NULL
        CHECK (source_type IN ('report', 'admin_action')),

    -- 来源ID（举报ID或管理员操作记录ID）
    source_id INTEGER,

    -- 采取的措施：warning, suspend_3d, suspend_7d, suspend_30d, suspend_permanent, none
    action_taken TEXT
        CHECK (action_taken IN ('warning', 'suspend_3d', 'suspend_7d', 'suspend_30d', 'suspend_permanent', 'none', 'decrease_points')),

    -- 暂停结束时间
    suspended_until TIMESTAMP WITH TIME ZONE,

    -- 处理人
    processed_by TEXT,

    -- 创建时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 外键约束
    CONSTRAINT fk_violations_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- 索引：按用户和时间查询违规记录
CREATE INDEX IF NOT EXISTS idx_violations_user
    ON user_violations(user_id, created_at DESC);

-- 索引：按违规等级查询
CREATE INDEX IF NOT EXISTS idx_violations_level
    ON user_violations(violation_level);

-- 索引：按违规类型查询
CREATE INDEX IF NOT EXISTS idx_violations_type
    ON user_violations(violation_type);

-- 索引：查询当前暂停的用户
CREATE INDEX IF NOT EXISTS idx_violations_suspended
    ON user_violations(user_id, suspended_until DESC)
    WHERE suspended_until IS NOT NULL AND suspended_until > NOW();

-- ================================================================
-- 3. 内容举报表 (content_reports)
-- 用途: 用户提交的帖子或评论举报
-- ================================================================

CREATE TABLE IF NOT EXISTS content_reports (
    -- 主键
    id SERIAL PRIMARY KEY,

    -- 被举报内容类型：post(帖子), comment(评论)
    content_type TEXT NOT NULL
        CHECK (content_type IN ('post', 'comment')),

    -- 被举报内容ID
    content_id INTEGER NOT NULL,

    -- 举报人用户ID
    reporter_user_id TEXT NOT NULL,

    -- 举报类型：spam(垃圾信息), harassment(骚扰), misinformation(虚假信息), scam(诈骗), illegal(违法), other(其他)
    report_type TEXT NOT NULL
        CHECK (report_type IN ('spam', 'harassment', 'misinformation', 'scam', 'illegal', 'other')),

    -- 举报描述
    description TEXT,

    -- 审核状态：pending(待审核), approved(通过), rejected(拒绝)
    review_status TEXT DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected')),

    -- 违规等级（审核后填写）
    violation_level TEXT
        CHECK (violation_level IN ('mild', 'medium', 'severe', 'critical')),

    -- 采取的措施
    action_taken TEXT,

    -- 分配的违规点数
    points_assigned INTEGER DEFAULT 0 NOT NULL
        CHECK (points_assigned >= 0),

    -- 处理人
    processed_by TEXT,

    -- 支持票数（PRO审核员投"通过"的数量）
    approve_count INTEGER DEFAULT 0 NOT NULL
        CHECK (approve_count >= 0),

    -- 反对票数（PRO审核员投"拒绝"的数量）
    reject_count INTEGER DEFAULT 0 NOT NULL
        CHECK (reject_count >= 0),

    -- 创建时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 更新时间
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 外键约束
    CONSTRAINT fk_report_reporter
        FOREIGN KEY (reporter_user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    -- 唯一约束：同一用户对同一内容只能举报一次
    CONSTRAINT uq_reporter_content
        UNIQUE (reporter_user_id, content_type, content_id),

    -- 约束：票数和状态一致性检查
    CONSTRAINT chk_report_vote_consistency
        CHECK (
            (review_status = 'pending' AND approve_count = 0 AND reject_count = 0) OR
            (review_status IN ('approved', 'rejected'))
        )
);

-- 索引：按被举报内容查询
CREATE INDEX IF NOT EXISTS idx_report_content
    ON content_reports(content_type, content_id);

-- 索引：按审核状态查询
CREATE INDEX IF NOT EXISTS idx_report_status
    ON content_reports(review_status, created_at DESC);

-- 索引：按创建时间查询
CREATE INDEX IF NOT EXISTS idx_report_created
    ON content_reports(created_at DESC);

-- 索引：按举报类型查询
CREATE INDEX IF NOT EXISTS idx_report_type
    ON content_reports(report_type);

-- ================================================================
-- 4. 举报审核投票表 (report_review_votes)
-- 用途: PRO用户对举报进行审核投票
-- ================================================================

CREATE TABLE IF NOT EXISTS report_review_votes (
    -- 主键
    id SERIAL PRIMARY KEY,

    -- 举报ID
    report_id INTEGER NOT NULL,

    -- 审核人用户ID（必须是PRO用户）
    reviewer_user_id TEXT NOT NULL,

    -- 投票类型：approve(认为违规，支持举报), reject(认为不违规，拒绝举报)
    vote_type TEXT NOT NULL
        CHECK (vote_type IN ('approve', 'reject')),

    -- 投票权重（可能因审核员声望而不同）
    vote_weight FLOAT DEFAULT 1.0 NOT NULL
        CHECK (vote_weight > 0),

    -- 投票时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 外键约束
    CONSTRAINT fk_review_report
        FOREIGN KEY (report_id)
        REFERENCES content_reports(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_review_reviewer
        FOREIGN KEY (reviewer_user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    -- 唯一约束：同一审核员对同一举报只能投票一次
    CONSTRAINT uq_reviewer_report
        UNIQUE (report_id, reviewer_user_id)
);

-- 索引：按举报ID查询投票
CREATE INDEX IF NOT EXISTS idx_review_report
    ON report_review_votes(report_id, vote_type);

-- 索引：按审核人查询投票记录
CREATE INDEX IF NOT EXISTS idx_review_user
    ON report_review_votes(reviewer_user_id, created_at DESC);

-- ================================================================
-- 5. 用户活动日志表 (user_activity_logs)
-- 用途: 记录用户活动，用于透明度和信任度评估
-- ================================================================

CREATE TABLE IF NOT EXISTS user_activity_logs (
    -- 主键
    id SERIAL PRIMARY KEY,

    -- 用户ID
    user_id TEXT NOT NULL,

    -- 活动类型
    -- post_created: 创建帖子
    -- comment_created: 创建评论
    -- post_liked: 点赞帖子
    -- comment_liked: 点赞评论
    -- report_submitted: 提交举报
    -- review_vote: 投票审核
    -- violation_received: 收到违规
    -- points_decremented: 点数递减
    -- etc.
    activity_type TEXT NOT NULL,

    -- 资源类型：post, comment, user, report等
    resource_type TEXT,

    -- 资源ID
    resource_id INTEGER,

    -- 元数据（灵活存储，JSONB格式）
    metadata JSONB,

    -- 是否成功
    success BOOLEAN DEFAULT TRUE,

    -- 错误信息
    error_message TEXT,

    -- IP地址
    ip_address TEXT,

    -- 用户代理
    user_agent TEXT,

    -- 创建时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 外键约束
    CONSTRAINT fk_activity_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- 索引：按用户和时间查询活动
CREATE INDEX IF NOT EXISTS idx_user_activity
    ON user_activity_logs(user_id, created_at DESC);

-- 索引：按活动类型查询
CREATE INDEX IF NOT EXISTS idx_activity_type
    ON user_activity_logs(activity_type, created_at DESC);

-- 索引：按资源和活动类型查询
CREATE INDEX IF NOT EXISTS idx_activity_resource
    ON user_activity_logs(resource_type, resource_id, created_at DESC)
    WHERE resource_type IS NOT NULL;

-- 索引：查询失败的活动
CREATE INDEX IF NOT EXISTS idx_activity_failures
    ON user_activity_logs(user_id, created_at DESC)
    WHERE success = FALSE;

-- ================================================================
-- 6. 审核员声望表 (audit_reputation)
-- 用途: 追踪PRO审核员的准确率和声望
-- ================================================================

CREATE TABLE IF NOT EXISTS audit_reputation (
    -- 主键 - 用户ID
    user_id TEXT PRIMARY KEY,

    -- 总审核次数
    total_reviews INTEGER DEFAULT 0 NOT NULL
        CHECK (total_reviews >= 0),

    -- 正确投票次数（与最终决定一致）
    correct_votes INTEGER DEFAULT 0 NOT NULL
        CHECK (correct_votes >= 0),

    -- 准确率（正确投票/总投票）
    accuracy_rate FLOAT DEFAULT 1.0 NOT NULL
        CHECK (accuracy_rate >= 0 AND accuracy_rate <= 1),

    -- 声望分数（用于确定投票权重）
    reputation_score INTEGER DEFAULT 0 NOT NULL
        CHECK (reputation_score >= 0),

    -- 更新时间
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 外键约束
    CONSTRAINT fk_audit_reputation_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    -- 约束：正确投票数不能超过总审核数
    CONSTRAINT chk_correct_votes_consistency
        CHECK (correct_votes <= total_reviews)
);

-- 索引：按声望分数降序查询（用于找最佳审核员）
CREATE INDEX IF NOT EXISTS idx_audit_reputation
    ON audit_reputation(reputation_score DESC);

-- 索引：按准确率查询
CREATE INDEX IF NOT EXISTS idx_audit_accuracy
    ON audit_reputation(accuracy_rate DESC);

-- ================================================================
-- 函数：递减违规点数 (decrement_violation_points)
-- 用途: 对30天内有违规且上次递减超过30天的用户，每日自动递减1点
-- 返回: 受影响的用户列表和递减的点数
-- ================================================================

CREATE OR REPLACE FUNCTION decrement_violation_points()
RETURNS TABLE (
    user_id TEXT,
    points_deducted INTEGER
) AS $$
DECLARE
    -- 游标：遍历需要递减点数的用户
    user_record RECORD;
    points_before INTEGER;
BEGIN
    -- 遍历所有有点数的用户
    FOR user_record IN
        SELECT user_id, points
        FROM user_violation_points
        WHERE points > 0
          AND (
            -- 从未递减过，且最后违规时间超过30天
            (last_decrement_at IS NULL AND last_violation_at < NOW() - INTERVAL '30 days')
            OR
            -- 上次递减超过30天，且最后违规也超过30天
            (last_decrement_at < NOW() - INTERVAL '30 days' AND last_violation_at < NOW() - INTERVAL '30 days')
          )
        ORDER BY points DESC
    LOOP
        -- 记录递减前的点数
        points_before := user_record.points;

        -- 更新用户点数（最多减到0）
        UPDATE user_violation_points
        SET
            points = GREATEST(0, points - 1),
            last_decrement_at = NOW(),
            updated_at = NOW()
        WHERE user_id = user_record.user_id;

        -- 返回结果
        RETURN QUERY
        SELECT
            user_record.user_id,
            GREATEST(0, points_before) - GREATEST(0, points_before - 1) AS points_deducted;
    END LOOP;

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- 触发器：自动更新 updated_at 时间戳
-- ================================================================

-- user_violation_points 表的 updated_at 自动更新
CREATE OR REPLACE FUNCTION update_user_violation_points_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_violation_points_updated_at
    BEFORE UPDATE ON user_violation_points
    FOR EACH ROW
    EXECUTE FUNCTION update_user_violation_points_updated_at();

-- audit_reputation 表的 updated_at 自动更新
CREATE OR REPLACE FUNCTION update_audit_reputation_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_reputation_updated_at
    BEFORE UPDATE ON audit_reputation
    FOR EACH ROW
    EXECUTE FUNCTION update_audit_reputation_updated_at();

-- ================================================================
-- 注释和文档
-- ================================================================

COMMENT ON TABLE user_violation_points IS '用户违规点数追踪表，记录当前点数、违规次数和暂停次数';
COMMENT ON COLUMN user_violation_points.points IS '当前违规点数，达到阈值将触发暂停';
COMMENT ON COLUMN user_violation_points.last_violation_at IS '最后违规时间，用于判断是否可以递减点数';
COMMENT ON COLUMN user_violation_points.last_decrement_at IS '最后递减点数时间，防止频繁递减';
COMMENT ON COLUMN user_violation_points.total_violations IS '总违规次数（累计）';
COMMENT ON COLUMN user_violation_points.suspension_count IS '累计被暂停次数';

COMMENT ON TABLE user_violations IS '用户违规记录表，记录每次违规的详细信息';
COMMENT ON COLUMN user_violations.violation_level IS '违规等级：mild(轻微), medium(中等), severe(严重), critical(极其严重)';
COMMENT ON COLUMN user_violations.action_taken IS '采取的措施：warning, suspend_3d, suspend_7d, suspend_30d, suspend_permanent, none';
COMMENT ON COLUMN user_violations.source_type IS '来源类型：report(举报), admin_action(管理员操作)';

COMMENT ON TABLE content_reports IS '内容举报表，用户提交的帖子或评论举报';
COMMENT ON COLUMN content_reports.report_type IS '举报类型：spam(垃圾信息), harassment(骚扰), misinformation(虚假信息), scam(诈骗), illegal(违法), other(其他)';
COMMENT ON COLUMN content_reports.review_status IS '审核状态：pending(待审核), approved(通过), rejected(拒绝)';
COMMENT ON COLUMN content_reports.approve_count IS 'PRO审核员投"通过"的数量';
COMMENT ON COLUMN content_reports.reject_count IS 'PRO审核员投"拒绝"的数量';

COMMENT ON TABLE report_review_votes IS '举报审核投票表，PRO用户对举报进行审核投票';
COMMENT ON COLUMN report_review_votes.vote_type IS '投票类型：approve(认为违规，支持举报), reject(认为不违规，拒绝举报)';
COMMENT ON COLUMN report_review_votes.vote_weight IS '投票权重，可能因审核员声望而不同';

COMMENT ON TABLE user_activity_logs IS '用户活动日志表，记录用户活动，用于透明度和信任度评估';
COMMENT ON COLUMN user_activity_logs.activity_type IS '活动类型：post_created, comment_created, post_liked, comment_liked, report_submitted, review_vote等';
COMMENT ON COLUMN user_activity_logs.metadata IS '元数据（灵活存储，JSONB格式）';

COMMENT ON TABLE audit_reputation IS '审核员声望表，追踪PRO审核员的准确率和声望';
COMMENT ON COLUMN audit_reputation.total_reviews IS '总审核次数';
COMMENT ON COLUMN audit_reputation.correct_votes IS '正确投票次数（与最终决定一致）';
COMMENT ON COLUMN audit_reputation.accuracy_rate IS '准确率（正确投票/总投票）';
COMMENT ON COLUMN audit_reputation.reputation_score IS '声望分数，用于确定投票权重';

COMMENT ON FUNCTION decrement_violation_points IS '递减违规点数函数，对30天内有违规且上次递减超过30天的用户，每日自动递减1点';

-- ================================================================
-- 使用示例
-- ================================================================

/*
-- 1. 创建用户违规记录
INSERT INTO user_violations (user_id, violation_level, violation_type, points, source_type, action_taken)
VALUES ('user123', 'medium', 'spam', 3, 'report', 'warning');

-- 2. 更新用户违规点数
INSERT INTO user_violation_points (user_id, points, total_violations, last_violation_at)
VALUES ('user123', 3, 1, NOW())
ON CONFLICT (user_id) DO UPDATE SET
    points = user_violation_points.points + EXCLUDED.points,
    total_violations = user_violation_points.total_violations + 1,
    last_violation_at = EXCLUDED.last_violation_at;

-- 3. 创建内容举报
INSERT INTO content_reports (content_type, content_id, reporter_user_id, report_type, description)
VALUES ('post', 456, 'user789', 'spam', 'This post contains spam content');

-- 4. PRO用户对举报进行投票
INSERT INTO report_review_votes (report_id, reviewer_user_id, vote_type, vote_weight)
VALUES (1, 'pro_user123', 'approve', 1.0);

-- 5. 记录用户活动
INSERT INTO user_activity_logs (user_id, activity_type, resource_type, resource_id, metadata)
VALUES ('user123', 'report_submitted', 'report', 1, '{"content_type": "post", "content_id": 456}'::jsonb);

-- 6. 递减违规点数（每日定时任务）
SELECT * FROM decrement_violation_points();

-- 7. 查询当前暂停的用户
SELECT u.user_id, u.username, vp.points, uv.suspended_until
FROM user_violation_points vp
JOIN users u ON u.user_id = vp.user_id
JOIN user_violations uv ON uv.user_id = vp.user_id
WHERE uv.suspended_until > NOW()
ORDER BY uv.suspended_until DESC;

-- 8. 查询待审核的举报
SELECT cr.*, u.username as reporter_name
FROM content_reports cr
JOIN users u ON u.user_id = cr.reporter_user_id
WHERE cr.review_status = 'pending'
ORDER BY cr.created_at ASC;

-- 9. 查询高准确率的审核员
SELECT u.user_id, u.username, ar.total_reviews, ar.correct_votes, ar.accuracy_rate, ar.reputation_score
FROM audit_reputation ar
JOIN users u ON u.user_id = ar.user_id
WHERE ar.total_reviews >= 10
ORDER BY ar.accuracy_rate DESC, ar.total_reviews DESC
LIMIT 50;
*/
