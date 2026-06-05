from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import traceback
import asyncio

from app.core.config import settings
from app.api.routes import protein, mutation, structure, similarity, batch, report, health, alignment, jobs
from app.api.middleware import RateLimitMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        logger.info("Alembic migrations applied.")
    except Exception as e:
        logger.warning(f"Alembic migration failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Protein Intelligence Platform...")

    # Primary: Alembic migrations (handles schema evolution)
    try:
        await asyncio.to_thread(run_migrations)
    except Exception as e:
        # Fallback: create all tables directly via asyncpg if Alembic fails
        logger.warning(f"Alembic failed ({e}), falling back to create_all...")
        from app.db.database import engine
        from app.db.database import Base
        import app.models.protein  # noqa — register models
        import app.models.mutation  # noqa
        import app.models.structure  # noqa
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created via create_all fallback.")

    logger.info("Startup complete.")
    yield
    logger.info("Shutting down.")


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
- `POST /api/v1/batch-analyze` — CSV bulk mutation analysis
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware order matters: outermost runs first on request, last on response
app.add_middleware(GZipMiddleware, minimum_size=1000)
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
    logger.error(f"Unhandled exception on {request.url}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(protein.router, prefix="/api/v1", tags=["protein"])
app.include_router(mutation.router, prefix="/api/v1", tags=["mutation"])
app.include_router(structure.router, prefix="/api/v1", tags=["structure"])
app.include_router(similarity.router, prefix="/api/v1", tags=["similarity"])
app.include_router(alignment.router, prefix="/api/v1", tags=["alignment"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(batch.router, prefix="/api/v1", tags=["batch"])
app.include_router(report.router, prefix="/api/v1", tags=["report"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Protein Intelligence Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }
