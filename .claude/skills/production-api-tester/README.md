# Production API Tester Skill

Live testing skill for the production research API. Enables optimization loops for strategy development.

## Quick Start

### 1. Set Environment Variables

```bash
# Production API (required)
export PROD_API_KEY="your_api_key_here"

# Optional: Override API URL
export PROD_API_URL="https://webresearchagent.replit.app"  # default

# Webhook receiver (for getting results)
export CALLBACK_URL="https://webhook.site/your-unique-url"
```

### 2. Create Test Task

```bash
cd /home/user/web_research_agent/.claude/skills/production-api-tester/helpers

python3 create_test_task.py \
  --api-key "$PROD_API_KEY" \
  --email "test@example.com" \
  --topic "AI developments in healthcare" \
  --frequency "daily" \
  --output /tmp/api_test/task.json
```

### 3. Execute Research

```bash
python3 execute_batch.py \
  --api-key "$PROD_API_KEY" \
  --frequency "daily" \
  --callback-url "$CALLBACK_URL"
```

### 4. Link to Langfuse

```bash
# Get task ID from step 2
TASK_ID=$(jq -r '.id' /tmp/api_test/task.json)

# Find Langfuse trace
python3 link_to_langfuse.py \
  --task-id "$TASK_ID" \
  --email "test@example.com" \
  --output /tmp/api_test/langfuse.json

# View trace ID
cat /tmp/api_test/langfuse.json
```

### 5. Cleanup

```bash
python3 delete_task.py \
  --api-key "$PROD_API_KEY" \
  --task-id "$TASK_ID"
```

## Helper Scripts

### create_test_task.py
Creates a research task subscription.

```bash
python3 create_test_task.py \
  --api-key "$PROD_API_KEY" \
  --email "test@example.com" \
  --topic "Research topic" \
  --frequency daily|weekly|monthly \
  [--schedule-time "09:00"] \
  --output /tmp/task.json
```

### execute_batch.py
Triggers batch execution for a frequency.

```bash
python3 execute_batch.py \
  --api-key "$PROD_API_KEY" \
  --frequency daily|weekly|monthly \
  --callback-url "https://webhook.site/..." \
  --output /tmp/execution.json
```

### link_to_langfuse.py
Finds Langfuse trace for task execution.

```bash
python3 link_to_langfuse.py \
  --task-id "abc123" \
  --email "test@example.com" \
  [--time-range last_1_hour|last_1_day] \
  [--topic "Research topic"] \
  --output /tmp/langfuse.json
```

### health_check.py
Checks API health status.

```bash
# Single check
python3 health_check.py

# Continuous monitoring
python3 health_check.py --continuous --interval 60 --duration 3600
```

### delete_task.py
Deletes a research task.

```bash
python3 delete_task.py \
  --api-key "$PROD_API_KEY" \
  --task-id "abc123"
```

## Optimization Loop Workflow

Complete workflow combining strategy-builder, production-api-tester, and langfuse skills:

```bash
# 1. Generate strategy (strategy-builder)
python3 ../../strategy-builder/helpers/generate_strategy.py \
  --slug "legal/court_cases_de" \
  --category "legal" \
  --time-window "month" \
  --depth "comprehensive" \
  --output /tmp/loop/strategy.yaml

# 2. Validate strategy (strategy-builder)
python3 ../../strategy-builder/helpers/validate_strategy.py \
  --strategy /tmp/loop/strategy.yaml

# 3. Deploy strategy to database
# (Manual: copy to strategies/, add to index.yaml, migrate)

# 4. Create test task (production-api-tester)
python3 create_test_task.py \
  --api-key "$PROD_API_KEY" \
  --email "legal-test@example.com" \
  --topic "Datenschutz DSGVO" \
  --frequency "daily" \
  --output /tmp/loop/task.json

# 5. Execute (production-api-tester)
TASK_ID=$(jq -r '.id' /tmp/loop/task.json)
python3 execute_batch.py \
  --api-key "$PROD_API_KEY" \
  --frequency "daily" \
  --callback-url "$CALLBACK_URL"

# 6. Wait 2-5 minutes for execution to complete

# 7. Link to Langfuse (production-api-tester)
python3 link_to_langfuse.py \
  --task-id "$TASK_ID" \
  --email "legal-test@example.com" \
  --time-range "last_1_hour" \
  --output /tmp/loop/langfuse.json

# 8. Retrieve trace (langfuse-optimization)
TRACE_ID=$(jq -r '.latest_trace_id' /tmp/loop/langfuse.json)
python3 ../../langfuse-optimization/helpers/retrieve_single_trace.py \
  "$TRACE_ID" \
  --filter-essential \
  --output /tmp/loop/trace.json

# 9. Analyze performance (strategy-builder)
python3 ../../strategy-builder/helpers/analyze_strategy_performance.py \
  --traces /tmp/loop/trace.json \
  --strategy "legal/court_cases_de" \
  --output /tmp/loop/performance.json

# 10. Review recommendations
cat /tmp/loop/performance.json

# 11. Cleanup (production-api-tester)
python3 delete_task.py --api-key "$PROD_API_KEY" --task-id "$TASK_ID"

# 12. Iterate: Apply fixes and repeat from step 1
```

## Webhook Setup

### Option 1: webhook.site (Easiest)

1. Go to https://webhook.site
2. Copy your unique URL
3. Use as `CALLBACK_URL`
4. View results in browser

### Option 2: Langdock Webhook

Use Langdock's webhook receiver action (07_webhook_receiver.js)

### Option 3: Local Webhook (Future)

Run local webhook receiver:
```bash
# Future helper script
python3 webhook_receiver.py --port 8080
export CALLBACK_URL="http://your-public-ip:8080/webhook"
```

## Tips

1. **Use unique test emails**: `test-{strategy}@example.com`
2. **Clean up after testing**: Always delete test tasks
3. **Wait for completion**: Research takes 30s-5min depending on strategy
4. **Check Langfuse timing**: Traces appear 30-60s after completion
5. **Use tags in topics**: `"[TEST] AI news - v2_iteration_3"` for easy filtering

## Troubleshooting

**"Authentication failed"**:
- Verify `PROD_API_KEY` is correct
- Check API key is active

**"No webhook results"**:
- Verify `CALLBACK_URL` is publicly accessible
- Wait 2-5 minutes for execution
- Check webhook.site or webhook receiver logs

**"No Langfuse trace found"**:
- Wait 30-60 seconds after execution completes
- Try wider time range: `--time-range last_1_day`
- Verify email matches exactly

## Related Skills

- **strategy-builder**: Generate and analyze strategies
- **langfuse-optimization**: Deep dive into trace data
- **langfuse-advanced-filters**: Advanced trace filtering

## Environment

Required environment variables:
```bash
# Production API
export PROD_API_KEY="your_key"              # Required
export PROD_API_URL="https://..."           # Optional (has default)
export CALLBACK_URL="https://webhook..."    # Required for execute_batch

# Langfuse (for link_to_langfuse.py)
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

## Examples

See `SKILL.md` for detailed examples of:
- Single strategy testing
- Full optimization loop
- Batch testing multiple strategies
- Health monitoring
