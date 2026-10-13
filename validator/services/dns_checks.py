import dns.exception
import dns.resolver
from django.conf import settings

class DNSCheckError(Exception):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)

def check_mail_route(domain: str) -> tuple[bool, str]:
    """
    Returns (has_mail_route, reason_code). MX is preferred; RFC-style address
    record fallback is accepted when MX records are absent. Temporary DNS
    errors are never treated as definitive nonexistence.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = settings.DNS_TIMEOUT_SECONDS
    resolver.lifetime = settings.DNS_LIFETIME_SECONDS
    attempts = max(1, settings.DNS_RETRY_ATTEMPTS)
    last_error = None

    for _ in range(attempts):
        try:
            answers = resolver.resolve(domain, "MX", raise_on_no_answer=False)
            if answers.rrset is not None and len(answers) > 0:
                return True, "MX_RECORD_FOUND"
            # No MX answer: check A/AAAA fallback. NoAnswer is not NXDOMAIN.
            for record_type in ("A", "AAAA"):
                try:
                    addr = resolver.resolve(domain, record_type, raise_on_no_answer=False)
                    if addr.rrset is not None and len(addr) > 0:
                        return True, "ADDRESS_RECORD_FALLBACK"
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                    continue
            return False, "NO_MAIL_ROUTE"
        except dns.resolver.NXDOMAIN:
            return False, "DOMAIN_NOT_FOUND"
        except (
            dns.exception.Timeout,
            dns.resolver.NoNameservers,
            dns.resolver.LifetimeTimeout,
        ) as exc:
            last_error = exc
            continue
        except dns.exception.DNSException as exc:
            last_error = exc
            continue

    raise DNSCheckError("DNS_TEMPORARY_FAILURE") from last_error
