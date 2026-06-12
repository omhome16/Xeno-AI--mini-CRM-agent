import asyncio
import os
import sys

# Set sys.path before imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crm-service"))

from dotenv import load_dotenv
load_dotenv()

import httpx
from app.main import app
from app.database import init_db, close_db
from app.config import get_settings

async def test_endpoints():
    settings = get_settings()
    await init_db(settings.DATABASE_URL)
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test Audience recommendations
        print("\n--- Testing /api/chat/recommendations/audience ---")
        try:
            res = await client.post("/api/chat/recommendations/audience")
            print(f"Status: {res.status_code}")
            # print response snippet
            data = res.json()
            print(f"Found {len(data)} recommendations.")
            for idx, rec in enumerate(data, 1):
                print(f"  {idx}. {rec['name']} (Count: {rec['count']}): {rec['reason']}")
                print(f"     Filters: {rec['filters']}")
        except Exception as e:
            print(f"Audience recommendations failed: {e}")

        # 2. Test Strategy recommendations
        print("\n--- Testing /api/chat/recommendations/strategy ---")
        try:
            res = await client.post("/api/chat/recommendations/strategy", json={
                "filters": {
                    "cities": ["Delhi"],
                    "tags": ["vip"]
                }
            })
            print(f"Status: {res.status_code}")
            print(f"Response: {res.json()}")
        except Exception as e:
            print(f"Strategy recommendations failed: {e}")

        # 3. Test Message recommendations
        print("\n--- Testing /api/chat/recommendations/message ---")
        try:
            # Let's call the LLM directly to see the raw response
            from app.agent.llm import DualLLMClient
            from app.agent.prompts import MESSAGE_RECOMMENDATION_PROMPT
            from app.agent.nodes import _fetch_brand_profile_ctx
            llm_client = DualLLMClient(gemini_key=settings.GEMINI_API_KEY)
            brand_profile = await _fetch_brand_profile_ctx()
            
            system_prompt = (
                MESSAGE_RECOMMENDATION_PROMPT
                .replace("{audience_desc}", "VIP customers in Delhi")
                .replace("{goal}", "VIP exclusive offer")
                .replace("{channel}", "whatsapp")
                .replace("{brand_profile}", brand_profile)
            )
            raw = await llm_client.reason(
                system_prompt=system_prompt,
                user_input="Generate 3 copy variations with reasons."
            )
            print("--- RAW LLM RESPONSE ---")
            safe_raw = raw.encode("utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
            print(safe_raw)
            print("------------------------")
            
            res = await client.post("/api/chat/recommendations/message", json={
                "audience_desc": "VIP customers in Delhi",
                "goal": "VIP exclusive offer",
                "channel": "whatsapp"
            })
            print(f"Status: {res.status_code}")
            data = res.json()
            print(f"Generated {len(data)} copy variations.")
            for item in data:
                safe_content = item['content'].encode("utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
                safe_reason = item['reason'].encode("utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
                print(f"  [{item['type']}] ({safe_reason}):\n{safe_content}\n")
        except Exception as e:
            print(f"Message recommendations failed: {e}")

        # 4. Test Copilot Chat Start
        print("\n--- Testing /api/chat copilot mode ---")
        try:
            res = await client.post("/api/chat", json={
                "message": "Change target city to Mumbai and set spend to 10000",
                "mode": "copilot",
                "conversation_id": "test-copilot-convo",
                "history": [],
                "brief": {
                    "cities": ["Delhi"],
                    "tags": ["vip"],
                    "min_spent": 5000,
                    "min_orders": 1
                }
            })
            print(f"Status: {res.status_code}")
            print(f"Response: {res.json()}")
        except Exception as e:
            print(f"Copilot mode failed: {e}")

    await close_db()

if __name__ == "__main__":
    asyncio.run(test_endpoints())
