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

    def _generate_followups(self, query: str, refiner_output, data_results) -> list:
        q = query.lower()
        if "peak" in q or "hour" in q:
            return [
                "Which 5 households had the highest daily consumption?",
                "What is the average consumption for Standard vs Time of Use tariffs?",
                "How does weather correlate with peak energy usage?"
            ]
        elif "household" in q or "highest" in q or "tariff" in q:
            return [
                "What was the average energy consumption on the coldest day in London?",
                "How does consumption vary across ACORN socio-economic groups?",
                "What are the top recommended energy conservation measures?"
            ]
        elif "conservation" in q or "measure" in q or "efficiency" in q or "outlier" in q:
            return [
                "What are the peak hours for residential electricity consumption in the UK?",
                "How does the energy whitepaper technically define outliers?",
                "What was the average consumption on the coldest day recorded?"
            ]
        elif "weather" in q or "cold" in q or "temperature" in q:
            return [
                "Which month in 2013 had the highest average daily consumption?",
                "Which 5 households recorded the highest daily consumption?",
                "What are the top recommended energy conservation measures?"
            ]
        else:
            return [
                "What are the peak hours for residential electricity consumption in the UK?",
                "Which 5 households recorded the highest daily consumption?",
                "What is the average consumption for Standard vs Time of Use tariffs?"
            ]

    def process_query(self, query: str, return_details: bool = False):
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
            msg = f"Clarification required: {question}\n{options_str}"
            if return_details:
                return {
                    "response": msg,
                    "sources": [],
                    "followups": options,
                    "intent": "clarification_needed",
                    "sql_queries": [],
                    "status": "needs_clarification"
                }
            return msg
            
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
        
        if return_details:
            formatted_sources = []
            for s in doc_evidence.get("sources", []):
                src_name = Path(s.get("source", "Document")).name
                page_info = f" (Page {s['page']})" if s.get("page") else ""
                formatted_sources.append({
                    "title": f"{src_name}{page_info}",
                    "text": s.get("text", "").strip(),
                    "relevance": round(float(s.get("relevance", 0)), 2)
                })
            
            sql_list = [q.get("sql", "") for q in data_results.get("queries", [])] if data_results else []
            followups = self._generate_followups(query, refiner_output, data_results)
            
            return {
                "response": final_answer,
                "sources": formatted_sources,
                "followups": followups,
                "intent": refiner_output.intent,
                "sql_queries": sql_list,
                "data_rows": len(data_results.get("results", [])) if data_results else 0,
                "status": "success"
            }
            
        return final_answer

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Energy Intelligence API")

# Add CORS Middleware so frontend can communicate smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
