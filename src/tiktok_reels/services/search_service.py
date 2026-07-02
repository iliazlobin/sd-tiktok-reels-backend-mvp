from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.schemas.search import SearchResult


class SearchService:
    """FTS query builder: websearch_to_tsquery, UNION, ts_rank."""

    PAGE_SIZE = 20

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        search_type: str = "all",
        cursor: str | None = None,
    ) -> tuple[list[SearchResult], str | None]:
        """Full-text search across videos, hashtags, and usernames."""
        if not query or not query.strip():
            return [], None

        results: list[SearchResult] = []

        if search_type in ("all", "video", "sound"):
            results.extend(await self._search_videos(query))

        if search_type in ("all", "hashtag"):
            results.extend(await self._search_hashtags(query))

        if search_type in ("all", "user"):
            results.extend(await self._search_users(query))

        # Apply simple cursor (offset-based for MVP — cursor complex across UNION)
        if cursor:
            try:
                offset = int(cursor)
            except (ValueError, TypeError) as exc:
                raise ValueError("malformed cursor") from exc
        else:
            offset = 0

        page = results[offset : offset + self.PAGE_SIZE]
        next_cursor = (
            str(offset + self.PAGE_SIZE) if len(results) > offset + self.PAGE_SIZE else None
        )

        return page, next_cursor

    async def _search_videos(self, query: str) -> list[SearchResult]:
        """Search videos by caption or sound_name using FTS."""
        stmt = text("""
            SELECT v.video_id, v.caption, v.like_count, v.created_at, u.username
            FROM videos v
            JOIN users u ON u.user_id = v.author_id
            WHERE
                to_tsvector('english', v.caption || ' ' || v.sound_name)
                    @@ websearch_to_tsquery('english', :q)
                OR v.caption ILIKE '%' || :q2 || '%'
                OR v.sound_name ILIKE '%' || :q3 || '%'
            ORDER BY v.created_at DESC
            LIMIT 20
        """)
        result = await self.session.execute(stmt, {"q": query, "q2": query, "q3": query})
        rows = result.all()

        return [
            SearchResult(
                type="video",
                video_id=str(row[0]),
                caption=row[1],
                like_count=row[2],
                created_at=row[3].isoformat() if row[3] else None,
                username=row[4],
            )
            for row in rows
        ]

    async def _search_hashtags(self, query: str) -> list[SearchResult]:
        """Search hashtags by name."""
        stmt = text("""
            SELECT hashtag_id, name
            FROM hashtags
            WHERE
                to_tsvector('english', name) @@ websearch_to_tsquery('english', :q)
                OR name ILIKE '%' || :q2 || '%'
            ORDER BY name ASC
            LIMIT 10
        """)
        result = await self.session.execute(stmt, {"q": query, "q2": query})
        rows = result.all()

        return [SearchResult(type="hashtag", hashtag_id=str(row[0]), name=row[1]) for row in rows]

    async def _search_users(self, query: str) -> list[SearchResult]:
        """Search users by username."""
        stmt = text("""
            SELECT user_id, username
            FROM users
            WHERE username ILIKE '%' || :q || '%'
            ORDER BY username ASC
            LIMIT 10
        """)
        result = await self.session.execute(stmt, {"q": query})
        rows = result.all()

        return [SearchResult(type="user", user_id=str(row[0]), username=row[1]) for row in rows]
