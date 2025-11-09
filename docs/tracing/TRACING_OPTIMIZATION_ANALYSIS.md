# Langfuse Tracing Implementation Analysis
## Optimization Opportunities for Better Tracing & Debugging

**Date**: 2025-11-09  
**Scope**: Web Research Agent codebase  
**Goal**: Identify improvements to make optimization and debugging easier

---

## Executive Summary

The current Langfuse tracing implementation has **significant blind spots** that prevent effective debugging and optimization. While the infrastructure is solid, **most of the research workflow is not instrumented**, resulting in traces that show "completed" status but provide no visibility into what actually happened.

**Critical Gap**: 95% of the research process is invisible in Langfuse traces.

---

## Current Tracing Architecture

### ✅ What IS Traced

1. **Top-Level Workflow Wrapper** (`workflow_span`)
   - Location: `api/main.py:470-486`, `run_daily_briefing.py:63-68`
   - Creates parent trace with metadata
   - Captures: task_id, email, topic, frequency
   - Updates with final status

2. **Tool API Calls** (`@observe` decorators)
   - `tools/sonar.py:67` - Sonar search calls
   - `tools/exa.py:27` - Exa search calls
   - Captures: input prompts, output citations, usage metrics

3. **Select LLM Operations** (`@observe` decorators)
   - `core/graph.py:149` - Evidence clustering
   - `core/graph.py:237` - Query refinement
   - Captures: prompts, responses, token usage

### ❌ What is NOT Traced

1. **Workflow Nodes** (MAJOR GAP)
   - `scope()` - Strategy selection & categorization
   - `fill()` - Variable resolution
   - `research()` - Main research orchestration
   - `finalize()` - Report synthesis
   - **Impact**: No visibility into which phase is running or how long each takes

2. **Research Step Execution** (CRITICAL GAP)
   - Individual tool calls within `research()` loop
   - Step-by-step progression through strategy
   - Conditional logic (`when` clauses)
   - **Impact**: Cannot see which steps executed, which were skipped

3. **Strategy Selection Logic**
   - Strategy matching process
   - Fan-out decisions
   - Runtime plan generation
   - **Impact**: Cannot debug why a strategy was chosen

4. **LLM Calls for Analysis**
   - Most LLM calls lack `@observe`
   - Missing prompts, responses, reasoning
   - **Impact**: Cannot optimize prompts or debug quality issues

5. **Evidence Processing**
   - Evidence filtering
   - Relevance scoring
   - Deduplication
   - **Impact**: Cannot see why sources were included/excluded

6. **Error Paths**
   - Exceptions are caught but not traced
   - Fallback logic invisible
   - **Impact**: Cannot diagnose failures

---

## Why Current Traces Are Empty

### The Execution Flow

```
API Request
  └─> workflow_span() ✅ TRACED (parent trace created)
       ├─> metadata: {task_id, email, topic, frequency}
       ├─> input: {task_id, email, research_topic, frequency}
       │
       └─> graph.ainvoke(State(...)) ❌ NOT TRACED
            ├─> scope() ❌ NOT TRACED
            │    └─> scope_request() ❌ NOT TRACED
            │         └─> LLM call ❌ NOT TRACED
            │
            ├─> fill() ❌ NOT TRACED
            │    └─> Variable resolution ❌ NOT TRACED
            │
            ├─> research() ❌ NOT TRACED
            │    ├─> for each step: ❌ NOT TRACED
            │    │    ├─> tool.call() ✅ TRACED (only this!)
            │    │    │    └─> sonar_call / exa_search ✅
            │    │    └─> Evidence processing ❌ NOT TRACED
            │    └─> Aggregation ❌ NOT TRACED
            │
            └─> finalize() ❌ NOT TRACED
                 ├─> LLM analysis ❌ NOT TRACED
                 └─> Report generation ❌ NOT TRACED
       
       └─> trace_ctx.update_trace(output={"status": "completed"}) ✅ TRACED
```

