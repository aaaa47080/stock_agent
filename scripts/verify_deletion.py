#!/usr/bin/env python3
"""
驗證用戶文章是否已完全刪除
用法: python verify_deletion.py <username>
"""
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_connection


def verify_deletion(username: str):
    """
    驗證用戶的所有文章是否已刪除
    
    Args:
        username: 用戶名
    """
    conn = get_connection()
    c = conn.cursor()
    
    try:
        # 查找用戶
        c.execute('SELECT user_id, username FROM users WHERE username = %s', (username,))
        user = c.fetchone()
        
        if not user:
            print(f"❌ 錯誤：找不到用戶 '{username}'")
            return
        
        user_id, username = user
        print(f"\n{'='*60}")
        print(f"🔍 驗證用戶: {username} (ID: {user_id})")
        print(f"{'='*60}\n")
        
        # 檢查文章
        c.execute('SELECT COUNT(*) FROM posts WHERE user_id = %s', (user_id,))
        post_count = c.fetchone()[0]
        
        # 檢查回覆（作為作者的回覆）
        c.execute('SELECT COUNT(*) FROM forum_comments WHERE user_id = %s', (user_id,))
        comment_count = c.fetchone()[0]
        
        # 檢查是否有孤立的回覆（文章已刪除但回覆還在）
        c.execute('''
            SELECT COUNT(*) FROM forum_comments fc
            WHERE fc.post_id IN (
                SELECT p.id FROM posts p WHERE p.user_id = %s
            )
        ''', (user_id,))
        orphaned_comments = c.fetchone()[0]
        
        # 檢查打賞記錄
        c.execute('''
            SELECT COUNT(*) FROM tips
            WHERE post_id IN (
                SELECT p.id FROM posts p WHERE p.user_id = %s
            )
        ''', (user_id,))
        orphaned_tips = c.fetchone()[0]
        
        # 檢查標籤關聯
        c.execute('''
            SELECT COUNT(*) FROM post_tags
            WHERE post_id IN (
                SELECT p.id FROM posts p WHERE p.user_id = %s
            )
        ''', (user_id,))
        orphaned_tags = c.fetchone()[0]
        
        print("📊 驗證結果:\n")
        print(f"   文章數量: {post_count}")
        print(f"   用戶回覆數: {comment_count} (用戶在其他文章的回覆，不應刪除)")
        print(f"   孤立回覆數: {orphaned_comments} (應為 0)")
        print(f"   孤立打賞記錄: {orphaned_tips} (應為 0)")
        print(f"   孤立標籤關聯: {orphaned_tags} (應為 0)")
        print()
        
        if post_count == 0 and orphaned_comments == 0 and orphaned_tips == 0 and orphaned_tags == 0:
            print("✅ 驗證通過：用戶 '{username}' 的所有文章及相關資料已完全刪除")
        else:
            print("⚠️  驗證失敗：仍有殘留資料")
            if post_count > 0:
                print(f"   - 還有 {post_count} 篇文章未刪除")
            if orphaned_comments > 0:
                print(f"   - 還有 {orphaned_comments} 條孤立回覆")
            if orphaned_tips > 0:
                print(f"   - 還有 {orphaned_tips} 條孤立打賞記錄")
            if orphaned_tags > 0:
                print(f"   - 還有 {orphaned_tags} 條孤立標籤關聯")
        
        print(f"\n{'='*60}\n")
        
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python verify_deletion.py <username>")
        print("\n範例:")
        print("  python verify_deletion.py \"翁\"")
        sys.exit(1)
    
    username = sys.argv[1]
    verify_deletion(username)
