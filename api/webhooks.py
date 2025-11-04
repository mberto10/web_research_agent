"""Webhook sender with retry logic."""
import httpx
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def send_webhook(
    url: str,
    payload: dict[str, Any],
    max_retries: int = 3
) -> bool:
    """Send webhook with exponential backoff retry.

    Args:
        url: Webhook URL to send to
        payload: JSON payload to send
        max_retries: Maximum number of retry attempts

    Returns:
        True if successful, False if all retries failed
    """
    task_id = payload.get('task_id', 'unknown')
    logger.info(f"📤 Sending webhook for task {task_id}")
    logger.info(f"   URL: {url}")
    logger.info(f"   Payload size: {len(str(payload))} chars")

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"   Attempt {attempt + 1}/{max_retries}...")
                response = await client.post(url, json=payload)
                logger.info(f"   Response status: {response.status_code}")
                logger.info(f"   Response body: {response.text[:200]}")
                response.raise_for_status()
                logger.info(f"✅ Webhook delivered successfully for task {task_id}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error: {e.response.status_code}")
            logger.error(f"   Response: {e.response.text[:200]}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Webhook failed after {max_retries} attempts")
                return False
            wait_time = 2 ** (attempt + 1)
            logger.warning(f"⚠️ Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(f"❌ Webhook error: {type(e).__name__}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Webhook failed after {max_retries} attempts")
                logger.error(f"   URL: {url}")
                logger.error(f"   Task: {task_id}")
                return False
            wait_time = 2 ** (attempt + 1)
            logger.warning(f"⚠️ Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

    return False
