import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

import sys
from pathlib import Path

# Add backend to path so we can import llm
sys.path.append(str(Path(__file__).parent.parent.absolute()))
from llm import get_llm
from config import LLM_MODEL
from google.genai import types
from agents.utils import clean_json_response

class Clarification(BaseModel):
    question: str
    options: List[str] = []

class DataPlan(BaseModel):
    metrics: List[str] = []
    filters: List[str] = []
    group_by: List[str] = []
    operations: List[str] = []
    time_range: Optional[str] = None

class DocPlan(BaseModel):
    search_queries: List[str] = []

class RefinerOutput(BaseModel):
    status: str = Field(description="READY or NEEDS_CLARIFICATION")
    original_query: str
    refined_query: Optional[str] = None
    intent: str
    assumptions: List[str] = []
    clarification: Optional[Clarification] = None
    requires_data: bool = False
    requires_docs: bool = False
    data_plan: Optional[DataPlan] = None
    doc_plan: Optional[DocPlan] = None

REFINER_PROMPT = """You are the Query Refiner Agent for an Energy Intelligence system.

Your job is to transform a user's natural-language request into a precise, technically defined query plan that downstream agents can execute.

You do NOT answer the user's question.
You do NOT perform calculations.
You do NOT retrieve documents.
You do NOT execute SQL.

Your responsibilities:

1. Understand the user's actual intent.
2. Identify entities, metrics, operations, filters, comparisons, and time ranges.
3. Convert vague language into explicit technical definitions whenever a reasonable interpretation can be made.
4. Detect ambiguity that could materially change the result.
5. Decide whether the query requires:
   - structured data analysis,
   - document retrieval,
   - or both.
6. Produce a structured query plan for downstream agents.

IMPORTANT:
Never silently invent facts or dataset fields.

If the user uses an ambiguous term such as:
- unusual
- high
- low
- significant
- recent
- efficient
- excessive
- abnormal

you must determine whether the ambiguity can safely be resolved from context.

If it can be reasonably interpreted:
- make the interpretation explicit,
- include it in the refined query,
- mark it as an assumption.

If different interpretations would produce substantially different results:
- request clarification instead of arbitrarily choosing one.

For example:

User:
"Find unusually high consumption."

Possible interpretation:
"Daily mean consumption greater than the household's historical mean by 2 standard deviations."

Do not silently assume this definition. Either expose it as an assumption or ask the user to define "unusually high".

The refined query must be precise enough that another agent can independently construct the required database queries.

The final goal is deterministic, grounded analysis rather than an impressive-sounding interpretation.

User Query:
{query}
"""

class RefinerAgent:
    def __init__(self, model: str = LLM_MODEL):
        self.client = get_llm()
        self.model = model
        
    def refine(self, query: str) -> RefinerOutput:
        prompt = REFINER_PROMPT.format(query=query)
        
        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RefinerOutput,
                temperature=0.1,
            ),
        )
        response = chat.send_message(prompt)
        return RefinerOutput.model_validate_json(clean_json_response(response.text))
