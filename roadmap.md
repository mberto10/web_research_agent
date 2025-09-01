ROADMAP

Below is the **revised architecture** and an expanded **implementation roadmap** reflecting your constraints:

* **No vector store for strategy retrieval** → use **file‑based YAML strategies** only.
* **QC is lightweight** (structural + source checks, not heavy inference).
* The system is set up as a **library** so you can **mix & match** request categories, strategies, and specialized tool adapters (Sonar, Exa, and future tools).

Where useful, I’ve grounded claims in primary docs for **LangGraph** (state, reducers, checkpointers, interrupts, multi‑agent handoffs), **Perplexity Sonar API** (OpenAI‑compatible, model family), and **Exa** (search types, categories, contents/findSimilar/answer endpoints). ([LangChain Docs][1], [LangChain][2], [Perplexity][3], [Exa][4], [GitHub][5])

---

## A. Architecture (YAML‑Strategy, Tool‑Plugin Library)

### 1) High‑level flow (deterministic, lightweight QC)

**Phases:**
**Scope → Research → Write → QC‑lite → Deliver**

* **Scope**: Categorize request and time window, then **select a YAML strategy** by rule (no vector store).
* **Research**: Deterministic tool sequence (Sonar → Exa) executed with **bounded loops**; optional parallelism for sub‑topics under a supervisor micro‑plan.
* **Write**: Render result using a chosen **output template** (briefing, exec memo, fact‑check card, JSON artifact, email body).
* **QC‑lite**: Only mechanical checks (structure present, citations present, URLs deduped/valid, recency window obeyed, minimum source quorum).
* **Deliver**: Emit Markdown/JSON/Email via adapters.

This mirrors the three‑stage deep‑research pattern (scope → research → write) while constraining control flow and parallelism for a smaller, cheaper model. ([LangChain Blog][6], [GitHub][7])
Deterministic orchestration, typed state, reducers, and handoffs are natural fits for **LangGraph** with **checkpointers** and **interrupts** available when you want them. ([LangChain Docs][1], [LangChain][2])

---

### 2) State model (typed & minimal)

Top‑level state keys (examples):

* `user_request`, `category`, `time_window`, `depth`
* `strategy_slug` (selected YAML id), `tasks[]` (sub‑topics)
* `queries[]` (Sonar/Exa canonicalized queries)
* `evidence[]` (normalized: `{url, publisher, title, date, snippet, tool, score}`)
* `sections[]` (draft fragments per renderer)
* `citations[]` (deduped canonical links)
* `limitations[]`, `errors[]`

**Reducers** merge arrays deterministically; **checkpointers** persist at super‑steps, enabling replay and fault tolerance without adding complexity to QC. ([LangChain Docs][1], [LangChain][2])

---

### 3) Strategy library (YAML files, no vector retrieval)

* Each strategy is a **YAML file** in `strategies/<category>/<name>.yaml`.
* **Deterministic selector**: a small rules table (category × time sensitivity × depth) → `strategy_slug`.
* **No semantic search** is used to pick strategies.

**YAML fields (schema sketch):**

* `meta`: `slug`, `version`, `category`, `time_window`, `depth`
* `tool_chain`: ordered steps referencing **logical tool names** (e.g., `sonar_snapshot`, `exa_search_primary`, `exa_contents_focus`, `exa_find_similar_optional`, `exa_answer_optional`) with **fixed parameters** and **loop bounds**
* `queries`: Jinja‑style templates per tool (`"latest {{topic}}"`, `"background {{topic}} site:gov"`), with deterministic slot filling
* `filters`: date/recency policy, domain allowlist/denylist
* `quorum`: min sources, outlet diversity (e.g., ≥1 wire/official, ≥3 independent outlets)
* `render`: output type, section layout, per‑section citation requirements
* `limits`: caps for iterations, results per tool, contents retrieval size

Because Exa supports **search type** (`keyword`/`neural`/`auto`), **category** (e.g., `"news"`), and **published date filters**, these parameters live in the YAML, not in prompts. ([Exa][8])

> **Note:** Keep your separate “knowledge‑folder search” as a *content* tool if you like, but **strategy retrieval** is now entirely file‑based and deterministic.

---

### 4) Pluggable tools (library/registry)

A **tool adapter registry** lets you add or swap specialized tools without touching the graph:

