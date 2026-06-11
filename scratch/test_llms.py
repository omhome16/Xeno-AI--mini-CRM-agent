import asyncio
import os
import sys
from dotenv import load_dotenv

# Set sys.path before imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crm-service"))

# Load env variables from .env
load_dotenv()

from app.agent.llm import DualLLMClient

async def test_llms():
    groq_key = os.getenv("GROQ_API_KEY", "")
    print(f"Loaded Keys:\nGroq: {groq_key[:10]}...")

    client = DualLLMClient(groq_key=groq_key)

    # 1. Test Groq call directly
    print("\n--- Testing Groq Direct ---")
    try:
        res = await client._call_groq("You are a helpful assistant", "Say hello")
        print(f"Groq output: {res}")
    except Exception as e:
        print(f"Groq failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test reason
    print("\n--- Testing client.reason() ---")
    try:
        res = await client.reason("You are a database intent parser", "Show me Bangalore customers")
        print(f"Reasoning output: {res}")
    except Exception as e:
        print(f"Reason failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_llms())
