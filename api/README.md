# Research Agent API

FastAPI-based REST API for managing research subscriptions and executing batch briefings.

## Architecture

```
External Scheduler (Langdock/Cron)
    ↓
POST /execute/batch
    ↓
Query database for active tasks
    ↓
Execute research for each task (sequential)
    ↓
Webhook results back to Langdock (per user)
```

## Files

- `main.py` - FastAPI app with all endpoints
- `schemas.py` - Pydantic request/response models
- `crud.py` - Database CRUD operations
- `webhooks.py` - Webhook delivery with retry logic
- `database.py` - PostgreSQL connection management
- `models.py` - SQLAlchemy ORM models

## API Endpoints

### Health Check
```bash
GET /health
```

### Subscription Management

**Create Task**
```bash
POST /tasks
Headers: X-API-Key: <your-api-key>

{
  "email": "user@example.com",
  "research_topic": "AI developments in healthcare",
  "frequency": "daily",
  "schedule_time": "09:00"
}
```

**Get Tasks by Email**
```bash
GET /tasks?email=user@example.com
Headers: X-API-Key: <your-api-key>
```

**Update Task**
```bash
PATCH /tasks/{task_id}
Headers: X-API-Key: <your-api-key>

{
  "research_topic": "AI in finance",
  "is_active": true
}
```

**Delete Task**
```bash
DELETE /tasks/{task_id}
Headers: X-API-Key: <your-api-key>
```

### Batch Execution

**Execute Batch Research**
```bash
POST /execute/batch
Headers: X-API-Key: <your-api-key>

{
  "frequency": "daily",
  "callback_url": "https://langdock.io/webhook/delivery"
}
```

Response:
```json
{
  "status": "running",
  "frequency": "daily",
  "tasks_found": 47,
  "started_at": "2025-11-03T20:00:00Z"
}
```

## Webhook Payload

After each task completes, a webhook is sent:

**Success:**
```json
{
  "task_id": "uuid",
  "email": "user@example.com",
  "research_topic": "AI developments",
  "frequency": "daily",
  "status": "completed",
  "result": {
    "sections": ["Section 1 content...", "Section 2..."],
    "citations": [
      {
        "title": "Article title",
        "url": "https://...",
        "snippet": "..."
      }
    ],
    "metadata": {
      "evidence_count": 12,
      "executed_at": "2025-11-03T20:05:00Z"
    }
  }
}
```

**Error:**
```json
{
  "task_id": "uuid",
  "email": "user@example.com",
  "status": "failed",
  "error": "Error message",
  "executed_at": "2025-11-03T20:05:00Z"
}
```

## Running the API

### Development
```bash
python run_api.py
```

### Production (Replit)
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - For LLM calls
- `API_SECRET_KEY` - For API authentication

Optional:
- `EXA_API_KEY` - For Exa search
- `PERPLEXITY_API_KEY` - For Perplexity search
- `LANGFUSE_PUBLIC_KEY` - For tracing
- `LANGFUSE_SECRET_KEY` - For tracing
- `LANGFUSE_HOST` - For tracing
- `PORT` - API port (default: 8000)
- `HOST` - API host (default: 0.0.0.0)

## Authentication

All endpoints (except `/health`) require API key authentication:

```bash
Headers:
  X-API-Key: your-secret-key
```

## Batch Execution Flow

1. **External trigger** (Langdock workflow or cron job) calls `/execute/batch`
2. API queries database for all active tasks with matching frequency
3. For each task:
   - Execute research agent with task's topic
   - Format results into structured payload
   - Send webhook to callback URL
   - Update `last_run_at` timestamp
4. Return immediately with task count
5. Execution happens in background

## Future Enhancements

### Parallel Execution
Uncomment the `run_batch_research_parallel()` function in `main.py` to enable concurrent execution with rate limiting.

```python
# In main.py - already scaffolded
async def run_batch_research_parallel(tasks, callback_url):
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent
    # ...
```

### Webhook Delivery Tracking
Add database table to track webhook delivery attempts and failures for debugging.

### Rate Limiting
Add per-user or per-email rate limiting to prevent abuse.

## Interactive API Docs

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
