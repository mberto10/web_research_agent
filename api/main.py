"""Research Agent API - Subscription management + batch execution."""
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID
import os

from api.database import get_db, db_manager
from api import schemas, crud
from api.webhooks import send_webhook

app = FastAPI(
    title="Research Agent API",
    description="Manage research subscriptions and execute batch briefings",
    version="1.0.0"
)

# --- Authentication ---

API_KEY = os.getenv("API_SECRET_KEY", "dev-key-change-in-prod")


async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# --- Health Check ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "research-agent-api"
    }


# --- Subscription Management Endpoints ---

@app.post(
    "/tasks",
    response_model=schemas.TaskResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Create research subscription"
)
async def create_task(
    task: schemas.TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new research subscription for a user.

    Args:
        task: Task creation data (email, topic, frequency, schedule_time)

    Returns:
        Created task with ID and timestamps
    """
    db_task = await crud.create_task(
        db,
        task.email,
        task.research_topic,
        task.frequency,
        task.schedule_time
    )
    return db_task.to_dict()


@app.get(
    "/tasks",
    response_model=list[schemas.TaskResponse],
    dependencies=[Depends(verify_api_key)],
    summary="Get tasks by email"
)
async def get_tasks(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all research tasks for a specific email.

    Args:
        email: User email address

    Returns:
        List of tasks for the email
    """
    tasks = await crud.get_tasks_by_email(db, email)
    return [task.to_dict() for task in tasks]


@app.patch(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Update task"
)
async def update_task(
    task_id: UUID,
    updates: schemas.TaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing research task.

    Args:
        task_id: UUID of the task
        updates: Fields to update

    Returns:
        Updated task

    Raises:
        HTTPException: 404 if task not found
    """
    task = await crud.update_task(
        db,
        task_id,
        **updates.model_dump(exclude_unset=True)
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@app.delete(
    "/tasks/{task_id}",
    dependencies=[Depends(verify_api_key)],
    summary="Delete task"
)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a research task.

    Args:
        task_id: UUID of the task

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: 404 if task not found
    """
    deleted = await crud.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True, "task_id": str(task_id)}


# --- Batch Execution Endpoint ---

@app.post(
    "/execute/batch",
    response_model=schemas.BatchExecuteResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Execute batch research"
)
async def execute_batch(
    request: schemas.BatchExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Execute research for all tasks matching the frequency.

    This endpoint:
    1. Queries database for active tasks with matching frequency
    2. Starts background execution for each task
    3. Sends webhook to callback_url for each completed task

    Args:
        request: Batch execution request (frequency, callback_url)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution status with task count
    """

    # Get all active tasks for this frequency
    tasks = await crud.get_tasks_by_frequency(db, request.frequency)

    if not tasks:
        return schemas.BatchExecuteResponse(
            status="completed",
            frequency=request.frequency,
            tasks_found=0,
            started_at=datetime.utcnow().isoformat()
        )

    # Start background execution
    background_tasks.add_task(
        run_batch_research,
        tasks,
        request.callback_url
    )

    return schemas.BatchExecuteResponse(
        status="running",
        frequency=request.frequency,
        tasks_found=len(tasks),
        started_at=datetime.utcnow().isoformat()
    )


# --- Background Execution Logic ---

async def run_batch_research(tasks: list, callback_url: str):
    """Execute research for each task sequentially.

    For each task:
    1. Run the research agent with the task's topic
    2. Format results into webhook payload
    3. Send webhook to Langdock
    4. Update last_run_at timestamp

    Args:
        tasks: List of ResearchTask objects
        callback_url: Langdock webhook URL
    """
    from core.graph import build_graph
    from core.state import State
    from tools import register_default_adapters

    # Initialize research tools once
    register_default_adapters()
    graph = build_graph()

    print(f"\n{'='*60}")
    print(f"Starting batch execution for {len(tasks)} tasks")
    print(f"{'='*60}\n")

    for idx, task in enumerate(tasks, 1):
        print(f"[{idx}/{len(tasks)}] Processing: {task.email} - {task.research_topic}")

        try:
            # Execute research
            result = graph.invoke(State(user_request=task.research_topic))

            # Format payload
            payload = {
                "task_id": str(task.id),
                "email": task.email,
                "research_topic": task.research_topic,
                "frequency": task.frequency,
                "status": "completed",
                "result": {
                    "sections": result.sections,
                    "citations": [
                        {
                            "title": e.title,
                            "url": e.url,
                            "snippet": e.snippet
                        }
                        for e in result.evidence[:10]  # Top 10 citations
                    ],
                    "metadata": {
                        "evidence_count": len(result.evidence),
                        "executed_at": datetime.utcnow().isoformat()
                    }
                }
            }

            # Send webhook
            success = await send_webhook(callback_url, payload)

            if success:
                # Update last_run_at timestamp
                async for session in db_manager.get_session():
                    await crud.mark_task_executed(session, task.id)

        except Exception as e:
            print(f"❌ Error processing task {task.id}: {e}")

            # Send error webhook for this task
            error_payload = {
                "task_id": str(task.id),
                "email": task.email,
                "research_topic": task.research_topic,
                "frequency": task.frequency,
                "status": "failed",
                "error": str(e),
                "executed_at": datetime.utcnow().isoformat()
            }
            await send_webhook(callback_url, error_payload)

    print(f"\n{'='*60}")
    print(f"Batch execution complete: {len(tasks)} tasks processed")
    print(f"{'='*60}\n")


# --- Optional: Parallel Execution (Future Enhancement) ---
#
# Uncomment and use this for parallel execution when ready:
#
# import asyncio
#
# async def run_batch_research_parallel(tasks: list, callback_url: str):
#     """Execute research in parallel with concurrency limit."""
#     semaphore = asyncio.Semaphore(5)  # Max 5 concurrent executions
#
#     async def execute_one(task):
#         async with semaphore:
#             # ... same logic as sequential version
#             pass
#
#     await asyncio.gather(*[execute_one(task) for task in tasks])
