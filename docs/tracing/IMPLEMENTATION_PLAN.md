# Langfuse Tracing Enhancement - Implementation Plan

## Phase 1: Foundation (Priority 1 - Critical)

### Issue 1: Add Workflow Node Observability (@observe decorators for 4 main phases)

**Goal**: Make workflow phases (scope, fill, research, finalize) visible in Langfuse traces

**Scope**: Add `@observe` decorators to the 4 main LangGraph nodes in `core/graph.py`

**Implementation Details**:

Based on official Langfuse v3 docs, use `@observe(as_type="span")` for workflow phases:

```python
from core.langfuse_tracing import observe, get_langfuse_client

@observe(as_type="span", name="scope-phase")
def scope(state: State) -> State:
    """Scope phase categorizes the request and selects a strategy."""
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_span(
            input={
                "user_request": state.user_request[:200],  # Truncate for size
                "existing_strategy": state.strategy_slug
            },
            metadata={
                "phase": "scope",
                "has_category": bool(state.category),
                "has_time_window": bool(state.time_window)
            }
        )
    
    # ... existing scope logic ...
    
    if lf_client:
        lf_client.update_current_span(
            output={
                "strategy_slug": state.strategy_slug,
                "category": state.category,
                "time_window": state.time_window,
                "depth": state.depth,
                "tasks_count": len(state.tasks)
            },
            metadata={
                "strategy_selected": state.strategy_slug,
                "tasks_generated": len(state.tasks)
            }
        )
    
    return state


@observe(as_type="span", name="fill-phase")
def fill(state: State) -> State:
    """Fill phase: resolve variables for strategy execution."""
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_span(
            input={
                "strategy": state.strategy_slug,
                "vars_keys": list(state.vars.keys()) if state.vars else []
            },
            metadata={
                "phase": "fill",
                "strategy": state.strategy_slug
            }
        )
    
    # ... existing fill logic ...
    
    if lf_client:
        lf_client.update_current_span(
            output={
                "vars_filled": list(state.vars.keys()) if state.vars else [],
                "runtime_plan_steps": len(state.vars.get("runtime_plan", []))
            }
        )
    
    return state


@observe(as_type="span", name="research-phase")
def research(state: State) -> State:
    """Execute the research phase based on the selected strategy."""
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_span(
            input={
                "strategy": state.strategy_slug,
                "topic": str(state.vars.get("topic", ""))[:100]
            },
            metadata={
                "phase": "research",
                "strategy": state.strategy_slug,
                "time_window": state.time_window
            }
        )
    
    # ... existing research logic ...
    
    if lf_client:
        lf_client.update_current_span(
            output={
                "evidence_count": len(state.evidence),
                "unique_sources": len(set(e.url for e in state.evidence if hasattr(e, 'url')))
            },
            metadata={
                "evidence_collected": len(state.evidence),
                "steps_executed": len(research_steps)
            }
        )
    
    return state


@observe(as_type="span", name="finalize-phase")
def finalize(state: State) -> State:
    """Finalize phase: synthesize report from evidence."""
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_span(
            input={
                "evidence_count": len(state.evidence),
                "strategy": state.strategy_slug
            },
            metadata={
                "phase": "finalize",
                "strategy": state.strategy_slug
            }
        )
    
    # ... existing finalize logic ...
    
    if lf_client:
        lf_client.update_current_span(
            output={
                "sections_count": len(state.sections),
                "citations_count": len(state.citations)
            },
            metadata={
                "sections_generated": len(state.sections),
                "citations_provided": len(state.citations)
            }
        )
    
    return state
```

**Files to Modify**:
- `core/graph.py` - Add @observe decorators and update calls to all 4 functions

**Acceptance Criteria**:
- [ ] All 4 workflow nodes have @observe decorators
- [ ] Each node updates with input at start
- [ ] Each node updates with output at end
- [ ] Metadata includes phase name and strategy
- [ ] Traces show 4 distinct phase spans
- [ ] Phase durations are visible in Langfuse
- [ ] No performance degradation (< 50ms overhead per phase)

