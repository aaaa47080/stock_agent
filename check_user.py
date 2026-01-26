import sqlite3
import os

db_path = 'user_data.db'
if not os.path.exists(db_path):
    print("Database file not found.")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT username, membership_tier, membership_expires_at FROM users WHERE username = 'a8031737'")
    row = c.fetchone()
    if row:
        print(f"User: {row[0]}")
        print(f"Tier: {row[1]}")
        print(f"Expires At: {row[2]}")
    else:
        print("User 'a8031737' not found.")
    conn.close()
