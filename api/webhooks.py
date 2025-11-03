"""Webhook sender with retry logic."""
import httpx
import asyncio
from typing import Any


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

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                print(f"✓ Webhook delivered: {payload.get('task_id', 'unknown')}")
                return True

        except Exception as e:
            if attempt == max_retries - 1:
                # Final attempt failed
                print(f"❌ Webhook failed after {max_retries} attempts: {e}")
                print(f"   URL: {url}")
                print(f"   Task: {payload.get('task_id', 'unknown')}")
                return False

            # Exponential backoff: 2s, 4s, 8s
            wait_time = 2 ** (attempt + 1)
            print(f"⚠ Webhook attempt {attempt + 1} failed, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

    return False
