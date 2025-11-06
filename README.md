# Web Research Agent (Architecture)

Deterministic, tool-centric research assistant built on LangGraph. Workflows are expressed as YAML strategies and executed through pluggable adapters, with a scoped LLM used for classification, light parameter fill and query refinement.

This README describes the current implementation precisely with file references for key entry points.

## Overview

- Phases: Scope → Fill → Research → Finalize → Write → QC
- Strategy selection and execution are fully declarative via YAML plus a dynamic strategy index.
- LLM use is scoped and schema-validated (tool calls and JSON). LLM classification is required for all workflows.

## Data Model

- State fields are defined in `core/state.py`:
  - `ScopeState` holds `user_request`, `category`, `time_window`, `depth`, `strategy_slug` (core/state.py:19).
  - `ResearchState` holds `tasks`, `queries`, `evidence` (core/state.py:28).
  - `WriteState` holds `sections`, `citations`, `limitations`, `errors`, `vars` (core/state.py:37).
  - `State` composes all three (core/state.py:47).

## Strategy Index

- Canonical registry of active strategies at `strategies/index.yaml`. Each entry defines:
  - `slug`, `category`, `time_window`, `depth`, `title`, `description`, `priority`, `active` (strategies/index.yaml:2).
  - `required_variables`: names the variables the classifier must provide (strategies/index.yaml:9).
  - `fan_out`: controls research iteration. Values:
    - `none` — single pass
    - `task` — loop full chain over `state.tasks`
    - `{ mode: var, var: <listVar>, map_to: <varName>, limit: <N> }` — loop full chain over a list variable, assigning each value into `map_to` (defaults to `topic`).
- Loader and selector:
  - `load_strategy_index` builds and caches the index; constructs a `(category, time_window, depth) -> slug` lookup (strategies/__init__.py:150).
  - `select_strategy` resolves slugs from the lookup (strategies/__init__.py:207).
  - Helper `get_index_entry_by_slug` fetches index metadata for the active slug (strategies/__init__.py:168).

## Configuration

- Centralised settings in `config/settings.yaml`:
  - Model defaults and per-node overrides under `llm.defaults.nodes.*` (config/settings.yaml:75).
  - Strategy-specific LLM overrides under `llm.per_strategy.*` (config/settings.yaml:60).
  - Prompt templates under `prompts.*` and `prompts.nodes.*` (config/settings.yaml:116).
- Accessors:
  - `get_node_llm_config(node, strategy_slug)` for node-level model config (core/config.py:200).
  - `get_node_prompt(node, strategy_slug)` for node-level prompt text (core/config.py:211).

## Scope (Classification)

- Purpose: select strategy, set `category/time_window/depth`, produce a small task list, and fill per‑strategy variables via a tool call.
- Implementation:
  - `_llm_scope` formats a central prompt + dynamic catalog from the strategy index and forces a `set_scope` tool call (core/scope.py:240).
  - The tool schema requires: `strategy_slug`, `category`, `time_window`, `depth`, `tasks`; optional `variables` supports string or string[] values (core/scope.py:75).
  - Results are cached per request and traced via Langfuse when configured (core/scope.py:246).
  - If LLM/tool call fails (missing API key, network error, etc.), `scope_request()` raises RuntimeError and the workflow fails immediately (core/scope.py:464). No heuristic fallback is used.
- Prompt source: `prompts.nodes.scope_classifier` (config/settings.yaml:118).
- Output propagation in graph:
  - `scope(state)` stores labels, slug and any variables into `state.vars` for downstream use (core/graph.py:337).

## Fill (Optional Parameter Generation)

- Purpose: pre-compute common variables (date windows/recency), and LLM-fill whitelisted inputs for modern `use:` steps.
- Behavior:
  - Computes `current_date`, `start_date/end_date`, and `search_recency_filter` from `time_window` (core/graph.py:739).
  - Builds a `runtime_plan` mirroring the strategy’s `tool_chain`, and optionally fills keys in `llm_fill` via a small JSON LLM call (core/graph.py:770).
  - Stores the plan under `state.vars["runtime_plan"]` (core/graph.py:793).

## Research (Execution)

- Purpose: run the strategy steps against variables (including those supplied at scope) and collect evidence.
- Fan‑out control (from the index):
  - `none`: single pass using a canonical `topic` derived from `state.vars['topic']` or fallback (core/graph.py:410).
  - `task`: one full pass per `state.tasks` entry, setting `topic/subtopic` accordingly (core/graph.py:418).
  - `var`: one full pass per value in `state.vars[fan_out.var]`, mapped into `map_to` (default `topic`) with optional `limit` (core/graph.py:424).
- Step types:
  - Legacy `name:` steps: built-ins for Sonar/Exa (search/contents/answer/similar) with per-step query refinement between steps (core/graph.py:474, core/graph.py:544, core/graph.py:246).
  - Modern `use:` steps: `use=provider.method` routed by `_execute_use`, with `inputs`, optional `foreach/when/save_as`, and runtime overrides (core/graph.py:556, core/graph.py:1221).
