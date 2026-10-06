import os
from pathlib import Path
from dotenv import load_dotenv

# Paths — all resolved cleanly relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

# Load environment variables explicitly from project root or backend
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

# Resolve API key - prefer .env file's gemini_api_key over system-level GOOGLE_API_KEY
GEMINI_API_KEY = os.getenv("gemini_api_key") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

def require_api_key():
    """Validates that a Gemini API key is present."""
    key = os.getenv("gemini_api_key") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key or key.startswith("PASTE_") or key.startswith("your_"):
        raise ValueError(
            "No API key found. Please set 'gemini_api_key' or 'GOOGLE_API_KEY' in your .env file."
        )
    return key

# Model Configurations
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")


# Auto-locate DOCS_DIR
default_docs = BACKEND_DIR / "dataset" / "docs"
if not default_docs.exists():
    default_docs = PROJECT_ROOT / "dataset" / "docs"
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(default_docs)))

# Auto-locate PARQUET_DIR
default_parquet = BACKEND_DIR / "dataset" / "parquet"
if not default_parquet.exists():
    default_parquet = PROJECT_ROOT / "dataset" / "parquet"
PARQUET_DIR = Path(os.getenv("PARQUET_DIR", str(default_parquet)))

# Storage / Database Paths (absolute paths prevent working-directory fragmentation)
default_chroma = PROJECT_ROOT / "db" / "chroma_db_gemini"
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(default_chroma)))

default_duckdb = BACKEND_DIR / "telemachus.duckdb"
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", str(default_duckdb)))

# Dataset Timeline
DATASET_START_DATE = "2011-11-23"
DATASET_END_DATE = "2014-02-28"

