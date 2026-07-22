"""Global request body-size limit middleware.

Rejects requests whose declared ``Content-Length`` exceeds a configurable
maximum with HTTP 413 (Payload Too Large) BEFORE the body is consumed, so a
single oversized upload cannot force the API to buffer a multi-GB body into
memory (every upload handler does ``await file.read()``) and OOM.

Applied once at the app level it covers EVERY route — template and document
uploads and anything else — so individual routers need no per-endpoint guard.

Limitation: ``Content-Length`` can be absent, e.g. with chunked
``Transfer-Encoding``. This middleware is the first-line defense against the
common oversized-upload case where clients DO send ``Content-Length``. A fully
robust cap would additionally bound the streamed body read as it is received;
the matching proxy limit (nginx ``client_max_body_size``) backs this up in the
production path.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BodySizeLimitMiddleware:
    """Pure-ASGI middleware that rejects requests declaring an oversized body.

    Implemented at the raw ASGI layer (not ``BaseHTTPMiddleware``) so the 413 is
    returned before the downstream app touches the request body. Requests with
    no body — GET, OPTIONS/preflight — carry no ``Content-Length`` (or a
    ``Content-Length: 0``) and pass through untouched.
    """

    def __init__(self, app: ASGIApp, max_upload_bytes: int) -> None:
        self._app = app
        self._max_upload_bytes = max_upload_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only HTTP requests carry a body; let websockets/lifespan pass through.
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        content_length = self._content_length(scope)
        if content_length is not None and content_length > self._max_upload_bytes:
            response = JSONResponse(
                status_code=413,
                content={
                    "error": "payload_too_large",
                    "detail": (
                        f"Request body of {content_length} bytes exceeds the "
                        f"maximum allowed size of {self._max_upload_bytes} bytes."
                    ),
                    "max_upload_bytes": self._max_upload_bytes,
                },
            )
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        """Return the request's ``Content-Length`` as an int, or None when the
        header is absent or not a valid integer."""
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None
