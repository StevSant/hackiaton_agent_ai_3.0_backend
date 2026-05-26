from app.core.errors.app_error import AppError


class Unauthorized(AppError):
    code = "unauthorized"
    status_code = 401
    message = "Authentication required"
