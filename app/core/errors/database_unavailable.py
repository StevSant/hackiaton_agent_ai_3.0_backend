from app.core.errors.app_error import AppError


class DatabaseUnavailable(AppError):
    code = "database_unavailable"
    status_code = 503
    message = "Database temporarily unavailable"
