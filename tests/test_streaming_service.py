"""Tests for the StreamingService manifest generation."""

import uuid

from tiktok_reels.models.segment import VideoSegment
from tiktok_reels.services.streaming_service import StreamingService


class TestManifestGeneration:
    def test_build_manifest_xml(self, db_session):
        service = StreamingService(db_session)
        video_id = str(uuid.uuid4())

        segments = [
            VideoSegment(
                segment_id=uuid.uuid4(),
                video_id=uuid.UUID(video_id),
                quality="720p",
                segment_index=0,
                file_path="/mock/seg0.ts",
                duration_seconds=5,
                size_bytes=524288,
            ),
            VideoSegment(
                segment_id=uuid.uuid4(),
                video_id=uuid.UUID(video_id),
                quality="720p",
                segment_index=1,
                file_path="/mock/seg1.ts",
                duration_seconds=5,
                size_bytes=524288,
            ),
            VideoSegment(
                segment_id=uuid.uuid4(),
                video_id=uuid.UUID(video_id),
                quality="540p",
                segment_index=0,
                file_path="/mock/seg540.ts",
                duration_seconds=5,
                size_bytes=393216,
            ),
        ]

        manifest = service.build_manifest_xml(video_id, segments)

        # Should be valid XML
        assert '<?xml version="1.0"' in manifest
        assert '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"' in manifest
        assert 'mimeType="video/mp2t"' in manifest
        assert 'Representation id="720p"' in manifest
        assert 'Representation id="540p"' in manifest
        assert manifest.count("<SegmentURL") == 3
        assert manifest.count("<AdaptationSet") == 2

    def test_empty_segments(self, db_session):
        service = StreamingService(db_session)
        manifest = service.build_manifest_xml(str(uuid.uuid4()), [])
        # Should still produce valid XML structure
        assert "<MPD" in manifest
        assert "</MPD>" in manifest
        assert manifest.count("<AdaptationSet") == 0
