from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from datetime import datetime
import json
import os
import re
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict, List

from .state import State, Evidence
from .utils import render_template_string, render_inputs, resolve_path, eval_list_expr
from .config import get_llm_config, get_prompt, get_step_call_overrides
from tools import get_tool, register_default_adapters
from .scope import categorize_request, split_tasks
from strategies import load_strategy, select_strategy
from renderers import get_renderer


def _cluster_llm(prompt: str, model: str | None = None) -> str:
    """Call an LLM to cluster evidence and return the raw text response."""
    from openai import OpenAI  # Lazy import to keep optional dependency
    
    # Get model from config if not provided
    if model is None:
        from core.config import get_llm_config
        cfg = get_llm_config("cluster")
        model = cfg.get("model", "gpt-4o-mini")

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    choice = response["choices"][0] if isinstance(response, dict) else response.choices[0]
    message = choice["message"] if isinstance(choice, dict) else choice.message
    return message.get("content") if isinstance(message, dict) else message.content


def _render_template(template: str, variables: Dict[str, str]) -> str:
    """Kept for backward compatibility; delegates to utils."""
    return render_template_string(template, variables)


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


def _step_query_key(name: str) -> str | None:
    """Map a tool step name to its query dictionary key."""
    if name.startswith("sonar"):
        return "sonar"
    if name.startswith("exa_search"):
        return "exa_search"
    if name.startswith("exa_answer"):
        return "exa_answer"
    return None


