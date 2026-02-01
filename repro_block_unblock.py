
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db, get_connection
from core.database.friends import (
    send_friend_request, 
    accept_friend_request, 
    block_user, 
    unblock_user, 
    get_friendship_status,
    remove_friend
)

# Mock user IDs
USER_A = "repro_user_a"
USER_B = "repro_user_b"

def setup_users():
    conn = get_connection()
    c = conn.cursor()
    try:
        # Create users if not exist
        for uid in [USER_A, USER_B]:
            c.execute("INSERT INTO users (user_id, username, created_at) VALUES (%s, %s, NOW()) ON CONFLICT (user_id) DO NOTHING", (uid, f"User_{uid}"))
        conn.commit()
    finally:
        conn.close()

def clean_state():
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM friendships WHERE user_id IN (%s, %s) OR friend_id IN (%s, %s)", (USER_A, USER_B, USER_A, USER_B))
        conn.commit()
    finally:
        conn.close()

def run_test():
    print("--- Starting Block/Unblock Logic Test ---")
    setup_users()
    clean_state()

    # 1. Make them friends
    print("\n1. Making them friends...")
    send_friend_request(USER_A, USER_B) # A sends to B
    accept_friend_request(USER_B, USER_A) # B accepts
    
    status = get_friendship_status(USER_A, USER_B)
    print(f"Status after accept: {status['status'] if status else 'None'}")
    assert status['status'] == 'accepted'

    # 2. Block
    print("\n2. User A blocks User B...")
    block_user(USER_A, USER_B)
    
    status = get_friendship_status(USER_A, USER_B)
    print(f"Status after block: {status['status'] if status else 'None'}")
    assert status['status'] == 'blocked'

    # Check from B's perspective (should be blocked logic, but row exists)
    # The `get_friendship_status` checks both directions.

    # 3. Unblock
    print("\n3. User A unblocks User B...")
    unblock_user(USER_A, USER_B)
    
    status = get_friendship_status(USER_A, USER_B)
    print(f"Status after unblock: {status['status'] if status else 'None'}")

    if status is None:
        print("RESULT: Relationship is GONE (Stranger). Correct.")
    elif status['status'] == 'accepted':
        print("RESULT: Relationship is ACCEPTED (Friend). INCORRECT!")
    else:
        print(f"RESULT: Status is {status['status']}")

if __name__ == "__main__":
    init_db()
    run_test()
