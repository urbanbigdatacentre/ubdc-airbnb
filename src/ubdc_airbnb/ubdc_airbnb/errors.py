class UBDCError(Exception):
    description = "A general error from the UBDC application"

    @property
    def name(self):
        return self.__class__.__name__


class UBDCCoordinateError(UBDCError):
    description = "Coordinate error of some kind."


class UBDCRetriableError(UBDCError):
    description = "An error that if caught inside a Task, it will be retried."


class UBDCResourceIsNotAvailable(UBDCError):
    description = "The resource was denied by remote"


class UBDCAsyncTaskDoesNotExist(UBDCError):
    description = "Could not find this task."


class AuthError(Exception):
    """
    Authentication error
    """

    pass


class VerificationError(AuthError):
    """
    Authentication error
    """

    pass


class MissingParameterError(Exception):
    """
    Missing parameter error
    """

    pass


class MissingAccessTokenError(MissingParameterError):
    """
    Missing access token error
    """

    pass


class NoBookingDatesError(Exception):
    """
    Unable to identify valid dates to ask for a booking quote.
    """

    pass