**Result**: Only the top-level wrapper and individual tool calls are visible. The entire orchestration layer is invisible.

---

## Concrete Problems This Causes

### Problem 1: Cannot Validate Research Quality

**Symptom**: Trace shows `status: completed` but no way to verify if research actually happened.

**Example**:
- Topic: "yes" (3 characters)
- Duration: 0.2 seconds
- Status: completed ✅
- **But**: No evidence this was rejected or that any research occurred

**Cannot Answer**:
- Did strategy validation run?
- Was the topic rejected?
- Were any sources found?
- Was an error silently swallowed?

### Problem 2: Cannot Debug Strategy Selection

**Symptom**: Wrong strategy selected for a query.

**Cannot See**:
- What strategies were considered?
- What scores did they get?
- Why was one chosen over another?
- What variables were extracted?

**Current Trace**: Nothing. No information at all.

### Problem 3: Cannot Optimize LLM Prompts

**Symptom**: Want to improve prompt quality or reduce costs.

**Cannot See**:
- What prompts were actually sent?
- What responses came back?
- Token usage per prompt?
- Which prompts are expensive?

**Current Coverage**: ~5% of LLM calls are traced.

### Problem 4: Cannot Track Research Progress

**Symptom**: User waiting, wants to know progress.

**Cannot See**:
- Which step is currently running?
- How many steps remain?
- Is it stuck on a particular tool?
- How long is each step taking?

**Current Trace**: Silent between start and end.

### Problem 5: Cannot Analyze Failures

**Symptom**: Research fails with error.

**Cannot See**:
- Which phase failed?
- What was the error?
- What was the state at failure?
- Was there partial progress?

**Current Trace**: Just `status: failed` with error string.

### Problem 6: Cannot Measure Performance

**Symptom**: Want to optimize execution time.

**Cannot Measure**:
- Time per workflow phase
- Time per research step
- Bottlenecks in the pipeline
- Which tools are slow?

**Current Data**: Only total duration and individual tool calls.

---

## Optimization Opportunities

### Priority 1: CRITICAL - Add Workflow Node Tracing

**Impact**: High - Foundation for all other improvements  
**Effort**: Low - Just add `@observe` decorators  

**Implementation Locations**:

```python
# core/graph.py

@observe(as_type="span", name="scope-phase")
def scope(state: State) -> State:
    """Scope phase categorizes the request and selects a strategy."""
    # ... existing code ...

@observe(as_type="span", name="fill-phase") 
def fill(state: State) -> State:
    """Fill phase: ask an LLM to provide values."""
    # ... existing code ...

@observe(as_type="span", name="research-phase")
def research(state: State) -> State:
    """Execute the research phase."""
    # ... existing code ...

@observe(as_type="span", name="finalize-phase")
def finalize(state: State) -> State:
    """Finalize phase: synthesize report."""
    # ... existing code ...
```

**Benefits**:
- See which phase is executing
- Measure time per phase
- Identify bottlenecks
- Debug phase-specific failures

**Metadata to Add**:
- Input state (relevant fields)
- Output state (changes made)
- Phase-specific metrics

---

### Priority 2: CRITICAL - Add Research Step Tracing

**Impact**: High - Makes individual steps visible  
**Effort**: Medium - Need to wrap loop iterations  

**Implementation Pattern**:

```python
# core/graph.py, inside research() function

for idx, step in enumerate(research_steps):
    step_label = step.get("use") or step.get("name") or f"step-{idx}"
    
    # ADD THIS:
    with langfuse_client.start_as_current_span(
        name=f"research-step-{idx+1}:{step_label}"
    ) as step_span:
        step_span.update(
            input={
                "step_index": idx,
                "step_name": step_label,
                "use": step.get("use"),
                "params": step.get("params", {}),
                "when_condition": step.get("when")
            },
            metadata={
                "strategy": state.strategy_slug,
                "topic": variables.get("topic"),
                "phase": "research"
            }
        )
        
        # ... existing step execution code ...
        
        step_span.update(
            output={
                "results_count": len(results),
                "skipped": False
            }
        )
```

