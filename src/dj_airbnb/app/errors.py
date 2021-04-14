

class UBDCError(Exception):
    description = 'A general error from the UBDC application. Not retryable.'

    @property
    def name(self):
        return self.__class__.__name__


class UBDCCoordinateError(UBDCError):
    description = 'Coordinate error of some kind.'


class UBDCRetriableError(UBDCError):
    description = 'An error that if caught inside a Task, it will be retried.'


class UBDCAsyncTaskDoesNotExist(UBDCError):
    description = 'Could not find this task.'
