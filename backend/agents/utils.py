import re


def clean_json_response(text: str) -> str:
    """
    Strip markdown code fences from LLM responses.
    
    Some models (e.g. Gemma) wrap their JSON output in markdown fences like:
        ```json
        { ... }
        ```
    This function extracts the raw JSON string.
    """
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()