* **Contract**: `name`, `capabilities` (e.g., `search`, `contents`, `verify`), `call(params) -> NormalizedEvidence|Contents`, **retry/backoff policy**, and **cost/latency hints**.
* **Core adapters today**:

  * **Sonar API** (OpenAI‑compatible Chat Completions with `model: "sonar"`/`"sonar-pro"`, recency filters; extract citations from results). ([Perplexity][3])
  * **Exa**: `/search` (type=auto/keyword/neural, `category="news"`, date filters), `/contents` (clean text / highlights / summary), `/findSimilar`, `/answer` (targeted conflict resolution). ([Exa][4], [GitHub][5])
* **Future tools**: finance filings, court dockets, patents, scientific preprints—just ship new adapters and reference them by **logical name** in strategies.

---

### 5) Research phase (bounded, parallel when useful)

**Supervisor subgraph:**

* Deterministic **task splitter** → `tasks[]` (bounded N).
* **Map** over tasks: each sub‑agent runs the same **micro‑plan** defined in the YAML:

  1. **Sonar snapshot** with recency filter from strategy; parse and normalize citations.
  2. **Exa primary search** (date filters + category + search type) to broaden/validate.
  3. **Exa contents (selective)** on top 1–2 URLs if snippets insufficient.
  4. **Optional** `findSimilar` for context; **optional** `answer` for conflicts.
  5. Merge & score `evidence[]`, dedupe, return compact digest.

Handoffs/command routing and reducers are handled by LangGraph patterns for multi‑agent systems. ([LangChain][9])

---

### 6) Lightweight QC (mechanical, fast)

* **Structure check**: Required sections present for the chosen renderer.
* **Citation check**: Each section has ≥1 URL; URLs deduped; **publisher+date** attached when available.
* **Recency check**: All citations comply with the strategy’s **time window**.
* **Source diversity**: Meets `quorum` (e.g., ≥3 independent outlets, include ≥1 wire/official).
* **Minimal contradiction ping** *(optional)*: flag if numeric facts differ across top sources (no heavy resolution pass unless strategy enables `exa_answer_optional`).

No human-in-the-loop by default; you can still wire **interrupts** later if needed. ([LangChain Docs][10])

---

### 7) Output system (extendable)

Renderers are **plugins** (templates + fillers):

* **Briefing v3** (your existing Markdown schema)
* **Executive memo** (one‑pager)
* **Fact‑check card** (claim → verdict → evidence)
* **Q\&A**
* **JSON** artifact for downstream tooling
* **Email** sink

Each renderer enforces per‑section citation minima before emitting.

---

### 8) Determinism levers

* Strategy encodes the **tool chain** and **parameters** (no open‑ended tool decisions).
* **Low temperature** for classification/writing; **structured JSON outputs**.
* **Hard caps**: iterations, results, contents length.
* **Date filters** in Sonar/Exa are **set from the strategy**, not inferred at runtime. ([Perplexity][11], [Exa][8])

---

## B. More Comprehensive Implementation Roadmap

> **Goal:** Ship a **library‑style package** with a stable, deterministic graph; file‑based strategies; and swappable tool adapters. No code below—this is a concrete build plan.

### Phase 0 — Repository & packaging

1. **Repo layout**

   ```
   research_agent/
     core/                # graph assembly, state, reducers, edges
     strategies/          # YAML files per category
     tools/               # adapters: sonar.py, exa.py, (future: filings.py)
     renderers/           # briefing.py, memo.py, factcheck.py, json.py, email.py
     checks/              # lightweight QC functions
     policies/            # domain allow/deny lists, recency defaults
     templates/           # query templates (optional Jinja) and text blocks
     cli/                 # optional CLI entrypoints
     tests/               # unit, integration, golden-set
   ```
2. **Packaging**: pyproject + optional extras: `[exa]`, `[sonar]`, `[all]`.
3. **Config**: `.env` for API keys and **strategy directory path** override.

### Phase 1 — State & graph skeleton

4. **Define typed state** (Pydantic dataclasses): top‑level + per‑phase (Scope/Research/Write).
5. **Reducers** for `evidence[]`, `citations[]`, `sections[]`. Leverage LangGraph **Graph API** patterns. ([LangChain Docs][1])
6. **Compile graph with a checkpointer** (Memory or SQLite) for durability and replay—even though QC is lightweight, persistence is useful for debugging. ([LangChain][2])

