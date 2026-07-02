"""Shared fixtures and helpers for the TikTok/Reels MVP black-box acceptance suite.

These tests do NOT import `src.tiktok_reels`. They talk to the running system
via HTTP at API_BASE_URL. Test isolation is achieved through unique
identifiers per test — no database clearing required.
"""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url():
    return API_BASE_URL


@pytest.fixture(scope="session")
def client(base_url):
    """Session-scoped httpx client for the entire acceptance run."""
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture
def fresh_uuid():
    """Unique UUID per test for isolation."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_status(r, expected_status):
    """Assert status and return parsed JSON."""
    assert (
        r.status_code == expected_status
    ), f"Expected {expected_status}, got {r.status_code}: {r.text}"
    if r.status_code == 204:
        return None
    return r.json()


def assert_200(r):
    return assert_status(r, 200)


def assert_201(r):
    return assert_status(r, 201)


def assert_204(r):
    return assert_status(r, 204)


def assert_400(r):
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    return r.json()


def assert_404(r):
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    return r.json()


def assert_409(r):
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    return r.json()


def assert_422(r):
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Setup helpers — create entities via HTTP
# ---------------------------------------------------------------------------


def create_user(client, username=None):
    """Create a user and return the parsed response body (201)."""
    if username is None:
        username = f"user-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/users", json={"username": username})
    return assert_201(r)


def create_video(
    client,
    author_id,
    caption="test video",
    sound_name="original sound",
    duration_ms=15000,
    hashtags=None,
):
    """Create a video and return the parsed response body (201)."""
    body = {
        "author_id": author_id,
        "caption": caption,
        "sound_name": sound_name,
        "duration_ms": duration_ms,
    }
    if hashtags is not None:
        body["hashtags"] = hashtags
    r = client.post("/api/v1/videos", json=body)
    return assert_201(r)


def add_segments(client, video_id, segments=None):
    """Add mock video segments to a video and return the parsed response body (201)."""
    if segments is None:
        segments = [
            {
                "quality": "720p",
                "segment_index": 0,
                "file_path": "/mock/segment_720p_0.ts",
                "duration_seconds": 5,
                "size_bytes": 524288,
            },
            {
                "quality": "720p",
                "segment_index": 1,
                "file_path": "/mock/segment_720p_1.ts",
                "duration_seconds": 5,
                "size_bytes": 524288,
            },
            {
                "quality": "540p",
                "segment_index": 0,
                "file_path": "/mock/segment_540p_0.ts",
                "duration_seconds": 5,
                "size_bytes": 393216,
            },
            {
                "quality": "360p",
                "segment_index": 0,
                "file_path": "/mock/segment_360p_0.ts",
                "duration_seconds": 5,
                "size_bytes": 262144,
            },
        ]
    r = client.post(
        f"/api/v1/videos/{video_id}/segments",
        json={"segments": segments},
    )
    return assert_201(r)


def like_video(client, video_id, user_id):
    """Like a video and return the parsed response body (200)."""
    r = client.post(
        f"/api/v1/videos/{video_id}/like",
        json={"user_id": user_id},
    )
    return assert_200(r)


def unlike_video(client, video_id, user_id):
    """Unlike a video and return the parsed response body (200)."""
    r = client.request(
        "DELETE",
        f"/api/v1/videos/{video_id}/like",
        json={"user_id": user_id},
    )
    return assert_200(r)


def post_comment(client, video_id, user_id, text="nice video!"):
    """Post a comment and return the parsed response body (201)."""
    r = client.post(
        f"/api/v1/videos/{video_id}/comments",
        json={"user_id": user_id, "text": text},
    )
    return assert_201(r)


def follow_user(client, followee_id, follower_id):
    """Follow a user. Returns 200 with status."""
    r = client.post(
        f"/api/v1/users/{followee_id}/follow",
        params={"follower_id": follower_id},
    )
    return assert_200(r)


def unfollow_user(client, followee_id, follower_id):
    """Unfollow a user and return the parsed response body (200)."""
    r = client.delete(
        f"/api/v1/users/{followee_id}/follow",
        params={"follower_id": follower_id},
    )
    return assert_200(r)


def get_feed(client, cursor=None):
    """Fetch the trending feed."""
    params = {}
    if cursor:
        params["cursor"] = cursor
    r = client.get("/api/v1/feed", params=params)
    return assert_200(r)


def get_video_detail(client, video_id):
    """Fetch video detail."""
    r = client.get(f"/api/v1/videos/{video_id}")
    return assert_200(r)


def get_manifest(client, video_id):
    """Fetch ABR manifest for a video (returns raw response — XML)."""
    r = client.get(f"/api/v1/videos/{video_id}/manifest")
    return r


def get_segment(client, segment_id):
    """Fetch a video segment (raw bytes)."""
    r = client.get(f"/api/v1/segments/{segment_id}")
    return r


def get_comments(client, video_id, cursor=None):
    """List comments for a video."""
    params = {}
    if cursor:
        params["cursor"] = cursor
    r = client.get(f"/api/v1/videos/{video_id}/comments", params=params)
    return assert_200(r)


def search_content(client, query, search_type="all", cursor=None):
    """Full-text search."""
    params = {"q": query, "type": search_type}
    if cursor:
        params["cursor"] = cursor
    r = client.get("/api/v1/search", params=params)
    return assert_200(r)


def healthz(client):
    """Hit the health check."""
    r = client.get("/healthz")
    return assert_200(r)
