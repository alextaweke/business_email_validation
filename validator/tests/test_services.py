from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from validator.services.syntax import normalize_and_validate
from validator.services.dns_checks import DNSCheckError
from validator.services.smtp_checks import provider_policy_allows_smtp, verify_recipient

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
    def test_major_consumer_provider_skips_smtp(self):
        self.assertFalse(provider_policy_allows_smtp("gmail.com"))
    def test_custom_domain_may_be_eligible(self):
        self.assertTrue(provider_policy_allows_smtp("example.org"))

class SMTPTests(SimpleTestCase):
    @patch("validator.services.smtp_checks.smtplib.SMTP")
    def test_rcpt_acceptance_is_true_and_never_data(self, smtp_class):
        smtp = smtp_class.return_value
        smtp.connect.return_value = (220, b"ready")
        smtp.ehlo.return_value = (250, b"hello")
        smtp.mail.return_value = (250, b"sender ok")
        smtp.rcpt.return_value = (250, b"accepted")
        result, reason = verify_recipient("mx.example.org", "person@example.org")
        self.assertEqual(result, "true")
        self.assertEqual(reason, "SMTP_RECIPIENT_ACCEPTED")
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
