from django.apps import AppConfig


class ItsystemsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "itsystems"
    verbose_name = "IT Systems Register"

    def ready(self):
        from . import signals