def _refine_queries_with_llm(
    last_results: List[Evidence],
    allowed_keys: List[str],
    max_queries: int | None = None,
) -> Dict[str, str]:
    """Use an LLM to suggest refined queries based on recent results."""
    if not last_results or not allowed_keys:
        return {}

    snippets: List[str] = []
    for ev in last_results:
        if ev.snippet:
            snippets.append(ev.snippet)
        elif ev.title:
            snippets.append(ev.title)
        if len(snippets) >= 3:
            break
    if not snippets:
        return {}

    prompt = (
        "Given the following snippets:\n"
        + "\n".join(f"- {s}" for s in snippets)
        + "\nSuggest refined or follow-up search queries for the following tools: "
        + ", ".join(allowed_keys)
        + ". Return a JSON object mapping tool names to query strings."
    )

    try:
        from openai import OpenAI  # Imported lazily

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message["content"]
        data = json.loads(content)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    refined: Dict[str, str] = {}
    for key in allowed_keys:
        if key in data:
            refined[key] = data[key]
            if max_queries is not None and len(refined) >= max_queries:
                break
    return refined


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
    """Execute the research phase based on the selected strategy.

    Supports legacy steps and extended `use` steps with optional foreach/when/save_as.
    """
    if not state.strategy_slug or not state.tasks:
        return state

    register_default_adapters(silent=True)
    strategy = load_strategy(state.strategy_slug)
    max_results = strategy.limits.get("max_results") if strategy.limits else None
    max_llm_queries = strategy.limits.get("max_llm_queries") if strategy.limits else None

    runtime_plan: List[Dict[str, Any]] = state.vars.get("runtime_plan", [])  # type: ignore

    for task in state.tasks:
        # Use dates from state.vars that were set in fill phase
        variables: Dict[str, Any] = {
            "topic": task,
            "subtopic": task,
            "time_window": state.time_window or "",
            "region": "",
        }
        # Include all vars from state (which includes dates from fill phase)
        variables.update(state.vars)
        
        task_evidence: List[Evidence] = []
        last_results: List[Evidence] = []

        # Choose steps: use runtime plan if present, else fall back to legacy strategy.tool_chain
        steps_iter: List[Any]
        if runtime_plan:
            steps_iter = [s for s in runtime_plan if (s.get("phase") or "research") == "research"]
        else:
            steps_iter = strategy.tool_chain

        for idx, step in enumerate(steps_iter):
            # Normalize step to dict-like
            sdict: Dict[str, Any]
            if hasattr(step, "use"):
                # pydantic ToolStep
                params_dict = getattr(step, "params", {}) or {}
                sdict = {
                    "use": getattr(step, "use", None),
                    "name": getattr(step, "name", None),
                    "inputs": getattr(step, "inputs", {}) or {},
                    "params": params_dict,
                    "llm_fill": getattr(step, "llm_fill", []) or [],
                    "save_as": getattr(step, "save_as", None),
                    "foreach": getattr(step, "foreach", None),
                    "when": getattr(step, "when", None),
                }
            else:
                sdict = step  # assume already a dict

            # Legacy routing by name prefix
            if not sdict.get("use") and sdict.get("name"):
                name: str = sdict["name"]
                if name.startswith("sonar"):
                    prompt_t = strategy.queries.get("sonar", "{{topic}}")
                    prompt = _render_template(prompt_t, variables)
                    try:
                        tool = get_tool("sonar")
                        results = tool.call(prompt, **sdict.get("params", {}))
                    except Exception:
                        results = []
                    last_results = results
                elif name.startswith("exa_search"):
                    query_t = strategy.queries.get("exa_search", "{{topic}}")
                    query = _render_template(query_t, variables)
                    try:
                        tool = get_tool("exa")
                        # Render parameters that might contain template variables
                        params = sdict.get("params", {})
                        rendered_params = {}
                        for key, value in params.items():
                            if isinstance(value, str):
                                rendered_params[key] = _render_template(value, variables)
                            else:
                                rendered_params[key] = value
                        results = tool.call(query, **rendered_params)
                    except Exception:
                        results = []
                    last_results = results
                elif name.startswith("exa_contents"):
                    top_k = sdict.get("params", {}).get("top_k", 0)
                    results = []
                    try:
                        tool = get_tool("exa")
                        for ev in last_results[:top_k]:
                            content = tool.contents(
                                ev.url,
                                **{k: v for k, v in sdict.get("params", {}).items() if k != "top_k"},
                            )
                            if content.snippet:
                                ev.snippet = content.snippet
                            results.append(ev)
                    except Exception:
                        results = []
                    last_results = results
                elif name.startswith("exa_find_similar"):
                    try:
                        tool = get_tool("exa")
                        seed = last_results[0].url if last_results else ""
                        results = tool.find_similar(seed, **sdict.get("params", {})) if seed else []
                    except Exception:
                        results = []
                    last_results = results
                elif name.startswith("exa_answer"):
                    query_t = strategy.queries.get("exa_answer", "{{topic}}")
                    query = _render_template(query_t, variables)
                    try:
                        tool = get_tool("exa")
                        answer_text = tool.answer(query, **sdict.get("params", {}))
                        # Store answer as a special Evidence object or directly in state
                        results = [Evidence(
                            url="exa_answer",
                            title="Exa Answer",
                            snippet=answer_text,
                            tool="exa"
                        )]
                    except Exception:
                        results = []
                else:
                    results = []

                task_evidence.extend(last_results)

                remaining = steps_iter[idx + 1 :]
                # For legacy: allow light LLM refinement if configured
                allowed_keys = [
                    k
                    for k in (
                        _step_query_key(s.get("name", "")) if isinstance(s, dict) else _step_query_key(getattr(s, "name", ""))
                        for s in remaining
                    )
                    if k
                ]
                if last_results and allowed_keys:
                    suggestions = _refine_queries_with_llm(
                        last_results, allowed_keys, max_llm_queries
                    )
                    for key, val in suggestions.items():
                        strategy.queries[key] = val
                continue

            # Extended routing via provider.method
            use = sdict.get("use")
            if not use:
                continue

            # Evaluate 'when'
            should_run = True
            when = sdict.get("when")
            if when:
                should_run = _eval_when(when, state)
            if not should_run:
                continue

            # Foreach support
            foreach = sdict.get("foreach")
            if foreach:
                items = eval_list_expr(foreach, {**variables, **state.vars, "last_results": last_results}) or []
                step_results: List[Any] = []
                for item in items:
                    call_vars = {**variables, **state.vars, "item": item}
                    inputs = render_inputs(sdict.get("inputs", {}), call_vars)
                    overrides = get_step_call_overrides(state.strategy_slug, use)
                    if overrides:
                        inputs.update(overrides)
                    results = _execute_use(use, inputs)
                    _maybe_add_evidence(results, task_evidence)
                    step_results.append(results)
                if sdict.get("save_as"):
                    state.vars[sdict["save_as"]] = step_results
                continue

            # Single execution
            inputs = render_inputs(sdict.get("inputs", {}), {**variables, **state.vars, "last_results": last_results})
            overrides = get_step_call_overrides(state.strategy_slug, use)
            if overrides:
                inputs.update(overrides)
            results = _execute_use(use, inputs)
            _maybe_add_evidence(results, task_evidence)
            if sdict.get("save_as"):
                state.vars[sdict["save_as"]] = results

        processed = _dedupe_and_score(task_evidence, max_results)
        state.evidence.extend(processed)

    # Global dedupe after processing all tasks
    state.evidence = _dedupe_and_score(state.evidence, max_results)
    return state




