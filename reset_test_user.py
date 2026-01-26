import sqlite3
from datetime import datetime, timedelta

db_path = 'user_data.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 設定過期時間為昨天
yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
c.execute("UPDATE users SET membership_tier = 'pro', membership_expires_at = ? WHERE username = 'a8031737'", (yesterday,))
conn.commit()

c.execute("SELECT username, membership_tier, membership_expires_at FROM users WHERE username = 'a8031737'")
print(f"Current Status: {c.fetchone()}")
conn.close()
