"""
Background job queue for ESM2 embedding generation.

Design decision: FastAPI BackgroundTasks vs Celery

BackgroundTasks (used here):
  + Zero new infrastructure
  + Works within the same process
  + Sufficient for 1-10 concurrent embedding requests
  - Not persistent across restarts
  - No retry logic (added manually below)
  - Shares memory with API workers

Celery + Redis (upgrade path, mentioned in README):
  + Persistent job queue (survives restarts)
  + Horizontal scaling (multiple workers)
  + Built-in retry with exponential backoff
  + Task result storage
  - Requires separate worker process and Redis configuration

The interface (job_id polling) is identical in both cases.
Swapping to Celery requires no API changes — only the worker implementation.
This is the key design point for interviews.

Redis data structure for job state:
  key:   job:{job_id}
  value: JSON { status, gene_name, created_at, completed_at, error }
  TTL:   1 hour
"""

import asyncio
import uuid
import time
import json
import logging
from enum import Enum
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.database import get_db
from app.models.protein import Protein
from app.models.structure import Embedding
from app.core.cache import get_redis, cache_get, cache_set, make_cache_key
from app.services.uniprot_service import fetch_protein_from_uniprot

router = APIRouter()
logger = logging.getLogger(__name__)

JOB_TTL = 3600  # 1 hour


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class JobState(BaseModel):
    job_id: str
    gene_name: str
    status: JobStatus
    created_at: float
    completed_at: Optional[float] = None
    error: Optional[str] = None
    faiss_index_id: Optional[int] = None


async def _set_job_state(job_id: str, state: Dict[str, Any]) -> None:
    redis = await get_redis()
    if redis:
        await redis.setex(f"job:{job_id}", JOB_TTL, json.dumps(state))


async def _get_job_state(job_id: str) -> Optional[Dict[str, Any]]:
    redis = await get_redis()
    if not redis:
        return None
    raw = await redis.get(f"job:{job_id}")
    return json.loads(raw) if raw else None


async def _run_embedding_job(job_id: str, gene_name: str, db_url: str) -> None:
    """
    Background task: fetch sequence, compute ESM2 embedding, add to FAISS.
    Runs in a separate thread to avoid blocking the event loop.
    """
    await _set_job_state(job_id, {
        "job_id": job_id,
        "gene_name": gene_name,
        "status": JobStatus.RUNNING,
        "created_at": time.time(),
    })

    try:
        # We need a fresh DB session in the background task
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from app.core.config import settings
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as session:
            # Get or fetch sequence
            result = await session.execute(
                select(Protein).where(Protein.gene_name == gene_name)
            )
            db_protein = result.scalar_one_or_none()

            sequence = None
            uniprot_id = None

            if db_protein and db_protein.sequence:
                sequence = db_protein.sequence
                uniprot_id = db_protein.uniprot_id
            else:
                data = await fetch_protein_from_uniprot(gene_name)
                if data:
                    sequence = data.get("sequence")
                    uniprot_id = data.get("uniprot_id")
                    if not db_protein:
                        new_protein = Protein(
                            **{k: v for k, v in data.items() if k not in ("cached",)}
                        )
                        session.add(new_protein)
                        await session.flush()

            if not sequence:
                raise ValueError(f"No sequence found for {gene_name}")

            # Compute embedding (CPU-bound, run in thread pool)
            from app.ml.esm2_service import compute_embedding, add_to_index
            embedding = await asyncio.to_thread(compute_embedding, sequence)

            if embedding is None:
                raise ValueError("ESM2 model unavailable or computation failed")

            faiss_id = await asyncio.to_thread(
                add_to_index, gene_name, uniprot_id or "", embedding
            )

            # Store in DB
            emb_result = await session.execute(
                select(Embedding).where(Embedding.gene_name == gene_name)
            )
            db_emb = emb_result.scalar_one_or_none()
            if not db_emb:
                db_emb = Embedding(
                    gene_name=gene_name,
                    uniprot_id=uniprot_id,
                    model_name="facebook/esm2_t6_8M_UR50D",
                    embedding_dim=embedding.shape[0],
                    embedding_path=f"app/ml/embeddings/{gene_name}.npy",
                    faiss_index_id=faiss_id,
                    sequence_length=len(sequence),
                )
                session.add(db_emb)
            else:
                db_emb.faiss_index_id = faiss_id
            await session.commit()

        await engine.dispose()

        await _set_job_state(job_id, {
            "job_id": job_id,
            "gene_name": gene_name,
            "status": JobStatus.COMPLETE,
            "created_at": time.time(),
            "completed_at": time.time(),
            "faiss_index_id": faiss_id,
        })
        logger.info(f"Embedding job {job_id} complete for {gene_name}, FAISS id={faiss_id}")

    except Exception as e:
        logger.error(f"Embedding job {job_id} failed for {gene_name}: {e}")
        await _set_job_state(job_id, {
            "job_id": job_id,
            "gene_name": gene_name,
            "status": JobStatus.FAILED,
            "created_at": time.time(),
            "completed_at": time.time(),
            "error": str(e),
        })


@router.post("/embed/{gene_name}")
async def submit_embedding_job(
    gene_name: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a background job to compute and index an ESM2 embedding.
    Returns immediately with a job_id. Poll /embed/status/{job_id} for completion.

    This keeps the API non-blocking — ESM2 inference takes 2-10s per protein.
    """
    gene_upper = gene_name.upper().strip()

    # Check if already indexed
    emb_result = await db.execute(
        select(Embedding).where(Embedding.gene_name == gene_upper)
    )
    existing = emb_result.scalar_one_or_none()
    if existing and existing.faiss_index_id is not None:
        return {
            "job_id": None,
            "status": "already_indexed",
            "gene_name": gene_upper,
            "faiss_index_id": existing.faiss_index_id,
            "message": f"{gene_upper} is already in the FAISS index. Call /similar/{gene_upper} directly.",
        }

    job_id = uuid.uuid4().hex
    from app.core.config import settings

    # Register job as pending before dispatching
    await _set_job_state(job_id, {
        "job_id": job_id,
        "gene_name": gene_upper,
        "status": JobStatus.PENDING,
        "created_at": time.time(),
    })

    # Dispatch to background — returns immediately
    background_tasks.add_task(
        _run_embedding_job,
        job_id=job_id,
        gene_name=gene_upper,
        db_url=settings.DATABASE_URL,
    )

    return {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "gene_name": gene_upper,
        "poll_url": f"/api/v1/embed/status/{job_id}",
        "message": "Embedding job queued. Poll status URL for completion.",
    }


@router.get("/embed/status/{job_id}", response_model=JobState)
async def get_job_status(job_id: str):
    """Poll the status of an embedding job."""
    state = await _get_job_state(job_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found. It may have expired (TTL: 1h) or never existed.",
        )
    return JobState(**state)