def write(state: State) -> State:
    """Render sections and assemble citations based on strategy."""
    if not state.strategy_slug:
        return state

    # Skip if finalize already wrote the sections (reactive mode)
    if state.sections:
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


def _qc_llm(sections: List[str], citations: List[str], model: str | None = None, system: str | None = None) -> Dict[str, Any]:
    """Call an LLM to verify factual grounding."""
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return {}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {}

    client = OpenAI(api_key=api_key)
    model = model or os.getenv("QC_MODEL", "gpt-4o-mini")
    system = system or (
        "You check whether report sections are grounded in the provided citations. "
        "Respond in JSON with keys 'grounded' (boolean), 'warnings' (list of strings), "
        "and 'inconsistencies' (list of strings)."
    )
    user = f"Sections:\n{chr(10).join(sections)}\n\nCitations:\n{chr(10).join(citations)}"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        choice = resp["choices"][0] if isinstance(resp, dict) else resp.choices[0]
        message = choice["message"] if isinstance(choice, dict) else choice.message
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", "{}")
        )
        return json.loads(content)
    except Exception:
        return {}


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

    # LLM grounding check ------------------------------------------------
    if state.sections and state.citations:
        llm_cfg = get_llm_config("qc", state.strategy_slug)
        system = get_prompt("qc", state.strategy_slug)
        result = _qc_llm(state.sections, state.citations, model=llm_cfg.get("model"), system=system)
        warnings = result.get("warnings") or []
        if warnings:
            state.limitations.extend(warnings)
        inconsistencies = result.get("inconsistencies") or []
        if inconsistencies:
            state.errors.extend(inconsistencies)
        if result.get("grounded") is False:
            state.limitations.append("model flagged potential ungrounded content")

    if errors:
        state.errors.extend(errors)
        state.limitations.append("qc-lite detected issues")
    return state


