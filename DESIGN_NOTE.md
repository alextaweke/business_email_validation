# Technical Design Note

## Decision flow

1. Authenticate the caller and apply request throttling.
2. Validate request shape and maximum email length.
3. Parse the address using `email-validator`, preserve local-part semantics, and normalize the domain.
4. Check the cache using a SHA-256 digest of the normalized address (the raw address is not put into the cache key).
5. Resolve MX. If there is no MX answer, check A/AAAA fallback. Map NXDOMAIN to `DOMAIN_NOT_FOUND`, missing route to `NO_MAIL_ROUTE`, and temporary DNS errors to `DNS_TEMPORARY_FAILURE`.
6. If SMTP is not requested, disabled globally, disallowed by provider policy, or the domain is cooling down, return `not_known`.
7. If allowed, connect to one MX host with a strict timeout, issue EHLO/MAIL/RCPT using configured SMTP identity settings, never DATA, and close the session.
8. SMTP recipient acceptance maps to best-effort `true` per the interview contract. Only a clearly identified permanent nonexistent-recipient rejection maps to `false`; catch-all suspicion, provider blocks, temporary failures, and ambiguity map to `not_known`.
9. Cache with short TTL for uncertain outcomes, and log a request ID, domain, reason, duration, and result without the full email address.

## Safeguards

- SMTP is disabled by default and has a global kill switch.
- Major consumer providers are excluded from recipient probing.
- No guessed addresses, message bodies, proxy/IP rotation, or repeated retries.
- SMTP attempts are bounded by a timeout and a short cooldown after transient failures.
- The SMTP envelope sender is configurable; the default blank value uses a null reverse-path so a fake sender domain does not prevent recipient acceptance from being observed.
- Caller throttling is enabled. The MVP's in-process cache is not a distributed lock; production should use Redis and shared concurrency limits.
- API responses do not expose raw SMTP transcripts, internal host details, or stack traces.

## Trade-offs and limitations

SMTP cannot prove that an inbox exists, is monitored, or belongs to a real person. Servers can accept all recipients, defer responses, greylist, or intentionally obscure mailbox validity. The service returns `true` for explicit recipient acceptance only as a best-effort likely-deliverable result, and otherwise prioritizes `not_known` rather than overclaiming. This MVP's business-email classification is omitted because a custom domain is not proof that an address is a business address.
