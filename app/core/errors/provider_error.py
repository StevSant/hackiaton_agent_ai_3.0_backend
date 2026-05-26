from app.core.errors.app_error import AppError


class ProviderError(AppError):
    code = "provider_error"
    status_code = 502
    message = "Upstream provider error"
