from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        from app import signals
        dir(signals)  # does nothing; but my IDE wants to remove it if I don't wrap it.