def fill(state: State) -> State:
    """Fill phase: ask an LLM to provide values for whitelisted inputs per step.

    Minimal implementation: creates a runtime plan and stores under state.vars["runtime_plan"].
    Skips if no llm_fill present or no API key; keeps architecture working even without fills.
    """
    if not state.strategy_slug:
        return state
    try:
        strategy = load_strategy(state.strategy_slug)
    except Exception:
        return state

    # Calculate dates based on time window to make them available to the LLM
    from datetime import datetime
    from core.utils import parse_date_range, format_date_for_query
    
    current_date = datetime.now()
    if state.time_window:
        start_date, end_date = parse_date_range(state.time_window, current_date)
    else:
        # Default to last 24 hours
        start_date, end_date = parse_date_range("last 24 hours", current_date)
    
    # Store dates in state.vars for use throughout the pipeline
    state.vars["current_date"] = format_date_for_query(current_date, "natural")
    state.vars["start_date"] = format_date_for_query(start_date, "iso")
    state.vars["end_date"] = format_date_for_query(end_date, "iso")
    state.vars["start_date_natural"] = format_date_for_query(start_date, "natural")
    state.vars["end_date_natural"] = format_date_for_query(end_date, "natural")
    
    # Map time_window to Sonar's search_recency_filter
    recency_map = {
        "day": "day",
        "daily": "day",
        "last 24 hours": "day",
        "week": "week",
        "weekly": "week",
        "month": "month",
        "monthly": "month",
        "year": "year",
        "yearly": "year"
    }
    state.vars["search_recency_filter"] = recency_map.get(state.time_window.lower() if state.time_window else "day", "week")

    runtime_plan: List[Dict[str, Any]] = []
    limits = strategy.limits or {}
    remaining_budget = limits.get("max_llm_queries", 0) or 0

    for step in strategy.tool_chain:
        entry: Dict[str, Any] = {
            "use": step.use,
            "name": step.name,
            "inputs": dict(step.inputs) if step.inputs else {},
            "llm_fill": list(step.llm_fill) if step.llm_fill else [],
            "save_as": step.save_as,
            "foreach": step.foreach,
            "when": step.when,
            "phase": step.phase or "research",
            "description": step.description,
        }
        # Legacy steps: no change
        if step.use and step.llm_fill and remaining_budget > 0:
            allowed = {k: entry["inputs"].get(k, "") for k in step.llm_fill}
            llm_cfg = get_llm_config("fill", state.strategy_slug, step.use)
            prompt = get_prompt("fill", state.strategy_slug, step.use)
            filled = _llm_fill_inputs_simple(step.description or "", allowed, model=llm_cfg.get("model"), base_instructions=prompt)
            for k, v in filled.items():
                entry["inputs"][k] = v
            remaining_budget = max(0, remaining_budget - 1)
        runtime_plan.append(entry)

    state.vars["runtime_plan"] = runtime_plan
    return state


