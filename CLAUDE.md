# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Web Research Agent** - A deterministic, tool-centric research assistant built on LangGraph. Workflows are expressed as YAML strategies and executed through pluggable tool adapters, with scoped LLM use for classification, parameter filling, and query refinement.

**Core Architecture**: Scope → Fill → Research → Finalize → Write → QC

LLM use is intentionally scoped and schema-validated (tool calls and JSON). All workflows require LLM classification via the scope phase - there are no heuristic fallbacks.

## Commands

### Development
```bash
# Run a daily briefing (most common use case)
python run_daily_briefing.py --topic "AI developments" --verbose

# Enable debug logging (captures prompts, tool calls, decisions)
python run_daily_briefing.py --topic "AI" --debug --debug-file debug.json

# Run the REST API server
python run_api.py

# Run tests
pytest

# Run specific test file
pytest tests/test_scope.py -v
```

### Required Environment Variables
- `OPENAI_API_KEY` - Required for all LLM calls
- `EXA_API_KEY` - For Exa search tool
- `SONAR_API_KEY` or `PERPLEXITY_API_KEY` - For Sonar/Perplexity search

### Optional Environment Variables
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` - For tracing
- `DATABASE_URL` - PostgreSQL connection (API server only)
- `API_SECRET_KEY` - API authentication (API server only)
- `DEBUG_LOG=true` or `WEB_RESEARCH_DEBUG=true` - Enable debug logging

## Architecture

### State Management (core/state.py)
The application uses a composed state model with three phases:
- **ScopeState**: `user_request`, `category`, `time_window`, `depth`, `strategy_slug`
- **ResearchState**: `tasks`, `queries`, `evidence` (list with operator.add for aggregation)
- **WriteState**: `sections`, `citations`, `vars` (runtime variables)
- **State**: Composes all three via Pydantic multi-inheritance

### Strategy System (strategies/)
Strategies are YAML files defining research workflows. The canonical registry is `strategies/index.yaml`.

**Index Entry Structure**:
- `slug`: Unique identifier (e.g., "daily_news_briefing", "company/dossier")
- `category`, `time_window`, `depth`: Classification labels
- `required_variables`: Variables the scope classifier must provide (typically includes `topic`)
- `fan_out`: Controls iteration mode:
  - `none`: Single pass
  - `task`: Loop over `state.tasks`
  - `{mode: var, var: <listVar>, map_to: <varName>, limit: <N>}`: Loop over list variable

**Strategy YAML Structure**:
- `meta`: Metadata block (slug, version, category, time_window, depth)
- `tool_chain`: List of steps (legacy `name:` steps or modern `use:` steps)
- `queries`: Named query templates (optional, for legacy steps)
- `limits`: Evidence budgets (optional)
- `render`: Output formatting (optional)
- `finalize`: ReAct configuration for tool-aware report assembly (optional)

**Adding a Strategy**:
1. Create `strategies/<category>/<slug>.yaml` with `meta` and `tool_chain`
2. Add entry to `strategies/index.yaml` with classification labels and `required_variables`
3. Optionally add strategy-specific prompts/LLM config in `config/settings.yaml` under `llm.per_strategy.<slug>`

### Configuration System (config/settings.yaml)
Centralized config for all LLM models and prompts.

**LLM Configuration**:
- `llm.defaults.*`: Base model config (fill, summarize, qc, analyzer, cluster)
- `llm.defaults.nodes.*`: Node-specific overrides (scope_classifier, query_refiner, finalize_react, llm_analyzer)
- `llm.per_strategy.<slug>`: Strategy-specific overrides

**Prompt Templates**:
- `prompts.nodes.scope_classifier`: Classification prompt (required, no fallback)
- `prompts.nodes.query_refiner`: Query refinement between research steps
- `prompts.nodes.finalize_react_*`: ReAct system and analysis prompts
- Other prompts for fill, summarize, qc phases

**Accessors** (core/config.py):
- `get_node_llm_config(node, strategy_slug)`: Returns model config for a node
- `get_node_prompt(node, strategy_slug)`: Returns prompt template for a node

### Workflow Phases

**1. Scope (core/scope.py)**
- **Purpose**: Select strategy, extract variables, generate task list via LLM tool call
- **Implementation**: `_llm_scope()` formats prompt with strategy catalog and forces `set_scope` tool call
- **Tool Schema**: Requires `strategy_slug`, `category`, `time_window`, `depth`, `tasks`; optional `variables` dict
- **Failure Mode**: RuntimeError if LLM/tool call fails (no fallback)
- **Output**: Populates state labels and `state.vars` for downstream use

**2. Fill (core/graph.py:721-793)**
- **Purpose**: Compute date windows and optionally LLM-fill whitelisted inputs
- **Behavior**:
  - Computes `current_date`, `start_date/end_date`, `search_recency_filter` from `time_window`
  - Builds `runtime_plan` mirroring strategy's `tool_chain`
  - Optionally fills keys in `llm_fill` via JSON LLM call
  - Stores plan in `state.vars["runtime_plan"]`

**3. Research (core/graph.py:405-620)**
- **Purpose**: Execute strategy steps and collect evidence
- **Fan-out Control**: Based on index entry's `fan_out` field
  - `none`: Single pass with canonical topic
  - `task`: One pass per `state.tasks` entry
  - `var`: One pass per value in specified list variable
- **Step Types**:
  - Legacy `name:` steps: Built-ins for Sonar/Exa (search/contents/answer/similar) with query refinement
  - Modern `use:` steps: `use=provider.method` with `inputs`, optional `foreach/when/save_as`, runtime overrides
- **Evidence**: Normalized per iteration, then deduped/scored against global budget

**4. Finalize (core/graph.py:778-1230)**
- **Purpose**: Optional ReAct pass for tool-aware report assembly
- **Behavior**: LLM can call tools during report generation when enabled in strategy's finalize config

**5. QC (core/graph.py:587)**
- **Purpose**: Validate grounding, consistency, completeness
- **Implementation**: `_qc_llm()` performs JSON LLM call with quality checks

### Tool System (tools/)
Tools are registered via adapter pattern. Built-in adapters:
- **SonarAdapter** (tools/sonar.py): Perplexity search with enhanced parameters
- **ExaAdapter** (tools/exa.py): Semantic search and answer generation

**Modern Tool Execution** (`use:` steps):
- Dispatch via `_execute_use()` in core/graph.py:1221
- Supports `inputs`, `foreach` (iteration), `when` (conditional), `save_as` (result storage)
- Runtime overrides via `state.vars["runtime_plan"]`

**Registration**: `register_default_adapters()` in tools/__init__.py

### API Server (api/)
FastAPI-based REST API for managing research subscriptions and batch execution.

**Files**:
- `main.py`: FastAPI app with endpoints
- `schemas.py`: Pydantic request/response models
- `crud.py`: Database CRUD operations
- `webhooks.py`: Webhook delivery with retry logic
- `database.py`: PostgreSQL connection
- `models.py`: SQLAlchemy ORM models

**Key Endpoints**:
- `POST /tasks`: Create subscription
- `GET /tasks?email=<email>`: List user's tasks
- `PATCH /tasks/{task_id}`: Update task
- `DELETE /tasks/{task_id}`: Delete task
- `POST /execute/batch`: Execute batch research (triggers webhooks)

**Batch Flow**:
1. External trigger calls `/execute/batch` with frequency filter
2. Query database for active tasks
3. Execute research for each task sequentially
4. Send webhook with results to callback URL
5. Update `last_run_at` timestamp

### Debug and Tracing

**Debug Logging**:
- Enable via `--debug` flag or `DEBUG_LOG=true` / `WEB_RESEARCH_DEBUG=true` env vars
- Captures prompts, tool calls, LLM responses, decisions
- Output: `debug_log_<timestamp>.json`
- Helper: `core/debug_log.py` (singleton `dbg` instance)
- Enhanced logging: `core/enhanced_debug.py` provides session-based logging

**Langfuse Tracing**:
- Enable by setting `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- Decorators: `@observe` for functions, `workflow_span()` context manager for workflows
- Helpers: `core/langfuse_tracing.py`

