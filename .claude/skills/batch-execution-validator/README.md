# Batch Execution Validator

End-to-end validation skill for production batch execution pipeline.

## Quick Start

```bash
cd .claude/skills/batch-execution-validator/helpers

# Step 1: Trigger batch execution
python3 api_client.py \
  --api-url https://your-api.com \
  --frequency daily \
  --wait 180

# Step 2: Fetch and analyze traces
python3 trace_fetcher.py \
  --from-timestamp "2025-11-07T14:30:00Z" \
  --tags batch_execution daily \
  --session-ids "task-id-1,task-id-2,task-id-3" \
  --output /tmp/batch_validation_results.json
```

## What It Does

1. **Triggers** batch execution for daily frequency via production API
2. **Waits** for execution to complete (default: 3 minutes)
3. **Fetches** traces from Langfuse using advanced filters
4. **Analyzes** architecture (node coverage, errors, metadata)
5. **Assesses** quality (sections, citations, content, performance)
6. **Reports** findings with pass/fail status and recommendations

## Required Environment Variables

```bash
export API_SECRET_KEY="your-api-secret-key"
export LANGFUSE_PUBLIC_KEY="your-langfuse-public-key"
export LANGFUSE_SECRET_KEY="your-langfuse-secret-key"
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

## Architecture Validation

**Checks:**
- ✓ Expected nodes present (router, research, write, edit)
- ✓ Trace metadata complete (task_id, frequency, callback_url)
- ✓ Correct trace hierarchy and observation linking
- ✓ No ERROR level observations
- ✓ Tags present (batch_execution, frequency)

**Status:**
- **PASS**: All checks passed
- **WARNING**: Minor issues (missing optional metadata)
- **FAIL**: Critical issues (missing nodes, errors)

## Quality Assessment

**Checks:**
- ✓ Sections: 2+ sections with substantive content (>100 words)
- ✓ Citations: 3-10 citations with title, url, snippet
- ✓ Performance: Total latency < 90s
- ✓ No placeholder text or empty fields

**Status:**
- **HIGH**: 3+ sections, 5-10 citations, >150 words/section, <60s latency
- **MEDIUM**: 2-3 sections, 3-5 citations, >100 words/section, <90s latency
- **LOW**: Incomplete sections, few citations, thin content, slow

## Output Format

```json
{
  "execution_metadata": {
    "analyzed_at": "2025-11-07T14:33:00Z",
    "from_timestamp": "2025-11-07T14:30:00Z",
    "tags": ["batch_execution", "daily"]
  },
  "traces": [
    {
      "trace_id": "abc-123",
      "user_id": "test@example.com",
      "architecture": {
        "status": "PASS",
        "nodes_found": ["router", "research", "write", "edit"],
        "errors": []
      },
      "quality": {
        "status": "HIGH",
        "sections_count": 4,
        "citations_count": 7,
        "total_latency_ms": 48200
      }
    }
  ],
  "summary": {
    "total_traces": 5,
    "architecture_pass": 5,
    "quality_high": 4,
    "quality_medium": 1
  },
  "recommendations": [
    "✓ All traces passed architecture validation",
    "✓ Quality is consistently high (4/5 HIGH)"
  ]
}
```

## Common Usage Patterns

### Test After Deployment

```bash
# Validate system health after changes
python3 api_client.py --api-url https://api.com --frequency daily --wait 180
python3 trace_fetcher.py --from-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --tags batch_execution daily --output /tmp/validation.json
```

### Debug Specific Tasks

```bash
# Analyze specific task IDs
python3 trace_fetcher.py \
  --session-ids "failing-task-id-1,failing-task-id-2" \
  --tags batch_execution \
  --output /tmp/debug_results.json
```

### Monitor Recent Runs

```bash
# Check last 10 daily batch executions
python3 trace_fetcher.py \
  --tags batch_execution daily \
  --limit 10 \
  --output /tmp/recent_runs.json
```

## Interpreting Results

### All Green (PASS + HIGH)
- System is healthy
- Ready for optimization
- Continue with normal operations

### Architecture Issues (FAIL)
- Missing nodes: Check LangGraph execution
- ERROR observations: Review logs for failures
- Missing metadata: Validate API payload and tracing setup

### Quality Issues (LOW)
- Few citations: Research node may be failing
- Thin content: Write node needs prompt tuning
- Slow performance: Identify bottleneck node

## Troubleshooting

**No tasks found:**
- Create test subscriptions: `POST /tasks` with frequency="daily"
- Verify active: `GET /tasks?email=test@example.com`

**No traces retrieved:**
- Increase wait time (may need >3min)
- Check Langfuse credentials
- Verify API execution succeeded

**Quality always LOW:**
- Check research node returns evidence
- Validate write node prompts
- Review LLM responses in traces

## Next Steps

1. **After validation PASS**: Use `langfuse-optimization` skill for tuning
2. **After architecture FAIL**: Fix tracing and node execution
3. **After quality LOW**: Tune prompts and optimize nodes

## Files

- `SKILL.md` - Full skill documentation
- `README.md` - This quick reference
- `helpers/api_client.py` - Trigger batch execution
- `helpers/trace_fetcher.py` - Fetch and analyze traces

## See Also

- `langfuse-advanced-filters` - Advanced trace querying
- `langfuse-optimization` - Config optimization based on traces
- `langfuse-feedback-analyst` - Analyze user feedback from annotation queues
