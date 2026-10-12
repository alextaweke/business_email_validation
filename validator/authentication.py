import secrets
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class APIKeyUser:
    """Minimal authenticated principal for API-key callers."""
    is_authenticated = True
    is_anonymous = False
    username = "api-key-client"
    pk = "api-key-client"

    def __str__(self):
        return self.username

class APIKeyAuthentication(BaseAuthentication):
    keyword = "X-API-Key"

    def authenticate(self, request):
        supplied = request.headers.get(self.keyword)
        if not supplied:
            return None
        expected = settings.API_KEY
        if not expected or expected == "replace-this-api-key":
            raise AuthenticationFailed("API key is not configured by the service operator.")
        if not secrets.compare_digest(supplied, expected):
            raise AuthenticationFailed("Invalid API key.")
        return (APIKeyUser(), supplied)

    def authenticate_header(self, request):
        return self.keyword
