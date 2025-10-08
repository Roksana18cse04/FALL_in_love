from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def setup_global_error_handlers(app: FastAPI):
    """Attach global error handlers to a FastAPI app"""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_str = str(exc)
        print(f"[GLOBAL HANDLER] Error on {request.url}: {error_str}")

        # Handle OpenAI quota exceeded
        if "429" in error_str or "exceeded your current quota" in error_str.lower():
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "error_type": "quota_exceeded",
                    "message": "OpenAI API quota limit exceeded. Please check your billing details.",
                    "action_required": "Upgrade your plan or wait for quota reset",
                    "docs": "https://platform.openai.com/docs/guides/error-codes/api-errors",
                    "path": str(request.url.path)
                }
            )

        # Handle OpenAI connection issues
        if "OpenAI API failed" in error_str or "connection to: OpenAI" in error_str:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "error_type": "api_unavailable",
                    "message": "OpenAI API service is temporarily unavailable",
                    "action_required": "Please try again later",
                    "path": str(request.url.path)
                }
            )

        # Handle rate limit
        if "rate limit" in error_str.lower():
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "error_type": "rate_limit",
                    "message": "API rate limit exceeded",
                    "action_required": "Please wait before making another request",
                    "path": str(request.url.path)
                }
            )

        # Handle Weaviate connection
        if "weaviate" in error_str.lower() and "connect" in error_str.lower():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "error_type": "database_unavailable",
                    "message": "Database service is temporarily unavailable",
                    "path": str(request.url.path)
                }
            )

        # Default
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_type": "internal_error",
                "message": "An unexpected error occurred",
                "details": error_str if getattr(app, "debug", False) else "Contact support for details",
                "path": str(request.url.path)
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "message": exc.detail,
                "path": str(request.url.path)
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error_type": "validation_error",
                "message": "Invalid request data",
                "details": exc.errors(),
                "path": str(request.url.path)
            }
        )
