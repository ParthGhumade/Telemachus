import sys
import os
import json
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "backend"))

from orchestrator import Orchestrator

prompts = [
    # 1. Document RAG: Conservation measures
    "What are the top recommended energy conservation measures to reduce domestic electricity usage?",
    
    # 2. Document RAG: Diurnal peak cycles
    "What are the peak hours for residential electricity consumption in the UK and what drives them?",
    
    # 3. Document RAG: Outlier & high consumption definition
    "How does the energy whitepaper technically define unusually high consumption and outliers?",
    
    # 4. Data Analytics: Top 5 consuming households
    "Which 5 households recorded the highest average daily consumption across the dataset?",
    
    # 5. Data Analytics: Tariff comparison (Std vs ToU)
    "What is the average daily energy consumption for households on Standard (Std) versus Time of Use (ToU) tariffs?",
    
    # 6. Data Analytics: ACORN socio-economic groups
    "What is the average daily consumption grouped by ACORN classification across all households?",
    
    # 7. Data Analytics: Weather correlation (Coldest day)
    "What was the average energy consumption on the coldest day recorded in London?",
    
    # 8. Hybrid RAG + Data: Evening peak causes & max reading
    "According to the reports, why do households show an evening peak, and what does the data show?",
    
    # 9. Data Analytics: Seasonal / Monthly extremes in 2013
    "Which month in 2013 had the highest average daily consumption across all households?",
    
    # 10. Boundary / Timeline Handling (Outside 2011-2014)
    "What was the total household energy consumption in December 2025?"
]

def run_tests():
    print("=" * 80)
    print("TELEMACHUS PIPELINE VERIFICATION: 10 PROMPTS TEST SUITE")
    print("=" * 80)
    
    orc = Orchestrator()
    results = []
    
    for i, p in enumerate(prompts, 1):
        print(f"\n[{i}/10] TESTING PROMPT: \"{p}\"")
        start_time = time.time()
        try:
            response = orc.process_query(p)
            elapsed = time.time() - start_time
            print(f"--> Response ({elapsed:.2f}s):\n{response}\n")
            results.append({
                "index": i,
                "prompt": p,
                "status": "SUCCESS",
                "elapsed_seconds": round(elapsed, 2),
                "response": response
            })
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"--> ERROR ({elapsed:.2f}s): {e}\n")
            results.append({
                "index": i,
                "prompt": p,
                "status": "ERROR",
                "elapsed_seconds": round(elapsed, 2),
                "error": str(e)
            })
            
    print("=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    print(f"Total Prompts: {len(prompts)} | Succeeded: {success_count} | Failed: {len(prompts) - success_count}")
    
    out_path = ROOT_DIR / "test_results_10_prompts.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Full results saved to '{out_path.name}'")

if __name__ == "__main__":
    run_tests()