## Key Workflows

### Running a Single Briefing
```python
from core.graph import build_graph
from core.state import State
from tools import register_default_adapters

register_default_adapters()
graph = build_graph()
state = State(user_request="daily briefing: large language models")
result = graph.invoke(state)
print("\n\n".join(result.sections))
```

### Creating a New Strategy
1. Create `strategies/news/my_strategy.yaml`:
```yaml
meta:
  slug: news/my_strategy
  version: 1
  category: news
  time_window: day
  depth: brief

tool_chain:
  - name: sonar_overview
    params:
      max_results: 5
  - use: llm_analyzer.call
    inputs:
      prompt: "Summarize: {{evidence_text}}"
```

2. Add to `strategies/index.yaml`:
```yaml
strategies:
  - slug: news/my_strategy
    title: My Strategy
    category: news
    time_window: day
    depth: brief
    fan_out: none
    required_variables:
      - name: topic
        description: Topic to research
```

### Modifying LLM Behavior
Edit `config/settings.yaml`:
```yaml
llm:
  per_strategy:
    daily_news_briefing:
      analyzer:
        model: gpt-5  # Change model
        temperature: 0.5  # Adjust temperature
```

## Important Notes

### Scope Phase is Critical
- The scope classifier (`core/scope._llm_scope`) is the entry point for ALL workflows
- If scope fails (missing API key, network error, invalid tool call), the workflow fails immediately
- No heuristic fallbacks exist - this is intentional design
- The scope prompt is in `config/settings.yaml` under `prompts.nodes.scope_classifier`

