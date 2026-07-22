"""Unit tests for BodySizeLimitMiddleware (global request body-size cap).

These build a minimal Starlette app wrapping ONLY the middleware under test, so
they never touch the DB-probing TierPreloadMiddleware and run fast.
"""

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.presentation.middleware.body_size_limit import BodySizeLimitMiddleware

MAX_BYTES = 100  # tiny cap so tests never allocate large buffers


def _build_client() -> tuple[TestClient, dict]:
    """Return a TestClient over a minimal app plus a dict tracking whether the
    downstream handler was reached."""
    reached = {"count": 0}

    async def upload(request):
        reached["count"] += 1
        body = await request.body()
        return JSONResponse({"received": len(body)})

    async def ping(request):
        return PlainTextResponse("pong")

    app = Starlette(
        routes=[
            Route("/upload", upload, methods=["POST", "OPTIONS"]),
            Route("/ping", ping, methods=["GET"]),
        ]
    )
    app.add_middleware(BodySizeLimitMiddleware, max_upload_bytes=MAX_BYTES)
    return TestClient(app), reached


def test_oversized_content_length_rejected_before_handler():
    """A request whose Content-Length exceeds the cap gets 413 and never
    reaches the downstream handler."""
    client, reached = _build_client()

    response = client.post("/upload", content=b"x" * (MAX_BYTES + 1))

    assert response.status_code == 413
    body = response.json()
    assert body["error"] == "payload_too_large"
    assert body["max_upload_bytes"] == MAX_BYTES
    assert reached["count"] == 0  # handler never invoked → body never read


def test_body_at_limit_passes():
    """A body exactly at the cap is allowed through to the handler."""
    client, reached = _build_client()

    response = client.post("/upload", content=b"x" * MAX_BYTES)

    assert response.status_code == 200
    assert response.json()["received"] == MAX_BYTES
    assert reached["count"] == 1


def test_small_request_passes():
    """A normal small upload is unaffected."""
    client, reached = _build_client()

    response = client.post("/upload", content=b"hello")

    assert response.status_code == 200
    assert response.json()["received"] == 5
    assert reached["count"] == 1


def test_options_preflight_passes_untouched():
    """An OPTIONS/preflight request (no body) is never rejected as too large."""
    client, _ = _build_client()

    response = client.options("/upload")

    assert response.status_code != 413


def test_get_without_body_passes():
    """A GET with no body is unaffected by the size cap."""
    client, reached = _build_client()

    response = client.get("/ping")

    assert response.status_code == 200
    assert response.text == "pong"
    assert reached["count"] == 0
