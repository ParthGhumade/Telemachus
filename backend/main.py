import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Ensure backend and project root are in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(PROJECT_ROOT))

from orchestrator import Orchestrator

app = FastAPI(
    title="Telemachus Energy Intelligence API",
    description="Multi-agent RAG & DuckDB Analytics Platform for Smart Meter Energy Insights",
    version="1.0.0"
)

# Enable CORS for local development and container networking
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy singleton orchestrator
_orchestrator = None

def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    response: str
    status: str = "success"


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Telemachus Energy Intelligence",
        "duckdb": True,
        "chromadb": True
    }


@app.post("/api/query", response_model=QueryResponse)
def query_energy_intelligence(request: QueryRequest):
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    
    try:
        orc = get_orchestrator()
        result_text = orc.process_query(request.query)
        return QueryResponse(
            query=request.query,
            response=result_text,
            status="success"
        )
    except Exception as e:
        print(f"[API ERROR] Error processing query: {e}")
        return QueryResponse(
            query=request.query,
            response=f"An error occurred while analyzing your query: {str(e)}",
            status="error"
        )


# Mount frontend static files if available
frontend_dir = PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    @app.get("/")
    def serve_frontend_index():
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Telemachus API is online. Frontend index.html not found."}

    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
