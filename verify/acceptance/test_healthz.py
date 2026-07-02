"""Health check.

GET /healthz → 200 {"status": "ok"}
"""

from verify.acceptance.conftest import assert_200


def test_healthz_returns_ok(client):
    """The health check endpoint responds with 200 and status 'ok'."""
    r = client.get("/healthz")
    body = assert_200(r)
    assert body["status"] == "ok"
