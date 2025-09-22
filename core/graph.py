from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from datetime import datetime
import json
import logging
import os
import re
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict, List, Optional

from .state import State, Evidence
from .utils import render_template_string, render_inputs, resolve_path, eval_list_expr
from .config import (
    get_llm_config,
    get_prompt,
    get_step_call_overrides,
    get_node_llm_config,
    get_node_prompt,
)
from .langfuse_tracing import get_langfuse_client, observe
from tools import get_tool, register_default_adapters
from .scope import categorize_request, split_tasks
from strategies import load_strategy, select_strategy, get_index_entry_by_slug
from renderers import get_renderer


logger = logging.getLogger(__name__)

DEFAULT_QUERY_REFINER_PROMPT = (
    "Given the snippets below, suggest refined search queries for the listed tools. "
    "Return a JSON object mapping tool names to query strings.\nSnippets:\n{snippets}\n\n"
    "Tools: {tools}"
)

DEFAULT_FINALIZE_SYSTEM_PROMPT = (
    "You are a ReAct agent. First analyze the evidence, decide if a tool call is needed, "
    "then produce the requested report. Never offer additional services or ask follow-up "
    "questions."
)

DEFAULT_FINALIZE_ANALYSIS_TEMPLATE = (
    "You are a ReAct agent that analyzes evidence, can call tools if needed, and writes "
    "report sections.\n\nCurrent evidence ({evidence_count} sources):\n{evidence_text}\n\n"
    "Topic: {topic}\nTime window: {time_window}\nCurrent date: {current_date}\n\n"
    "Instructions:\n{instructions}\n\nThink step by step:\n"
    "1. Review the evidence - is it complete and recent enough?\n"
    "2. If critical information is missing, make ONE tool call to fill the gap\n"
    "3. Then write the report sections\n\nAvailable tools you can use:\n"
    "- exa_answer: Get a direct answer to a question\n"
    "- exa_search: Search for information\n"
    "- sonar_call: Get an AI-generated response with web search\n\nRespond with your analysis and actions."
)

DEFAULT_FINALIZE_WRITER_TEMPLATE = (
    "Based on all the evidence (including new information from tool calls), write the report.\n\n"
    "Updated evidence ({evidence_count} sources):\n{evidence_text}\n\n"
    "Write these sections with markdown headers (##):\n{sections_prompt}\n\n"
    "IMPORTANT RULES:\n"
    "1. Each section starts with ## and the section name\n"
    "2. Use [1], [2], [3] etc. to cite sources in the text\n"
    "3. End with a ## Sources section listing all sources with numbers\n"
    "4. Do NOT add any offers or follow-up questions\n"
    "5. End the report immediately after the Sources section"
)


def _format_prompt(template: str, **kwargs: Any) -> str:
    """Format a template while escaping braces in values."""
    safe_kwargs: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            safe_kwargs[key] = value.replace("{", "{{").replace("}", "}}")
        else:
            safe_kwargs[key] = value
    return template.format(**safe_kwargs)


