from django.apps import AppConfig
from importlib import import_module


class MarketplaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "marketplace"

    def ready(self):
        import_module(f"{self.name}.signals")
