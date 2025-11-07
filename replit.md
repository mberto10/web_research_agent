# Web Research Agent

## Overview

A deterministic, tool-centric research assistant built on LangGraph that executes declarative YAML-based research workflows. The system orchestrates multi-phase research pipelines (Scope → Research → Write → QC) using pluggable adapters for search APIs (Exa, Perplexity Sonar) and LLM-powered analysis. Includes a FastAPI-based subscription management system for scheduled research briefings with webhook delivery to Langdock email workflows.

**Core Value Proposition**: Transform user queries into comprehensive research reports by combining neural/keyword search, semantic filtering, and structured content generation—all controlled via strategy YAML files without code changes.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### 1. Research Workflow Engine (LangGraph-based)

**Core Design**: State machine with 6 phases executed sequentially via LangGraph nodes.

**Phases**:
- **Scope**: LLM classifies request → selects strategy → extracts variables (category, time_window, depth)
- **Fill**: Optional LLM-based variable population for strategy inputs
- **Research**: Executes tool chains (search APIs) → collects evidence → deduplicates by URL
- **Finalize**: Optional ReAct loop for gap-filling with additional tool calls
- **Write**: Generates markdown sections from evidence using LLM
- **QC**: Validates output quality (source count, recency, citation format)

**State Model** (`core/state.py`):
- `ScopeState`: user_request, category, time_window, depth, strategy_slug
- `ResearchState`: tasks, queries, evidence (accumulated list)
- `WriteState`: sections, citations, vars (runtime variables)
- Combined `State` class composes all three

**Graph Construction** (`core/graph.py`):
- Builds StateGraph with conditional routing based on strategy configuration
- Supports fan-out patterns: `none`, `task` (loop over tasks), `var` (loop over list variables)
- Memory checkpoint support for state persistence

### 2. Strategy System (YAML-Driven Configuration)

**Strategy Index** (`strategies/index.yaml`):
- Canonical registry mapping `(category, time_window, depth)` → `strategy_slug`
- Each entry defines: required_variables, fan_out mode, priority, active status
- Loader caches index at startup for fast lookup

**Strategy Files** (`strategies/*.yaml`):
- Define complete workflow: tool_chain (search steps), queries (templates), filters, quorum rules
- Support both legacy (name/params) and extended (use/inputs/llm_fill) step formats
- LLM overrides per strategy via `config/settings.yaml`

**Database-First Design**:
- Strategies stored in PostgreSQL `strategies` table (YAML content in JSONB)
- Fallback to file system if DB empty
- Runtime updates via API endpoints (no redeploy needed)

### 3. Tool Adapter Registry

**Architecture**: Protocol-based adapter pattern for pluggable search providers.

**Adapters** (`tools/`):
- `SonarAdapter`: Perplexity API with chat completions → citation normalization
- `ExaAdapter`: Exa neural/keyword search → Evidence records
- `LLMAnalyzerAdapter`: OpenAI for structured analysis/synthesis

**Registry** (`tools/registry.py`):
- Simple dict-based registration: `register_tool(adapter)` → `get_tool(name)`
- Lazy initialization to avoid requiring all API keys upfront

**Evidence Normalization**:
- All adapters return `List[Evidence]` with standardized fields: url, title, snippet, date, publisher, tool, score
- Deduplication by URL in research phase

### 4. Configuration Management

**Centralized Settings** (`config/settings.yaml` + PostgreSQL):
- LLM model/temperature defaults per node (scope_classifier, query_refiner, finalize_react, llm_analyzer)
- Per-strategy overrides: `llm.per_strategy.<slug>`
- Prompt templates: `prompts.nodes.<node_name>`

**Database Storage**:
- `global_settings` table for runtime LLM config changes
- `strategies` table for YAML content updates
- Cache invalidation on updates

**Access Patterns**:
- `get_node_llm_config(node, strategy_slug)`: Resolves model config with strategy overrides
- `get_node_prompt(node, strategy_slug)`: Fetches prompt templates
- `load_config_from_db()`: Populates cache at startup

### 5. Subscription & Batch Execution API

**FastAPI Application** (`api/main.py`):
- CRUD endpoints for research task subscriptions
- Batch execution endpoint (`/execute/batch`) for scheduled runs
- Webhook delivery with exponential backoff retry

**Database Schema** (`api/models.py`):
- `research_tasks`: User subscriptions (email, topic, frequency, schedule_time)
- `scope_classifications`: Cached LLM scope results (request hash → classification)
- `strategies`: YAML content storage
- `global_settings`: Runtime config overrides

**Execution Flow**:
1. Scheduler (external) calls `/execute/batch?frequency=daily`
2. Query DB for active tasks matching frequency
3. For each task: run research workflow → format result
4. Send webhook to Langdock with structured payload
5. Langdock renders HTML email from sections/citations

