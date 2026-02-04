#!/usr/bin/env python3
"""
刪除用戶所有論壇文章的管理腳本
用法: python delete_user_posts.py <username>
"""
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_connection


def delete_user_posts(username: str, dry_run: bool = True):
    """
    刪除指定用戶的所有論壇文章及相關資料
    
    Args:
        username: 用戶名
        dry_run: 是否為試運行模式（不實際刪除）
    """
    conn = get_connection()
    c = conn.cursor()
    
    try:
        # 1. 查找用戶
        c.execute('SELECT user_id, username FROM users WHERE username = %s', (username,))
        user = c.fetchone()
        
        if not user:
            print(f"❌ 錯誤：找不到用戶 '{username}'")
            return
        
        user_id, username = user
        print(f"\n{'='*60}")
        print(f"🔍 找到用戶: {username} (ID: {user_id})")
        print(f"{'='*60}\n")
        
        # 2. 查找該用戶的所有文章
        c.execute('''
            SELECT p.id, p.title, p.category, p.created_at, b.name as board_name,
                   p.comment_count, p.push_count, p.boo_count, p.tips_total
            FROM posts p
            LEFT JOIN boards b ON p.board_id = b.id
            WHERE p.user_id = %s
            ORDER BY p.created_at DESC
        ''', (user_id,))
        
        posts = c.fetchall()
        
        if not posts:
            print(f"ℹ️  用戶 '{username}' 沒有任何文章")
            return
        
        print(f"📝 找到 {len(posts)} 篇文章:\n")
        
        total_comments = 0
        total_tips = 0
        
        for i, post in enumerate(posts, 1):
            post_id, title, category, created_at, board_name, comment_count, push_count, boo_count, tips_total = post
            total_comments += comment_count + push_count + boo_count
            total_tips += tips_total
            
            print(f"{i}. [{category}] {title}")
            print(f"   ID: {post_id} | 看板: {board_name} | 創建: {created_at}")
            print(f"   回覆: {comment_count} | 推: {push_count} | 噓: {boo_count} | 打賞: {tips_total} Pi")
            print()
        
        print(f"{'='*60}")
        print(f"📊 統計:")
        print(f"   文章總數: {len(posts)}")
        print(f"   回覆/推噓總數: {total_comments}")
        print(f"   打賞總額: {total_tips} Pi")
        print(f"{'='*60}\n")
        
        if dry_run:
            print("🔍 試運行模式：不會實際刪除資料")
            print("\n如要實際刪除，請執行:")
            print(f"   python scripts/delete_user_posts.py \"{username}\" --confirm")
            return
        
        # 確認刪除
        print("⚠️  警告：此操作不可逆！")
        print("⚠️  將刪除以下資料:")
        print("   - 所有文章")
        print("   - 所有相關的回覆和推噓")
        print("   - 所有相關的打賞記錄")
        print("   - 文章標籤關聯")
        print()
        
        confirm = input(f"確定要刪除用戶 '{username}' 的所有 {len(posts)} 篇文章嗎？ (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("\n❌ 已取消刪除操作")
            return
        
        # 開始刪除
        print(f"\n{'='*60}")
        print("🗑️  開始刪除...")
        print(f"{'='*60}\n")
        
        post_ids = [p[0] for p in posts]
        post_ids_tuple = tuple(post_ids)
        
        # 3. 刪除回覆/推噓
        c.execute(f'''
            DELETE FROM forum_comments 
            WHERE post_id IN %s
        ''', (post_ids_tuple,))
        deleted_comments = c.rowcount
        print(f"✓ 已刪除 {deleted_comments} 條回覆/推噓")
        
        # 4. 刪除打賞記錄
        c.execute(f'''
            DELETE FROM tips 
            WHERE post_id IN %s
        ''', (post_ids_tuple,))
        deleted_tips = c.rowcount
        print(f"✓ 已刪除 {deleted_tips} 條打賞記錄")
        
        # 5. 刪除文章標籤關聯
        c.execute(f'''
            DELETE FROM post_tags 
            WHERE post_id IN %s
        ''', (post_ids_tuple,))
        deleted_post_tags = c.rowcount
        print(f"✓ 已刪除 {deleted_post_tags} 條標籤關聯")
        
        # 6. 獲取受影響的看板和標籤（用於更新計數）
        c.execute('''
            SELECT DISTINCT board_id, COUNT(*) as count
            FROM posts
            WHERE id IN %s
            GROUP BY board_id
        ''', (post_ids_tuple,))
        board_counts = c.fetchall()
        
        # 7. 刪除文章本身
        c.execute(f'''
            DELETE FROM posts 
            WHERE user_id = %s
        ''', (user_id,))
        deleted_posts = c.rowcount
        print(f"✓ 已刪除 {deleted_posts} 篇文章")
        
        # 8. 更新看板文章計數
        for board_id, count in board_counts:
            if board_id:
                c.execute('''
                    UPDATE boards 
                    SET post_count = GREATEST(0, post_count - %s)
                    WHERE id = %s
                ''', (count, board_id))
        print(f"✓ 已更新 {len(board_counts)} 個看板的文章計數")
        
        # 9. 更新標籤計數（需要重新計算）
        c.execute('''
            UPDATE tags t
            SET post_count = (
                SELECT COUNT(DISTINCT pt.post_id)
                FROM post_tags pt
                WHERE pt.tag_id = t.id
            )
        ''')
        print(f"✓ 已重新計算標籤文章計數")
        
        # 提交事務
        conn.commit()
        
        print(f"\n{'='*60}")
        print(f"✅ 刪除完成！")
        print(f"{'='*60}\n")
        print(f"已刪除用戶 '{username}' 的:")
        print(f"   - {deleted_posts} 篇文章")
        print(f"   - {deleted_comments} 條回覆/推噓")
        print(f"   - {deleted_tips} 條打賞記錄")
        print(f"   - {deleted_post_tags} 條標籤關聯")
        print()
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python delete_user_posts.py <username> [--confirm]")
        print("\n範例:")
        print("  python delete_user_posts.py \"翁\"              # 試運行，查看將刪除的資料")
        print("  python delete_user_posts.py \"翁\" --confirm    # 實際執行刪除")
        sys.exit(1)
    
    username = sys.argv[1]
    dry_run = '--confirm' not in sys.argv
    
    delete_user_posts(username, dry_run=dry_run)