def _prompt_text(value: Any, default: str) -> str:
    """Normalize prompt config entries."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("template", "prompt", "system", "text"):
            text = value.get(key)
            if isinstance(text, str):
                return text
    return default


def _normalize_step(step: Any) -> Dict[str, Any]:
    """Return a plain-dict representation of a strategy/tool step."""

    if isinstance(step, dict):
        base = dict(step)
    else:
        base = {
            "use": getattr(step, "use", None),
            "name": getattr(step, "name", None),
            "inputs": getattr(step, "inputs", None),
            "params": getattr(step, "params", None),
            "llm_fill": getattr(step, "llm_fill", None),
            "save_as": getattr(step, "save_as", None),
            "foreach": getattr(step, "foreach", None),
            "when": getattr(step, "when", None),
            "phase": getattr(step, "phase", None),
            "description": getattr(step, "description", None),
        }

    base.setdefault("phase", base.get("phase") or "research")
    base["inputs"] = dict(base.get("inputs") or {})
    base["params"] = dict(base.get("params") or {})
    base["llm_fill"] = list(base.get("llm_fill") or [])
    return base


def _resolve_step_inputs(
    step_inputs: Dict[str, Any],
    variables: Dict[str, Any],
    state_vars: Dict[str, Any],
    *,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = {**variables, **state_vars}
    rendered = render_inputs(step_inputs or {}, context)
    if overrides:
        rendered.update(overrides)
    return rendered


def _record_evidence(results: Any, bucket: List[Evidence]) -> None:
    _maybe_add_evidence(results, bucket)


def _log_step_error(step_label: str, exc: Exception) -> None:
    logger.exception("Research step '%s' failed", step_label, exc_info=exc)


def _as_evidence_list(results: Any) -> List[Evidence]:
    if isinstance(results, Evidence):
        return [results]
    if isinstance(results, list) and results and isinstance(results[0], Evidence):
        return results
    return []


@observe(as_type="generation", name="cluster-evidence")
def _cluster_llm(prompt: str, model: str | None = None) -> str:
    """Call an LLM to cluster evidence and return the raw text response."""
    from openai import OpenAI  # Lazy import to keep optional dependency
    
    # Get model from config if not provided
    if model is None:
        from core.config import get_llm_config
        cfg = get_llm_config("cluster")
        model = cfg.get("model", "gpt-4o-mini")

    client = OpenAI()
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_generation(
            model=model,
            input={"prompt": prompt},
            metadata={"component": "cluster_llm"},
        )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    choice = response["choices"][0] if isinstance(response, dict) else response.choices[0]
    message = choice["message"] if isinstance(choice, dict) else choice.message
    content = message.get("content") if isinstance(message, dict) else message.content
    if lf_client:
        usage = getattr(response, "usage", None)
        usage_details = None
        if usage:
            usage_details = {
                "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
            }
        lf_client.update_current_generation(
            output=content,
            usage_details=usage_details,
        )
    return content


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


@observe(as_type="generation", name="query-refinement")
def _refine_queries_with_llm(
    last_results: List[Evidence],
    allowed_keys: List[str],
    max_queries: int | None = None,
    strategy_slug: str | None = None,
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

    snippets_block = "\n".join(f"- {s}" for s in snippets)
    prompt_template = _prompt_text(
        get_node_prompt("query_refiner", strategy_slug),
        DEFAULT_QUERY_REFINER_PROMPT,
    )
    prompt = _format_prompt(
        prompt_template,
        snippets=snippets_block or "-",
        tools=", ".join(allowed_keys),
    )

    try:
        from openai import OpenAI  # Imported lazily

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {}

        node_cfg = get_node_llm_config("query_refiner", strategy_slug)
        model = node_cfg.get("model", "gpt-4o-mini")
        call_kwargs = {k: v for k, v in node_cfg.items() if k != "model"}

        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_generation(
                model=model,
                input={
                    "snippets": snippets_block.split("\n"),
                    "tools": allowed_keys,
                    "strategy": strategy_slug,
                },
                metadata={"component": "query_refiner"},
            )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **call_kwargs,
        )
        content = response.choices[0].message["content"]
        if lf_client:
            usage = getattr(response, "usage", None)
            usage_details = None
            if usage:
                usage_details = {
                    "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                }
            lf_client.update_current_generation(
                output=content,
                usage_details=usage_details,
            )
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
        if not state.strategy_slug:
            slug = cat.get("strategy_slug")
            if isinstance(slug, str) and slug:
                state.strategy_slug = slug
        cat_vars = cat.get("variables")
        if isinstance(cat_vars, dict):
            for key, value in cat_vars.items():
                if not isinstance(key, str):
                    continue
                if isinstance(value, str):
                    state.vars[key] = value
                elif isinstance(value, list):
                    # Only store list of strings
                    vv = [str(it) for it in value if isinstance(it, (str, int, float))]
                    state.vars[key] = vv

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
    """Execute the research phase based on the selected strategy using a single pass.

    Variables from the scope/fill phases (e.g., topic, dates) are rendered into the
    strategy's steps. We no longer fan-out across multiple tasks; instead we derive
    a canonical topic and run the chain once.
    """
    if not state.strategy_slug:
        return state

    register_default_adapters(silent=True)
    strategy = load_strategy(state.strategy_slug)
    max_results = strategy.limits.get("max_results") if strategy.limits else None
    max_llm_queries = strategy.limits.get("max_llm_queries") if strategy.limits else None

    runtime_plan: List[Dict[str, Any]] = state.vars.get("runtime_plan", [])  # type: ignore
    source_steps: List[Any] = runtime_plan if runtime_plan else strategy.tool_chain
    normalized_steps = [_normalize_step(step) for step in source_steps]
    research_steps = [s for s in normalized_steps if (s.get("phase") or "research") == "research"]
    if not research_steps:
        return state

    base_queries = dict(strategy.queries or {})

    # Determine fan-out policy and iteration patches
    patches: List[Dict[str, Any]] = []
    idx_entry = get_index_entry_by_slug(state.strategy_slug) if state.strategy_slug else None
    fan_out_policy = idx_entry.normalized_fan_out() if idx_entry else "none"

    # Base variables (single canonical topic)
    single_topic = (
        (state.vars.get("topic") or (state.tasks[0] if state.tasks else state.user_request))
        if state.user_request is not None
        else ""
    )
    canonical_topic = single_topic if isinstance(single_topic, str) else str(single_topic)

    if fan_out_policy == "task" and state.tasks:
        for t in state.tasks:
            if isinstance(t, str) and t:
                patches.append({"topic": t, "subtopic": t})
        if not patches:
            patches.append({})
    elif fan_out_policy == "var" and idx_entry is not None:
        var_name = idx_entry.fan_out_var_name()
        map_to = idx_entry.fan_out_map_to()
        limit = idx_entry.fan_out_limit()
        values: List[Any] = []
        if var_name:
            v = state.vars.get(var_name)
            if isinstance(v, list):
                values = v
            elif isinstance(v, str) and v:
                values = [v]
        if limit is not None:
            values = values[: max(0, limit)]
        for val in values:
            sval = val if isinstance(val, str) else str(val)
            patch: Dict[str, Any] = {map_to: sval}
            if map_to == "topic":
                patch.setdefault("subtopic", sval)
            patches.append(patch)
        if not patches:
            patches.append({})
    else:
        patches = [{}]

    aggregated_evidence: List[Evidence] = []

    for patch in patches:
        variables: Dict[str, Any] = {
            "topic": canonical_topic,
            "subtopic": canonical_topic,
            "time_window": state.time_window or "",
            "region": "",
        }
        variables.update(state.vars)
        variables.update(patch)

        task_evidence: List[Evidence] = []
        last_results: List[Evidence] = []
        task_queries = dict(base_queries)

        for idx, step in enumerate(research_steps):
            step_label = step.get("use") or step.get("name") or f"step-{idx}"

            if step.get("when") and not _eval_when(step["when"], state):
                continue

            use = step.get("use")
            if not use and not step.get("name"):
                continue

            # Legacy tool-chain support -------------------------------------------------
            if not use and step.get("name"):
                name: str = step["name"]
                results: Any = []
                try:
                    if name.startswith("sonar"):
                        prompt_t = task_queries.get("sonar", "{{topic}}")
                        prompt = _render_template(prompt_t, variables)
                        tool = get_tool("sonar")
                        results = tool.call(prompt, **step.get("params", {}))
                    elif name.startswith("exa_search"):
                        query_t = task_queries.get("exa_search", "{{topic}}")
                        query = _render_template(query_t, variables)
                        params = {
                            key: _render_template(val, variables) if isinstance(val, str) else val
                            for key, val in step.get("params", {}).items()
                        }
                        tool = get_tool("exa")
                        results = tool.call(query, **params)
                    elif name.startswith("exa_contents"):
                        top_k = step.get("params", {}).get("top_k", 0)
                        tool = get_tool("exa")
                        fetched: List[Evidence] = []
                        for ev in last_results[:top_k]:
                            content = tool.contents(
                                ev.url,
                                **{k: v for k, v in step.get("params", {}).items() if k != "top_k"},
                            )
                            if content.snippet:
                                ev.snippet = content.snippet
                            fetched.append(ev)
                        results = fetched
                    elif name.startswith("exa_find_similar"):
                        seed = last_results[0].url if last_results else ""
                        if seed:
                            tool = get_tool("exa")
                            results = tool.find_similar(seed, **step.get("params", {}))
                        else:
                            results = []
                    elif name.startswith("exa_answer"):
                        query_t = task_queries.get("exa_answer", "{{topic}}")
                        query = _render_template(query_t, variables)
                        tool = get_tool("exa")
                        answer_text = tool.answer(query, **step.get("params", {}))
                        results = [
                            Evidence(
                                url="exa_answer",
                                title="Exa Answer",
                                snippet=answer_text,
                                tool="exa",
                            )
                        ]
                    else:
                        results = []
                except Exception as exc:  # pragma: no cover - network errors mocked in tests
                    _log_step_error(step_label, exc)
                    results = []

                _record_evidence(results, task_evidence)
                last_results = _as_evidence_list(results)

                remaining = research_steps[idx + 1 :]
                allowed_keys = [
                    key
                    for key in (
                        _step_query_key(s.get("name", ""))
                        for s in remaining
                    )
                    if key
                ]
                if last_results and allowed_keys:
                    suggestions = _refine_queries_with_llm(
                        last_results,
                        allowed_keys,
                        max_llm_queries,
                        state.strategy_slug,
                    )
                    if suggestions:
                        task_queries.update(suggestions)
                        base_queries.update(suggestions)
                continue

            # Extended provider.method routing ---------------------------------------
            overrides = get_step_call_overrides(state.strategy_slug, use)
            foreach_expr = step.get("foreach")
            try:
                if foreach_expr:
                    items = eval_list_expr(
                        foreach_expr,
                        {**variables, **state.vars, "last_results": last_results},
                    ) or []
                    step_outputs: List[Any] = []
                    collected: List[Evidence] = []
                    for item in items:
                        render_context = {
                            **variables,
                            **state.vars,
                            "item": item,
                            "last_results": last_results,
                        }
                        inputs = _resolve_step_inputs(
                            step.get("inputs", {}),
                            render_context,
                            state.vars,
                            overrides=overrides,
                        )
                        result = _execute_use(use, inputs)
                        step_outputs.append(result)
                        _record_evidence(result, task_evidence)
                        collected.extend(_as_evidence_list(result))
                    if step.get("save_as"):
                        state.vars[step["save_as"]] = step_outputs
                    if collected:
                        last_results = collected
                    continue

                render_context = {**variables, **state.vars, "last_results": last_results}
                inputs = _resolve_step_inputs(
                    step.get("inputs", {}),
                    render_context,
                    state.vars,
                    overrides=overrides,
                )
                results = _execute_use(use, inputs)
            except Exception as exc:  # pragma: no cover - defensive
                _log_step_error(step_label, exc)
                results = []

            _record_evidence(results, task_evidence)
            if step.get("save_as"):
                state.vars[step["save_as"]] = results
            new_results = _as_evidence_list(results)
            if new_results:
                last_results = new_results

        # End for over research steps

        processed = _dedupe_and_score(task_evidence, max_results)
        aggregated_evidence.extend(processed)

    # Aggregate across topics (if any), then dedupe and apply budget once
    state.evidence.extend(aggregated_evidence)
    state.evidence = _dedupe_and_score(state.evidence, max_results)
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

    # If sections already exist (reactive finalize), still allow transforming to
    # newsletter/pdf; otherwise skip rendering to preserve reactive output.
    if state.sections and renderer_type not in {"newsletter", "pdf"}:
        return state

    renderer = get_renderer(renderer_type)
    result = renderer.render(section_names, state.evidence)
    # If we already had sections (reactive), replace with transformed content
    if state.sections and renderer_type in {"newsletter", "pdf"}:
        state.sections = result.get("sections", [])
        # Merge citations uniquely
        existing = set(state.citations)
        for c in result.get("citations", []):
            if c not in existing:
                state.citations.append(c)
                existing.add(c)
        return state

    state.sections.extend(result.get("sections", []))
    state.citations.extend(result.get("citations", []))
    return state


@observe(as_type="generation", name="qc-llm")
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
    lf_client = get_langfuse_client()
    system = system or (
        "You check whether report sections are grounded in the provided citations. "
        "Respond in JSON with keys 'grounded' (boolean), 'warnings' (list of strings), "
        "and 'inconsistencies' (list of strings)."
    )
    user = f"Sections:\n{chr(10).join(sections)}\n\nCitations:\n{chr(10).join(citations)}"
    if lf_client:
        lf_client.update_current_generation(
            model=model,
            input={"sections": sections, "citations": citations},
            metadata={"component": "qc_llm"},
        )
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
        if lf_client:
            usage = getattr(resp, "usage", None)
            usage_details = None
            if usage:
                usage_details = {
                    "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                }
            lf_client.update_current_generation(
                output=content,
                usage_details=usage_details,
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
    
    def format_evidence_lines(
        items: List[Evidence],
        limit: int = 30,
        skip_urls: Optional[set[str]] = None,
    ) -> List[str]:
        lines: List[str] = []
        for i, ev in enumerate(items[:limit], 1):
            text = f"{i}. "
            if ev.title:
                text += f"{ev.title} "
            if ev.snippet:
                text += f"- {ev.snippet[:200]}... "
            if ev.date:
                text += f"({ev.date}) "
            elif ev.publisher:
                text += f"({ev.publisher}) "
            if ev.url and (not skip_urls or ev.url not in skip_urls):
                text += f"[{ev.url}]"
            lines.append(text)
        return lines

    node_cfg = get_node_llm_config("finalize_react", state.strategy_slug)
    model = node_cfg.get("model", "gpt-4o-mini")
    call_kwargs = {k: v for k, v in node_cfg.items() if k != "model"}
    if model == "gpt-5-mini":
        call_kwargs.pop("temperature", None)

    evidence_lines = format_evidence_lines(state.evidence)
    instructions = finalize_config.get("instructions", "")
    # Prefer topic provided by scope/fill, then first task, then user request
    topic_guess = (
        state.vars.get("topic")
        or (state.tasks[0] if state.tasks else None)
        or state.user_request
        or ""
    )
    if not isinstance(topic_guess, str):
        topic_guess = str(topic_guess)
    instructions = instructions.replace("{{topic}}", topic_guess)

    system_prompt = _prompt_text(
        get_node_prompt("finalize_react_system", state.strategy_slug),
        DEFAULT_FINALIZE_SYSTEM_PROMPT,
    )
    analysis_template = _prompt_text(
        get_node_prompt("finalize_react_analysis", state.strategy_slug),
        DEFAULT_FINALIZE_ANALYSIS_TEMPLATE,
    )
    analysis_prompt = _format_prompt(
        analysis_template,
        evidence_count=len(state.evidence),
        evidence_text="\n".join(evidence_lines),
        topic=topic_guess,
        time_window=state.time_window or "recent",
        current_date=state.vars.get("current_date", ""),
        instructions=instructions,
    )

    tools_payload = [
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
                    "required": ["query"],
                },
            },
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
                        "search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]},
                    },
                    "required": ["query"],
                },
            },
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
                        "search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]},
                    },
                    "required": ["prompt"],
                },
            },
        },
    ]

    try:
        from openai import OpenAI
        client = OpenAI()
        lf_client = get_langfuse_client()

        if lf_client:
            lf_client.update_current_generation(
                model=model,
                input={
                    "analysis_prompt": analysis_prompt,
                    "instructions": instructions,
                    "topic": topic,
                },
                metadata={"component": "finalize_react_analysis"},
            )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt},
            ],
            tools=tools_payload,
            tool_choice="auto",
            **call_kwargs,
        )

        message = response.choices[0].message
        if lf_client:
            usage = getattr(response, "usage", None)
            usage_details = None
            if usage:
                usage_details = {
                    "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                }
            lf_client.update_current_generation(
                output=getattr(message, "content", None),
                usage_details=usage_details,
            )

        # Handle tool calls if any (enforce at most one tool call)
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # Execute only the first tool call
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
            except Exception:
                # Log but don't fail
                pass
            
            # Dedupe evidence after tool call and before writing
            try:
                state.evidence = _dedupe_and_score(state.evidence, None)
            except Exception:
                pass

            # Now get the report with enhanced evidence
            updated_lines = format_evidence_lines(
                state.evidence,
                limit=40,
                skip_urls={"exa_answer_verification"},
            )

            sections_part = ""
            if "Then write these sections:" in instructions:
                sections_part = instructions.split("Then write these sections:")[1].strip()
            elif "sections:" in instructions.lower():
                sections_part = instructions.split("sections:")[1].strip()

            sections_prompt = sections_part or "Write a comprehensive report with appropriate sections"
            writer_template = _prompt_text(
                get_node_prompt("finalize_react_writer", state.strategy_slug),
                DEFAULT_FINALIZE_WRITER_TEMPLATE,
            )
            writer_prompt = _format_prompt(
                writer_template,
                evidence_count=len(state.evidence),
                evidence_text="\n".join(updated_lines),
                sections_prompt=sections_prompt,
            )

            if lf_client:
                lf_client.update_current_generation(
                    model=model,
                    input={"writer_prompt": writer_prompt},
                    metadata={"component": "finalize_react_writer"},
                )

            final_response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": writer_prompt},
                ],
                **call_kwargs,
            )

            report_content = final_response.choices[0].message.content
            if lf_client:
                usage = getattr(final_response, "usage", None)
                usage_details = None
                if usage:
                    usage_details = {
                        "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                        "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                    }
                lf_client.update_current_generation(
                    output=report_content,
                    usage_details=usage_details,
                )
        else:
            # No tools needed, extract report from initial message
            report_content = message.content
            # If the response includes thinking, extract just the report part
            if "## " in report_content:
                # Find where the actual report sections start
                report_start = report_content.find("## ")
                if report_start > 0:
                    report_content = report_content[report_start:]
        
        # Try to extract citations from a '## Sources' section
        try:
            src_idx = report_content.lower().find("## sources")
            if src_idx != -1:
                sources_block = report_content[src_idx:]
                lines = sources_block.splitlines()
                # drop the header line
                if lines and lines[0].strip().lower().startswith("## sources"):
                    lines = lines[1:]
                parsed: List[str] = []
                for ln in lines:
                    s = ln.strip()
                    if not s:
                        continue
                    if s.startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.", "[", "(") ) or ":" in s:
                        parsed.append(s)
                if parsed:
                    # Merge uniquely with existing citations
                    existing = set(state.citations)
                    for c in parsed:
                        if c not in existing:
                            state.citations.append(c)
                            existing.add(c)
        except Exception:
            pass

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
        logger.error("Invalid use specification '%s'", use)
        return []
    try:
        adapter = get_tool(provider)
    except Exception as exc:
        logger.exception("Adapter '%s' not registered", provider, exc_info=exc)
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
        logger.error("Adapter '%s' has no callable for method '%s'", provider, method)
        return []
    try:
        return fn(**inputs) if isinstance(inputs, dict) else fn(inputs)
    except TypeError as exc:
        logger.debug("Attempting positional fallback for %s due to TypeError: %s", use, exc)
        # Try positional fallback
        try:
            return fn(*inputs.values())  # type: ignore[arg-type]
        except Exception as inner_exc:
            logger.exception("Failed fallback invocation for %s", use, exc_info=inner_exc)
            return []
    except Exception as exc:
        logger.exception("Error executing use '%s'", use, exc_info=exc)
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


@observe(as_type="generation", name="fill-llm")
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
    lf_client = get_langfuse_client()
    instructions = (
        (base_instructions or "Fill the following JSON keys with concise values (strings or small lists). Only include the provided keys; no extras.")
        + "\n"
        + f"Keys: {list(allowed.keys())}\n"
        + f"Task: {description or 'fill search query parameters'}\n"
        + "Respond as a JSON object."
    )
    if lf_client:
        lf_client.update_current_generation(
            model=model or "gpt-4o-mini",
            input={"allowed_keys": list(allowed.keys()), "description": description},
            metadata={"component": "fill_llm"},
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
        if lf_client:
            usage = getattr(resp, "usage", None)
            usage_details = None
            if usage:
                usage_details = {
                    "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                }
            lf_client.update_current_generation(
                output=content,
                usage_details=usage_details,
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
