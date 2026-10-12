from unittest.mock import patch
from django.test import override_settings
from rest_framework.test import APITestCase
from django.core.cache import cache


@override_settings(API_KEY="test-secret")
class EmailValidationAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = "/api/v1/email/validate/"
        self.client.credentials(HTTP_X_API_KEY="test-secret")

    def test_invalid_syntax_returns_false(self):
        response = self.client.post(self.url, {"email": "not-an-email"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "false")
        self.assertEqual(response.data["reason_code"], "INVALID_SYNTAX")

    def test_missing_email_is_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_missing_api_key_is_401(self):
        self.client.credentials()
        response = self.client.post(
            self.url, {"email": "person@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    @patch(
        "validator.services.engine.check_mail_route",
        return_value=(True, "MX_RECORD_FOUND"),
    )
    def test_dns_route_without_smtp_is_not_known(self, mocked_dns):
        response = self.client.post(
            self.url, {"email": "person@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "not_known")
        self.assertEqual(response.data["reason_code"], "SMTP_NOT_REQUESTED")
        self.assertFalse(response.data["smtp_checked"])

    @patch(
        "validator.services.engine.check_mail_route",
        return_value=(False, "DOMAIN_NOT_FOUND"),
    )
    def test_nonexistent_domain_maps_false(self, mocked_dns):
        cache.clear()

        response = self.client.post(
            self.url,
            {"email": "person@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mocked_dns.assert_called_once_with("example.com")
        self.assertEqual(response.data["result"], "false")
        self.assertEqual(response.data["reason_code"], "DOMAIN_NOT_FOUND")

    @override_settings(SMTP_CHECKS_ENABLED=True, GLOBAL_SMTP_ENABLED=True)
    @patch("validator.services.engine.verify_recipient")
    @patch("validator.services.engine.smtp_allowed", return_value=(True, "SMTP_POLICY_ALLOWED"))
    @patch(
        "validator.services.engine.check_mail_route",
        return_value=(True, "ADDRESS_RECORD_FALLBACK"),
    )
    def test_smtp_acceptance_maps_true(self, mocked_dns, mocked_policy, mocked_smtp):
        mocked_smtp.return_value = ("true", "SMTP_RECIPIENT_ACCEPTED")

        response = self.client.post(
            self.url,
            {"email": "person@example.com", "check_smtp": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], "true")
        self.assertEqual(response.data["reason_code"], "SMTP_RECIPIENT_ACCEPTED")
        self.assertTrue(response.data["smtp_checked"])
        mocked_smtp.assert_called_once_with("example.com", "person@example.com")