**Webhook Payload Structure**:
```json
{
  "task_id": "uuid",
  "email": "user@example.com",
  "research_topic": "AI news",
  "frequency": "daily",
  "status": "completed",
  "result": {
    "sections": ["## Section 1\n...", "## Section 2\n..."],
    "citations": ["Source (2024-01-15) http://..."],
    "metadata": {
      "strategy_slug": "daily_news_briefing",
      "executed_at": "2024-01-15T09:00:00Z"
    }
  }
}
```

### 6. Scope Classification & Caching

**Purpose**: Convert natural language requests → structured strategy selection.

**LLM Scope Node** (`core/scope.py`):
- Formats prompt with dynamic strategy catalog from index
- Forces tool call: `set_scope(strategy_slug, category, time_window, depth, tasks, variables)`
- Tool schema validates required variables per strategy

**Caching Layer** (`api/crud.py`):
- Hash request text → lookup in `scope_classifications` table
- 24-hour TTL for cached results
- Reduces LLM calls for repeated queries

### 7. Debug & Observability

**Enhanced Debug Logging** (`core/enhanced_debug.py`):
- Captures all LLM prompts/responses, tool calls, decision points
- JSONL event stream + session summary
- Environment-controlled: `DEBUG_LOG=true` or `--debug` flag

**Langfuse Tracing** (`core/langfuse_tracing.py`):
- Workflow spans with metadata (strategy_slug, frequency, task_id)
- Generation tracking for LLM calls
- Graceful degradation if credentials missing

**Structured Logging**:
- Startup logs show environment variable status (API keys, DB connection)
- Batch execution logs task discovery → background execution → webhook delivery
- Error traces with full context

### 8. Template Rendering System

**Jinja-like Templating** (`core/utils.py`):
- `{{var}}` replacement with dotted/indexed path resolution
- Filters: `{{var | shortlist:K}}` for list truncation
- Used in: queries, prompts, fill instructions

**Path Resolution**:
- Supports: `foo.bar`, `foo[0]`, `foo[0].bar.baz`
- Graceful fallback for missing paths (leaves token unchanged)

## External Dependencies

### APIs & Services

**Search & Data**:
- **Exa** (`EXA_API_KEY`): Neural/keyword search with semantic filtering
- **Perplexity Sonar** (`SONAR_API_KEY` or `PERPLEXITY_API_KEY`): Web search with citations
- **OpenAI** (`OPENAI_API_KEY`): GPT-4o-mini for scope classification, analysis, QC, content generation

**Observability**:
- **Langfuse** (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`): Trace collection and analysis

**Email Delivery**:
- **Langdock**: Webhook receiver → JavaScript email renderer → Outlook email action
- Webhook URL stored per-task in database for result delivery

### Database

**PostgreSQL** (`DATABASE_URL`):
- **Connection**: SQLAlchemy async engine with asyncpg driver
- **SSL**: Auto-configured from `sslmode` query parameter
- **Tables**: research_tasks, scope_classifications, strategies, global_settings
- **Indexes**: Email lookup, active tasks, request hashing, strategy categories

### Python Packages

**Core Framework**:
- `langgraph>=0.6`: Workflow state machine and graph execution
- `pydantic>=2.0`: Data validation and serialization
- `pyyaml>=6.0`: Strategy YAML parsing
- `jsonschema>=4.0`: Strategy schema validation

**API & Database**:
- `fastapi`: REST API framework
- `uvicorn`: ASGI server
- `sqlalchemy[asyncio]`: Async ORM
- `asyncpg`: PostgreSQL async driver

**Search Clients**:
- `exa-py`: Exa API client (optional)
- `openai`: OpenAI/Perplexity client (optional, lazy import)

**Utilities**:
- `httpx`: Async HTTP for webhooks
- `python-dotenv`: Environment variable loading
- `langfuse`: Tracing SDK (optional)

### File System Structure

**Key Entry Points**:
- `run_daily_briefing.py`: CLI for single research execution
- `run_api.py`: FastAPI server startup
- `init_database.py`: Schema initialization script

**Configuration**:
- `config/settings.yaml`: Default LLM/prompt settings
- `strategies/index.yaml`: Strategy catalog
- `strategies/*.yaml`: Individual strategy definitions

**Workflow Phases**:
- `core/scope.py`: Request classification
- `core/graph.py`: Research/finalize/write/QC nodes
- `core/llm_analyzer.py`: Structured analysis tool

**API Layer**:
- `api/main.py`: FastAPI routes
- `api/crud.py`: Database operations
- `api/webhooks.py`: Result delivery
- `api/models.py`: ORM models
- `api/schemas.py`: Pydantic request/response types

### Environment Variables Reference

**Required**:
- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: LLM operations
- `API_SECRET_KEY`: API authentication

**Search Providers** (at least one required):
- `EXA_API_KEY`: Exa search
- `SONAR_API_KEY` or `PERPLEXITY_API_KEY`: Perplexity search

**Optional**:
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`: Observability
- `DEBUG_LOG` or `WEB_RESEARCH_DEBUG`: Enable debug logging
- `DEBUG_LEVEL`: Logging verbosity (INFO, DEBUG, WARNING, ERROR)
- `PORT`: API server port (default: 8000)
- `HOST`: API server host (default: 0.0.0.0)