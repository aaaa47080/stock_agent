
import os
import sys
import uuid
from datetime import datetime

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from core.database.connection import get_connection

def seed_users():
    conn = get_connection()
    c = conn.cursor()
    
    users = [
        {"id": "test-user-001", "username": "TestUser_001", "email": "test1@example.com"},
        {"id": "test-user-002", "username": "TestUser_002", "email": "test2@example.com"}
    ]
    
    print("Seeding test users...")
    
    try:
        for u in users:
            # Check if user exists
            c.execute("SELECT user_id FROM users WHERE user_id = %s", (u['id'],))
            existing = c.fetchone()
            
            if existing:
                print(f"User {u['username']} (ID: {u['id']}) already exists. Updating...")
                c.execute("""
                    UPDATE users 
                    SET username = %s, email = %s 
                    WHERE user_id = %s
                """, (u['username'], u['email'], u['id']))
            else:
                print(f"Creating User {u['username']} (ID: {u['id']})...")
                c.execute("""
                    INSERT INTO users (user_id, username, email, created_at, auth_method, password_hash)
                    VALUES (%s, %s, %s, NOW(), 'test_mode', 'mock_hash')
                """, (u['id'], u['username'], u['email']))
        
        conn.commit()
        print("Success! Users seeded.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error seeding users: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_users()
 