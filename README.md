# Business Email Validation Service

A Django REST Framework API for **best-effort** email deliverability estimation. It returns exactly one normalized `result` value: `"true"`, `"false"`, or `"not_known"`.

> Important: SMTP-based mailbox verification is inherently uncertain. This project does not send email or issue SMTP `DATA`. SMTP checks are disabled by default. A recipient accepted at `RCPT TO` is reported as `true` only as a best-effort, likely-deliverable result; ambiguous, policy-blocked, timeout, greylisting, and catch-all-suspected outcomes remain `not_known`.

## Features

- Syntax parsing and safe normalization using `email-validator`
- DNS MX lookup and address-record fallback
- Separate handling of NXDOMAIN versus temporary DNS failures
- Optional single-attempt SMTP dialogue, disabled by default
- Conservative three-state result classifier and machine-readable reason codes
- API key authentication (`X-API-Key`)
- DRF request throttling; domain cooldown after SMTP failures
- Cache with result-dependent TTLs and hashed email cache keys
- Minimal structured logs: no full email address is logged
- Swagger/OpenAPI docs
- Mock-based tests that do not need live DNS/SMTP

## Requirements

- Python 3.11+
- Internet access for DNS queries if testing real domains
- SMTP verification should only be enabled after reviewing provider policies and network/IP configuration

## Windows PowerShell setup

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a strong `SECRET_KEY` and `API_KEY`. Keep `.env` private and never commit it.

```powershell
python manage.py check
python manage.py migrate
python manage.py runserver
```

API runs at `http://127.0.0.1:8000`. Swagger UI: `http://127.0.0.1:8000/api/docs/`.

## Request

```powershell
$headers = @{ "X-API-Key" = "replace-this-api-key" }
$body = @{ email = "person@example.com"; check_smtp = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/email/validate/" `
  -Headers $headers -ContentType "application/json" -Body $body
```

Equivalent curl:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/email/validate/ \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: replace-this-api-key" \\
  -d '{"email":"person@example.com","check_smtp":true}'
```

To see `result: "true"`, SMTP checks must be enabled and the request must set
`check_smtp` to `true`. The target domain must also allow the SMTP recipient
check and explicitly accept the recipient. Consumer providers such as Gmail,
Outlook, Yahoo, and iCloud are skipped by policy and return `not_known`.

## Response contract

```json
{
  "result": "not_known",
  "reason_code": "SMTP_NOT_REQUESTED",
  "syntax_valid": true,
  "domain_has_mail_route": true,
  "smtp_checked": false,
  "catch_all": "unknown",
  "checked_at": "2026-01-01T12:00:00+00:00",
  "duration_ms": 45,
  "request_id": "generated-correlation-id"
}
```

### Result semantics

- `true`: syntax is valid, the domain has a usable mail route, and an enabled SMTP check explicitly accepted the recipient. This remains best-effort, not a guarantee that the mailbox exists or is monitored.
- `false`: invalid syntax, a definitively nonexistent domain, no usable mail route, or a clearly identified permanent recipient rejection.
- `not_known`: temporary DNS failure, timeout, provider policy, SMTP disabled, ambiguous SMTP response, possible catch-all behavior, or insufficient evidence.

A `200` means the validation workflow completed; it does not mean the email address exists. `400` means malformed input; `401` means API key missing/invalid; `429` means caller throttling; `500` is an unexpected internal failure.

## Environment settings

| Variable | Purpose | Default |
|---|---|---|
| `API_KEY` | API key | Must be changed |
| `SMTP_CHECKS_ENABLED` | Enables SMTP checks when true | `False` |
| `GLOBAL_SMTP_ENABLED` | Emergency SMTP kill switch | `True` |
| `SMTP_TIMEOUT_SECONDS` | SMTP timeout | `4` |
| `DNS_TIMEOUT_SECONDS` | DNS per-query timeout | `3` |
| `DNS_LIFETIME_SECONDS` | DNS overall timeout | `4` |
| `SMTP_GLOBAL_CONCURRENCY_LIMIT` | In-process outbound SMTP concurrency cap | `5` |
| `SMTP_DOMAIN_CONCURRENCY_LIMIT` | In-process per-domain SMTP concurrency cap | `1` |
| `SMTP_HELO_NAME` | Hostname sent in SMTP EHLO/HELO | `email-validator.example.invalid` |
| `SMTP_MAIL_FROM` | Envelope sender used for SMTP `MAIL FROM`; blank sends a null reverse-path | blank |
| `API_RATE_LIMIT` | Per-client request limit | `30/min` |
| `CACHE_TTL_TRUE` | Cache TTL for true | `900` |
| `CACHE_TTL_FALSE` | Cache TTL for false | `3600` |
| `CACHE_TTL_UNKNOWN` | Cache TTL for uncertain outcomes | `60` |

## Run tests

```powershell
python manage.py test
```

Tests mock DNS and SMTP for core service scenarios. No live external SMTP probes are required. The suite covers syntax, API key enforcement, invalid requests, DNS outcome mapping, provider policy, SMTP acceptance uncertainty, explicit rejection, and the guarantee that `DATA` is never called.

## Design and limitations

1. Parse and normalize input before external lookups.
2. Query MX records; when MX is absent, check A/AAAA fallback. NXDOMAIN and temporary resolver failures are distinct.
3. If there is no usable mail route, return `false`.
4. If SMTP is not requested, disabled, blocked by provider policy, or in cooldown, return `not_known`.
5. If enabled, make one bounded attempt to one MX host. Do not send `DATA`, guess recipient variants, retry repeatedly, rotate IPs, use proxies, or evade throttling.
6. Treat SMTP recipient acceptance as best-effort evidence for `true`, and treat only clearly identified permanent recipient rejection as evidence for `false`. Temporary and ambiguous outcomes are `not_known`.
7. Cache outcomes with short TTL for uncertain results and log only domain/result/reason/duration/correlation ID.

For live SMTP checks, set `SMTP_HELO_NAME` to a stable hostname for the machine or service. Leave `SMTP_MAIL_FROM` blank to use the SMTP null reverse-path, or set it to a monitored sender address on a domain you control. An invalid sender domain can cause the remote server to reject `MAIL FROM` before the recipient is checked, which correctly returns `not_known` instead of `true`.

### Production hardening recommendations

- Replace local-memory cache with Redis; LocMemCache is process-local and is not a distributed concurrency control.
- Replace the in-process SMTP concurrency guards with shared per-domain/global semaphores and a robust circuit breaker if SMTP is enabled in production.
- Use a managed API-key model with key rotation, per-key quotas, and admin revocation instead of one shared key.
- Use HTTPS, secret management, monitoring/metrics, log retention policies, and a stable outbound identity.
- Consider a queue (Celery) for higher latency or volume, with a job/status endpoint.
- Review provider terms and legal/privacy requirements before any SMTP verification. For high-confidence workflows, use consent-based confirmation emails or a reputable verification provider.

## Assumptions

- Internationalized domains are supported through IDNA normalization; SMTPUTF8 local parts are not supported.
- Business/consumer classification is not returned because domain type alone is not reliable evidence of business identity.
- Catch-all status remains `"unknown"` rather than probing guessed addresses; if catch-all behavior is suspected from provider policy or ambiguity, the result remains `not_known`.
- This is an interview MVP, not a guarantee of mailbox existence or deliverability.
