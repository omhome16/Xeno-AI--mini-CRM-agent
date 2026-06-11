import asyncio
import logging
from app.services.redis_queue import pop_from_queue
from app.workers.campaign_worker import dispatch_campaign

logger = logging.getLogger(__name__)

async def start_dispatch_worker():
    """Background worker that processes outbound campaign dispatches from Redis queue."""
    logger.info("Outbox Dispatch Queue Worker started.")
    
    while True:
        try:
            # Block-pop a campaign dispatch task from the queue
            # Timeout is 1 second to allow graceful loops
            task = pop_from_queue("crm_dispatch_queue", timeout=2)
            if task:
                campaign_id = task.get("campaign_id")
                conversation_id = task.get("conversation_id")
                
                if campaign_id:
                    logger.info(f"Picked up dispatch job for campaign: {campaign_id[:8]}...")
                    # Run the dispatch logic
                    await dispatch_campaign(campaign_id, conversation_id=conversation_id)
            
            # Yield control back to event loop
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Outbox Dispatch Queue Worker shutting down.")
            break
        except Exception as e:
            logger.error(f"Error in Outbox Dispatch Queue Worker loop: {e}")
            await asyncio.sleep(2)  # Pause on error to avoid hot looping
