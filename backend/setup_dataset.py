import os
import sys
import zipfile
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend directory is in python path
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

from config import PARQUET_DIR, DOCS_DIR, CHROMA_PERSIST_DIR, DUCKDB_PATH
from database import init_db
from inputpdf import ingest


def download_from_drive(drive_url_or_id: str, dest_path: Path) -> bool:
    """
    Downloads dataset.zip from Google Drive using gdown.
    Supports either full sharing URL or direct file ID.
    """
    print(f"[Dataset Setup] Downloading dataset archive from Google Drive: {drive_url_or_id}")
    try:
        import gdown
        if "drive.google.com" in drive_url_or_id:
            output = gdown.download(url=drive_url_or_id, output=str(dest_path), quiet=False, fuzzy=True)
        else:
            url = f"https://drive.google.com/uc?id={drive_url_or_id}"
            output = gdown.download(url=url, output=str(dest_path), quiet=False, fuzzy=True)
            
        if output and dest_path.exists() and dest_path.stat().st_size > 1000:
            print(f"[Dataset Setup] Download complete: {dest_path} ({round(dest_path.stat().st_size / (1024*1024), 2)} MB)")
            return True
        else:
            print(f"[Dataset Setup] Warning: Downloaded file appears invalid or empty: {output}")
            return False
    except Exception as e:
        print(f"[Dataset Setup] Error downloading from Google Drive: {e}")
        return False


def extract_dataset_zip(zip_path: Path, target_base_dir: Path):
    """
    Unzips dataset.zip ensuring parquet files go into backend/dataset/parquet
    and text docs go into backend/dataset/docs.
    """
    print(f"[Dataset Setup] Extracting '{zip_path}' to '{target_base_dir}'...")
    target_parquet = target_base_dir / "parquet"
    target_docs = target_base_dir / "docs"
    target_parquet.mkdir(parents=True, exist_ok=True)
    target_docs.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            filename = Path(member.filename).name
            if filename.endswith(".parquet"):
                dest = target_parquet / filename
                with zf.open(member) as source, open(dest, "wb") as target:
                    target.write(source.read())
                print(f"[Dataset Setup] Extracted Parquet: {filename}")
            elif filename.endswith(".txt") or filename.endswith(".md"):
                dest = target_docs / filename
                with zf.open(member) as source, open(dest, "wb") as target:
                    target.write(source.read())
                print(f"[Dataset Setup] Extracted Doc: {filename}")


def setup_all(force: bool = False):
    print("=" * 70)
    print("TELEMACHUS DATASET SETUP & VECTOR INDEXING")
    print("=" * 70)

    parquet_dir = Path(PARQUET_DIR)
    docs_dir = Path(DOCS_DIR)

    # Check if dataset is already extracted and present
    has_parquet = parquet_dir.exists() and any(parquet_dir.glob("*.parquet"))
    has_docs = docs_dir.exists() and any(docs_dir.glob("*.txt"))

    if has_parquet and has_docs and not force:
        print(f"[Dataset Setup] Parquet datasets and text documentation already present in '{parquet_dir.parent}'.")
    else:
        # Locate or download dataset.zip
        candidate_zips = [
            PROJECT_ROOT / "dataset.zip",
            BACKEND_DIR / "dataset.zip",
            Path("/app/dataset.zip"),
            Path("dataset.zip")
        ]
        existing_zip = next((z for z in candidate_zips if z.exists() and z.stat().st_size > 1000), None)

        if not existing_zip:
            drive_target = os.getenv("DATASET_DRIVE_URL") or os.getenv("DATASET_DRIVE_ID")
            dest_zip = PROJECT_ROOT / "dataset.zip"
            if drive_target:
                success = download_from_drive(drive_target, dest_zip)
                if success:
                    existing_zip = dest_zip
            else:
                print("[Dataset Setup] Note: No dataset.zip found locally and DATASET_DRIVE_URL/ID not set.")
                print("[Dataset Setup] Please provide DATASET_DRIVE_URL in .env or mount dataset.zip.")

        if existing_zip:
            extract_dataset_zip(existing_zip, parquet_dir.parent)
        else:
            print("[Dataset Setup] Proceeding with existing local files if available...")

    # Step 1: Initialize DuckDB views
    print("\n[Step 1/2] Initializing DuckDB Views...")
    try:
        init_db()
    except Exception as e:
        print(f"[Dataset Setup] Warning initializing DuckDB: {e}")

    # Step 2: Index text documents into ChromaDB (skip if already indexed on persistent volume)
    chroma_dir = Path(CHROMA_PERSIST_DIR)
    chroma_exists = chroma_dir.exists() and any(chroma_dir.glob("*.sqlite3"))
    if chroma_exists and not force:
        print(f"\n[Step 2/2] ChromaDB vector store already populated at '{chroma_dir}'. Skipping re-indexing.")
    else:
        print("\n[Step 2/2] Ingesting and Vectorizing Text Documents into ChromaDB...")
        try:
            ingest()
        except Exception as e:
            print(f"[Dataset Setup] Warning indexing ChromaDB: {e}")

    print("\n[Dataset Setup] Dataset initialization and indexing complete!")
    print("=" * 70)


if __name__ == "__main__":
    force_run = "--force" in sys.argv
    setup_all(force=force_run)
