# Web Research Agent

Deterministic research assistant built with [LangGraph](https://langchain-ai.github.io/langgraph/).
The agent runs constrained web-research workflows defined in YAML strategies and executed
through pluggable tool adapters.

## Features

- **Structured workflow** – graph phases *Scope → Research → Write → QC*.
- **File-based strategies** – YAML files in `strategies/` describe tool sequences, query
  templates and output renderers. No vector search is used for retrieval.
- **Pluggable tools** – registry currently ships adapters for Perplexity **Sonar** and
  **Exa** search. Custom tools can be added by implementing the `ToolAdapter` protocol and
  registering the instance with `register_tool`.
- **Lightweight QC** – mechanical checks for section structure, citation quorum and
  recency windows.
- **Multiple renderers** – briefing, memo, dossier, fact‑check, Q&A and JSON outputs.

## Project layout

```
core/        graph definition, state models and scope helpers
strategies/  YAML strategies and reusable macros
tools/       tool adapter implementations and registry
renderers/   output renderers
templates/   placeholder for template utilities
checks/      schema and lint helpers
tests/       unit tests
```

## Installation

Requires **Python 3.12+**.

```bash
git clone <repo-url>
cd web_research_agent
python -m venv .venv
source .venv/bin/activate
pip install langgraph pydantic pyyaml jsonschema exa-py openai
```

### API keys

Set the following environment variables before running workflows:

```bash
export SONAR_API_KEY="your-perplexity-key"   # or reuse OPENAI_API_KEY
export EXA_API_KEY="your-exa-key"
```

## Running a research workflow

```python
from core.graph import build_graph
from core.state import State
from tools import register_tool, SonarAdapter, ExaAdapter

register_tool(SonarAdapter())
register_tool(ExaAdapter())

graph = build_graph()
state = State(user_request="latest on renewable energy policy")
final = graph.invoke(state)
for section in final.sections:
    print(section)
```

### Customising strategies

Strategies live under `strategies/<category>/<name>.yaml`.
Each file contains `meta`, `tool_chain`, `queries`, `filters`, `quorum`,
`render` and `limits` blocks.  Reusable steps are stored in `strategies/macros/`.
Creating a new YAML file lets you craft specialised research workflows without
modifying Python code.

## Testing

Run the test suite after changes:

```bash
pytest
```

Tests rely on mocked adapters and do not perform network calls.

## Roadmap

See [roadmap.md](roadmap.md) for upcoming tasks and future enhancements.
