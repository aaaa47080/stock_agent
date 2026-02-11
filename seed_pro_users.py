import os
import sys
from datetime import datetime, timedelta

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from core.database.connection import get_connection

def seed_pro_users():
    conn = get_connection()
    c = conn.cursor()
    
    users = [
        {"id": "test-user-003", "username": "TestUser_003", "email": "test3@example.com"},
        {"id": "test-user-004", "username": "TestUser_004", "email": "test4@example.com"}
    ]
    
    print("Seeding PRO test users...")
    
    try:
        for u in users:
            # Check if user exists
            c.execute("SELECT user_id FROM users WHERE user_id = %s", (u['id'],))
            existing = c.fetchone()
            
            # 30 days expiration
            expires_at = datetime.utcnow() + timedelta(days=30)
            
            if existing:
                print(f"User {u['username']} (ID: {u['id']}) already exists. Updating to PRO...")
                c.execute("""
                    UPDATE users 
                    SET username = %s, email = %s, membership_tier = 'pro', membership_expires_at = %s
                    WHERE user_id = %s
                """, (u['username'], u['email'], expires_at, u['id']))
            else:
                print(f"Creating PRO User {u['username']} (ID: {u['id']})...")
                c.execute("""
                    INSERT INTO users (user_id, username, email, created_at, auth_method, password_hash, membership_tier, membership_expires_at)
                    VALUES (%s, %s, %s, NOW(), 'test_mode', 'mock_hash', 'pro', %s)
                """, (u['id'], u['username'], u['email'], expires_at))
        
        conn.commit()
        print("Success! PRO Users seeded.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error seeding users: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_pro_users()
