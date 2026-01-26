"""
數據庫索引遷移腳本
執行此腳本以添加所有推薦的性能索引
"""
import sqlite3
from core.database.connection import get_connection

def add_performance_indexes():
    """添加所有性能優化索引"""
    conn = get_connection()
    c = conn.cursor()
    
    indexes = [
        # 文章相關索引
        ("idx_posts_board_created", "CREATE INDEX IF NOT EXISTS idx_posts_board_created ON posts(board_id, created_at DESC)"),
        ("idx_posts_user_created", "CREATE INDEX IF NOT EXISTS idx_posts_user_created ON posts(user_id, created_at DESC)"),
        ("idx_posts_category", "CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)"),
        ("idx_posts_hidden", "CREATE INDEX IF NOT EXISTS idx_posts_hidden ON posts(is_hidden)"),
        
        # 評論相關索引
        ("idx_comments_post_created", "CREATE INDEX IF NOT EXISTS idx_comments_post_created ON forum_comments(post_id, created_at ASC)"),
        ("idx_comments_user", "CREATE INDEX IF NOT EXISTS idx_comments_user ON forum_comments(user_id)"),
        ("idx_comments_type", "CREATE INDEX IF NOT EXISTS idx_comments_type ON forum_comments(type)"),
        
        # 每日限制相關索引
        ("idx_daily_posts_user_date", "CREATE INDEX IF NOT EXISTS idx_daily_posts_user_date ON user_daily_posts(user_id, date)"),
        ("idx_daily_comments_user_date", "CREATE INDEX IF NOT EXISTS idx_daily_comments_user_date ON user_daily_comments(user_id, date)"),
        
        # 支付相關索引（防重複 + 查詢優化）
        ("idx_membership_tx_hash", "CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_tx_hash ON membership_payments(tx_hash)"),
        ("idx_membership_user", "CREATE INDEX IF NOT EXISTS idx_membership_user ON membership_payments(user_id, created_at DESC)"),
        ("idx_posts_tx_hash", "CREATE INDEX IF NOT EXISTS idx_posts_tx_hash ON posts(payment_tx_hash)"),
        
        # 打賞相關索引
        ("idx_tips_from_user", "CREATE INDEX IF NOT EXISTS idx_tips_from_user ON tips(from_user_id, created_at DESC)"),
        ("idx_tips_to_user", "CREATE INDEX IF NOT EXISTS idx_tips_to_user ON tips(to_user_id, created_at DESC)"),
        ("idx_tips_post", "CREATE INDEX IF NOT EXISTS idx_tips_post ON tips(post_id)"),
        
        # 標籤相關索引
        ("idx_tags_name", "CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name ON tags(name)"),
        ("idx_tags_post_count", "CREATE INDEX IF NOT EXISTS idx_tags_post_count ON tags(post_count DESC, last_used_at DESC)"),
        ("idx_post_tags_post", "CREATE INDEX IF NOT EXISTS idx_post_tags_post ON post_tags(post_id)"),
        ("idx_post_tags_tag", "CREATE INDEX IF NOT EXISTS idx_post_tags_tag ON post_tags(tag_id)"),
        
        # 用戶相關索引
        ("idx_users_username", "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)"),
        ("idx_users_email", "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"),
        ("idx_users_pi_uid", "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_pi_uid ON users(pi_uid)"),
        ("idx_users_membership", "CREATE INDEX IF NOT EXISTS idx_users_membership ON users(membership_tier, membership_expires_at)"),
    ]
    
    try:
        print("開始添加數據庫索引...")
        for name, sql in indexes:
            try:
                c.execute(sql)
                print(f"✓ 成功創建索引: {name}")
            except Exception as e:
                print(f"✗ 創建索引失敗 {name}: {e}")
        
        conn.commit()
        print(f"\n總計: {len(indexes)} 個索引已處理")
        print("索引創建完成！")
        
    except Exception as e:
        print(f"錯誤: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    add_performance_indexes()
