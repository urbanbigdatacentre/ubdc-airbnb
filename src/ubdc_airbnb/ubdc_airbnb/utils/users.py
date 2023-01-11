from celery.utils.log import get_task_logger
from requests import HTTPError

from app import ubdc_airbnbapi
from app.models import AirBnBResponse, AirBnBResponseTypes

# logger = get_task_logger(__name__)


# def ubdc_response_for_airbnb_user(user_id: int, task_id=None, **kwargs) -> AirBnBResponse:
#     """  Do a GET request for user_id, and store the response into the database.
#
#     :returns AirBnBResponse
#     """
#