**Status:** Phase 1 complete

### Phase 2 — YAML strategy system (no vector store)

7. **YAML schema & loader** (with JSON Schema validation).
8. **Strategy selector** (pure function): `(category, time_window, depth) -> strategy_slug`.
9. **Strategy library MVP**:

 * `news/real_time_briefing.yaml` (Sonar→Exa flow; strict time window)
  * `general/week_overview.yaml` (broader Exa window, optional Sonar)
  * `company/dossier.yaml` (Exa keyword + official sites bias)
10. **Macros/partials**: Extract common blocks:

    * `sonar_first_look`, `exa_primary_news_search`, `exa_contents_focus`, `exa_find_similar`, `exa_answer_conflict`
    * Reuse via `include:` within YAML.

**Status:** Phase 5 complete — research subgraph executes YAML-defined tool chains with query templating, evidence scoring, dedupe, and per-task budgets.
**Next:** Phase 7 — QC‑lite.

> By driving **search type**, **category**, and date filters from YAML you exploit Exa’s strengths (news category, `keyword/neural/auto`) deterministically. ([Exa][8])

### Phase 3 — Tool adapter registry

11. **Registry** with `register_tool(adapter)` and `get_tool(name)`.
12. **Sonar adapter**:

    * OpenAI‑compatible Chat Completions call; support `model: "sonar" | "sonar-pro"`, and recency filter / after‑date; return normalized citations table. ([Perplexity][3])
13. **Exa adapter**:

    * `/search`: params for `type`, `category`, `startPublishedDate`, `endPublishedDate`, include/exclude domains.
    * `/contents`: text/highlights (caps for characters/sentences).
    * `/findSimilar`: accept a seed URL; cap results.
    * `/answer`: gated by strategy for conflict resolution. ([Exa][4], [GitHub][5])
14. **Normalization**: unify all outputs into `Evidence` records (url, title, publisher, date, snippet, tool, score\_parts).

### Phase 4 — Scope phase

15. **Categorizer** (small model or rules first): returns `{category, time_window, depth}` (structured JSON).
16. **Task splitter**: deterministic sub‑topic extraction (cap N); produce `tasks[]` and per‑task query variables.

*Implementation:* Keyword rules map requests to existing strategy dimensions, and a delimiter-based splitter expands `tasks[]` and mirrored `queries[]`.

### Phase 5 — Research subgraph

17. **Supervisor with handoffs**: a worker per task runs the strategy’s **tool\_chain**; use LangGraph’s multi‑agent patterns (handoffs / Command) with **bounded iterations**. ([LangChain][9])
18. **Query templating**: fill Jinja‑like templates using `{topic, subtopic, time_window, region}` consistently (no LLM improvisation).
19. **Scoring & dedupe**: domain authority weights, recency decay, canonical URL normalization.
20. **Evidence budget**: cap `evidence[]` per task to keep the write phase small.

*Implementation:* `core.graph.research` now iterates through each task's tool chain, renders query templates, normalizes URLs with scoring and deduplication, and trims results using `limits.max_results`.

### Phase 6 — Write phase & renderers *(completed)*

21. Renderer contracts implemented for briefing, memo, dossier, fact‑check, Q\&A, and JSON outputs.
22. Templates render deterministic section headings with bullet summaries.
23. Citations assembled from `evidence[]` with publisher, date, and URL, avoiding Sonar as a cited source.

### Phase 7 — QC‑lite

24. **Structure check**: sections required by renderer present.
25. **Citation check**: ≥1 URL per section; dedupe; dates present when available; all URLs in time window.
26. **Quorum check**: min sources and outlet diversity per strategy.
27. **Optional quick contradiction ping** (numeric inconsistency).
28. **Fail path**: one **bounded retry** according to strategy (e.g., relax Exa filters or run `exa_answer_optional`)—then annotate `limitations[]` and proceed.

### Phase 8 — Delivery & sinks

29. **Emit Markdown/JSON/Email** via adapters.
30. Optional **send\_email** sink (subject/body formatter) if you want automated delivery.

### Phase 9 — Testing & evaluation

