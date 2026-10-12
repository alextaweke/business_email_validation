import smtplib
import socket
from django.conf import settings

# SMTP recipient probing is skipped for major consumer providers because their
# responses are often deliberately ambiguous and probing may violate provider policy.
CONSUMER_PROVIDERS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}


def provider_policy_allows_smtp(domain: str) -> bool:
    return domain.lower() not in CONSUMER_PROVIDERS


def verify_recipient(mx_host: str, email: str) -> tuple[str, str]:
    """
    Make one bounded SMTP dialogue; never issue DATA or transmit a message.
    Returns (result, reason_code). SMTP evidence is inherently uncertain.
    """
    smtp = None
    try:
        smtp = smtplib.SMTP(timeout=settings.SMTP_TIMEOUT_SECONDS)
        code, _ = smtp.connect(mx_host, 25)
        if code not in (220,):
            return "not_known", "SMTP_AMBIGUOUS"
        code, _ = smtp.ehlo(settings.SMTP_HELO_NAME)
        if code >= 400:
            return "not_known", "SMTP_AMBIGUOUS"
        code, _ = smtp.mail("validator@" + settings.SMTP_HELO_NAME)
        if code >= 400:
            return "not_known", "SMTP_AMBIGUOUS"
        code, response = smtp.rcpt(email)
        message = (
            response.decode("utf-8", "replace")
            if isinstance(response, bytes)
            else str(response)
        )
        lower = message.lower()

        if 200 <= code < 300:
            return "true", "SMTP_RECIPIENT_ACCEPTED"
        if code == 550 and any(
            term in lower
            for term in (
                "user unknown",
                "no such user",
                "mailbox does not exist",
                "recipient address rejected",
                "unknown recipient",
            )
        ):
            return "false", "SMTP_RECIPIENT_REJECTED"
        if 400 <= code < 500:
            return "not_known", "SMTP_TEMPORARY_FAILURE"
        return "not_known", "SMTP_AMBIGUOUS"
    except (TimeoutError, socket.timeout):
        return "not_known", "SMTP_TIMEOUT"
    except (OSError, smtplib.SMTPException):
        return "not_known", "SMTP_UNAVAILABLE"
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass
