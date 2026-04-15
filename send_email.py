import os
import smtplib
import ssl
from email.message import EmailMessage


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "465").strip())
    smtp_sender = required_env("SMTP_SENDER")
    smtp_password = required_env("SMTP_PASSWORD")
    smtp_receiver = required_env("SMTP_RECEIVER")
    subject = os.environ.get("ALERT_SUBJECT", "Stock Alert").strip()
    body = os.environ.get("ALERT_BODY", "").strip()

    msg = EmailMessage()
    msg["From"] = smtp_sender
    msg["To"] = smtp_receiver
    msg["Subject"] = subject
    msg.set_content(body or "Stock alert")

    context = ssl.create_default_context()
    if smtp_port == 465:
        # Port 465 expects implicit TLS (SMTP over SSL).
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=60, context=context) as server:
            server.login(smtp_sender, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
            server.starttls(context=context)
            server.login(smtp_sender, smtp_password)
            server.send_message(msg)

    print("Email alert sent successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
