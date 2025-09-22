# Debug Logging Guide

## Overview

The research workflow now includes comprehensive debug logging that captures:
- All workflow node executions with timings
- LLM prompts and responses
- Tool/API calls and results
- Decision points and branching logic
- Performance metrics
- Error traces

## Enabling Debug Logging

### Method 1: Environment Variables

Set any of these environment variables:
```bash
# Enable debug logging
export DEBUG_LOG=true
export WEB_RESEARCH_DEBUG=1

# Control verbosity
export DEBUG_LEVEL=INFO  # or DEBUG, WARNING, ERROR

# Save prompts/responses (default: true)
export DEBUG_SAVE_PROMPTS=true
export DEBUG_SAVE_RESPONSES=true

# Custom log directory (default: ./debug_logs)
export DEBUG_LOG_DIR=./my_debug_logs
```

### Method 2: Command Line

```bash
# Run with debug flag
python run_daily_briefing.py "artificial intelligence" --debug

# Debug mode is auto-enabled with verbose flag
python run_daily_briefing.py "AI news" --verbose
```

## Log Files

Debug logs are saved to `./debug_logs/` directory:

- `debug_YYYYMMDD_HHMMSS.jsonl` - Main event log (JSON Lines format)
- `summary_YYYYMMDD_HHMMSS.json` - Session summary with statistics

## Viewing Logs

### Interactive Viewer

```bash
# View latest log with summary
python debug_viewer.py

# View specific log
python debug_viewer.py debug_20250122_143025.jsonl

# Interactive mode
python debug_viewer.py --interactive

# Show only prompts
python debug_viewer.py --prompts

# Show only errors
python debug_viewer.py --errors

# Show execution timeline
python debug_viewer.py --timeline
```

### Export Prompts

```bash
# In interactive mode, choose option 6
# Or directly export from command line
python -c "from debug_viewer import DebugLogViewer; viewer = DebugLogViewer('./debug_logs/latest.jsonl'); viewer.export_prompts()"
```

## Log Event Types

### Node Events
- `node_start` - Workflow node begins execution
- `node_end` - Node completes (with timing and success status)

### LLM Events
- `llm_call` - Complete prompt, response, tokens, timing

### Tool Events
- `tool_call` - API calls with inputs, outputs, timing

### Decision Events
- `decision` - Branching logic with conditions and results

### Evidence Events
- `evidence_update` - Tracking evidence collection

### Strategy Events
- `strategy_selected` - Strategy selection with reasoning

## Example: Debugging a Failed Briefing

1. Run with debug enabled:
```bash
export DEBUG_LOG=true
python run_daily_briefing.py "quantum computing"
```

2. If it fails, check errors:
```bash
python debug_viewer.py --errors
```

3. Review the prompts that led to the error:
```bash
python debug_viewer.py --prompts
```

4. Check performance bottlenecks:
```bash
python debug_viewer.py --summary
```

## Performance Analysis

The summary view shows:
- Node execution times (total, average, max)
- Tool API call statistics
- LLM token usage and costs estimation
- Error rates by component

## Troubleshooting Workflow Issues

### Issue: Empty or Poor Quality Output

1. Check evidence collection:
```bash
grep "evidence_update" debug_logs/latest.jsonl | jq .
```

2. Review LLM prompts for truncation:
```bash
python debug_viewer.py --prompts | grep "truncated"
```

### Issue: Slow Performance

1. View node timings:
```bash
python debug_viewer.py --summary | grep -A10 "NODE PERFORMANCE"
```

2. Check API call durations:
```bash
grep "tool_call" debug_logs/latest.jsonl | jq '.duration_seconds' | sort -n
```

### Issue: Wrong Strategy Selected

1. Check scope decision:
```bash
grep "strategy_selected" debug_logs/latest.jsonl | jq .
```

2. Review categorization:
```bash
grep "scope.result" debug_logs/latest.jsonl | jq .
```

## Advanced Usage

### Custom Analysis Script

```python
import json
from pathlib import Path

# Load events
events = []
with open('./debug_logs/latest.jsonl', 'r') as f:
    for line in f:
        events.append(json.loads(line))

# Analyze LLM costs
total_tokens = 0
for event in events:
    if event['type'] == 'llm_call' and event.get('tokens'):
        total_tokens += event['tokens'].get('total_tokens', 0)

print(f"Total tokens used: {total_tokens}")
print(f"Estimated cost: ${total_tokens * 0.00001:.4f}")  # Adjust rate

# Find slowest tool calls
tool_times = []
for event in events:
    if event['type'] == 'tool_call' and event.get('duration_seconds'):
        tool_times.append((event['provider'], event['method'], event['duration_seconds']))

tool_times.sort(key=lambda x: x[2], reverse=True)
print("\nSlowest tool calls:")
for provider, method, duration in tool_times[:5]:
    print(f"  {provider}.{method}: {duration:.3f}s")
```

### Monitoring with grep/jq

```bash
# Watch for errors in real-time
tail -f debug_logs/latest.jsonl | jq 'select(.error != null)'

# Count events by type
cat debug_logs/latest.jsonl | jq -r .type | sort | uniq -c

# Extract all prompts to file
cat debug_logs/latest.jsonl | jq -r 'select(.type == "llm_call") | .prompt' > prompts.txt
```

## Privacy & Security

- API keys and secrets are automatically redacted
- Prompts/responses can be disabled via environment variables
- Logs are stored locally only
- Consider adding `.gitignore` entry for `debug_logs/`

## Integration with Other Tools

### Langfuse Integration
Debug logs complement Langfuse tracing. Use both for complete observability:
- Langfuse: Production monitoring, cost tracking
- Debug logs: Development troubleshooting, prompt engineering

### Custom Hooks
Add your own logging in strategy files:
```python
from core.enhanced_debug import enhanced_logger as elog

# In your custom code
elog.decision("custom_logic", "condition > threshold", result=True, context={"value": 42})
```

## Best Practices

1. **Enable debug logging during development** to catch issues early
2. **Review summaries after each run** to spot performance degradation  
3. **Export prompts regularly** for prompt engineering improvements
4. **Archive important debug logs** for regression testing
5. **Disable response logging in production** to save space

## Troubleshooting the Logger

If logs aren't being created:
1. Check environment variables: `env | grep DEBUG`
2. Verify directory permissions: `ls -la ./debug_logs`
3. Check Python imports: `python -c "from core.enhanced_debug import enhanced_logger"`
4. Look for errors in stderr: `python run_daily_briefing.py 2>&1 | grep DEBUG`