### Variable Templating
- Variables use Jinja2-style syntax: `{{variable_name}}`
- Available in query templates, step inputs, prompts
- Sources: `state.vars` (populated by scope/fill), iteration variables (`topic`, `subtopic`), time windows
- Merge order: built-in time variables → state.vars → iteration-specific overrides

### Evidence Budget
- Evidence is collected per iteration, then globally deduped/scored
- Budget controlled via strategy's `limits` section (optional)
- Normalization happens in `_normalize_evidence()` before aggregation

### Graph Construction
The workflow graph is built in `core/graph.py:1367` via `build_graph()`. Node wiring:
- scope → fill → research (with fan-out logic) → finalize/write → qc → END

## File Organization

```
├── core/                    # Core workflow engine
│   ├── state.py            # State model (Pydantic)
│   ├── graph.py            # LangGraph workflow definition
│   ├── scope.py            # Scope/classification logic
│   ├── config.py           # Configuration accessors
│   ├── utils.py            # Template rendering, path resolution
│   ├── langfuse_tracing.py # Tracing decorators
│   └── debug_log.py        # Debug logging singleton
├── strategies/             # YAML strategy definitions
│   ├── index.yaml         # Strategy registry (source of truth)
│   ├── daily_news_briefing.yaml
│   ├── news/              # Category-based organization
│   ├── company/
│   └── general/
├── tools/                  # Tool adapters
│   ├── registry.py        # Tool registration system
│   ├── sonar.py           # Sonar/Perplexity adapter
│   └── exa.py             # Exa search adapter
├── api/                    # REST API for subscriptions
│   ├── main.py            # FastAPI endpoints
│   ├── database.py        # PostgreSQL connection
│   └── webhooks.py        # Webhook delivery
├── config/
│   └── settings.yaml      # Centralized LLM/prompt config
├── tests/                 # Unit tests
└── run_daily_briefing.py  # CLI entry point
```