31. **Unit tests**: YAML validation, strategy selection, tool adapter mocks, normalization.
32. **Integration tests**: end‑to‑end on a small canned topic set; assert structure, recency, quorum.
33. **Golden briefings**: compare renderer output against fixtures (allow small diffs).
34. **Tracing**: integrate LangSmith or simple logging; later you can enable checkpointer‑based replay and (optionally) **interrupts** if editorial review is desired. ([LangChain][2], [LangChain Docs][10])

### Phase 10 — Ops & performance

35. **Retry/backoff** policies in adapters (429/5xx); **caching** per step (hash of query+filters).
36. **Cost/latency guardrails**: maximum calls per phase; Sonar used only for specific tasks (e.g., first snapshot, claim checks), Exa used for breadth. Sonar‑Pro reserved for complex/breaking queries per strategy. ([Perplexity][12])
37. **Domain policy**: central allow/deny lists; YAML strategies reference them to bias authority.

### Phase 11 — Extending the library

38. **Add a new specialized tool**: implement adapter, register it, reference its logical name in a new or existing strategy YAML.
39. **Create a new request category**: add YAML strategy (or reuse macros), update the selector rules, and add a renderer if needed.
40. **Swap models**: strategies carry model hints per node (classifier vs writer); swap to cheaper models without changing process.

---

## How this meets your goals

* **No vector store for strategies**: Strategies are **plain YAML files** selected by rules.
* **Lightweight QC**: Fast, mechanical checks keep total latency and cost low.
* **Precise & deterministic**: Tool parameters, time windows, and query templates are fixed in YAML; the LLM mainly fills text, not plans.
* **Mix & match**: A **tool registry** and **strategy macros** make it trivial to compose specialized flows; you can ship new tools/strategies without touching the graph.
* **Grounded in current tooling**: LangGraph patterns (state, reducers, handoffs, checkpointers, interrupts) + Sonar (OpenAI‑compatible) + Exa (search types/categories/contents) are all supported today. ([LangChain Docs][1], [LangChain][9], [Perplexity][3], [Exa][8])

---

### Suggested first strategies to author (YAML)

1. **News / Real‑time briefing** — Sonar snapshot (recency=`day`/`week`) → Exa search (`category="news"`, `type="auto"`, date filters) → selective contents → optional findSimilar → optional answer → render Briefing v3. ([Perplexity][11], [Exa][8])
2. **General research / Weekly** — Exa breadth first (`type="neural"`), then Sonar verify claims; broader date span; render memo. ([Exa][4])
3. **Company dossier** — Exa `keyword` + `category="company"`; official site bias; render JSON dossier + memo. ([Exa][8])

If you want, I can next translate this into **YAML schemas** (strategy + macros) and a **tool adapter contract**—still without writing the Python graph—so your team can start drafting strategies before implementation.

[1]: https://docs.langchain.com/oss/python/langgraph/use-graph-api?utm_source=chatgpt.com "Use the graph API - Docs by LangChain"
[2]: https://langchain-ai.github.io/langgraph/concepts/persistence/?utm_source=chatgpt.com "LangGraph persistence - GitHub Pages"
[3]: https://docs.perplexity.ai/guides/chat-completions-guide?utm_source=chatgpt.com "OpenAI Compatibility"
[4]: https://docs.exa.ai/reference/search?utm_source=chatgpt.com "Search"
[5]: https://raw.githubusercontent.com/exa-labs/openapi-spec/refs/heads/master/exa-openapi-spec.yaml?utm_source=chatgpt.com "Search API Spec - GitHub"
[6]: https://blog.langchain.com/open-deep-research/?utm_source=chatgpt.com "Open Deep Research - LangChain Blog"
[7]: https://github.com/langchain-ai/open_deep_research?utm_source=chatgpt.com "langchain-ai/open_deep_research - GitHub"
[8]: https://docs.exa.ai/sdks/typescript-sdk-specification?utm_source=chatgpt.com "TypeScript SDK Specification"
[9]: https://langchain-ai.github.io/langgraph/how-tos/multi_agent/?utm_source=chatgpt.com "Build multi-agent systems - GitHub Pages"
[10]: https://docs.langchain.com/oss/python/langgraph/use-functional-api?utm_source=chatgpt.com "Use the functional API - Docs by LangChain"
[11]: https://docs.perplexity.ai/api-reference/chat-completions-post?utm_source=chatgpt.com "Chat Completions"
[12]: https://docs.perplexity.ai/getting-started/models/models/sonar-pro?utm_source=chatgpt.com "Sonar pro"