def finalize(state: State) -> State:
    """ReAct-style finalize node that can call tools then write report sections."""
    # Check if we should use ReAct mode based on strategy
    if not state.strategy_slug:
        return state
    
    strategy = load_strategy(state.strategy_slug)
    finalize_config = getattr(strategy, 'finalize', None) or {}
    
    # If reactive mode is enabled, use ReAct approach
    if finalize_config.get("reactive"):
        return _finalize_reactive(state, strategy, finalize_config)
    
    # Otherwise, fall back to original behavior
    runtime_plan: List[Dict[str, Any]] = state.vars.get("runtime_plan", [])  # type: ignore
    if not runtime_plan:
        return state

    register_default_adapters(silent=True)
    steps = [s for s in runtime_plan if (s.get("phase") or "research") == "finalize"]
    if not steps:
        # Heuristic: any step with 'when' and provider in {http, parse}
        steps = [
            s
            for s in runtime_plan
            if s.get("when") and str(s.get("use", "")).split(".")[0] in {"http", "parse"}
        ]
    if not steps:
        return state

    # Format evidence as text for LLM consumption
    evidence_text = []
    for i, ev in enumerate(state.evidence[:30], 1):
        text = f"{i}. "
        if ev.title:
            text += f"{ev.title} "
        if ev.snippet:
            text += f"- {ev.snippet[:200]} "
        # Add date before URL for better formatting
        if ev.date:
            text += f"({ev.date}) "
        elif ev.publisher:
            text += f"({ev.publisher}) "
        if ev.url:
            text += f"[{ev.url}]"
        evidence_text.append(text)
    
    variables: Dict[str, Any] = {
        "topic": state.tasks[0] if state.tasks else "",
        "time_window": state.time_window or "",
        "evidence": state.evidence,  # Keep original for compatibility
        "evidence_text": "\n".join(evidence_text),  # Formatted text for LLM
        "evidence_count": len(state.evidence),
        "current_date": state.vars.get("current_date", ""),
        "start_date": state.vars.get("start_date", ""),
        "end_date": state.vars.get("end_date", ""),
    }
    variables.update(state.vars)

    task_evidence: List[Evidence] = []
    for sdict in steps:
        if sdict.get("when") and not _eval_when(sdict["when"], state):
            continue
        foreach = sdict.get("foreach")
        if foreach:
            items = eval_list_expr(foreach, {**variables, **state.vars}) or []
            step_results: List[Any] = []
            for item in items:
                call_vars = {**variables, **state.vars, "item": item}
                inputs = render_inputs(sdict.get("inputs", {}), call_vars)
                overrides = get_step_call_overrides(state.strategy_slug, sdict.get("use", ""))
                if overrides:
                    inputs.update(overrides)
                results = _execute_use(sdict.get("use", ""), inputs)
                _maybe_add_evidence(results, task_evidence)
                step_results.append(results)
            if sdict.get("save_as"):
                state.vars[sdict["save_as"]] = step_results
            continue
        inputs = render_inputs(sdict.get("inputs", {}), {**variables, **state.vars})
        overrides = get_step_call_overrides(state.strategy_slug, sdict.get("use", ""))
        if overrides:
            inputs.update(overrides)
        results = _execute_use(sdict.get("use", ""), inputs)
        
        # Only add to evidence if NOT saving to vars (avoid duplication)
        if sdict.get("save_as"):
            state.vars[sdict["save_as"]] = results
        else:
            _maybe_add_evidence(results, task_evidence)

    # Merge evidence
    state.evidence.extend(_dedupe_and_score(task_evidence, None))
    return state


