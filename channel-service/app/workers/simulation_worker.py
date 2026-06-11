import asyncio
import logging
from app.services.redis_queue import pop_from_queue
from app.simulator import schedule_delivery

logger = logging.getLogger(__name__)

async def start_simulation_worker():
    """Background worker that pops events from channel_simulation_queue and schedules simulations."""
    logger.info("Channel Simulation Worker started.")

    while True:
        try:
            task = await asyncio.to_thread(pop_from_queue, "channel_simulation_queue", 2)
            if task:
                comm_id = task.get("communication_id")
                recipient = task.get("recipient")
                message = task.get("message")
                channel = task.get("channel")

                if comm_id and recipient and message and channel:
                    logger.info(f"Picked up simulation job for communication: {comm_id[:8]}...")
                    schedule_delivery(
                        communication_id=comm_id,
                        recipient=recipient,
                        message=message,
                        channel=channel.lower(),
                    )
                else:
                    logger.warning(f"Invalid simulation job popped: {task}")

            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Channel Simulation Worker shutting down.")
            break
        except Exception as e:
            logger.error(f"Error in Channel Simulation Worker loop: {e}")
            await asyncio.sleep(2)
