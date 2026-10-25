from types import SimpleNamespace


class StorageError(Exception):
    """Base exception for storage operations with HTTP compatible status codes."""

    def __init__(self, code: str, message: str, status_code: int = 500) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status_code = status_code

    @property
    def response(self) -> SimpleNamespace:
        return SimpleNamespace(status_code=self.status_code)


class StorageNotFoundError(StorageError):
    def __init__(self, code: str = "not_found", message: str = "Resource not found") -> None:
        super().__init__(code=code, message=message, status_code=404)


class StorageConflictError(StorageError):
    def __init__(self, code: str = "conflict", message: str = "Conflict") -> None:
        super().__init__(code=code, message=message, status_code=409)


class StorageLimitExceededError(StorageError):
    def __init__(self, code: str = "limit_exceeded", message: str = "Limit exceeded") -> None:
        super().__init__(code=code, message=message, status_code=413)
