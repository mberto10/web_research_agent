from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from datetime import datetime
import re
from urllib.parse import urlparse, urlunparse
from typing import Dict, List

from .state import State, Evidence
from .scope import categorize_request, split_tasks
from strategies import load_strategy, select_strategy
from tools import get_tool
from renderers import get_renderer


def _cluster_llm(prompt: str) -> str:
    """Call an LLM to cluster evidence and return the raw text response."""
    from openai import OpenAI  # Lazy import to keep optional dependency

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    choice = response["choices"][0] if isinstance(response, dict) else response.choices[0]
    message = choice["message"] if isinstance(choice, dict) else choice.message
    return message.get("content") if isinstance(message, dict) else message.content


def _render_template(template: str, variables: Dict[str, str]) -> str:
    """Very small Jinja-like template renderer."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def _canonical_url(url: str) -> str:
    """Normalize URLs for deduplication."""
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))


def _dedupe_and_score(evidence: List[Evidence], limit: int | None) -> List[Evidence]:
    """Dedupe by canonical URL and apply simple scoring and budget."""
    deduped: Dict[str, Evidence] = {}
    for ev in evidence:
        key = _canonical_url(ev.url)
        current = deduped.get(key)
        if current is None or (ev.score or 0.0) > (current.score or 0.0):
            deduped[key] = ev

    # Apply recency decay and sort
    today = datetime.utcnow().date()
    scored: List[Evidence] = []
    for ev in deduped.values():
        recency = 1.0
        if ev.date:
            try:
                dt = datetime.fromisoformat(ev.date.split("T")[0]).date()
                days = max((today - dt).days, 0)
                recency = 1 / (1 + days)
            except Exception:
                recency = 1.0
        base = ev.score or 0.0
        ev.score = base + recency
        scored.append(ev)

    scored.sort(key=lambda e: e.score or 0.0, reverse=True)
    if limit is not None:
        scored = scored[:limit]
    return scored


def scope(state: State) -> State:
    """Scope phase categorizes the request and selects a strategy."""
    # Categorize if needed
    if not (state.category and state.time_window and state.depth):
        cat = categorize_request(state.user_request)
        state.category = state.category or cat["category"]
        state.time_window = state.time_window or cat["time_window"]
        state.depth = state.depth or cat["depth"]

    # Split into sub-tasks if not already present
    if not state.tasks:
        state.tasks = split_tasks(state.user_request)
        state.queries = list(state.tasks)

    # Select strategy
    if (
        state.strategy_slug is None
        and state.category
        and state.time_window
        and state.depth
    ):
        slug = select_strategy(state.category, state.time_window, state.depth)
        if slug:
            state.strategy_slug = slug
            # Load strategy to surface validation errors early.
            load_strategy(slug)
    return state


def research(state: State) -> State:
    """Execute the research phase based on the selected strategy."""
    if not state.strategy_slug or not state.tasks:
        return state

    strategy = load_strategy(state.strategy_slug)
    max_results = strategy.limits.get("max_results") if strategy.limits else None

    for task in state.tasks:
        variables = {
            "topic": task,
            "subtopic": task,
            "time_window": state.time_window or "",
            "region": "",
        }
        task_evidence: List[Evidence] = []
        last_results: List[Evidence] = []

        for step in strategy.tool_chain:
            tool_name = "sonar" if step.name.startswith("sonar") else "exa"
            tool = get_tool(tool_name)

            if step.name.startswith("sonar"):
                query_t = strategy.queries.get("sonar", "{{topic}}")
                prompt = _render_template(query_t, variables)
                results = tool.call(prompt, **step.params)
            elif step.name.startswith("exa_search"):
                query_t = strategy.queries.get("exa_search", "{{topic}}")
                query = _render_template(query_t, variables)
                results = tool.call(query, **step.params)
                last_results = results
            elif step.name.startswith("exa_contents"):
                top_k = step.params.get("top_k", 0)
                results = []
                for ev in last_results[:top_k]:
                    content = tool.contents(ev.url, **{k: v for k, v in step.params.items() if k != "top_k"})
                    if content.snippet:
                        ev.snippet = content.snippet
                    results.append(ev)
            elif step.name.startswith("exa_find_similar"):
                results = []
                if last_results:
                    seed = last_results[0].url
                    results = tool.find_similar(seed, **step.params)
            elif step.name.startswith("exa_answer"):
                # ``answer`` returns text; we ignore for now in evidence gathering
                query_t = strategy.queries.get("exa_answer", "{{topic}}")
                query = _render_template(query_t, variables)
                tool.answer(query, **step.params)
                results = []
            else:
                results = []

            task_evidence.extend(results)

        processed = _dedupe_and_score(task_evidence, max_results)
        state.evidence.extend(processed)

    # Global dedupe after processing all tasks
    state.evidence = _dedupe_and_score(state.evidence, max_results)
    return state


def summarize(state: State) -> State:
    """Cluster evidence with an LLM and store bullet summaries."""
    if not state.evidence:
        return state

    # Prepare prompt with key evidence lines
    lines = []
    for ev in state.evidence:
        desc = ev.title or ev.snippet or ev.url
        lines.append(f"- {desc}")
    prompt = (
        "Cluster the following evidence into topical groups and provide a brief bullet "
        "summary for each cluster:\n" + "\n".join(lines)
    )
    output = _cluster_llm(prompt)
    bullets = [
        line.lstrip("- ").strip()
        for line in output.splitlines()
        if line.strip().startswith("-")
    ]
    state.summaries = bullets
    return state


def write(state: State) -> State:
    """Render sections and assemble citations based on strategy."""
    if not state.strategy_slug:
        return state

    strategy = load_strategy(state.strategy_slug)
    render_cfg = strategy.render or {}
    renderer_type = render_cfg.get("type")
    section_names = render_cfg.get("sections", [])
    if not renderer_type:
        return state

    renderer = get_renderer(renderer_type)
    result = renderer.render(section_names, state.evidence)
    state.sections.extend(result.get("sections", []))
    state.citations.extend(result.get("citations", []))
    return state


def qc(state: State) -> State:
    """Lightweight QC checks on structure, citations, and quorum."""
    if not state.strategy_slug:
        return state

    strategy = load_strategy(state.strategy_slug)
    errors: list[str] = []

    # Structure check -----------------------------------------------------
    render_cfg = strategy.render or {}
    section_names = render_cfg.get("sections", [])
    for name in section_names:
        if not any(sec.startswith(f"## {name}") for sec in state.sections):
            errors.append(f"missing section: {name}")

    # Citation check ------------------------------------------------------
    if section_names and len(state.citations) < len(section_names):
        errors.append("insufficient citations")
    if len(state.citations) != len(set(state.citations)):
        errors.append("duplicate citations")

    recency = (strategy.filters or {}).get("recency")
    if recency:
        max_days = {
            "day": 1,
            "week": 7,
            "month": 30,
            "year": 365,
        }.get(recency)
        if max_days:
            today = datetime.utcnow().date()
            for ev in state.evidence:
                if ev.date:
                    try:
                        dt = datetime.fromisoformat(ev.date.split("T")[0]).date()
                        if (today - dt).days > max_days:
                            errors.append(f"out of time window: {ev.url}")
                            break
                    except Exception:
                        continue

    # Quorum check -------------------------------------------------------
    quorum = strategy.quorum or {}
    min_sources = quorum.get("min_sources")
    if min_sources:
        unique_urls = {ev.url for ev in state.evidence}
        if len(unique_urls) < min_sources:
            errors.append("insufficient sources")

    # Optional quick contradiction ping ---------------------------------
    numbers: set[str] = set()
    for ev in state.evidence:
        if ev.snippet:
            numbers.update(re.findall(r"\b\d+(?:\.\d+)?\b", ev.snippet))
    if len(numbers) > 1:
        state.limitations.append("potential numeric contradiction across sources")

    if errors:
        state.errors.extend(errors)
        state.limitations.append("qc-lite detected issues")
    return state


def build_graph() -> StateGraph:
    """Construct the LangGraph workflow."""
    builder = StateGraph(State)
    builder.add_node("scope", scope)
    builder.add_node("research", research)
    builder.add_node("summarize", summarize)
    builder.add_node("write", write)
    builder.add_node("qc", qc)

    builder.set_entry_point("scope")
    builder.add_edge("scope", "research")
    builder.add_edge("research", "summarize")
    builder.add_edge("summarize", "write")
    builder.add_edge("write", "qc")
    builder.add_edge("qc", END)

    return builder.compile(checkpointer=MemorySaver())
