import sys
from pathlib import Path
import json

# Add current dir to path to import local modules
sys.path.append(str(Path(__file__).parent.absolute()))

from agents.refiner import RefinerAgent
from agents.data_agent import DataAgent
from agents.response import ResponseAgent
from inputpdf import DocsAgent

class Orchestrator:
    def __init__(self):
        print("Initializing Agents...")
        self.refiner = RefinerAgent()
        self.data_agent = DataAgent()
        self.response_agent = ResponseAgent()
        
        # Try initializing DocsAgent, if chroma_db doesn't exist it might output an error
        try:
            self.docs_agent = DocsAgent()
        except Exception as e:
            print(f"Warning: DocsAgent failed to initialize (Ensure chroma_db exists): {e}")
            self.docs_agent = None

    def process_query(self, query: str):
        print(f"\n--- Orchestrating Query: '{query}' ---")
        
        # 1. Refiner Agent
        print("\n1. Refiner Agent analyzing intent...")
        refiner_output = self.refiner.refine(query)
        
        if refiner_output.status == "NEEDS_CLARIFICATION":
            question = refiner_output.clarification.question
            options = refiner_output.clarification.options
            print(f"Agent requires clarification: {question}")
            print(f"Options: {options}")
            options_str = "\n".join([f"- {opt}" for opt in options])
            return f"Clarification required: {question}\n{options_str}"
            
        print(f"Intent: {refiner_output.intent}")
        print(f"Refined Query: {refiner_output.refined_query}")
        
        # 2. Routing
        doc_evidence = {}
        if refiner_output.requires_docs and self.docs_agent:
            print("\n2a. Docs Agent retrieving evidence...")
            # We can use the refined search queries if available, else original query
            search_query = query
            if refiner_output.doc_plan and refiner_output.doc_plan.search_queries:
                search_query = refiner_output.doc_plan.search_queries[0]
                
            doc_evidence = self.docs_agent.retrieve(search_query)
            print(f"Retrieved {len(doc_evidence.get('sources', []))} chunks.")
        
        data_results = {}
        limitations = []
        if refiner_output.requires_data:
            print("\n2b. Data Agent executing DuckDB queries...")
            data_output = self.data_agent.analyze(
                refined_query=refiner_output.refined_query or query,
                data_plan=refiner_output.data_plan.dict() if refiner_output.data_plan else {}
            )
            data_results = {
                "queries": [q.dict() for q in data_output.queries],
                "results": data_output.results,
                "summary": data_output.summary
            }
            limitations = data_output.limitations
            print(f"Status: {data_output.status}. Retrieved {data_output.summary.get('row_count', 0)} rows.")
            if data_output.status == "ERROR" and limitations:
                print(f"[DataAgent] Errors: {limitations}")
            
        # 3. Response Agent
        print("\n3. Response Agent synthesizing final answer...")
        final_answer = self.response_agent.synthesize(
            original_query=query,
            refined_query=refiner_output.refined_query or "",
            assumptions=refiner_output.assumptions,
            doc_evidence=doc_evidence,
            data_results=data_results,
            limitations=limitations
        )
        
        print("\n--- FINAL ANSWER ---")
        print(final_answer)
        print("--------------------")
        
        return final_answer

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Energy Intelligence API")

# Initialize orchestrator once on startup
orchestrator_instance = Orchestrator()

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str

@app.post("/api/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    """
    Single endpoint to process natural language queries through the multi-agent system.
    """
    final_answer = orchestrator_instance.process_query(request.query)
    return QueryResponse(response=final_answer)

# If run directly, start uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator:app",reload=True)