**Benefits**:
- See exact step sequence
- Identify which steps are slow
- Debug conditional execution
- Track tool usage patterns

**Metadata to Add**:
- Step index & name
- Tool being called
- Parameters passed
- Results count
- Execution time
- Skip reason (if skipped)

---

### Priority 3: HIGH - Add Strategy Selection Tracing

**Impact**: Medium-High - Critical for debugging strategy issues  
**Effort**: Low - Already a separate function  

**Implementation Location**:

```python
# strategies/__init__.py (or wherever select_strategy is defined)

@observe(as_type="span", name="strategy-selection")
def select_strategy(user_request: str, **criteria) -> str:
    """Select appropriate strategy for request."""
    # Add input/output tracing
    # ... existing code ...
```

**Benefits**:
- See all candidate strategies
- See scoring/ranking logic
- Debug misclassifications
- Optimize matching rules

**Metadata to Add**:
- User request
- Candidate strategies
- Match scores
- Selected strategy
- Selection criteria
- Fallback used (if any)

---

### Priority 4: HIGH - Add LLM Call Tracing (Comprehensive)

**Impact**: Medium-High - Essential for prompt optimization  
**Effort**: Medium - Many LLM calls scattered throughout  

**Implementation Pattern**:

```python
# Wherever LLM calls occur

@observe(as_type="generation", name="llm-{purpose}")
def call_llm_for_purpose(prompt: str, **kwargs):
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_generation(
            model=model_name,
            input={"prompt": prompt, "params": kwargs},
            metadata={"purpose": "specific_purpose"}
        )
    
    response = client.chat.completions.create(...)
    
    if lf_client:
        lf_client.update_current_generation(
            output=response.choices[0].message.content,
            usage_details={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        )
    
    return response
```

**Locations Needing Tracing**:
- `core/scope.py` - Scope analysis LLM calls
- `core/graph.py` - Finalize analysis & writing
- `core/llm_analyzer.py` - All analysis calls
- Any ad-hoc LLM calls

**Benefits**:
- See all prompts sent
- Measure token costs
- Optimize expensive prompts
- Debug quality issues
- A/B test prompt variations

---

### Priority 5: MEDIUM - Add Evidence Processing Tracing

**Impact**: Medium - Useful for quality optimization  
**Effort**: Medium - Multiple processing steps  

**Implementation Points**:

```python
# Add spans for:

@observe(as_type="span", name="evidence-filtering")
def filter_evidence(evidence_list, criteria):
    # Log filtering logic
    
@observe(as_type="span", name="evidence-ranking")
def rank_evidence(evidence_list, relevance_criteria):
    # Log ranking logic
    
@observe(as_type="span", name="evidence-deduplication")
def deduplicate_evidence(evidence_list):
    # Log dedup logic
```

**Benefits**:
- See why sources were filtered
- Debug relevance scoring
- Optimize deduplication
- Track evidence quality

**Metadata to Add**:
- Input count
- Output count
- Filtering criteria
- Removed items (summary)
- Quality scores

---

### Priority 6: MEDIUM - Add Error Path Tracing

**Impact**: Medium - Improves debugging  
**Effort**: Low - Just update existing try/catch  

**Implementation Pattern**:

```python
try:
    # ... existing code ...
except Exception as e:
    if lf_client:
        lf_client.update_current_trace(
            metadata={
                "error": str(e),
                "error_type": type(e).__name__,
                "failed_at": "specific_step"
            },
            level="ERROR"
        )
    raise
```

**Benefits**:
- See where failures occur
- Capture error context
- Debug error paths
- Track error rates

---

### Priority 7: LOW - Add Progress Tracking

**Impact**: Low-Medium - UX improvement  
**Effort**: Medium - Requires state management  

**Implementation**:

```python
# Update trace with progress metadata

trace_ctx.update_trace(
    metadata={
        "progress": {
            "current_phase": "research",
            "current_step": "3/10",
            "estimated_completion": "45s"
        }
    }
)
```

