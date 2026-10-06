#!/bin/bash
set -e

echo "=================================================="
echo " Starting Telemachus Energy Intelligence Service  "
echo "=================================================="

# Run dataset check, download from drive if missing, unzip, DuckDB init & Chroma indexing
python backend/setup_dataset.py

echo "=================================================="
echo " Application is ready! Launching Uvicorn Server... "
echo " Access UI at: http://localhost:8000              "
echo " API Docs at:  http://localhost:8000/docs         "
echo "=================================================="

exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
