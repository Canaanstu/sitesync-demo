"""Transactional email (verification and password reset). Configure ONE of:
  - Resend:  RESEND_API_KEY and MAIL_FROM (a sender on a domain verified in Resend)
  - SMTP:    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD and MAIL_FROM
When neither is set, email features switch off cleanly (see mail_enabled)."""
import smtplib
import ssl
from email.message import EmailMessage
import httpx
from .config import settings


def mail_enabled():
    return bool((settings.resend_api_key or settings.smtp_host) and settings.mail_from)


def send_email(to, subject, text):
    """Send a plain-text email. Returns True when the provider accepted it; never raises."""
    try:
        if settings.resend_api_key:
            r = httpx.post('https://api.resend.com/emails', headers={'Authorization': f'Bearer {settings.resend_api_key}'},
                           json={'from': settings.mail_from, 'to': [to], 'subject': subject, 'text': text}, timeout=10)
            r.raise_for_status()
            return True
        if settings.smtp_host:
            msg = EmailMessage()
            msg['From'], msg['To'], msg['Subject'] = settings.mail_from, to, subject
            msg.set_content(text)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
            return True
    except Exception as exc:  # delivery problems must not break sign-up or reset requests
        print(f'Email delivery failed: {type(exc).__name__}', flush=True)
    return False
