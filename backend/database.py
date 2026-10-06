import duckdb
import os
from pathlib import Path
import sys

# Ensure config can be loaded
sys.path.append(str(Path(__file__).resolve().parent))
from config import PARQUET_DIR, DUCKDB_PATH, PROJECT_ROOT

DB_PATH = DUCKDB_PATH


def get_connection(read_only: bool = False):
    """
    Returns a connection to the DuckDB database.
    If the database doesn't exist, it will be created.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH), read_only=read_only)
    return conn


def init_db():
    """
    Initializes the database views over the energy parquet and csv files.
    """
    conn = get_connection(read_only=False)
    print(f"[DuckDB] Initializing DuckDB database at: {DB_PATH}")

    parquet_dir = Path(PARQUET_DIR)
    db_raw_dir = PROJECT_ROOT / "db"

    # Helper function to register view
    def register_view(view_name: str, parquet_filename: str, fallback_csv_path: str = None):
        pq_path = parquet_dir / parquet_filename
        if pq_path.exists():
            try:
                conn.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{pq_path.as_posix()}');")
                count = conn.execute(f"SELECT count(*) FROM {view_name};").fetchone()[0]
                print(f"[DuckDB] Registered view '{view_name}' ({count:,} rows) from {pq_path.name}")
                return True
            except Exception as e:
                print(f"[DuckDB] Error registering '{view_name}' from parquet: {e}")
        elif fallback_csv_path and Path(fallback_csv_path).exists():
            try:
                conn.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_csv_auto('{fallback_csv_path}');")
                count = conn.execute(f"SELECT count(*) FROM {view_name};").fetchone()[0]
                print(f"[DuckDB] Registered view '{view_name}' ({count:,} rows) from CSV: {fallback_csv_path}")
                return True
            except Exception as e:
                print(f"[DuckDB] Error registering '{view_name}' from CSV: {e}")
        return False

    # 1. Main energy_data view (joined daily dataset)
    register_view("energy_data", "energy_data.parquet", str(db_raw_dir / "daily_dataset.csv"))

    # 2. Half-hourly block readings (hh_0 through hh_47)
    register_view("hhblock_energy", "hhblock_energy.parquet")

    # 3. Households demographic classifications
    register_view("households", "households.parquet", str(db_raw_dir / "informations_households.csv"))

    # 4. Daily weather
    register_view("weather_daily", "weather_daily.parquet", str(db_raw_dir / "weather_daily_darksky.csv"))

    # 5. Hourly weather
    register_view("weather_hourly", "weather_hourly.parquet", str(db_raw_dir / "weather_hourly_darksky.csv"))

    # 6. ACORN demographic details
    register_view("acorn_details", "acorn_details.parquet")

    # 7. UK Bank Holidays calendar
    register_view("uk_bank_holidays", "uk_bank_holidays.parquet", str(db_raw_dir / "uk_bank_holidays.csv"))

    conn.close()
    print("[DuckDB] Database initialization complete.")


if __name__ == '__main__':
    init_db()
