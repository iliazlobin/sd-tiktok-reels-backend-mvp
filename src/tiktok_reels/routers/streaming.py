import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.services.streaming_service import StreamingService

router = APIRouter(prefix="/api/v1", tags=["streaming"])


@router.get("/videos/{video_id}/manifest")
async def get_manifest(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = StreamingService(session)
    segments = await service.get_video_segments(video_id)
    if not segments:
        raise HTTPException(status_code=404, detail="video has no segments")

    manifest_xml = service.build_manifest_xml(str(video_id), segments)
    return Response(
        content=manifest_xml,
        media_type="application/dash+xml",
        headers={"Content-Disposition": f'inline; filename="{video_id}.mpd"'},
    )


@router.get("/segments/{segment_id}")
async def get_segment(
    segment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = StreamingService(session)
    segment = await service.get_segment(segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="segment not found")

    # Try to read the mock .ts file from disk
    bytes_data = None
    if segment.file_path and os.path.exists(segment.file_path):
        try:
            with open(segment.file_path, "rb") as f:
                bytes_data = f.read()
        except OSError:
            pass

    # Fallback: return a minimal mock .ts segment
    if bytes_data is None:
        # MPEG-TS minimum packet is 188 bytes; return a tiny valid-ish packet
        bytes_data = b"\x47" * 188 * 3  # 3 sync-byte packets

    return Response(content=bytes_data, media_type="video/mp2t")
