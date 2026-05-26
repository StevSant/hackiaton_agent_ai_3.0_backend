from app.core.errors.app_error import AppError


class ValidationFailed(AppError):
    code = "validation_failed"
    status_code = 422
    message = "Validation failed"
