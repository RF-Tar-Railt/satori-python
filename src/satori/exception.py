class ActionFailed(Exception):
    CODE = 400
    pass


class BadRequestException(ActionFailed):
    CODE = 400
    pass


class UnauthorizedException(ActionFailed):
    CODE = 401
    pass


class ForbiddenException(ActionFailed):
    CODE = 403
    pass


class NotFoundException(ActionFailed):
    CODE = 404
    pass


class MethodNotAllowedException(ActionFailed):
    CODE = 405
    pass


class ServerException(ActionFailed):
    CODE = 500
    pass


class NetworkError(Exception):
    pass


class ApiNotAvailable(Exception):
    pass
