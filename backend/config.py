import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Resolve API key - prefer .env file's gemini_api_key over system-level GOOGLE_API_KEY
GEMINI_API_KEY = os.getenv("gemini_api_key") or os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("No API key found. Set 'gemini_api_key' in your .env file.")

# Model Configurations
LLM_MODEL = os.getenv("LLM_MODEL", "gemma-4-31b-it")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/embedding-004")

# Dataset Paths — all relative to project root (v:/Telemachus)
PROJECT_ROOT = Path(__file__).parent.parent
DATASET_DIR = Path(os.getenv("DATASET_DIR", str(PROJECT_ROOT / "dataset")))
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(DATASET_DIR)))           # PDFs live here
PARQUET_DIR = Path(os.getenv("PARQUET_DIR", str(DATASET_DIR / "Upload")))  # Parquet files

# Storage / Database Paths
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "db/chroma_db_gemini")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "telemachus.duckdb")

# Dataset Timeline
DATASET_START_DATE = "2011-11-23"
DATASET_END_DATE = "2014-02-28"
