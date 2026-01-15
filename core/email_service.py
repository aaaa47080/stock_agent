"""
Email 服務模組
使用 Gmail SMTP 發送密碼重置郵件
"""

import os
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# 從環境變數讀取配置
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
RESET_URL_BASE = os.getenv("RESET_URL_BASE", "http://localhost:8111")

# Gmail SMTP 設定 (SSL 模式)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465  # SSL port


def is_email_configured() -> bool:
    """檢查 Email 服務是否已配置"""
    return bool(SMTP_EMAIL and SMTP_PASSWORD)


def send_reset_email(to_email: str, reset_token: str, username: str = "User") -> bool:
    """
    發送密碼重置郵件

    Args:
        to_email: 收件人 Email
        reset_token: 重置 Token
        username: 用戶名（用於郵件內容）

    Returns:
        bool: 發送成功返回 True
    """
    if not is_email_configured():
        print("Email service not configured. Please set SMTP_EMAIL and SMTP_PASSWORD.")
        return False

    reset_link = f"{RESET_URL_BASE}?reset_token={reset_token}"

    # 建立郵件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "CryptoMind - Password Reset Request"
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    # 純文字版本
    text_content = f"""
Hi {username},

You requested to reset your password for CryptoMind.

Click the link below to reset your password (valid for 30 minutes):
{reset_link}

If you didn't request this, please ignore this email.

Best regards,
CryptoMind Team
"""

    # HTML 版本
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1c; color: #f4f4f5; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: #252529; border-radius: 24px; padding: 40px; border: 1px solid rgba(255,255,255,0.1); }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo span {{ font-size: 28px; background: linear-gradient(to right, #d4b693, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: bold; }}
        h1 {{ font-size: 24px; margin-bottom: 20px; color: #e4e4e7; }}
        p {{ color: #a1a1aa; line-height: 1.6; margin-bottom: 15px; }}
        .button {{ display: inline-block; padding: 14px 32px; background: linear-gradient(to right, #d4b693, #c084fc); color: #1a1a1c; text-decoration: none; border-radius: 12px; font-weight: bold; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 12px; color: #71717a; }}
        .warning {{ background: rgba(253,164,175,0.1); border: 1px solid rgba(253,164,175,0.3); padding: 12px 16px; border-radius: 8px; font-size: 13px; color: #fda4af; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <span>CryptoMind</span>
        </div>
        <h1>Password Reset Request</h1>
        <p>Hi <strong>{username}</strong>,</p>
        <p>You requested to reset your password. Click the button below to set a new password:</p>
        <p style="text-align: center;">
            <a href="{reset_link}" class="button">Reset Password</a>
        </p>
        <p class="warning">This link will expire in <strong>30 minutes</strong>. If you didn't request this, please ignore this email.</p>
        <div class="footer">
            <p>If the button doesn't work, copy and paste this link:</p>
            <p style="word-break: break-all; color: #d4b693;">{reset_link}</p>
        </div>
    </div>
</body>
</html>
"""

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        # 使用 SSL 模式連接 Gmail SMTP
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        print(f"Reset email sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP Authentication failed: {e}")
        print("Please check your Gmail App Password settings.")
        return False
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
