# Web Research Agent - Replit Setup

## Overview

This is a deterministic, tool-centric research assistant built on LangGraph. It executes research workflows expressed as YAML strategies through pluggable adapters, using a scoped LLM for classification, parameter filling, and query refinement.

**Last Updated**: 2025-11-03

## Project Type

- **Language**: Python 3.12+
- **Framework**: LangGraph (workflow engine)
- **Project Type**: CLI-based research agent (no web frontend)
- **Main Entry Points**:
  - `run_daily_briefing.py` - Generate news briefings on topics
  - `verify_setup.py` - Verify system configuration
  - `debug_viewer.py` - View debug logs from research sessions

## Current State

✅ **Fully Configured and Ready**
- Python 3.12 installed
- All dependencies installed via uv package manager
- API keys configured (OpenAI, Exa, Sonar/Perplexity)
- Setup verification passing
- Workflow configured for setup verification

## Configuration

### API Keys (Configured in Replit Secrets)
- `OPENAI_API_KEY` - For LLM analysis and synthesis
- `EXA_API_KEY` - For semantic search
- `SONAR_API_KEY` - For Perplexity Sonar search

### Database (PostgreSQL)
- **Provider**: Replit's built-in PostgreSQL (Neon-backed)
- **Environment Variables**: Automatically configured (DATABASE_URL, PGHOST, PGPORT, etc.)
- **Schema**: research_tasks table for storing scheduled research tasks
- **Features**: Async SQLAlchemy with proper TLS verification

### Dependencies
All dependencies are managed in `pyproject.toml`:
- **Core**: langgraph, pydantic, pyyaml, jsonschema, langfuse
- **Search Tools**: exa-py, openai
- **Database**: sqlalchemy[asyncio], asyncpg, psycopg2-binary
- **Utils**: python-dotenv

### Workflows
- **verify-setup**: Runs `verify_setup.py` to check system configuration

## How to Use

### Run a News Briefing
```bash
python run_daily_briefing.py --topic "artificial intelligence"
```

With additional options:
```bash
python run_daily_briefing.py --topic "renewable energy" --industry "technology" --timeframe "last 7 days" --verbose
```

### Debug Mode
```bash
python run_daily_briefing.py --topic "quantum computing" --debug
```

### View Debug Logs
```bash
python debug_viewer.py --summary
python debug_viewer.py --prompts
python debug_viewer.py --errors
```

### Database Operations

Initialize the database (first time setup):
```bash
python init_database.py
```

Test CRUD operations:
```bash
python example_task_operations.py
```

## Project Structure

```
/
├── api/               # Database API
│   ├── database.py    # Async SQLAlchemy connection
│   ├── models.py      # Database models
│   └── __init__.py
├── core/              # Core workflow engine
│   ├── graph.py       # LangGraph workflow builder
│   ├── state.py       # State management
│   ├── scope.py       # Request classification
│   └── config.py      # Configuration loader
├── strategies/        # YAML workflow definitions
│   ├── index.yaml     # Strategy registry
│   ├── daily_news_briefing.yaml
│   ├── news/          # News-focused strategies
│   ├── company/       # Company research strategies
│   └── general/       # General-purpose strategies
├── tools/             # Tool adapters
│   ├── exa.py         # Exa search adapter
│   ├── sonar.py       # Perplexity Sonar adapter
│   └── registry.py    # Tool registration
├── config/
│   └── settings.yaml  # LLM configs and prompts
├── tests/             # Unit tests
├── init_database.py   # Database initialization
└── example_task_operations.py  # CRUD examples
```

## Key Features

1. **Declarative Workflows**: Research strategies defined in YAML
2. **Pluggable Tools**: Easy to add new search/analysis tools
3. **LLM-Scoped**: Uses LLM only for classification and refinement
4. **Evidence-Based**: Collects and cites sources
5. **Configurable**: Centralized settings for models and prompts

## Development Notes

### Adding New Strategies
1. Create YAML file in `strategies/` directory
2. Add entry to `strategies/index.yaml`
3. Define `tool_chain`, `queries`, `limits`, and `render` sections

### Testing
```bash
pytest tests/
```

### Package Management
This project uses `uv` (via Replit's Python packager):
- `pyproject.toml` defines dependencies
- `.pythonlibs/` contains virtual environment (gitignored)
- Fixed setuptools configuration to support flat layout with multiple packages

## Database Schema

### research_tasks Table
Stores scheduled research tasks for automated briefings.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key (auto-generated) |
| email | TEXT | User email address |
| research_topic | TEXT | Topic to research |
| frequency | TEXT | Schedule frequency (daily, weekly, monthly) |
| schedule_time | TEXT | Time to run (e.g., "09:00") |
| is_active | BOOLEAN | Whether task is active |
| created_at | TIMESTAMP | When task was created |
| last_run_at | TIMESTAMP | Last execution time |

**Indexes:**
- `idx_research_tasks_email` on email
- `idx_research_tasks_active` on is_active

## Recent Changes

- **2025-11-03**: Initial Replit setup
  - Fixed `pyproject.toml` to include package discovery configuration
  - Installed all dependencies
  - Configured API keys via Replit Secrets
  - Updated `.gitignore` for Python and generated files
  - Verified complete setup with all checks passing

- **2025-11-03**: Database integration
  - Added PostgreSQL database for research task storage
  - Implemented async SQLAlchemy with proper TLS verification
  - Created ResearchTask model with UUID primary key
  - Added database initialization and example CRUD operations
  - Configured secure connection to Replit's Neon database
