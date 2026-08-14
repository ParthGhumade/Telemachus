import os
from dotenv import load_dotenv
from google import genai
import warnings

# Suppress the AFC warning emitted by google-genai
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")

# Load environment variables
load_dotenv()

def get_llm():
    """
    Initializes and returns the raw google-genai Client.
    This client instance can be shared by the Refiner, Data, and Response agents.
    """
    key = os.getenv("gemini_api_key") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("API key is not set. Please check your .env file.")
        
    client = genai.Client(api_key=key)
    return client

if __name__ == "__main__":
    client = get_llm()
    print("Initialized GenAI Client successfully.")
