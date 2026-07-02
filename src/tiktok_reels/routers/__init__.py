from tiktok_reels.routers.comments import router as comments_router
from tiktok_reels.routers.engagement import router as engagement_router
from tiktok_reels.routers.feed import router as feed_router
from tiktok_reels.routers.search import router as search_router
from tiktok_reels.routers.streaming import router as streaming_router
from tiktok_reels.routers.users import router as users_router
from tiktok_reels.routers.videos import router as videos_router

routers = [
    users_router,
    videos_router,
    feed_router,
    streaming_router,
    comments_router,
    engagement_router,
    search_router,
]

__all__ = ["routers"]
