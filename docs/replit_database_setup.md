# Replit Database Setup Prompt

## Task: Create PostgreSQL Database for Research Tasks

Create a PostgreSQL database for storing research tasks with this simple schema:

### Table: research_tasks

```sql
CREATE TABLE research_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    research_topic TEXT NOT NULL,
    frequency TEXT,  -- e.g., "daily", "weekly", "monthly"
    schedule_time TEXT,  -- e.g., "09:00"
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run_at TIMESTAMP
);

CREATE INDEX idx_research_tasks_email ON research_tasks(email);
CREATE INDEX idx_research_tasks_active ON research_tasks(is_active);
```

### Implementation Requirements

- Create database connection in `api/database.py` using SQLAlchemy
- Define the model in `api/models.py`
- Use async SQLAlchemy for better performance
- Include proper connection pooling

### Files to Create

1. `api/database.py` - Database connection and session management
2. `api/models.py` - SQLAlchemy model for research_tasks table
