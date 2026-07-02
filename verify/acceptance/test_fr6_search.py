"""FR6: Search videos by hashtag, sound, or creator handle.

GET /api/v1/search?q=<term>&type=hashtag → results
GET /api/v1/search?q=<term>&type=sound → results
GET /api/v1/search?q=<term>&type=user → results
GET /api/v1/search?q=<term>&type=all → results across all types
Empty query → 200 empty results
Results have expected structure
"""

from verify.acceptance.conftest import (
    create_user,
    create_video,
    search_content,
)


def test_search_by_hashtag(client):
    """Searching by hashtag name returns matching results."""
    user = create_user(client)
    create_video(client, user["user_id"], caption="dance video", hashtags=["viral", "dance"])

    body = search_content(client, "dance", search_type="hashtag")
    assert "results" in body
    # Should find at least the video tagged with 'dance'
    assert len(body["results"]) >= 1


def test_search_by_caption_keyword(client):
    """Searching by caption keyword returns matching videos."""
    user = create_user(client)
    create_video(client, user["user_id"], caption="sunset timelapse amazing")
    create_video(client, user["user_id"], caption="cooking recipe")

    body = search_content(client, "sunset", search_type="all")
    assert len(body["results"]) >= 1

    captions_found = False
    for item in body["results"]:
        if item.get("type") == "video" and "sunset" in str(item).lower():
            captions_found = True
    assert captions_found, f"Should find 'sunset' in results: {body['results']}"


def test_search_by_username(client):
    """Searching by username returns matching users."""
    user = create_user(client, username="dance_king_2024")

    body = search_content(client, "dance_king", search_type="user")
    assert "results" in body
    assert len(body["results"]) >= 1


def test_search_by_sound(client):
    """Searching by sound name returns matching results."""
    user = create_user(client)
    create_video(client, user["user_id"], caption="my video", sound_name="cool remix beat")

    body = search_content(client, "remix", search_type="sound")
    assert "results" in body
    assert len(body["results"]) >= 1


def test_search_empty_query(client):
    """Searching with an empty query returns empty results (not an error)."""
    body = search_content(client, "", search_type="all")
    assert body["results"] == []


def test_search_result_structure(client):
    """Each search result has a type and relevant fields."""
    user = create_user(client, username="searcher")
    create_video(client, user["user_id"], caption="unique keyword xylophone", hashtags=["music"])

    body = search_content(client, "xylophone", search_type="all")
    assert len(body["results"]) >= 1

    for item in body["results"]:
        assert "type" in item, f"Result missing 'type': {item}"
        assert item["type"] in ("video", "hashtag", "user"), f"Unknown type: {item['type']}"


def test_search_no_match(client):
    """Searching for a term that doesn't exist returns empty results."""
    body = search_content(client, "zzz_nonexistent_term_42", search_type="all")
    assert body["results"] == []
