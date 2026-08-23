"""Centralized error handling for the application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str = "An unexpected error occurred", status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, status_code=404)


class ValidationError(AppError):
    """Input validation failure."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message=message, status_code=422)


def register_error_handlers(app: FastAPI) -> None:
    """Attach centralized exception handlers to the FastAPI app."""

    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
