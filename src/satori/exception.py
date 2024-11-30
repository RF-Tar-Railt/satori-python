class ActionFailed(Exception):
    pass


class BadRequestException(ActionFailed):
    pass


class UnauthorizedException(ActionFailed):
    pass


class ForbiddenException(ActionFailed):
    pass


class NotFoundException(ActionFailed):
    pass


class MethodNotAllowedException(ActionFailed):
    pass


class ServerException(ActionFailed):
    pass


class NetworkError(Exception):
    pass


class ApiNotAvailable(Exception):
    pass
