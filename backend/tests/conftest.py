"""
Test configuration and fixtures.

Test strategy:
  - Unit tests: pure functions (mutation parser, alignment, AA properties)
    → no mocking, no DB, no network. Fast and deterministic.
  - Integration tests: API routes via httpx.AsyncClient
    → in-memory SQLite DB, mocked external APIs via respx
  - No tests hit real UniProt/ClinVar/AlphaFold APIs.
    External calls are mocked at the httpx level.
"""
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.database import Base, get_db

# Use SQLite for tests (no Postgres needed in CI)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create in-memory SQLite engine for the test session."""
    _engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Fresh DB session per test, rolled back after."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP test client with injected test DB session.
    External API calls (UniProt, AlphaFold) must be mocked per-test.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Seed data fixtures ────────────────────────────────────────────────────────

MOCK_TP53_DATA = {
    "gene_name": "TP53",
    "uniprot_id": "P04637",
    "protein_name": "Cellular tumor antigen p53",
    "organism": "Homo sapiens",
    "sequence": "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYPQGLNGTVNLFRNLNKALTDLQSLAHLHHNTMDLQAFARLNKEQVSTELKTLQTHVDDLQKVVSNLQQEMSTTRKLFLQTIDQLLNGNL",
    "sequence_length": 393,
    "function_summary": "Acts as a tumor suppressor in many tumor types.",
    "domains": [
        {"type": "Domain", "name": "DNA-binding domain", "start": 102, "end": 292},
        {"type": "Domain", "name": "Tetramerization domain", "start": 323, "end": 356},
    ],
    "disease_annotations": [
        {"name": "Li-Fraumeni syndrome", "description": "Autosomal dominant cancer predisposition", "mim_id": "151623"}
    ],
    "go_terms": [],
    "subcellular_location": "Nucleus",
    "mass_da": 43653.0,
    "raw_uniprot": {},
    "cached": False,
}

MOCK_BRCA1_SEQUENCE = (
    "MDLSALRVEEVQNVINAMQKILECPICLELIKEPVSTKCDHIFCKFCMLKLLNQKKGPSQCPLCKNDITKRSLQESTRFSQLVEELLKIICAFQLDTGLEYANSYNFAKKENNSPEHLKDEVSIIQSMGYRNACKESSNLRGTFE"
)
