from django.apps import AppConfig


class UbdcAirbnbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "app"
    name = "ubdc_airbnb"

    def ready(self):
        from ubdc_airbnb import signals  # noqa
