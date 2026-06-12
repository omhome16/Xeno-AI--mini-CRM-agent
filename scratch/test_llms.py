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
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    print(f"Loaded Keys:\nGemini: {gemini_key[:10]}...")

    client = DualLLMClient(gemini_key=gemini_key)

    # 1. Test Gemini call directly
    print("\n--- Testing Gemini Direct ---")
    try:
        res = await client._call_gemini("You are a helpful assistant. Keep it concise. No JSON constraint.", "Say hello", want_json=False)
        print(f"Gemini output: {res}")
    except Exception as e:
        print(f"Gemini failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test reason
    print("\n--- Testing client.reason() ---")
    try:
        res = await client.reason("You are a database intent parser. Return JSON only.", "Show me Bangalore customers")
        print(f"Reasoning output: {res}")
    except Exception as e:
        print(f"Reason failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_llms())
