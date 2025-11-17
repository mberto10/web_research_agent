#!/usr/bin/env python3
"""Test script for the Research Agent API."""

import asyncio
import httpx
import os
from datetime import datetime

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_SECRET_KEY", "dev-key-change-in-prod")

headers = {"X-API-Key": API_KEY}


async def test_health():
    """Test health endpoint."""
    print("\n" + "="*60)
    print("Testing Health Endpoint")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")


async def test_create_task():
    """Test creating a research task."""
    print("\n" + "="*60)
    print("Testing Create Task")
    print("="*60)

    task_data = {
        "email": "test@example.com",
        "research_topic": "Latest developments in AI reasoning models",
        "frequency": "daily",
        "schedule_time": "09:00"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/tasks",
            json=task_data,
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Created Task ID: {data['id']}")
        print(f"Email: {data['email']}")
        print(f"Topic: {data['research_topic']}")
        return data['id']


async def test_get_tasks(email: str):
    """Test getting tasks by email."""
    print("\n" + "="*60)
    print(f"Testing Get Tasks for {email}")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE_URL}/tasks",
            params={"email": email},
            headers=headers
        )
        print(f"Status: {response.status_code}")
        tasks = response.json()
        print(f"Found {len(tasks)} task(s)")
        for task in tasks:
            print(f"  - {task['id']}: {task['research_topic']}")
        return tasks


async def test_update_task(task_id: str):
    """Test updating a task."""
    print("\n" + "="*60)
    print(f"Testing Update Task {task_id}")
    print("="*60)

    updates = {
        "research_topic": "AI developments in healthcare and medicine",
        "is_active": True
    }

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{API_BASE_URL}/tasks/{task_id}",
            json=updates,
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Updated topic: {data['research_topic']}")


async def test_batch_execute():
    """Test batch execution."""
    print("\n" + "="*60)
    print("Testing Batch Execution")
    print("="*60)

    batch_data = {
        "frequency": "daily",
        "callback_url": "https://defaulte29fc699127e425da75fed341dc328.38.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/05a44fcda78f472d9943dc52d3e66641/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2l-aB7LtZ7hDnyqUdZg4lccHzr0H_favXxG-VZqSmd8"  # Power Automate webhook URL
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/execute/batch",
            json=batch_data,
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Batch Status: {data['status']}")
        print(f"Tasks Found: {data['tasks_found']}")
        print(f"Started At: {data['started_at']}")


async def test_delete_task(task_id: str):
    """Test deleting a task."""
    print("\n" + "="*60)
    print(f"Testing Delete Task {task_id}")
    print("="*60)

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{API_BASE_URL}/tasks/{task_id}",
            headers=headers
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Deleted: {data['deleted']}")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("RESEARCH AGENT API TEST SUITE")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")

    try:
        # Test health
        await test_health()

        # Create a task
        task_id = await test_create_task()

        # Get tasks
        await test_get_tasks("test@example.com")

        # Update task
        await test_update_task(task_id)

        # Note: Uncomment to test batch execution (requires valid callback URL)
        # await test_batch_execute()

        # Delete task (cleanup)
        await test_delete_task(task_id)

        print("\n" + "="*60)
        print("✓ All tests completed successfully")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
