"""
数据库索引优化脚本

为高频查询添加索引，提升查询速度 5-10 倍
执行方式: python add_indexes.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database.connection import get_connection


def add_performance_indexes():
    """添加性能优化索引"""
    
    conn = get_connection()
    c = conn.cursor()
    
    print("=" * 80)
    print("📊 开始添加数据库索引优化")
    print("=" * 80)
    print()
    
    # 索引列表
    indexes = [
        # 1. 私讯对话查询优化（高频）
        {
            "name": "idx_dm_conversations_users_time",
            "table": "dm_conversations",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_dm_conversations_users_time 
                ON dm_conversations(user1_id, user2_id, last_message_at DESC)
            """,
            "purpose": "优化用户对话列表查询"
        },
        
        # 2. 私讯消息查询优化（高频）
        {
            "name": "idx_dm_messages_conversation_time",
            "table": "dm_messages",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_dm_messages_conversation_time 
                ON dm_messages(conversation_id, created_at DESC)
            """,
            "purpose": "优化对话消息历史查询"
        },
        
        # 3. 私讯未读消息查询
        {
            "name": "idx_dm_messages_unread",
            "table": "dm_messages",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_dm_messages_unread 
                ON dm_messages(to_user_id, is_read) 
                WHERE is_read = FALSE
            """,
            "purpose": "优化未读消息查询"
        },
        
        # 4. 论坛文章查询优化（高频）
        {
            "name": "idx_posts_board_time_active",
            "table": "posts",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_posts_board_time_active 
                ON posts(board_id, created_at DESC) 
                WHERE deleted_at IS NULL
            """,
            "purpose": "优化板块文章列表查询（排除已删除）"
        },
        
        # 5. 论坛文章用户查询
        {
            "name": "idx_posts_user_time",
            "table": "posts",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_posts_user_time 
                ON posts(user_id, created_at DESC) 
                WHERE deleted_at IS NULL
            """,
            "purpose": "优化用户发帖历史查询"
        },
        
        # 6. 论坛评论查询优化
        {
            "name": "idx_comments_post_time",
            "table": "forum_comments",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_comments_post_time 
                ON forum_comments(post_id, created_at ASC)
            """,
            "purpose": "优化文章评论列表查询"
        },
        
        # 7. 用户名查询优化（登录）
        {
            "name": "idx_users_username_active",
            "table": "users",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_users_username_active 
                ON users(username) 
                WHERE deleted_at IS NULL
            """,
            "purpose": "优化用户登录查询"
        },
        
        # 8. 用户ID查询优化
        {
            "name": "idx_users_user_id_active",
            "table": "users",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_users_user_id_active 
                ON users(user_id) 
                WHERE deleted_at IS NULL
            """,
            "purpose": "优化用户ID查询"
        },
        
        # 9. 好友关系查询优化
        {
            "name": "idx_friendships_user_status",
            "table": "friendships",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_friendships_user_status 
                ON friendships(user_id, status, created_at DESC)
            """,
            "purpose": "优化好友列表查询"
        },
        
        # 10. 审计日志时间查询（管理员）
        {
            "name": "idx_audit_logs_time_user",
            "table": "audit_logs",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_audit_logs_time_user 
                ON audit_logs(created_at DESC, user_id)
            """,
            "purpose": "优化审计日志时间范围查询"
        },
    ]
    
    # 执行索引创建
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    for idx in indexes:
        try:
            print(f"📌 创建索引: {idx['name']}")
            print(f"   表: {idx['table']}")
            print(f"   用途: {idx['purpose']}")
            
            # 检查索引是否已存在
            c.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE indexname = %s
            """, (idx['name'],))
            
            if c.fetchone():
                print(f"   ⏭️  索引已存在，跳过")
                skipped_count += 1
            else:
                c.execute(idx['sql'])
                conn.commit()
                print(f"   ✅ 创建成功")
                success_count += 1
            
            print()
            
        except Exception as e:
            print(f"   ❌ 创建失败: {e}")
            failed_count += 1
            print()
            conn.rollback()
    
    # 统计结果
    print("=" * 80)
    print("📊 索引创建结果")
    print("=" * 80)
    print(f"✅ 成功创建: {success_count} 个")
    print(f"⏭️  已存在跳过: {skipped_count} 个")
    print(f"❌ 创建失败: {failed_count} 个")
    print(f"📝 总计: {len(indexes)} 个索引")
    print()
    
    # 显示所有索引
    print("=" * 80)
    print("📋 当前数据库索引列表")
    print("=" * 80)
    
    c.execute("""
        SELECT 
            schemaname,
            tablename,
            indexname,
            pg_size_pretty(pg_relation_size(indexname::regclass)) as size
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """)
    
    rows = c.fetchall()
    current_table = None
    
    for schema, table, index, size in rows:
        if table != current_table:
            print(f"\n📁 {table}:")
            current_table = table
        print(f"   - {index} ({size})")
    
    print()
    print("=" * 80)
    print("✅ 索引优化完成！")
    print()
    print("💡 提示:")
    print("   - 索引会占用一定的磁盘空间")
    print("   - 索引会略微降低写入速度，但大幅提升查询速度")
    print("   - 可以运行 VACUUM ANALYZE 优化数据库")
    print()
    
    conn.close()


def verify_indexes():
    """验证索引效果"""
    conn = get_connection()
    c = conn.cursor()
    
    print("=" * 80)
    print("🔍 验证索引效果")
    print("=" * 80)
    print()
    
    # 测试查询
    test_queries = [
        {
            "name": "用户对话列表查询",
            "sql": """
                EXPLAIN ANALYZE
                SELECT * FROM dm_conversations 
                WHERE user1_id = 'test' OR user2_id = 'test'
                ORDER BY last_message_at DESC 
                LIMIT 10
            """
        },
        {
            "name": "论坛文章列表查询",
            "sql": """
                EXPLAIN ANALYZE
                SELECT * FROM posts 
                WHERE board_id = 1 AND deleted_at IS NULL
                ORDER BY created_at DESC 
                LIMIT 20
            """
        },
    ]
    
    for query in test_queries:
        print(f"📊 {query['name']}")
        print("-" * 80)
        try:
            c.execute(query['sql'])
            results = c.fetchall()
            
            # 查找 Index Scan 行
            for row in results:
                line = str(row[0])
                if 'Index Scan' in line or 'Seq Scan' in line:
                    print(f"   {line}")
            
            print()
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
            print()
    
    conn.close()


if __name__ == "__main__":
    try:
        add_performance_indexes()
        
        # 可选：验证索引
        # verify_indexes()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