**Testing**:
```bash
# Run test and verify traces
python3 run_daily_briefing.py --topic "AI news" --debug
# Check Langfuse for 4 visible phase spans
```

**Estimated Effort**: 4 hours

---

### Issue 2: Add Research Step-Level Tracing (nested spans for strategy execution)

**Goal**: Make individual research steps visible within the research phase

**Scope**: Add nested span creation for each step in the research loop in `core/graph.py`

**Implementation Details**:

Per Langfuse docs: "Nesting is handled automatically by OpenTelemetry's context propagation."

```python
# In research() function, inside the step execution loop

for idx, step in enumerate(research_steps):
    step_label = step.get("use") or step.get("name") or f"step-{idx}"
    
    # Create nested span for this step
    lf_client = get_langfuse_client()
    if lf_client:
        with lf_client.start_as_current_span(
            name=f"research-step-{idx+1}:{step_label}"
        ) as step_span:
            step_span.update(
                input={
                    "step_index": idx + 1,
                    "step_name": step_label,
                    "tool": step.get("use"),
                    "params": {k: str(v)[:100] if isinstance(v, str) else v 
                              for k, v in step.get("params", {}).items()}
                },
                metadata={
                    "strategy": state.strategy_slug,
                    "phase": "research",
                    "step_index": idx + 1,
                    "when_condition": str(step.get("when", "")) if step.get("when") else None
                }
            )
            
            # Handle "when" condition
            if step.get("when") and not _eval_when(step["when"], state):
                step_span.update(
                    output={"skipped": True, "reason": "when_condition_false"},
                    metadata={"skipped": True}
                )
                continue
            
            # Execute step (existing code)
            use = step.get("use")
            results = []
            
            try:
                # ... existing step execution logic ...
                
                step_span.update(
                    output={
                        "results_count": len(results),
                        "skipped": False
                    },
                    metadata={
                        "results_found": len(results),
                        "execution_success": True
                    }
                )
            except Exception as e:
                step_span.update(
                    output={"error": str(e), "skipped": False},
                    metadata={"error": str(e), "execution_success": False},
                    level="ERROR"
                )
                raise
    else:
        # Fallback: execute without tracing
        # ... existing step execution logic ...
```

**Files to Modify**:
- `core/graph.py` - Modify research() function step loop (around line 486)

**Acceptance Criteria**:
- [ ] Each research step creates a nested span
- [ ] Step spans show step index and name
- [ ] Skipped steps are marked with skip reason
- [ ] Tool parameters are captured (truncated)
- [ ] Results count is captured
- [ ] Errors are captured with ERROR level
- [ ] Step timing is visible in Langfuse
- [ ] Steps are properly nested under research-phase span

**Testing**:
```bash
# Run with strategy that has multiple steps
python3 run_daily_briefing.py --topic "Financial news" --debug
# Verify each step appears as child of research-phase
```

**Estimated Effort**: 6 hours

---

## Phase 2: Deep Instrumentation (Priority 2 - High)

### Issue 3: Add LLM Call Tracing (generations for all LLM operations)

**Goal**: Make all LLM calls visible with prompts, responses, and token usage

**Scope**: Add `@observe(as_type="generation")` to all LLM call functions

**Implementation Details**:

Per Langfuse docs: Use `as_type="generation"` for LLM calls and include usage_details.

