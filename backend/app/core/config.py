from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os


def _fix_db_url(url: str) -> str:
    """
    Neon/Render provide postgresql:// URLs with sslmode=require.
    asyncpg needs postgresql+asyncpg:// and ssl=require (not sslmode).
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg doesn't understand sslmode= — replace with ssl=
    url = url.replace("sslmode=require", "ssl=require")
    return url


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Protein Intelligence Platform"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database — auto-converts postgresql:// → postgresql+asyncpg://
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/proteindb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 3600

    # CORS — wildcard removed.
    # Set via ALLOWED_ORIGINS env var as comma-separated string:
    #   ALLOWED_ORIGINS=https://myapp.vercel.app,http://localhost:3000
    # Never use "*" in production.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # External APIs
    UNIPROT_BASE_URL: str = "https://rest.uniprot.org/uniprotkb"
    ALPHAFOLD_BASE_URL: str = "https://alphafold.ebi.ac.uk/api"
    PDB_BASE_URL: str = "https://data.rcsb.org/rest/v1/core"
    PDB_SEARCH_URL: str = "https://search.rcsb.org/rcsbsearch/v2/query"
    CLINVAR_BASE_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    NCBI_API_KEY: str = ""

    # ML
    ESM2_MODEL: str = "facebook/esm2_t6_8M_UR50D"
    FAISS_INDEX_PATH: str = "app/ml/faiss_index"
    EMBEDDINGS_CACHE_PATH: str = "app/ml/embeddings_cache"

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        return _fix_db_url(str(v))

    def get_allowed_origins(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS string into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
