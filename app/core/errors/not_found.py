from app.core.errors.app_error import AppError


class NotFound(AppError):
    code = "not_found"
    status_code = 404
    message = "Resource not found"
