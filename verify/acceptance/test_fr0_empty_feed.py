"""FR0: Feed returns empty results when database has no videos.

This test MUST run FIRST (alphabetically) before any FR1 tests create
videos, because the database starts empty from Alembic migrations + clean
Docker Compose volumes.

GET /api/v1/feed → 200 {videos: [], next_cursor: null}
"""

from verify.acceptance.conftest import get_feed


def test_feed_empty_database(client):
    """Feed returns empty list when no videos exist (not a crash)."""
    body = get_feed(client)
    assert body["videos"] == []
    assert body.get("next_cursor") is None
