from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.db.database import get_db
from app.core.cache import get_redis
from app.ml.esm2_service import get_index_stats
from app.schemas.schemas import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """System health check. Verifies DB, Redis, and FAISS index status."""
    # DB
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    # Redis
    redis_status = "ok"
    try:
        client = await get_redis()
        if client:
            await client.ping()
        else:
            redis_status = "unavailable (caching disabled)"
    except Exception as e:
        redis_status = f"error: {e}"

    # FAISS
    stats = get_index_stats()
    faiss_status = f"ok ({stats['total_indexed']} vectors indexed)"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        redis=redis_status,
        faiss_index=faiss_status,
        version="1.0.0",
    )