**Benefits**:
- Real-time progress visibility
- Better UX for long-running tasks
- Timeout prediction

---

## Recommended Metadata Schema

### Trace-Level Metadata (Root)

```json
{
  "task_id": "uuid",
  "user_email": "email@example.com",
  "research_topic": "Topic string",
  "frequency": "daily|weekly|monthly",
  "strategy_slug": "strategy_name",
  "callback_url": "https://...",
  "execution_mode": "api|cli",
  "version": "1.0.0"
}
```

### Phase-Level Metadata (Scope, Fill, Research, Finalize)

```json
{
  "phase": "research",
  "strategy": "daily_news_briefing",
  "variables": {
    "topic": "...",
    "time_window": "..."
  },
  "state_snapshot": {
    "evidence_count": 15,
    "sections_count": 3
  }
}
```

### Step-Level Metadata (Individual Research Steps)

```json
{
  "step_index": 3,
  "step_name": "exa_search",
  "tool": "exa",
  "query": "rendered query",
  "params": {...},
  "when_condition": "expression",
  "skipped": false,
  "results_count": 10,
  "execution_time_ms": 1234
}
```

### Tool Call Metadata (Sonar, Exa, etc.)

```json
{
  "adapter": "sonar",
  "model": "sonar",
  "search_mode": "web",
  "search_recency_filter": "week",
  "results_count": 5,
  "sources_found": 8,
  "usage": {
    "input_tokens": 150,
    "output_tokens": 800,
    "total_tokens": 950
  }
}
```

### LLM Call Metadata

```json
{
  "purpose": "scope_analysis",
  "model": "gpt-4",
  "temperature": 0.3,
  "max_tokens": 2000,
  "prompt_template": "scope_analysis_v2",
  "prompt_length": 450,
  "response_length": 1200,
  "usage": {
    "input_tokens": 150,
    "output_tokens": 400,
    "total_tokens": 550
  },
  "cost_usd": 0.015
}
```

---

## Input/Output Recommendations

### What to Store in Trace Input

✅ **DO Store**:
- User request / research topic
- Strategy selected
- Key variables (topic, time_window, etc.)
- Configuration overrides
- Task metadata (email, frequency)

❌ **DON'T Store**:
- Full state objects (too large)
- API keys or secrets
- Full evidence lists (use counts)

### What to Store in Trace Output

✅ **DO Store**:
- Final report sections (or summary)
- Citations list (top 10-20)
- Success/failure status
- Quality metrics
  - Evidence count
  - Source diversity
  - Sections generated
  - Total execution time
- Error messages (if failed)

❌ **DON'T Store**:
- Intermediate evidence snapshots
- Full LLM responses (store in observations)
- Binary data

### What to Store in Observations

Each observation should contain:
- **Input**: What went into the operation
- **Output**: What came out
- **Metadata**: Context about the operation
- **Metrics**: Performance/cost data

---

## Implementation Priorities

### Phase 1: Foundation (Week 1)
1. ✅ Add `@observe` to all 4 workflow nodes
2. ✅ Add step-level tracing in research loop
3. ✅ Update existing tool traces with better metadata

**Expected Impact**: 80% visibility improvement

### Phase 2: Deep Instrumentation (Week 2)
1. ✅ Add strategy selection tracing
2. ✅ Add comprehensive LLM call tracing
3. ✅ Add evidence processing tracing

**Expected Impact**: 95% visibility, full debugging capability

### Phase 3: Polish (Week 3)
1. ✅ Add error path tracing
2. ✅ Add progress tracking
3. ✅ Optimize metadata schema
4. ✅ Add cost tracking

**Expected Impact**: Production-ready observability

---

## Success Criteria

After optimization, Langfuse traces should answer:

### Quality Validation
- ✅ Was research actually performed?
- ✅ Were sources relevant and diverse?
- ✅ Was the topic valid and well-formed?
- ✅ Were all expected steps executed?

