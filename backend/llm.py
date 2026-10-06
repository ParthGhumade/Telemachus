import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import warnings

# Suppress the AFC warning emitted by google-genai
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")

# Load environment variables deterministically
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


def get_llm():
    """
    Initializes and returns the raw google-genai Client.
    Validates that a real API key is present.
    """
    key = os.getenv("gemini_api_key") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key or key.startswith("PASTE_") or key.startswith("your_") or len(key.strip()) < 10:
        raise ValueError("API key is not configured. Please set 'gemini_api_key' in your .env file.")
        
    client = genai.Client(api_key=key)
    return client


if __name__ == "__main__":
    try:
        client = get_llm()
        print("Initialized GenAI Client successfully.")
    except Exception as e:
        print(f"GenAI Client note: {e}")
