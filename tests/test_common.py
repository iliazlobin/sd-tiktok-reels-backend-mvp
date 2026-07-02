"""Tests for cursor encoding/decoding and common utilities."""

import json
import uuid
from base64 import b64decode
from datetime import UTC, datetime

import pytest

from tiktok_reels.schemas.common import decode_cursor, encode_cursor, encode_cursor_datetime


class TestCursorEncodeDecode:
    def test_encode_decode_score_based(self):
        item_id = uuid.uuid4()
        token = encode_cursor(42.5, item_id)
        decoded = decode_cursor(token)
        assert decoded["score"] == 42.5
        assert decoded["id"] == str(item_id)

    def test_encode_decode_no_score(self):
        item_id = uuid.uuid4()
        token = encode_cursor(None, item_id)
        decoded = decode_cursor(token)
        assert "score" not in decoded
        assert decoded["id"] == str(item_id)

    def test_encode_decode_datetime_based(self):
        now = datetime.now(UTC)
        item_id = uuid.uuid4()
        token = encode_cursor_datetime(now, item_id)
        decoded = decode_cursor(token)
        assert decoded["created_at"] == now.isoformat()
        assert decoded["id"] == str(item_id)

    def test_decode_malformed_raises(self):
        with pytest.raises(ValueError, match="malformed cursor"):
            decode_cursor("not-valid-base64!!")

    def test_decode_missing_id_raises(self):
        import base64

        bad_payload = base64.b64encode(json.dumps({"foo": "bar"}).encode()).decode()
        with pytest.raises(ValueError, match="malformed cursor"):
            decode_cursor(bad_payload)

    def test_token_is_base64(self):
        item_id = uuid.uuid4()
        token = encode_cursor(10.0, item_id)
        # Should be valid base64
        decoded_bytes = b64decode(token.encode())
        parsed = json.loads(decoded_bytes)
        assert parsed["id"] == str(item_id)
        assert parsed["score"] == 10.0