def _finalize_reactive(state: State, strategy: Any, finalize_config: Dict[str, Any]) -> State:
    """ReAct implementation of finalize - can call tools then write report."""
    register_default_adapters(silent=True)
    
    # Format evidence for LLM
    evidence_text = []
    for i, ev in enumerate(state.evidence[:30], 1):
        text = f"{i}. "
        if ev.title:
            text += f"{ev.title} "
        if ev.snippet:
            text += f"- {ev.snippet[:200]}... "
        if ev.date:
            text += f"({ev.date}) "
        elif ev.publisher:
            text += f"({ev.publisher}) "
        if ev.url:
            text += f"[{ev.url}]"
        evidence_text.append(text)
    
    # Get instructions and replace template variables
    instructions = finalize_config.get("instructions", "")
    topic = state.tasks[0] if state.tasks else ""
    instructions = instructions.replace("{{topic}}", topic)
    
    # Build ReAct prompt
    react_prompt = f"""You are a ReAct agent that analyzes evidence, can call tools if needed, and writes report sections.

Current evidence ({len(state.evidence)} sources):
{chr(10).join(evidence_text)}

Topic: {topic}
Time window: {state.time_window or 'recent'}
Current date: {state.vars.get('current_date', '')}

Instructions:
{instructions}

Think step by step:
1. Review the evidence - is it complete and recent enough?
2. If critical information is missing, make ONE tool call to fill the gap
3. Then write the report sections

Available tools you can use:
- exa_answer: Get a direct answer to a question
- exa_search: Search for specific information
- sonar_call: Get an AI-generated response with web search

Respond with your analysis and actions."""

    try:
        from openai import OpenAI
        client = OpenAI()
        
        # First call - analyze and potentially use tools
        response = client.chat.completions.create(
            model="gpt-5-mini",  # Using GPT-5 mini as specified
            messages=[
                {"role": "system", "content": "You are a ReAct agent. First analyze the evidence, then decide if you need to call a tool to fill critical gaps, then write the report. Never offer additional services or ask if the user wants more help."},
                {"role": "user", "content": react_prompt}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "exa_answer",
                        "description": "Get a direct answer to a question",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The question to answer"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "exa_search",
                        "description": "Search for information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "num_results": {"type": "integer", "default": 5},
                                "search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "sonar_call",
                        "description": "Get an AI response with web search",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "The prompt/question"},
                                "search_mode": {"type": "string", "enum": ["web", "academic"], "default": "web"},
                                "search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]}
                            },
                            "required": ["prompt"]
                        }
                    }
                }
            ],
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # Handle tool calls if any
        if message.tool_calls:
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                # Execute the tool
                try:
                    if function_name == "exa_answer":
                        tool = get_tool("exa")
                        result = tool.answer(arguments["query"])
                        # Add result as evidence
                        state.evidence.append(Evidence(
                            url="exa_answer_verification",
                            title="Additional Information",
                            snippet=result,
                            tool="exa",
                            date=state.vars.get('current_date', '')
                        ))
                        
                    elif function_name == "exa_search":
                        tool = get_tool("exa")
                        params = {k: v for k, v in arguments.items() if k != "query"}
                        results = tool.search(arguments["query"], **params)
                        state.evidence.extend(results)
                        
                    elif function_name == "sonar_call":
                        tool = get_tool("sonar")
                        params = {k: v for k, v in arguments.items() if k != "prompt"}
                        results = tool.call(arguments["prompt"], **params)
                        state.evidence.extend(results)
                except Exception as e:
                    # Log but don't fail
                    pass
            
            # Now get the report with enhanced evidence
            evidence_text = []
            for i, ev in enumerate(state.evidence[:40], 1):  # Include more evidence after tool calls
                text = f"{i}. "
                if ev.title:
                    text += f"{ev.title} "
                if ev.snippet:
                    text += f"- {ev.snippet[:200]}... "
                if ev.date:
                    text += f"({ev.date}) "
                if ev.url and ev.url != "exa_answer_verification":
                    text += f"[{ev.url}]"
                evidence_text.append(text)
            
            # Extract sections from instructions
            sections_part = ""
            if "Then write these sections:" in instructions:
                sections_part = instructions.split("Then write these sections:")[1].strip()
            elif "sections:" in instructions.lower():
                sections_part = instructions.split("sections:")[1].strip()
            
            # Second call - write the report
            final_response = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "user", "content": f"""Based on all the evidence (including new information from tool calls), write the report.

Updated evidence ({len(state.evidence)} sources):
{chr(10).join(evidence_text)}

Write these sections with markdown headers (##):
{sections_part if sections_part else 'Write a comprehensive report with appropriate sections'}

IMPORTANT RULES:
1. Each section starts with ## and the section name
2. Use [1], [2], [3] etc. to cite sources in the text
3. End with a ## Sources section listing all sources with numbers
4. Do NOT add any offers like 'If you want I can...' or 'I can also help with...'
5. End the report immediately after the Sources section - no additional text"""}
                ]
            )
            
            report_content = final_response.choices[0].message.content
        else:
            # No tools needed, extract report from initial message
            report_content = message.content
            # If the response includes thinking, extract just the report part
            if "## " in report_content:
                # Find where the actual report sections start
                report_start = report_content.find("## ")
                if report_start > 0:
                    report_content = report_content[report_start:]
        
        # Parse sections from the report
        if "## " in report_content:
            # Split by ## but keep the headers
            parts = report_content.split("## ")
            for part in parts[1:]:  # Skip the first empty part
                if part.strip():
                    state.sections.append(f"## {part.strip()}")
        else:
            # If no sections found, add as single section
            state.sections.append(report_content)
            
    except Exception as e:
        # Fallback to original behavior if ReAct fails
        import traceback
        traceback.print_exc()
        return state
    
    return state


