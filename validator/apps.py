from django.apps import AppConfig


class ValidatorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "validator"

    def ready(self):
        from . import schema  # noqa: F401
