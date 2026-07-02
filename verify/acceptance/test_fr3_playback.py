"""FR3: Play videos instantly on swipe with adaptive streaming.

GET /api/v1/videos/{id}/manifest → 200 with valid XML (DASH MPD)
GET /api/v1/segments/{id} → 200 with video/mp2t content type
Manifest for video with no segments → 404
Segment not found → 404
"""

from verify.acceptance.conftest import (
    add_segments,
    assert_201,
    assert_404,
    create_user,
    create_video,
    get_manifest,
)


def test_manifest_returns_xml(client):
    """Manifest endpoint returns valid XML content."""
    user = create_user(client)
    video = create_video(client, user["user_id"])
    add_segments(client, video["video_id"])

    r = get_manifest(client, video["video_id"])
    assert r.status_code == 200
    content_type = r.headers.get("content-type", "")
    is_xml = "xml" in content_type.lower() or r.text.strip().startswith("<?xml")
    assert is_xml, f"Expected XML, got Content-Type={content_type}, body={r.text[:100]}"


def test_manifest_contains_adaptation_sets(client):
    """Manifest includes AdaptationSet elements for each quality level."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    segments = [
        {
            "quality": "720p",
            "segment_index": 0,
            "file_path": "/mock/720p_0.ts",
            "duration_seconds": 5,
            "size_bytes": 500000,
        },
        {
            "quality": "540p",
            "segment_index": 0,
            "file_path": "/mock/540p_0.ts",
            "duration_seconds": 5,
            "size_bytes": 400000,
        },
    ]
    add_segments(client, video["video_id"], segments=segments)

    r = get_manifest(client, video["video_id"])
    assert r.status_code == 200
    text = r.text

    # DASH manifest should contain AdaptationSet elements
    assert "AdaptationSet" in text, f"Manifest missing AdaptationSet: {text[:200]}"
    assert "720p" in text


def test_manifest_no_segments_404(client):
    """Requesting manifest for a video with no segments returns 404."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    r = client.get(f"/api/v1/videos/{video['video_id']}/manifest")
    assert_404(r)


def test_segment_not_found_404(client):
    """Requesting a non-existent segment returns 404."""
    fake_segment_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/segments/{fake_segment_id}")
    assert_404(r)


def test_add_segments_201(client):
    """Adding segments to a video returns 201 with segment count."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    segments = [
        {
            "quality": "720p",
            "segment_index": 0,
            "file_path": "/mock/a.ts",
            "duration_seconds": 5,
            "size_bytes": 100000,
        },
        {
            "quality": "720p",
            "segment_index": 1,
            "file_path": "/mock/b.ts",
            "duration_seconds": 5,
            "size_bytes": 100000,
        },
        {
            "quality": "540p",
            "segment_index": 0,
            "file_path": "/mock/c.ts",
            "duration_seconds": 5,
            "size_bytes": 80000,
        },
    ]

    r = client.post(
        f"/api/v1/videos/{video['video_id']}/segments",
        json={"segments": segments},
    )
    body = assert_201(r)
    assert body["video_id"] == video["video_id"]
    assert body.get("segment_count", 0) >= len(segments)


def test_add_segments_unknown_video_404(client):
    """Adding segments to a non-existent video returns 404."""
    fake_video_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        f"/api/v1/videos/{fake_video_id}/segments",
        json={
            "segments": [
                {
                    "quality": "720p",
                    "segment_index": 0,
                    "file_path": "/x.ts",
                    "duration_seconds": 5,
                    "size_bytes": 1000,
                }
            ]
        },
    )
    assert_404(r)


def test_add_segments_empty_list_422(client):
    """Adding an empty segment list returns 422."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    r = client.post(
        f"/api/v1/videos/{video['video_id']}/segments",
        json={"segments": []},
    )
    assert r.status_code == 422
