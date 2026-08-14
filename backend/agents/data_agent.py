import json
import sys
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pathlib import Path

# Add backend to path so we can import modules
sys.path.append(str(Path(__file__).parent.parent.absolute()))
from llm import get_llm
from config import LLM_MODEL
from database import get_connection
from google.genai import types
from agents.utils import clean_json_response

class QueryResult(BaseModel):
    purpose: str
    sql: str

class LLMQueryPlan(BaseModel):
    queries: List[QueryResult]
    timeline_acknowledgement: Optional[str] = Field(default=None, description="If the requested date is outside the available dataset timeline (2011-2014) or refers to the future/past, provide a brief acknowledgement here. Otherwise, leave null.")

class DataAgentOutput(BaseModel):
    status: str = Field(description="SUCCESS, NO_DATA, or ERROR")
    queries: List[QueryResult] = []
    results: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}
    limitations: List[str] = []

DATA_AGENT_PROMPT = """You are the Data Agent for an Energy Intelligence system.

Your job is to translate a refined query plan into deterministic analytical operations over the structured energy dataset using DuckDB.

You do NOT directly answer the user.
You do NOT invent numerical results.
You do NOT perform semantic document retrieval.
You do NOT modify the user's intent.

Your responsibilities:
1. Read the Refiner Agent's structured query plan.
2. Determine which structured datasets are required.
3. Construct appropriate DuckDB queries.
4. Return the exact queries to execute.

DATA SOURCES:
A unified view called `energy_data` exists combining daily, hhblock, and halfhourly parquet files.

ACTUAL SCHEMA (key columns):
- LCLid (VARCHAR) — household identifier
- day (VARCHAR) — date stored as string, e.g. '2013-01-05'. MUST cast to DATE for comparisons: CAST(day AS DATE)
- energy_median (DOUBLE)
- energy_mean (DOUBLE)
- energy_max (DOUBLE)
- energy_min (DOUBLE)
- energy_sum (DOUBLE)
- energy_std (DOUBLE)
- energy_count (BIGINT)
- stdorToU (VARCHAR) — tariff type (Std or ToU)
- Acorn (VARCHAR) — ACORN classification
- Acorn_grouped (VARCHAR) — grouped ACORN classification
- hh_0 through hh_47 (DOUBLE) — 48 half-hourly energy readings per day
- temperatureMax, temperatureMin, temperatureHigh, temperatureLow (DOUBLE) — weather
- windSpeed, humidity, cloudCover, pressure, uvIndex (DOUBLE) — weather
- summary (VARCHAR) — weather summary

CRITICAL RULES:
1. The `day` column is VARCHAR. Always use CAST(day AS DATE) for date comparisons and ordering.
2. Numerical calculations must be performed by DuckDB, not by the LLM.
3. Do not estimate values when exact data is available.
4. Use appropriate aggregation functions.
5. When calculating statistical thresholds, perform the calculation in DuckDB.
6. Provide SQL queries compatible with DuckDB syntax.
7. Use double quotes for column names with special characters, e.g. "energy(kWh/hh)".
8. DATA TIMELINE: The dataset covers the period 2011-2014. If the user's query asks for future data or data outside this period, populate the `timeline_acknowledgement` field acknowledging this limitation (e.g., "The dataset only covers 2011-2014, so I cannot provide data for requested dates outside this range. However, here is the relevant historical data...").

Construct SQL based on the structured query plan:
Refined Query: {refined_query}
Data Plan: {data_plan}

Provide your response with the required queries. The actual execution will be performed by the system.
"""

class DataAgent:
    def __init__(self, model: str = LLM_MODEL):
        self.client = get_llm()
        self.model = model
        
    def execute_queries(self, queries: List[QueryResult]) -> List[Dict[str, Any]]:
        conn = get_connection()
        combined_results = []
        
        for q in queries:
            try:
                # Execute SQL with DuckDB
                result_df = conn.execute(q.sql).fetchdf()
                # Convert DataFrame to list of dicts for JSON serialization
                records = result_df.to_dict(orient='records')
                combined_results.extend(records)
            except Exception as e:
                print(f"SQL Execution Error on query '{q.purpose}': {e}")
                
        conn.close()
        return combined_results
        
    def analyze(self, refined_query: str, data_plan: Any) -> DataAgentOutput:
        prompt = DATA_AGENT_PROMPT.format(
            refined_query=refined_query, 
            data_plan=data_plan
        )
        
        try:
            chat = self.client.chats.create(
                model=self.model,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LLMQueryPlan,
                    temperature=0.1,
                ),
            )
            response = chat.send_message(prompt)
            llm_plan = LLMQueryPlan.model_validate_json(clean_json_response(response.text))
            
            # Now we execute the generated queries
            results = self.execute_queries(llm_plan.queries)
            
            status = "SUCCESS" if results else "NO_DATA"
            
            limitations = []
            if llm_plan.timeline_acknowledgement:
                limitations.append(llm_plan.timeline_acknowledgement)
            
            return DataAgentOutput(
                status=status,
                queries=llm_plan.queries,
                results=results,
                summary={"row_count": len(results)},
                limitations=limitations
            )
        except Exception as e:
            print(f"[DataAgent ERROR] {type(e).__name__}: {e}")
            return DataAgentOutput(
                status="ERROR",
                queries=[],
                results=[],
                summary={},
                limitations=[str(e)]
            )