```python
# In core/scope.py (example - scope_request function)

@observe(as_type="generation", name="scope-analysis-llm")
def scope_request(user_request: str) -> Dict[str, Any]:
    """Analyze request and categorize."""
    lf_client = get_langfuse_client()
    
    # Prepare prompt
    prompt = f"Analyze this research request: {user_request}"
    
    if lf_client:
        lf_client.update_current_generation(
            model="gpt-4",  # Use actual model from config
            input={"prompt": prompt, "user_request": user_request[:500]},
            metadata={
                "purpose": "scope_analysis",
                "request_length": len(user_request)
            }
        )
    
    # Make LLM call
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    result = response.choices[0].message.content
    
    if lf_client:
        lf_client.update_current_generation(
            output=result,
            usage_details={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            metadata={
                "response_length": len(result)
            }
        )
    
    return parse_scope_result(result)


# In core/graph.py - finalize() function

@observe(as_type="generation", name="finalize-analysis-llm")
def _finalize_analysis_llm(evidence_text: str, instructions: str, **kwargs) -> str:
    """LLM call for analyzing evidence before writing."""
    lf_client = get_langfuse_client()
    
    messages = [
        {"role": "system", "content": kwargs.get("system_prompt", "")},
        {"role": "user", "content": f"Evidence:\n{evidence_text}\n\nInstructions:\n{instructions}"}
    ]
    
    if lf_client:
        lf_client.update_current_generation(
            model=kwargs.get("model", "gpt-4"),
            input={"messages": messages, "evidence_count": kwargs.get("evidence_count", 0)},
            metadata={
                "purpose": "finalize_analysis",
                "evidence_length": len(evidence_text),
                "phase": "finalize"
            }
        )
    
    response = client.chat.completions.create(
        model=kwargs.get("model", "gpt-4"),
        messages=messages,
        **kwargs.get("llm_params", {})
    )
    
    result = response.choices[0].message.content
    
    if lf_client:
        lf_client.update_current_generation(
            output=result,
            usage_details={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )
    
    return result


@observe(as_type="generation", name="finalize-writer-llm")
def _finalize_writer_llm(evidence_text: str, sections_prompt: str, **kwargs) -> str:
    """LLM call for writing final report."""
    # Similar pattern as above
    pass
```

**Files to Modify**:
- `core/scope.py` - scope_request() function
- `core/graph.py` - finalize() helper LLM calls
- `core/llm_analyzer.py` - All LLM call functions

**Locations Needing @observe**:
1. `core/scope.py:scope_request()` - Strategy selection LLM
2. `core/graph.py:finalize()` - Analysis LLM call
3. `core/graph.py:finalize()` - Writer LLM call  
4. `core/llm_analyzer.py` - Any analysis functions
5. `core/graph.py:_cluster_llm()` - Already has @observe ✓
6. `core/graph.py:_refine_queries_with_llm()` - Already has @observe ✓

**Acceptance Criteria**:
- [ ] All LLM calls have @observe(as_type="generation")
- [ ] Prompts are captured in input
- [ ] Responses are captured in output
- [ ] Token usage is captured in usage_details
- [ ] Model name is specified
- [ ] Purpose/context is in metadata
- [ ] No duplicate tracing (avoid double-wrapping)
- [ ] Generations properly nest under parent spans

**Testing**:
```bash
python3 run_daily_briefing.py --topic "Tech news" --debug
# Verify all LLM calls appear as generations in Langfuse
# Check token counts are accurate
```

**Estimated Effort**: 8 hours

---

### Issue 4: Add Strategy Selection Tracing (observability for strategy matching)

**Goal**: Make strategy selection process visible with candidates and scoring

**Scope**: Add tracing to strategy selection logic in `strategies/__init__.py`

**Implementation Details**:

```python
# In strategies/__init__.py

@observe(as_type="span", name="strategy-selection")
def select_strategy(
    category: str,
    time_window: str,
    depth: str,
    user_request: str = ""
) -> str:
    """Select appropriate strategy based on request characteristics."""
    lf_client = get_langfuse_client()
    
    if lf_client:
        lf_client.update_current_span(
            input={
                "category": category,
                "time_window": time_window,
                "depth": depth,
                "user_request": user_request[:200]
            },
            metadata={
                "selection_criteria": {
                    "category": category,
                    "time_window": time_window,
                    "depth": depth
                }
            }
        )
    
    # Get all strategies
    all_strategies = get_all_strategies()
    
    # Score and rank
    candidates = []
    for slug, strategy in all_strategies.items():
        score = _calculate_match_score(strategy, category, time_window, depth)
        candidates.append({
            "slug": slug,
            "score": score,
            "category": strategy.category
        })
    
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[0]["slug"] if candidates else "default"
    
    if lf_client:
        lf_client.update_current_span(
            output={
                "selected_strategy": selected,
                "top_candidates": candidates[:5],  # Top 5
                "total_candidates": len(candidates)
            },
            metadata={
                "strategy_selected": selected,
                "match_score": candidates[0]["score"] if candidates else 0,
                "candidates_considered": len(candidates)
            }
        )
    
    return selected
```

