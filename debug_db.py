
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Load env
load_dotenv()

from core.database.connection import get_connection, init_db
from core.database.messages import get_conversations
from core.database.forum import get_user_payment_history

def test_db_connection():
    print("--- Testing DB Connection ---")
    try:
        conn = get_connection()
        print("✅ Connection successful")
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")

def test_messages(user_id):
    print(f"\n--- Testing Messages for {user_id} ---")
    try:
        convs = get_conversations(user_id)
        print(f"✅ get_conversations success. Count: {len(convs)}")
    except Exception as e:
        print(f"❌ get_conversations failed: {e}")
        import traceback
        traceback.print_exc()

def test_forum(user_id):
    print(f"\n--- Testing Forum for {user_id} ---")
    try:
        # Check get_user_payment_history as it was failing in logs
        payments = get_user_payment_history(user_id)
        print(f"✅ get_user_payment_history success. Count: {len(payments)}")
    except Exception as e:
        print(f"❌ get_user_payment_history failed: {e}")
        import traceback
        traceback.print_exc()

def check_tables():
    print("\n--- Checking Tables ---")
    tables = [
        'dm_conversations', 'dm_messages', 'users', 'membership_payments', 'tips'
    ]
    conn = get_connection()
    c = conn.cursor()
    try:
        for t in tables:
            try:
                c.execute(f"SELECT COUNT(*) FROM {t}")
                print(f"✅ Table '{t}' exists. Rows: {c.fetchone()[0]}")
            except Exception as e:
                print(f"❌ Table '{t}' check failed: {e}")
                conn.rollback() # Reset transaction
    finally:
        conn.close()

if __name__ == "__main__":
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
    # Force init_db to ensure tables exist
    print("Running init_db()...")
    init_db()
    
    test_user_id = "test-user-001"
    
    check_tables()
    test_db_connection()
    test_messages(test_user_id)
    test_forum(test_user_id)
