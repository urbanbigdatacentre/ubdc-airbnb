from django.conf import settings

from .airbnb_api import AirbnbApi

airbnb_client = AirbnbApi(proxy=settings.AIRBNB_PROXY, extra_headers=settings.EXTRA_HEADERS)

__all__ = [airbnb_client]
