import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from django.conf import settings
from django.core.cache import cache
from .syntax import normalize_and_validate
from .dns_checks import check_mail_route, DNSCheckError
from .policy import smtp_allowed, record_smtp_failure, smtp_probe_slot
from .smtp_checks import verify_recipient
import dns.exception
import dns.resolver

logger = logging.getLogger("validator")


def _cache_key(normalized: str, check_smtp: bool) -> str:
    # Do not place raw email addresses in cache keys.
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"email-validation:v1:{digest}:{int(check_smtp)}"


def _base(result, reason, syntax_valid, mail_route, smtp_checked, duration, request_id):
    return {
        "result": result,
        "reason_code": reason,
        "syntax_valid": syntax_valid,
        "domain_has_mail_route": mail_route,
        "smtp_checked": smtp_checked,
        "catch_all": "unknown",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": max(0, int(duration * 1000)),
        "request_id": request_id,
    }


def validate_email_address(email: str, check_smtp: bool = False) -> dict:
    started = time.monotonic()
    request_id = str(uuid.uuid4())
    valid, normalized, syntax_reason = normalize_and_validate(email)

    if not valid:
        return _base(
            "false",
            syntax_reason,
            False,
            None,
            False,
            time.monotonic() - started,
            request_id,
        )

    local, domain = normalized.rsplit("@", 1)
    # Domain is normalized lowercase/IDNA by email-validator.
    cache_key = _cache_key(normalized, check_smtp)
    cached = cache.get(cache_key)
    if cached:
        cached = dict(cached)
        cached["request_id"] = request_id
        cached["duration_ms"] = max(0, int((time.monotonic() - started) * 1000))
        cached["cached"] = True
        return cached

    try:
        has_route, dns_reason = check_mail_route(domain)
    except DNSCheckError as exc:
        output = _base(
            "not_known",
            exc.reason_code,
            True,
            None,
            False,
            time.monotonic() - started,
            request_id,
        )
        cache.set(cache_key, output, settings.CACHE_TTL_UNKNOWN)
        return output

    if not has_route:
        result = (
            "false"
            if dns_reason in {"DOMAIN_NOT_FOUND", "NO_MAIL_ROUTE"}
            else "not_known"
        )
        output = _base(
            result,
            dns_reason,
            True,
            False,
            False,
            time.monotonic() - started,
            request_id,
        )
        cache.set(
            cache_key,
            output,
            (
                settings.CACHE_TTL_FALSE
                if result == "false"
                else settings.CACHE_TTL_UNKNOWN
            ),
        )
        return output

    result, reason, smtp_checked = "not_known", "SMTP_NOT_REQUESTED", False
    if check_smtp:
        allowed, policy_reason = smtp_allowed(domain)
        if not allowed:
            reason = policy_reason
        else:
            with smtp_probe_slot(domain) as slot_acquired:
                if not slot_acquired:
                    result, reason = "not_known", "SMTP_RATE_LIMITED"
                else:
                    # Select one MX host only. No retries and no recipient-variant probing.
                    try:
                        if dns_reason == "ADDRESS_RECORD_FALLBACK":
                            mx_host = domain
                        else:
                            resolver = dns.resolver.Resolver()
                            resolver.timeout = settings.DNS_TIMEOUT_SECONDS
                            resolver.lifetime = settings.DNS_LIFETIME_SECONDS
                            mx_records = resolver.resolve(domain, "MX")
                            mx_host = sorted(
                                mx_records, key=lambda item: item.preference
                            )[0].exchange.to_text(omit_final_dot=True)
                        result, reason = verify_recipient(mx_host, normalized)
                        smtp_checked = True
                    except dns.exception.DNSException:
                        result, reason = "not_known", "DNS_TEMPORARY_FAILURE"
                    except Exception:
                        result, reason = "not_known", "SMTP_UNAVAILABLE"
                record_smtp_failure(domain, reason)

    output = _base(
        result, reason, True, True, smtp_checked, time.monotonic() - started, request_id
    )
    ttl = settings.CACHE_TTL_UNKNOWN
    if result == "false":
        ttl = settings.CACHE_TTL_FALSE
    elif result == "true":
        ttl = settings.CACHE_TTL_TRUE
    cache.set(cache_key, output, ttl)
    logger.info(
        "email_validation_completed",
        extra={
            "request_id": request_id,
            "domain": domain,
            "result": result,
            "reason_code": reason,
            "smtp_checked": smtp_checked,
            "duration_ms": output["duration_ms"],
        },
    )
    return output
