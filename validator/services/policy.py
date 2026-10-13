from collections import defaultdict
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock
from django.conf import settings
from django.core.cache import cache

_global_smtp_slots = BoundedSemaphore(settings.SMTP_GLOBAL_CONCURRENCY_LIMIT)
_domain_slots_lock = Lock()
_domain_smtp_slots = defaultdict(
    lambda: BoundedSemaphore(settings.SMTP_DOMAIN_CONCURRENCY_LIMIT)
)


def smtp_allowed(domain: str) -> tuple[bool, str]:
    if not settings.GLOBAL_SMTP_ENABLED or not settings.SMTP_CHECKS_ENABLED:
        return False, "SMTP_SKIPPED_BY_POLICY"
    from .smtp_checks import provider_policy_allows_smtp

    if not provider_policy_allows_smtp(domain):
        return False, "SMTP_SKIPPED_BY_POLICY"
    if cache.get(f"smtp-cooldown:{domain}"):
        return False, "SMTP_DOMAIN_COOLDOWN"
    return True, "SMTP_POLICY_ALLOWED"


@contextmanager
def smtp_probe_slot(domain: str):
    """Best-effort in-process global and per-domain SMTP concurrency guard."""
    if not _global_smtp_slots.acquire(blocking=False):
        yield False
        return

    with _domain_slots_lock:
        domain_slots = _domain_smtp_slots[domain]

    if not domain_slots.acquire(blocking=False):
        _global_smtp_slots.release()
        yield False
        return

    try:
        yield True
    finally:
        domain_slots.release()
        _global_smtp_slots.release()


def record_smtp_failure(domain: str, reason_code: str) -> None:
    """Short domain cooldown for transient/unavailable SMTP outcomes."""
    if reason_code in {
        "SMTP_TEMPORARY_FAILURE",
        "SMTP_TIMEOUT",
        "SMTP_UNAVAILABLE",
        "SMTP_AMBIGUOUS",
        "SMTP_RATE_LIMITED",
    }:
        cache.set(
            f"smtp-cooldown:{domain}",
            True,
            timeout=settings.SMTP_DOMAIN_COOLDOWN_SECONDS,
        )
