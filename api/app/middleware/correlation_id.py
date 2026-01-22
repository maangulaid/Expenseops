from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.logging import correlation_id_var
import uuid


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract or generate correlation ID for request tracing.

    Flow:
    1. Check for X-Correlation-ID header from client
    2. Generate UUID if not provided
    3. Store in request.state for route handlers
    4. Set in context variable for logging
    5. Add to response headers

    Usage in routes:
        @router.get("/receipts")
        def list_receipts(request: Request):
            correlation_id = request.state.correlation_id
            # Use correlation_id for logging, passing to Celery, etc.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state
        request.state.correlation_id = correlation_id

        # Set in context variable for logging
        correlation_id_var.set(correlation_id)

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers['X-Correlation-ID'] = correlation_id

        return response


def get_correlation_id(request: Request) -> str:
    """
    Dependency to get correlation ID from request.

    Usage:
        @router.post("/receipts")
        async def upload_receipt(
            correlation_id: str = Depends(get_correlation_id)
        ):
            # Use correlation_id
    """
    return getattr(request.state, 'correlation_id', str(uuid.uuid4()))