def _execute_use(use: str, inputs: Dict[str, Any]) -> Any:
    """Execute a routed adapter method use=provider.method with inputs."""
    try:
        provider, method = use.split(".", 1)
    except ValueError:
        return []
    try:
        adapter = get_tool(provider)
    except Exception:
        return []
    fn = getattr(adapter, method, None)
    if fn is None:
        # try snake_case conversion from camelCase
        snake = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), method)
        fn = getattr(adapter, snake, None)
    if fn is None:
        # default to call
        fn = getattr(adapter, "call", None)
    if fn is None:
        return []
    try:
        return fn(**inputs) if isinstance(inputs, dict) else fn(inputs)
    except TypeError:
        # Try positional fallback
        try:
            return fn(*inputs.values())  # type: ignore[arg-type]
        except Exception:
            return []
    except Exception:
        return []


def _maybe_add_evidence(results: Any, bucket: List[Evidence]) -> None:
    if isinstance(results, Evidence):
        bucket.append(results)
    elif isinstance(results, list) and results and isinstance(results[0], Evidence):
        bucket.extend(results)  # type: ignore[arg-type]


def _eval_when(expr: str, state: State) -> bool:
    """Very small evaluator for `when` predicates.

    Supports patterns like "unique_sources < 3" or truthiness of a saved var.
    """
    expr = expr.strip()
    unique_sources = len({ev.url for ev in state.evidence}) if state.evidence else 0
    context: Dict[str, Any] = {**state.vars, "unique_sources": unique_sources}

    # Simple comparator: var < N  | var > N | var == N
    m = re.match(r"^(\w+)\s*(==|<=|>=|<|>)\s*(\d+)$", expr)
    if m:
        key, op, num_s = m.group(1), m.group(2), m.group(3)
        left = context.get(key, 0)
        try:
            right = int(num_s)
        except Exception:
            return False
        try:
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
            if op == "==":
                return left == right
        except Exception:
            return False
        return False

    # Fallback: truthiness of a saved variable name
    return bool(context.get(expr))


def _llm_fill_inputs_simple(description: str, allowed: Dict[str, Any], model: str | None = None, base_instructions: str | None = None) -> Dict[str, str]:
    """Ask an LLM to fill a few strings. Minimal, best-effort implementation.

    Returns an empty dict when API key or client is unavailable.
    """
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return {}
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {}
    client = OpenAI(api_key=api_key)
    instructions = (
        (base_instructions or "Fill the following JSON keys with concise values (strings or small lists). Only include the provided keys; no extras.")
        + "\n"
        + f"Keys: {list(allowed.keys())}\n"
        + f"Task: {description or 'fill search query parameters'}\n"
        + "Respond as a JSON object."
    )
    try:
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[{"role": "user", "content": instructions}],
        )
        choice = resp["choices"][0] if isinstance(resp, dict) else resp.choices[0]
        message = choice["message"] if isinstance(choice, dict) else choice.message
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", "{}")
        )
        import json as _json

        data = _json.loads(content)
        if isinstance(data, dict):
            return {k: str(v) if not isinstance(v, str) else v for k, v in data.items() if k in allowed}
    except Exception:
        return {}
    return {}


def build_graph() -> StateGraph:
    """Construct the LangGraph workflow (with fill/finalize phases)."""
    builder = StateGraph(State)
    builder.add_node("scope", scope)
    builder.add_node("fill", fill)
    builder.add_node("research", research)
    builder.add_node("finalize", finalize)
    builder.add_node("write", write)
    builder.add_node("qc", qc)

    builder.set_entry_point("scope")
    builder.add_edge("scope", "fill")
    builder.add_edge("fill", "research")
    builder.add_edge("research", "finalize")
    builder.add_edge("finalize", "write")
    builder.add_edge("write", "qc")
    builder.add_edge("qc", END)

    return builder.compile(checkpointer=MemorySaver())
