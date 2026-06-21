class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=404,
        )


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=409)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message=message, status_code=403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, status_code=401)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=422)


class LLMProviderError(AppError):
    def __init__(self, message: str, provider: str):
        super().__init__(
            message=message,
            status_code=502,
            detail={"provider": provider},
        )
