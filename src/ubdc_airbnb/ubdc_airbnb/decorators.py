from functools import wraps
from logging import Logger
from typing import Any, Callable

from celery.utils.log import get_task_logger
from requests.exceptions import HTTPError, ProxyError

from ubdc_airbnb.errors import UBDCRetriableError, UBDCError

logger: Logger = get_task_logger(__name__)


# TODO:Refactor convert the following to match/switch


# inspired from:
# https://github.com/DHI-GRAS/terracotta/blob/5ceb6ad217d6eae705b3bc6e1358aeb3f565e38c/terracotta/server/flask_api.py#L43
def convert_exceptions(fun: Callable):
    """Converts exceptions to appropriate retryable-or-not exception"""

    @wraps(fun)
    def convert_exceptions_wrap(*args: Any, **kwargs: Any):
        """Convert Exceptions to something known"""
        try:
            return fun(*args, **kwargs)
        except HTTPError as exc:
            status_code = exc.response.status_code

            message = (
                f"HTTPError: {status_code} when trying to contact Airbnb Resource at {exc.response.url}. "
                f"Params were: \nFunName: {fun.__name__} ,  \nargs: {args}, \nkwargs: {kwargs}.\n"
                f"Headers: {exc.request.headers}"
            )
            logger.info(message)

            # Exception Chaining, PEP 3134,
            # https://stackoverflow.com/a/792163/528025

            # 429 Too Many Request
            if status_code == 429:
                raise UBDCRetriableError("too-many-requests") from exc
            # 407 Proxy Authentication Required
            elif status_code == 407:
                raise UBDCError("proxy-error") from exc

            # 403 Resource Unavailable
            elif status_code == 403:
                raise UBDCError("resource-unavailable")

            else:
                raise UBDCError("unhandled-exception") from exc

        except ProxyError as exc:
            message = f"PROXY-ERROR when trying to fetch Airbnb Resource." f"Params were args: {args}, kwargs: {kwargs}"
            logger.info(message)
            raise UBDCRetriableError("proxy-error") from exc

    return convert_exceptions_wrap
