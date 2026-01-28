
import sys
import os
import sqlite3
from datetime import datetime

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.database.connection import get_connection
from core.database.messages import (
    get_or_create_conversation,
    send_message,
    mark_as_read,
    get_messages
)

def test_read_status_bug_real_ids():
    print("=== Testing Read Status Bug with REAL User IDs ===")
    
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Setup users (User A and User B based on User's report)
    # Using the IDs user mentioned (assuming a1031737 and a8031737 were just examples or actual IDs)
    # Wait, the user mentioned "a1031737" (sender) -> "a8031737" (recipient)
    user_a = "a1031737"  # Sender
    user_b = "a8031737"  # Recipient
    
    print(f"User A (Sender): {user_a}")
    print(f"User B (Recipient): {user_b}")

    # Ensure they exist
    c.execute("INSERT OR IGNORE INTO users (user_id, username, email, password_hash) VALUES (?, ?, ?, ?)", (user_a, f"User {user_a}", f"{user_a}@test.com", "hash"))
    c.execute("INSERT OR IGNORE INTO users (user_id, username, email, password_hash) VALUES (?, ?, ?, ?)", (user_b, f"User {user_b}", f"{user_b}@test.com", "hash"))
    conn.commit()

    # 2. User A sends message to User B
    print(f"\n[Step 1] {user_a} sends message to {user_b}")
    res = send_message(user_a, user_b, f"Test Message to {user_b}")
    if not res["success"]:
        print("Failed to send message:", res)
        # Try to debug why
        print("Error details:", res.get("error"))
        return
    
    msg = res["message"]
    msg_id = msg["id"]
    conv_id = msg["conversation_id"]
    print(f"Message sent. ID: {msg_id}, Conv ID: {conv_id}, is_read: {msg['is_read']}")
    
    if msg['is_read']:
        print("ERROR: New message should be unread!")
        
    # Check DB directly
    c.execute("SELECT is_read, from_user_id, to_user_id FROM dm_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    print(f"Immediate DB Check: is_read={row[0]}")
    
    # 3. User A views the conversation (enters chat)
    # This triggers mark_as_read(conv_id, user_a)
    print(f"\n[Step 2] {user_a} (Sender) enters chat and calls mark_as_read")
    
    # Simulate API call: user_id provided is user_a
    mark_res = mark_as_read(conv_id, user_a)
    print(f"mark_as_read result: {mark_res}")
    
    # 4. Check message status again
    print(f"\n[Step 3] Checking message status (as User A)")
    c.execute("SELECT id, from_user_id, to_user_id, is_read FROM dm_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    print(f"DB Row: {row}")
    
    is_read_db = bool(row[3])
    print(f"Message is_read in DB: {is_read_db}")
    
    if is_read_db:
        print("!!! TEST FAILED: Message became READ after SENDER viewed it !!!")
    else:
        print("TEST PASSED: Message remains UNREAD after SENDER viewed it.")

    # 5. Check what get_messages returns for A
    print(f"\n[Step 4] Calling get_messages as {user_a}")
    msgs_res = get_messages(conv_id, user_a, limit=5)
    
    found_msg = None
    if msgs_res["success"]:
        for m in msgs_res["messages"]:
            if m["id"] == msg_id:
                found_msg = m
                break
    
    if found_msg:
        print(f"get_messages returned: is_read={found_msg['is_read']}")
        if found_msg['is_read']:
             print("!!! API RETURNED READ=TRUE !!!")
    else:
        print("Message not found in get_messages")

    conn.close()

if __name__ == "__main__":
    try:
        test_read_status_bug_real_ids()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