**Files to Modify**:
- `strategies/__init__.py` - select_strategy() and related functions

**Acceptance Criteria**:
- [ ] Strategy selection creates a span
- [ ] Selection criteria (category, time_window, depth) captured
- [ ] All candidate strategies and scores captured (top 5)
- [ ] Selected strategy is in output
- [ ] Match score is captured
- [ ] Span properly nests under scope-phase

**Testing**:
```bash
python3 run_daily_briefing.py --topic "News from yesterday"
# Verify strategy-selection span appears under scope-phase
# Check candidates list shows alternatives considered
```

**Estimated Effort**: 4 hours

---

### Issue 5: Add Error Path Tracing and Progress Metadata

**Goal**: Capture errors with context and add progress tracking metadata

**Scope**: Add error handling to all traced operations and progress updates

**Implementation Details**:

**Error Tracing Pattern**:
```python
# In all workflow nodes and steps

try:
    # ... operation ...
    
except Exception as e:
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_span(
            output={"error": str(e), "error_type": type(e).__name__},
            metadata={
                "error_occurred": True,
                "error_type": type(e).__name__,
                "error_message": str(e)[:500]
            },
            level="ERROR"
        )
    raise
```

**Progress Tracking** (in api/main.py):
```python
# During batch execution

for idx, task in enumerate(tasks, 1):
    # ... task setup ...
    
    with workflow_span(...) as trace_ctx:
        # Update progress metadata
        trace_ctx.update_trace(
            metadata={
                **trace_ctx.span.metadata,
                "progress": {
                    "current_task": idx,
                    "total_tasks": len(tasks),
                    "percent_complete": int((idx / len(tasks)) * 100)
                }
            }
        )
        
        # ... execute research ...
```

**Files to Modify**:
- `core/graph.py` - Add try/except with error tracing to all nodes
- `api/main.py` - Add progress metadata updates
- All new spans/generations from Issues 1-4

**Acceptance Criteria**:
- [ ] All exceptions are caught and traced with ERROR level
- [ ] Error type and message are captured
- [ ] Stack trace context is available (via Langfuse error capture)
- [ ] Progress metadata shows current phase/step
- [ ] Progress percentage is calculated for batch operations
- [ ] No silent failures (all errors visible in traces)

**Testing**:
```bash
# Test error scenarios
python3 run_daily_briefing.py --topic "InvalidTest!!!" --debug
# Verify error is captured with details in Langfuse

# Test progress tracking
# Trigger batch with multiple tasks
# Verify progress metadata updates
```

**Estimated Effort**: 6 hours

---

## Summary

**Total Issues**: 5
**Total Estimated Effort**: 28 hours (~1 sprint)

**Priority Order**:
1. Issue 1: Workflow Node Tracing (4h) - CRITICAL
2. Issue 2: Research Step Tracing (6h) - CRITICAL  
3. Issue 3: LLM Call Tracing (8h) - HIGH
4. Issue 4: Strategy Selection Tracing (4h) - HIGH
5. Issue 5: Error & Progress Tracing (6h) - MEDIUM

**Expected Visibility Improvement**:
- After Issue 1+2: 80% visibility
- After Issue 3+4: 95% visibility
- After Issue 5: 100% visibility + error debugging

**Key Technical Decisions (Based on Langfuse v3 Docs)**:
1. Use `@observe(as_type="span")` for workflow phases and steps
2. Use `@observe(as_type="generation")` for all LLM calls
3. Use `lf_client.update_current_span()` / `update_current_generation()` for metadata
4. Use context managers (`with langfuse.start_as_current_span()`) for nested spans
5. Include `usage_details` for all LLM calls (token tracking)
6. Keep metadata keys alphanumeric, values ≤200 chars
7. Set trace-level input/output for end-to-end tracking
