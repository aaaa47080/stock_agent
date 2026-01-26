#!/usr/bin/env python3
"""
Simple debug script for forum post functionality
"""
import sys
import os

# 添加项目根目录到路径
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

from core.database.connection import get_connection
from core.database.forum import get_board_by_slug, check_daily_post_limit
from core.database.user import get_user_membership

def simple_debug():
    print("=== Simple Forum Debug ===\n")
    
    # 1. Check database connection
    print("1. Checking database connection...")
    try:
        conn = get_connection()
        print("   OK - Database connection works")
        conn.close()
    except Exception as e:
        print(f"   ERROR - Database connection failed: {e}")
        return
    
    # 2. Check boards table
    print("\n2. Checking boards table...")
    try:
        board = get_board_by_slug('crypto')
        if board:
            print(f"   OK - Crypto board exists (ID: {board['id']})")
        else:
            print("   ERROR - Crypto board does not exist")
            # Try to get all boards
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM boards;")
            all_boards = c.fetchall()
            print(f"   Available boards: {all_boards}")
            conn.close()
    except Exception as e:
        print(f"   ERROR - Check boards failed: {e}")
    
    # 3. Check user
    print("\n3. Checking test user...")
    try:
        # Try to get any user
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT user_id, username FROM users LIMIT 1;")
        user_row = c.fetchone()
        if user_row:
            user_id, username = user_row
            print(f"   OK - Found test user: {username} (ID: {user_id})")
            
            # Check user's post limit
            limit_result = check_daily_post_limit(user_id)
            print(f"   User post limit check: {limit_result}")
            
            # Check if user is premium member
            membership = get_user_membership(user_id)
            print(f"   User membership status: {membership}")
        else:
            print("   ERROR - No users found")
        conn.close()
    except Exception as e:
        print(f"   ERROR - Check user failed: {e}")
    
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    simple_debug()