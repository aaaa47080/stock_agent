"""
Security Alert Dispatcher (Stage 4 Security)

Dispatches security alerts to multiple channels:
- Telegram (for instant notifications)
- Email (for detailed alerts)

Configuration via environment variables:
- TELEGRAM_BOT_TOKEN: Bot token for Telegram
- TELEGRAM_CHAT_ID: Chat ID to send messages to
- SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD: Email configuration
- ADMIN_EMAIL: Email address to receive alerts
"""
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from api.utils import logger


class AlertDispatcher:
    """
    Dispatches security alerts to multiple channels.

    Supports Telegram and email notifications for critical security events.
    All channels are optional - the dispatcher will silently skip
    unconfigured channels.
    """

    def __init__(self):
        """Initialize alert dispatcher with environment configuration."""
        # Telegram configuration
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        # Email configuration
        self.smtp_config = {
            "host": os.getenv("SMTP_HOST"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("SMTP_USERNAME"),
            "password": os.getenv("SMTP_PASSWORD"),
        }
        self.admin_email = os.getenv("ADMIN_EMAIL")

        # Check what's configured
        self.has_telegram = bool(self.telegram_bot_token and self.telegram_chat_id)
        self.has_email = bool(
            self.smtp_config["host"] and
            self.smtp_config["username"] and
            self.admin_email
        )

        if self.has_telegram:
            logger.info("✅ Telegram alerts configured")
        if self.has_email:
            logger.info("✅ Email alerts configured")

        if not self.has_telegram and not self.has_email:
            logger.warning("⚠️ No alert channels configured. Set TELEGRAM_BOT_TOKEN or SMTP_* variables.")

    def send(
        self,
        channel: str,
        severity: str,
        title: str,
        message: str
    ) -> bool:
        """
        Send alert to specified channel.

        Args:
            channel: Either "telegram" or "email"
            severity: Severity level (low, medium, high, critical)
            title: Alert title
            message: Alert message body

        Returns:
            True if alert was sent successfully, False otherwise
        """
        if channel == "telegram":
            return self._send_telegram(severity, title, message)
        elif channel == "email":
            return self._send_email(severity, title, message)
        else:
            logger.warning(f"Unknown alert channel: {channel}")
            return False

    def _send_telegram(self, severity: str, title: str, message: str) -> bool:
        """
        Send alert via Telegram bot.

        Args:
            severity: Severity level
            title: Alert title
            message: Alert message

        Returns:
            True if sent successfully
        """
        if not self.has_telegram:
            return False

        # Map severity to emoji
        emoji_map = {
            "low": "🔵",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        emoji = emoji_map.get(severity, "⚪")

        # Format message with HTML
        formatted_message = (
            f"{emoji} <b>{title}</b>\n\n"
            f"{message}\n\n"
            f"<i>Severity: {severity.upper()}</i>"
        )

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"

        try:
            import httpx
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    json={
                        "chat_id": self.telegram_chat_id,
                        "text": formatted_message,
                        "parse_mode": "HTML"
                    }
                )
                response.raise_for_status()

            logger.debug(f"Telegram alert sent: {title}")
            return True

        except ImportError:
            logger.error("httpx not installed, cannot send Telegram alerts")
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    def _send_email(self, severity: str, title: str, message: str) -> bool:
        """
        Send alert via email.

        Args:
            severity: Severity level
            title: Alert title
            message: Alert message

        Returns:
            True if sent successfully
        """
        if not self.has_email:
            return False

        # Create message
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = f"[{severity.upper()}] {title}"
        msg["From"] = self.smtp_config["username"]
        msg["To"] = self.admin_email

        try:
            with smtplib.SMTP(
                self.smtp_config["host"],
                self.smtp_config["port"],
                timeout=10
            ) as server:
                server.starttls()
                server.login(
                    self.smtp_config["username"],
                    self.smtp_config["password"]
                )
                server.send_message(msg)

            logger.debug(f"Email alert sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def send_critical(self, title: str, message: str) -> bool:
        """
        Send a critical severity alert to all configured channels.

        Args:
            title: Alert title
            message: Alert message

        Returns:
            True if at least one channel succeeded
        """
        success = False

        if self.has_telegram:
            if self._send_telegram("critical", title, message):
                success = True

        if self.has_email:
            if self._send_email("critical", title, message):
                success = True

        return success


# ============================================================================
# Convenience Functions
# ============================================================================

_global_dispatcher: Optional[AlertDispatcher] = None


def get_alert_dispatcher() -> AlertDispatcher:
    """Get the global alert dispatcher instance."""
    global _global_dispatcher
    if _global_dispatcher is None:
        _global_dispatcher = AlertDispatcher()
    return _global_dispatcher


def send_security_alert(
    severity: str,
    title: str,
    message: str,
    channel: str = "telegram"
) -> bool:
    """
    Convenience function to send a security alert.

    Args:
        severity: Severity level (low, medium, high, critical)
        title: Alert title
        message: Alert message
        channel: Alert channel (telegram or email)

    Returns:
        True if alert was sent successfully
    """
    dispatcher = get_alert_dispatcher()
    return dispatcher.send(channel, severity, title, message)
