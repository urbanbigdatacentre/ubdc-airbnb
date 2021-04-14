import os
import warnings
from airbnbapi.api import Api

if os.getenv('AIRBNB_PROXY') is None:
    message = f"No proxy is set. Not using a proxy could lead Airbnb QoS to be activated."
    warnings.warn(message)
else:
    print(f'proxy set: {os.getenv("AIRBNB_PROXY")}')


ubdc_airbnbapi = Api(proxy=os.getenv("AIRBNB_PROXY", None))
