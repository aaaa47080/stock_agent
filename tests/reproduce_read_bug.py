
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

def test_read_status_bug():
    print("=== Testing Read Status Bug ===")
    
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Setup users (User A and User B)
    user_a = "user_a_test"
    user_b = "user_b_test"
    
    # Ensure they exist (mocking or inserting if needed, but assuming simple strings work for this DB shim if users table constraints aren't strict, 
    # but the code joins users table. So we might need to insert dummy users if they don't exist)
    # The current `messages.py` joins `users`. We should ensure they exist to avoid empty results in get_messages queries that join.
    c.execute("INSERT OR IGNORE INTO users (user_id, username, email, password_hash) VALUES (?, ?, ?, ?)", (user_a, "User A", "a@test.com", "hash"))
    c.execute("INSERT OR IGNORE INTO users (user_id, username, email, password_hash) VALUES (?, ?, ?, ?)", (user_b, "User B", "b@test.com", "hash"))
    conn.commit()

    # 2. User A sends message to User B
    print(f"\n[Step 1] {user_a} sends message to {user_b}")
    res = send_message(user_a, user_b, "Hello User B")
    if not res["success"]:
        print("Failed to send message:", res)
        return
    
    msg = res["message"]
    msg_id = msg["id"]
    conv_id = msg["conversation_id"]
    print(f"Message sent. ID: {msg_id}, Conv ID: {conv_id}, is_read: {msg['is_read']}")
    
    if msg['is_read']:
        print("ERROR: New message should be unread!")
    
    # 3. User A views the conversation (enters chat)
    # This triggers mark_as_read(conv_id, user_a)
    print(f"\n[Step 2] {user_a} (Sender) enters chat and calls mark_as_read")
    mark_res = mark_as_read(conv_id, user_a)
    print(f"mark_as_read result: {mark_res}")
    
    # 4. Check message status again
    print(f"\n[Step 3] Checking message status (as User A)")
    # We use direct SQL to be sure, or get_messages
    c.execute("SELECT id, from_user_id, to_user_id, is_read FROM dm_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    print(f"DB Row: {row}")
    
    is_read_db = bool(row[3])
    print(f"Message is_read in DB: {is_read_db}")
    
    if is_read_db:
        print("!!! TEST FAILED: Message became READ after SENDER viewed it !!!")
    else:
        print("TEST PASSED: Message remains UNREAD after SENDER viewed it.")

    # 5. User B views the conversation
    print(f"\n[Step 4] {user_b} (Recipient) enters chat and calls mark_as_read")
    mark_res_b = mark_as_read(conv_id, user_b)
    print(f"mark_as_read result: {mark_res_b}")
    
    c.execute("SELECT id, from_user_id, to_user_id, is_read FROM dm_messages WHERE id = ?", (msg_id,))
    row = c.fetchone()
    print(f"DB Row after Recipient view: {row}")
    
    if bool(row[3]):
        print("TEST PASSED: Message became READ after RECIPIENT viewed it.")
    else:
        print("TEST FAILED: Message stayed UNREAD after RECIPIENT viewed it.")

    # Cleanup
    # c.execute("DELETE FROM dm_messages WHERE conversation_id = ?", (conv_id,))
    # c.execute("DELETE FROM dm_conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    try:
        test_read_status_bug()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
