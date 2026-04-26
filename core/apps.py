from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.models   # noqa: F401 — ensures User profile signal is registered
        import core.signals  # noqa: F401 — ensures tournament stage progression signal is registered
