import sqlite3
import os
from datetime import datetime

db_path = 'user_data.db'
if not os.path.exists(db_path):
    print("Database file not found.")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT username, membership_tier, membership_expires_at FROM users WHERE username = 'a8031737'")
    row = c.fetchone()
    
    print("-" * 30)
    if row:
        username, tier, expires_at = row
        print(f"User:       {username}")
        print(f"Tier:       {tier}")
        print(f"Expires At: {expires_at}")
        
        # Helper to check if expired relative to UTC now
        if expires_at:
            try:
                dt = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                now = datetime.utcnow()
                status = "ACTIVE" if dt > now else "EXPIRED"
                print(f"Status:     {status} (Current UTC: {now.strftime('%Y-%m-%d %H:%M:%S')})")
            except ValueError:
                print("Status:     Invalid Date Format")
    else:
        print("User 'a8031737' not found.")
    print("-" * 30)
    conn.close()