- Variables for templating are merged per iteration: `topic/subtopic/time_window/region` + everything from `state.vars` (core/graph.py:451).
- Evidence is normalized, aggregated per iteration, then deduped/scored once against the global budget (core/graph.py:611, core/graph.py:615).

## Finalize

- Finalize (optional ReAct): tool-aware ReAct pass that can call tools during report assembly when enabled in a strategy's finalize config. The LLM generates markdown sections and citations directly from the evidence (core/graph.py:778-1230).

## QC

- `_qc_llm` validates grounding/consistency/completeness with a JSON LLM call (core/graph.py:587).
- Mechanical checks for citation quorum and recency are performed during research/aggregation.

## Tool Adapters

- Adapters are provided via a simple registry; `use=provider.method` dispatch is resolved by `_execute_use` (core/graph.py:1221).
- Built-ins include Exa and Sonar adapters under `tools/`.

## Prompts and Models

- All prompts live in `config/settings.yaml` and are accessed at runtime; nodes consult `get_node_prompt` and `get_node_llm_config` so model/provider changes are centralized (core/config.py:200, core/config.py:211).

## Typical Flow

1. Scope: classify, choose strategy, gather variables via `set_scope` tool (core/scope.py:236; config/settings.yaml:118).
2. Fill: compute dates/recency and optional llm_fill for specific steps (core/graph.py:721).
3. Research: execute steps with fan‑out per index config (core/graph.py:405).
4. Finalize/Write: generate sections and citations (core/graph.py:860, core/graph.py:564).
5. QC: LLM and mechanical checks (core/graph.py:587).
6. Graph wiring is defined in `build_graph()` (core/graph.py:1367).

## Adding a Strategy

- Create `strategies/<category>/<slug>.yaml` with a `meta` block and `tool_chain`, `queries`, `limits`, `render`, optional `finalize`.
- Add an entry to `strategies/index.yaml` with `slug`, labels, `required_variables`, and `fan_out` policy.
- Optionally add or adjust prompts in `config/settings.yaml` per node or per strategy.

## Configuration Management API

The system supports **runtime configuration updates** via REST API endpoints, allowing you to create, update, and delete strategies and settings **without redeploying**.

### Database-Backed Configuration

- **Strategies** and **global settings** are stored in PostgreSQL and loaded at startup
- File-based YAML configurations serve as fallback if database is empty
- In-memory caching with automatic invalidation on updates
- Changes take effect immediately (no restart required)

### API Endpoints

**Strategy Management** (requires `X-API-Key` header):
- `GET /api/strategies` - List all strategies
- `GET /api/strategies/{slug}` - Get single strategy
- `POST /api/strategies` - Create new strategy
- `PUT /api/strategies/{slug}` - Update existing strategy
- `DELETE /api/strategies/{slug}` - Delete strategy

**Global Settings Management**:
- `GET /api/settings` - List all settings
- `GET /api/settings/{key}` - Get setting (e.g., `llm_defaults`, `prompts`)
- `PUT /api/settings/{key}` - Update LLM configs or prompts

### Quick Example

Update LLM temperature globally:
```bash
curl -X PUT \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"value": {"fill": {"model": "gpt-5-mini", "temperature": 0.5}}}' \
  https://your-api.com/api/settings/llm_defaults
```

Create new strategy:
```bash
curl -X POST \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "my_custom_strategy",
    "yaml_content": {
      "meta": {"slug": "my_custom_strategy", "version": 1, "category": "news", "time_window": "week", "depth": "brief"},
      "queries": {"exa_search": "{{topic}} updates"},
      "tool_chain": [{"use": "exa.search", "inputs": {"query": "{{topic}}", "num_results": 10}}]
    }
  }' \
  https://your-api.com/api/strategies
```

### Migration from YAML to Database

Run the migration script to move existing strategies to database:
```bash
python scripts/migrate_main_strategies.py
```

**Documentation**: See `docs/API_CONFIGURATION.md` for complete API reference and examples.

## Running

```python
from core.graph import build_graph
from core.state import State
from tools import register_tool
from tools.sonar import SonarAdapter
from tools.exa import ExaAdapter

register_tool(SonarAdapter())
register_tool(ExaAdapter())

graph = build_graph()
state = State(user_request="daily briefing: large language models")
final = graph.invoke(state)
print("\n\n".join(final.sections))
```

## Environment

- `OPENAI_API_KEY` required for LLM calls.
- Tool adapters may require their own keys (e.g., `EXA_API_KEY`, `SONAR_API_KEY` or `PERPLEXITY_API_KEY`).
- Optional Langfuse tracing via `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.

## Testing

- Unit tests live in `tests/`. Install `pytest` to run: `pip install pytest && pytest`.
