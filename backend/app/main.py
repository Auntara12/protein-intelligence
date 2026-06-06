from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import traceback

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import (
    protein, mutation, structure, similarity,
    batch, report, health, alignment, jobs, metrics
)
from app.api.middleware import RateLimitMiddleware
from app.api.observability import RequestContextMiddleware, MetricsMiddleware

logger = get_logger(__name__)


def run_migrations() -> None:
    """Run Alembic migrations on startup. Requires psycopg2 sync driver."""
    from alembic.config import Config
    from alembic import command
    import os

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "..", "alembic"),
    )
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("migrations_complete")
    except Exception as e:
        logger.warning("migrations_warning", error=str(e))
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("startup_begin")

    # Step 1: ensure all tables exist via asyncpg (idempotent, always safe)
    from app.db.database import engine, Base
    from sqlalchemy import text
    import app.models.protein   # noqa
    import app.models.mutation  # noqa
    import app.models.structure # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("tables_ensured")

    # Step 1b: remove duplicate mutation rows so Alembic's unique index migration succeeds
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(
                "DELETE FROM mutations WHERE id NOT IN "
                "(SELECT MIN(id) FROM mutations GROUP BY gene_name, mutation_str)"
            ))
            logger.info("mutations_dedup", removed=result.rowcount)
    except Exception as e:
        logger.warning("mutations_dedup_skipped", error=str(e))

    # Step 2: run Alembic to apply any column-level migrations
    try:
        await asyncio.to_thread(run_migrations)
    except Exception as e:
        logger.warning("migrations_skipped", error=str(e))

    logger.info("startup_complete")
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Protein Intelligence Platform",
    description="""
Full-stack BioAI platform for protein search, 3D structure visualization,
mutation analysis, and ML-powered similarity search.

**Key endpoints:**
- `GET /api/v1/protein/{gene}` — UniProt metadata
- `GET /api/v1/mutation/{gene}/{mutation}` — Biochemical analysis + ClinVar
- `GET /api/v1/structure/{gene}` — AlphaFold/PDB + 3Dmol config
- `GET /api/v1/similar/{gene}` — ESM2 + FAISS similarity search
- `GET /api/v1/align/{gene1}/{gene2}` — Smith-Waterman sequence alignment
- `GET /api/v1/compare/{gene1}/{gene2}` — Side-by-side protein comparison
- `POST /api/v1/batch-analyze` — CSV bulk mutation analysis
- `GET /api/v1/report/{gene}/pdf` — Download PDF research report
- `GET /api/v1/metrics` — Prometheus-format application metrics
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware stack — order matters, outermost runs first on request
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=str(request.url), error=str(exc), traceback=traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# Routers
app.include_router(health.router,      prefix="/api/v1", tags=["health"])
app.include_router(metrics.router,     prefix="/api/v1", tags=["metrics"])
app.include_router(protein.router,     prefix="/api/v1", tags=["protein"])
app.include_router(mutation.router,    prefix="/api/v1", tags=["mutation"])
app.include_router(structure.router,   prefix="/api/v1", tags=["structure"])
app.include_router(similarity.router,  prefix="/api/v1", tags=["similarity"])
app.include_router(alignment.router,   prefix="/api/v1", tags=["alignment"])
app.include_router(jobs.router,        prefix="/api/v1", tags=["jobs"])
app.include_router(batch.router,       prefix="/api/v1", tags=["batch"])
app.include_router(report.router,      prefix="/api/v1", tags=["report"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Protein Intelligence Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "metrics": "/api/v1/metrics",
        "status": "running",
    }
