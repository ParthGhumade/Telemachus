import duckdb
import os
from pathlib import Path
from config import PARQUET_DIR

# Determine the path for the DuckDB database file
DB_PATH = Path(__file__).parent / 'telemachus.duckdb'

def get_connection():
    """
    Returns a connection to the DuckDB database.
    If the database doesn't exist, it will be created.
    """
    # Using a file-based database for persistence
    # If you prefer in-memory, you can use: duckdb.connect(':memory:')
    conn = duckdb.connect(str(DB_PATH))
    return conn

def init_db():
    """
    Initializes the database. You can add setup logic here,
    such as creating tables, views over parquet files, etc.
    """
    conn = get_connection()
    
    print(f"Initialized DuckDB database at: {DB_PATH}")
    
    parquet_dir = PARQUET_DIR
    
    try:
        # Create a view that reads all parquet files recursively
        query = f"CREATE OR REPLACE VIEW energy_data AS SELECT * FROM read_parquet('{parquet_dir.as_posix()}/**/*.parquet', filename=true, union_by_name=true)"
        conn.execute(query)
        print(f"Successfully created 'energy_data' view over: {parquet_dir}")
    except Exception as e:
        print(f"Warning: Could not create view (Parquet files might not exist yet or path is incorrect): {e}")
            
    conn.close()

if __name__ == '__main__':
    init_db()
