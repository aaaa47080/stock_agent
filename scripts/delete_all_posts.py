#!/usr/bin/env python3
"""
刪除所有論壇文章的管理腳本
⚠️ 警告：此腳本會刪除所有論壇文章及相關資料！
用法: python delete_all_posts.py [--confirm]
"""
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_connection


def delete_all_posts(dry_run: bool = True):
    """
    刪除所有論壇文章及相關資料
    
    Args:
        dry_run: 是否為試運行模式（不實際刪除）
    """
    conn = get_connection()
    c = conn.cursor()
    
    try:
        # 1. 統計現有資料
        c.execute('SELECT COUNT(*) FROM posts')
        total_posts = c.fetchone()[0]
        
        if total_posts == 0:
            print("\nℹ️  資料庫中沒有任何文章")
            return
        
        c.execute('SELECT COUNT(*) FROM forum_comments')
        total_comments = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM tips')
        total_tips = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM post_tags')
        total_post_tags = c.fetchone()[0]
        
        # 顯示統計
        print(f"\n{'='*60}")
        print(f"📊 資料庫現有資料統計:")
        print(f"{'='*60}\n")
        print(f"   文章總數: {total_posts}")
        print(f"   回覆/推噓總數: {total_comments}")
        print(f"   打賞記錄: {total_tips}")
        print(f"   標籤關聯: {total_post_tags}")
        
        # 顯示部分文章樣本
        c.execute('''
            SELECT p.id, p.title, p.category, u.username, p.created_at
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC
            LIMIT 10
        ''')
        sample_posts = c.fetchall()
        
        print(f"\n{'='*60}")
        print(f"📝 文章樣本 (最近 {min(10, len(sample_posts))} 篇):")
        print(f"{'='*60}\n")
        
        for i, post in enumerate(sample_posts, 1):
            post_id, title, category, username, created_at = post
            print(f"{i}. [{category}] {title}")
            print(f"   ID: {post_id} | 作者: {username or '(未知)'} | 創建: {created_at}")
            print()
        
        print(f"{'='*60}\n")
        
        if dry_run:
            print("🔍 試運行模式：不會實際刪除資料")
            print("\n如要實際刪除所有文章，請執行:")
            print("   python scripts/delete_all_posts.py --confirm")
            print("\n⚠️  此操作不可逆！請確保已備份資料庫！")
            return
        
        # 確認刪除
        print("⚠️  ⚠️  ⚠️  嚴重警告  ⚠️  ⚠️  ⚠️")
        print("\n此操作將刪除:")
        print(f"   - 所有 {total_posts} 篇文章")
        print(f"   - 所有 {total_comments} 條回覆和推噓")
        print(f"   - 所有 {total_tips} 條打賞記錄")
        print(f"   - 所有 {total_post_tags} 條標籤關聯")
        print("\n⚠️  此操作不可逆！資料刪除後無法恢復！")
        print("⚠️  請確保已備份資料庫！\n")
        
        confirm1 = input("確定要刪除所有論壇文章嗎？ 輸入 'DELETE ALL' 確認: ").strip()
        
        if confirm1 != 'DELETE ALL':
            print("\n❌ 已取消刪除操作")
            return
        
        confirm2 = input("\n最後確認：您真的要刪除所有論壇資料嗎？ (yes/no): ").strip().lower()
        
        if confirm2 != 'yes':
            print("\n❌ 已取消刪除操作")
            return
        
        # 開始刪除
        print(f"\n{'='*60}")
        print("🗑️  開始刪除所有論壇資料...")
        print(f"{'='*60}\n")
        
        # 1. 刪除所有回覆/推噓
        c.execute('DELETE FROM forum_comments')
        deleted_comments = c.rowcount
        print(f"✓ 已刪除 {deleted_comments} 條回覆/推噓")
        
        # 2. 刪除所有打賞記錄
        c.execute('DELETE FROM tips')
        deleted_tips = c.rowcount
        print(f"✓ 已刪除 {deleted_tips} 條打賞記錄")
        
        # 3. 刪除所有文章標籤關聯
        c.execute('DELETE FROM post_tags')
        deleted_post_tags = c.rowcount
        print(f"✓ 已刪除 {deleted_post_tags} 條標籤關聯")
        
        # 4. 刪除所有文章
        c.execute('DELETE FROM posts')
        deleted_posts = c.rowcount
        print(f"✓ 已刪除 {deleted_posts} 篇文章")
        
        # 5. 重置看板文章計數
        c.execute('UPDATE boards SET post_count = 0')
        updated_boards = c.rowcount
        print(f"✓ 已重置 {updated_boards} 個看板的文章計數")
        
        # 6. 重置標籤文章計數
        c.execute('UPDATE tags SET post_count = 0')
        updated_tags = c.rowcount
        print(f"✓ 已重置 {updated_tags} 個標籤的文章計數")
        
        # 7. 清除用戶每日發文/回覆計數
        c.execute('DELETE FROM user_daily_posts')
        deleted_daily_posts = c.rowcount
        print(f"✓ 已清除 {deleted_daily_posts} 條每日發文記錄")
        
        c.execute('DELETE FROM user_daily_comments')
        deleted_daily_comments = c.rowcount
        print(f"✓ 已清除 {deleted_daily_comments} 條每日回覆記錄")
        
        # 提交事務
        conn.commit()
        
        print(f"\n{'='*60}")
        print(f"✅ 刪除完成！")
        print(f"{'='*60}\n")
        print("已清空所有論壇資料:")
        print(f"   - {deleted_posts} 篇文章")
        print(f"   - {deleted_comments} 條回覆/推噓")
        print(f"   - {deleted_tips} 條打賞記錄")
        print(f"   - {deleted_post_tags} 條標籤關聯")
        print(f"   - {deleted_daily_posts} 條每日發文記錄")
        print(f"   - {deleted_daily_comments} 條每日回覆記錄")
        print()
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    dry_run = '--confirm' not in sys.argv
    
    if len(sys.argv) > 1 and sys.argv[1] not in ['--confirm']:
        print("用法: python delete_all_posts.py [--confirm]")
        print("\n說明:")
        print("  不帶參數運行    - 試運行模式，查看將刪除的資料")
        print("  --confirm      - 實際執行刪除（需要雙重確認）")
        print("\n⚠️  警告：此操作會刪除所有論壇文章及相關資料！")
        sys.exit(1)
    
    delete_all_posts(dry_run=dry_run)
