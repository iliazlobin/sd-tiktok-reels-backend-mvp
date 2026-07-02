"""Test fixtures and helpers for white-box unit/integration tests."""

import os
import tempfile
import uuid

import pytest
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tiktok_reels.models import Base
from tiktok_reels.models.hashtag import Hashtag
from tiktok_reels.models.user import User
from tiktok_reels.models.video import Video

# Use a temp file to avoid SQLite in-memory connection isolation issues
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_tmp_db.name}"


@pytest.fixture(scope="session")
def _db_path():
    path = _tmp_db.name
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
async def setup_db(_db_path):
    """Create a fresh DB before each test using the shared temp file path."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture
async def db_session(setup_db):
    """Provide a session connected to the temp DB."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def sample_user_factory(db_session):
    """Create users with unique usernames."""
    counter = [0]

    async def _make(username=None):
        counter[0] += 1
        user = User(
            username=username or f"testuser_{counter[0]}_{uuid.uuid4().hex[:6]}",
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _make


@pytest.fixture
async def sample_video_factory(db_session, sample_user_factory):
    """Create videos with auto-created author."""

    async def _make(author=None, caption="Test video", sound_name="test sound", duration_ms=15000):
        if author is None:
            author = await sample_user_factory()
        video = Video(
            author_id=author.user_id,
            caption=caption,
            sound_name=sound_name,
            duration_ms=duration_ms,
        )
        db_session.add(video)
        await db_session.flush()
        return video, author

    return _make


@pytest.fixture
async def sample_hashtag_factory(db_session):
    """Create hashtags."""

    async def _make(name=None):
        if name is None:
            name = f"tag_{uuid.uuid4().hex[:6]}"
        hashtag = Hashtag(name=name)
        db_session.add(hashtag)
        await db_session.flush()
        return hashtag

    return _make


@pytest.fixture
def fresh_uuid():
    return uuid.uuid4()
