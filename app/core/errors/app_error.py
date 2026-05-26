class AppError(Exception):
    code: str = "app_error"
    status_code: int = 500
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)
