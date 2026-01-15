import smtplib
import ssl
from dotenv import load_dotenv
import os

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

print("=" * 50)
print("SMTP 連接測試 (SSL 模式)")
print("=" * 50)

try:
    print("🔄 正在透過 Port 465 建立 SSL 連線...")
    # 建立安全上下文
    context = ssl.create_default_context()
    
    # 改用 SMTP_SSL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.set_debuglevel(1)
        
        print("🔄 登入中...")
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        print("\n✅ SMTP 連接成功！")
        
except Exception as e:
    print(f"\n❌ 連接失敗: {e}")