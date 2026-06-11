import asyncio
import os
import sys
from dotenv import load_dotenv

# Set sys.path before imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crm-service"))

# Load env variables from .env
load_dotenv()

from app.agent.graph import build_campaign_graph
from app.agent.llm import DualLLMClient
from app.agent.state import CampaignState
from app.database import init_db, close_db
from app.config import get_settings

async def test_graph():
    settings = get_settings()
    # Initialize DB pools since agent needs to query stats / brand profile
    await init_db(settings.DATABASE_URL)
    
    llm_client = DualLLMClient(
        groq_key=settings.GROQ_API_KEY,
    )

    state: CampaignState = {
        "user_message": "Let's plan a campaign for customers in Bangalore",
        "mode": "brainstorm",
        "conversation_id": "test-convo-id",
        "messages": [],
        "brief": {},
        "current_step": "starting",
    }

    try:
        graph = build_campaign_graph(llm_client)
        print("Running graph workflow...")
        config = {"configurable": {"thread_id": "test-convo-id"}}
        
        async for event in graph.astream(state, config=config):
            print(f"\n--- Graph event: {event} ---")
    except Exception as e:
        print(f"\nGraph execution failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(test_graph())