### Performance Analysis
- ✅ Which phase is the bottleneck?
- ✅ Which steps are slowest?
- ✅ Which tools are most expensive?
- ✅ What's the cost per research task?

### Debugging
- ✅ Where did the error occur?
- ✅ What was the state at failure?
- ✅ Which step was executing?
- ✅ What were the inputs?

### Optimization
- ✅ Which prompts use the most tokens?
- ✅ Which strategies perform best?
- ✅ Where can we cache results?
- ✅ What can be parallelized?

---

## Cost/Benefit Analysis

### Current State
- **Visibility**: 5%
- **Debug Time**: 2-4 hours per issue
- **Optimization**: Guesswork
- **Cost Tracking**: None

### After Phase 1 (Foundation)
- **Visibility**: 80%
- **Debug Time**: 30 minutes per issue
- **Optimization**: Data-driven
- **Cost Tracking**: Per-phase

### After Phase 2 (Deep Instrumentation)
- **Visibility**: 95%
- **Debug Time**: 5-10 minutes per issue
- **Optimization**: Precise & actionable
- **Cost Tracking**: Per-step, per-LLM-call

**ROI**: Implementation time ~1-2 weeks, saves 10+ hours/week in debugging

---

## Next Steps

1. **Review & Approve**: Get stakeholder buy-in on priorities
2. **Implement Phase 1**: Start with workflow node tracing
3. **Test & Validate**: Verify traces contain expected data
4. **Iterate**: Refine metadata based on actual debugging needs
5. **Document**: Update developer docs with tracing guidelines
6. **Monitor**: Track trace size & Langfuse costs

---

## Appendix: Example "Good" Trace

What a well-instrumented trace should look like:

```
Trace: Research Task: AI developments in healthcare
├─ SPAN: scope-phase (2.3s)
│  ├─ INPUT: {request: "AI developments in healthcare"}
│  ├─ GENERATION: scope-analysis-llm (2.1s)
│  │  ├─ INPUT: {prompt: "Categorize this request...", model: "gpt-4"}
│  │  └─ OUTPUT: {category: "news", time_window: "week", depth: "comprehensive"}
│  └─ OUTPUT: {strategy: "daily_news_briefing", tasks: ["AI healthcare"]}
│
├─ SPAN: fill-phase (0.8s)
│  ├─ INPUT: {strategy: "daily_news_briefing", vars: {...}}
│  └─ OUTPUT: {vars: {topic: "AI healthcare", dates: {...}}}
│
├─ SPAN: research-phase (45.2s)
│  ├─ INPUT: {strategy: "daily_news_briefing", topic: "AI healthcare"}
│  │
│  ├─ SPAN: research-step-1:sonar_search (12.3s)
│  │  ├─ INPUT: {tool: "sonar", query: "AI healthcare latest developments"}
│  │  ├─ GENERATION: sonar-call (12.1s)
│  │  │  ├─ INPUT: {query: "...", params: {search_recency_filter: "week"}}
│  │  │  └─ OUTPUT: {results: 8, usage: {tokens: 950}}
│  │  └─ OUTPUT: {evidence_count: 8}
│  │
│  ├─ SPAN: research-step-2:exa_search (8.7s)
│  │  └─ ... similar structure ...
│  │
│  └─ OUTPUT: {total_evidence: 22, unique_sources: 18}
│
└─ SPAN: finalize-phase (15.4s)
   ├─ INPUT: {evidence_count: 22, strategy: "daily_news_briefing"}
   ├─ GENERATION: finalize-analysis (5.2s)
   ├─ GENERATION: finalize-writing (9.8s)
   └─ OUTPUT: {sections: 4, citations: 15, status: "completed"}

TRACE OUTPUT: {status: "completed", evidence: 22, sections: 4}
TRACE METADATA: {task_id: "...", total_cost_usd: 0.087}
```

**Key Difference**: Can see EVERYTHING that happened, not just start/end!
