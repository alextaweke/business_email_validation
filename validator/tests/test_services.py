import socket
from unittest.mock import patch
import dns.exception
from django.test import SimpleTestCase, override_settings
from django.core.cache import cache
from validator.services.syntax import normalize_and_validate
from validator.services.dns_checks import DNSCheckError, check_mail_route
from validator.services.policy import record_smtp_failure, smtp_allowed
from validator.services.smtp_checks import provider_policy_allows_smtp, verify_recipient


class FakeAnswer:
    def __init__(self, has_records):
        self.rrset = ["record"] if has_records else None

    def __len__(self):
        return 1 if self.rrset else 0


class SyntaxTests(SimpleTestCase):
    def test_invalid_email(self):
        valid, normalized, reason = normalize_and_validate("bad")
        self.assertFalse(valid)
        self.assertIsNone(normalized)
        self.assertEqual(reason, "INVALID_SYNTAX")

    def test_domain_normalized_lowercase(self):
        valid, normalized, reason = normalize_and_validate("Person@EXAMPLE.COM")
        self.assertTrue(valid)
        self.assertEqual(normalized.split("@", 1)[1], "example.com")


class PolicyTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_major_consumer_provider_skips_smtp(self):
        self.assertFalse(provider_policy_allows_smtp("gmail.com"))

    def test_custom_domain_may_be_eligible(self):
        self.assertTrue(provider_policy_allows_smtp("example.org"))

    @override_settings(
        SMTP_CHECKS_ENABLED=True,
        GLOBAL_SMTP_ENABLED=True,
        SMTP_DOMAIN_COOLDOWN_SECONDS=1,
    )
    def test_transient_smtp_failure_sets_domain_cooldown(self):
        record_smtp_failure("example.org", "SMTP_TIMEOUT")
        allowed, reason = smtp_allowed("example.org")
        self.assertFalse(allowed)
        self.assertEqual(reason, "SMTP_DOMAIN_COOLDOWN")


class DNSTests(SimpleTestCase):
    @patch("validator.services.dns_checks.dns.resolver.Resolver")
    def test_mx_record_found(self, resolver_class):
        resolver = resolver_class.return_value
        resolver.resolve.return_value = FakeAnswer(True)

        has_route, reason = check_mail_route("example.org")

        self.assertTrue(has_route)
        self.assertEqual(reason, "MX_RECORD_FOUND")
        resolver.resolve.assert_called_once_with(
            "example.org", "MX", raise_on_no_answer=False
        )

    @patch("validator.services.dns_checks.dns.resolver.Resolver")
    def test_address_record_fallback_when_no_mx(self, resolver_class):
        resolver = resolver_class.return_value
        resolver.resolve.side_effect = [
            FakeAnswer(False),
            FakeAnswer(True),
        ]

        has_route, reason = check_mail_route("example.org")

        self.assertTrue(has_route)
        self.assertEqual(reason, "ADDRESS_RECORD_FALLBACK")

    @patch("validator.services.dns_checks.dns.resolver.Resolver")
    def test_dns_timeout_is_temporary_failure(self, resolver_class):
        resolver = resolver_class.return_value
        resolver.resolve.side_effect = dns.exception.Timeout()

        with self.assertRaises(DNSCheckError) as context:
            check_mail_route("example.org")

        self.assertEqual(context.exception.reason_code, "DNS_TEMPORARY_FAILURE")


class SMTPTests(SimpleTestCase):
    @override_settings(SMTP_MAIL_FROM="probe@example.org")
    @patch("validator.services.smtp_checks.smtplib.SMTP")
    def test_rcpt_acceptance_is_true_and_uses_configured_sender(self, smtp_class):
        smtp = smtp_class.return_value
        smtp.connect.return_value = (220, b"ready")
        smtp.ehlo.return_value = (250, b"hello")
        smtp.mail.return_value = (250, b"sender ok")
        smtp.rcpt.return_value = (250, b"accepted")
        result, reason = verify_recipient("mx.example.org", "person@example.org")
        self.assertEqual(result, "true")
        self.assertEqual(reason, "SMTP_RECIPIENT_ACCEPTED")
        smtp.mail.assert_called_once_with("probe@example.org")
        smtp.data.assert_not_called()
        smtp.quit.assert_called_once()

    @patch("validator.services.smtp_checks.smtplib.SMTP")
    def test_clear_550_rejection(self, smtp_class):
        smtp = smtp_class.return_value
        smtp.connect.return_value = (220, b"ready")
        smtp.ehlo.return_value = (250, b"hello")
        smtp.mail.return_value = (250, b"sender ok")
        smtp.rcpt.return_value = (550, b"User unknown")
        result, reason = verify_recipient("mx.example.org", "bad@example.org")
        self.assertEqual(result, "false")
        self.assertEqual(reason, "SMTP_RECIPIENT_REJECTED")
        smtp.data.assert_not_called()

    @patch("validator.services.smtp_checks.smtplib.SMTP")
    def test_temporary_smtp_response_is_not_known(self, smtp_class):
        smtp = smtp_class.return_value
        smtp.connect.return_value = (220, b"ready")
        smtp.ehlo.return_value = (250, b"hello")
        smtp.mail.return_value = (250, b"sender ok")
        smtp.rcpt.return_value = (450, b"try again later")
        result, reason = verify_recipient("mx.example.org", "person@example.org")
        self.assertEqual(result, "not_known")
        self.assertEqual(reason, "SMTP_TEMPORARY_FAILURE")
        smtp.data.assert_not_called()

    @patch("validator.services.smtp_checks.smtplib.SMTP")
    def test_ambiguous_550_is_not_known(self, smtp_class):
        smtp = smtp_class.return_value
        smtp.connect.return_value = (220, b"ready")
        smtp.ehlo.return_value = (250, b"hello")
        smtp.mail.return_value = (250, b"sender ok")
        smtp.rcpt.return_value = (550, b"blocked by policy")

        result, reason = verify_recipient("mx.example.org", "person@example.org")

        self.assertEqual(result, "not_known")
        self.assertEqual(reason, "SMTP_AMBIGUOUS")
        smtp.data.assert_not_called()

    @patch("validator.services.smtp_checks.smtplib.SMTP")
    def test_smtp_timeout_is_not_known(self, smtp_class):
        smtp = smtp_class.return_value
        smtp.connect.side_effect = socket.timeout()

        result, reason = verify_recipient("mx.example.org", "person@example.org")

        self.assertEqual(result, "not_known")
        self.assertEqual(reason, "SMTP_TIMEOUT")
        smtp.data.assert_not_called()
