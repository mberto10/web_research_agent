#!/usr/bin/env python3
"""Example CRUD operations for research tasks."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, update, delete
from api.database import get_db, db_manager
from api.models import ResearchTask


async def create_task_example():
    """Example: Create a new research task."""
    print("\n1. Creating a new research task...")
    
    async for session in get_db():
        new_task = ResearchTask(
            email="user@example.com",
            research_topic="artificial intelligence trends",
            frequency="daily",
            schedule_time="09:00",
            is_active=True,
        )
        
        session.add(new_task)
        await session.commit()
        await session.refresh(new_task)
        
        print(f"   ✓ Created task: {new_task.id}")
        print(f"   - Topic: {new_task.research_topic}")
        print(f"   - Email: {new_task.email}")
        print(f"   - Frequency: {new_task.frequency}")
        
        return new_task.id


async def read_tasks_example(email: str):
    """Example: Read all tasks for a user."""
    print(f"\n2. Reading all tasks for {email}...")
    
    async for session in get_db():
        result = await session.execute(
            select(ResearchTask)
            .where(ResearchTask.email == email)
            .order_by(ResearchTask.created_at.desc())
        )
        tasks = result.scalars().all()
        
        print(f"   Found {len(tasks)} task(s):")
        for task in tasks:
            print(f"   - {task.research_topic} ({task.frequency})")
        
        return tasks


async def update_task_example(task_id):
    """Example: Update a research task."""
    print(f"\n3. Updating task {task_id}...")
    
    async for session in get_db():
        result = await session.execute(
            select(ResearchTask).where(ResearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task:
            task.last_run_at = datetime.utcnow()
            task.frequency = "weekly"
            await session.commit()
            
            print(f"   ✓ Updated task:")
            print(f"   - New frequency: {task.frequency}")
            print(f"   - Last run: {task.last_run_at}")


async def read_active_tasks_example():
    """Example: Read all active tasks."""
    print("\n4. Reading all active tasks...")
    
    async for session in get_db():
        result = await session.execute(
            select(ResearchTask)
            .where(ResearchTask.is_active == True)
            .order_by(ResearchTask.created_at.desc())
        )
        tasks = result.scalars().all()
        
        print(f"   Found {len(tasks)} active task(s)")
        return tasks


async def deactivate_task_example(task_id):
    """Example: Deactivate a task (soft delete)."""
    print(f"\n5. Deactivating task {task_id}...")
    
    async for session in get_db():
        await session.execute(
            update(ResearchTask)
            .where(ResearchTask.id == task_id)
            .values(is_active=False)
        )
        await session.commit()
        print("   ✓ Task deactivated")


async def delete_task_example(task_id):
    """Example: Delete a task permanently."""
    print(f"\n6. Deleting task {task_id} permanently...")
    
    async for session in get_db():
        await session.execute(
            delete(ResearchTask).where(ResearchTask.id == task_id)
        )
        await session.commit()
        print("   ✓ Task deleted permanently")


async def main():
    """Run all examples."""
    print("="* 60)
    print("RESEARCH TASKS - CRUD OPERATIONS EXAMPLES")
    print("="* 60)
    
    try:
        task_id = await create_task_example()
        
        await read_tasks_example("user@example.com")
        
        await update_task_example(task_id)
        
        await read_active_tasks_example()
        
        await deactivate_task_example(task_id)
        
        await read_active_tasks_example()
        
        await delete_task_example(task_id)
        
        print("\n" + "="* 60)
        print("All examples completed successfully!")
        print("="* 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
