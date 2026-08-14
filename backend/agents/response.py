import sys
from typing import Dict, Any, List
from pathlib import Path
from pydantic import BaseModel

sys.path.append(str(Path(__file__).parent.parent.absolute()))
from llm import get_llm
from config import LLM_MODEL
from google.genai import types

RESPONSE_AGENT_PROMPT = """You are the Response Agent for an Energy Intelligence system.

Your job is to produce the final answer to the user's original question using ONLY the information supplied by the upstream agents.

You receive:
1. The original user query.
2. The Refiner Agent's interpretation (Refined Query).
3. Document evidence from the Docs Agent, when available.
4. Exact structured-data results from the Data Agent, when available.

YOUR RESPONSIBILITIES:
1. Answer the user's original question clearly.
2. Respect the refined interpretation. Make the important assumptions visible.
3. Ground numerical claims in Data Agent results. Do not calculate a new numerical result from memory.
4. Ground document-based claims in retrieved evidence. Cite the document name and page.
5. Mention limitations when the available evidence is insufficient.
6. Avoid hallucination.

If the Data Agent reports NO_DATA, do not fabricate an answer.
If the supplied evidence cannot answer the question, say so.

--- CONTEXT ---
Original Query: {original_query}

Refined Query / Interpretation: {refined_query}

Assumptions Made: {assumptions}

Document Evidence (Docs Agent):
{doc_evidence}

Numerical Results (Data Agent):
{data_results}

Limitations / Errors: {limitations}
----------------

Please provide the final helpful response based on the context provided above.
"""

class ResponseAgent:
    def __init__(self, model: str = LLM_MODEL):
        self.client = get_llm()
        self.model = model
        
    def synthesize(self, 
                   original_query: str, 
                   refined_query: str, 
                   assumptions: List[str], 
                   doc_evidence: Dict[str, Any], 
                   data_results: Dict[str, Any],
                   limitations: List[str]) -> str:
                       
        prompt = RESPONSE_AGENT_PROMPT.format(
            original_query=original_query,
            refined_query=refined_query,
            assumptions=assumptions,
            doc_evidence=doc_evidence,
            data_results=data_results,
            limitations=limitations
        )
        
        # This agent just returns a natural language string, so we don't need structured output
        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                temperature=0.1,
            ),
        )
        response = chat.send_message(prompt)
        return response.text
