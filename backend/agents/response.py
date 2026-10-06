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
        try:
            self.client = get_llm()
        except Exception as e:
            self.client = None
            print(f"[ResponseAgent] Note: LLM client not configured ({e}). Running in resilient fallback mode.")
        self.model = model
        
    def synthesize(self, 
                   original_query: str, 
                   refined_query: str, 
                   assumptions: List[str], 
                   doc_evidence: Dict[str, Any], 
                   data_results: Dict[str, Any],
                   limitations: List[str]) -> str:
                       
        if self.client:
            try:
                prompt = RESPONSE_AGENT_PROMPT.format(
                    original_query=original_query,
                    refined_query=refined_query,
                    assumptions=assumptions,
                    doc_evidence=doc_evidence,
                    data_results=data_results,
                    limitations=limitations
                )
                chat = self.client.chats.create(
                    model=self.model,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                    ),
                )
                response = chat.send_message(prompt)
                return response.text
            except Exception as e:
                print(f"[ResponseAgent] Warning during LLM generation ({e}). Falling back to grounded excerpt synthesis.")

        # Grounded fallback synthesis directly from retrieved RAG evidence
        sources = doc_evidence.get("sources", [])
        if sources:
            response_parts = [
                f"### Evidence from Retrieved Documents\n",
                f"Based on the indexed energy reports and reference documentation:\n"
            ]
            for i, src in enumerate(sources[:3]):
                source_name = Path(src.get('source', 'document')).name
                page_info = f" (Page {src.get('page')})" if src.get('page') else ""
                relevance_info = f" [Relevance: {src.get('relevance', 0):.0%}]"
                response_parts.append(f"**{i+1}. `{source_name}`{page_info}{relevance_info}:**\n> {src.get('text', '').strip()}\n")
            
            if not self.client:
                response_parts.append("\n*(Tip: Add `gemini_api_key` to `.env` to enable full conversational LLM synthesis)*")
            return "\n".join(response_parts)
            
        return "I could not find relevant documentation or dataset records answering your query."

