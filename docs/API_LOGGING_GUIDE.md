# API Production Logging Guide

## Summary of Changes

Comprehensive logging has been added to the Research Agent API to debug production issues.

## What Was Added

### 1. Startup Logging (`api/main.py`)

**On API startup, you'll now see:**
```
🔑 API Key loaded: 60b8a838... (length: 64)
✅ DATABASE_URL: postgres:... (length: 120)
✅ PERPLEXITY_API_KEY: pplx-abc... (length: 56)
✅ EXA_API_KEY: exa-def... (length: 48)
✅ OPENAI_API_KEY: sk-proj-... (length: 89)
⚠️ LANGFUSE_SECRET_KEY: NOT SET  # If missing
```

**What to check:**
- ✅ All API keys should show `✅` with partial values
- ❌ Any `⚠️ NOT SET` means environment variables are missing

---

### 2. Batch Execution Request Logging

**When `/execute/batch` is called:**
```
📥 Batch execution request received: frequency=daily
📞 Callback URL: https://app.langdock.com/api/hooks/workflows/...
🔍 Found 2 tasks for frequency 'daily'
  - Task 8244fdb6-...: m.bruhn@faz.de - AI research updates
  - Task abc123-...: test@example.com - Market analysis
🚀 Starting background execution for 2 tasks
```

**What to check:**
- If you see `Found 0 tasks` → No active tasks in database for that frequency
- If tasks are found but background doesn't start → Check next section

---

### 3. Background Task Execution Logging

**This is the critical part that was failing silently before:**

```
============================================================
🎯 BACKGROUND TASK STARTED: Processing 2 tasks
============================================================

📦 Importing research modules...
✅ Imports successful
🔧 Registering default adapters...
✅ Adapters registered
🏗️ Building research graph...
✅ Graph built successfully

[1/2] 🔬 Processing task 8244fdb6-...
  Email: m.bruhn@faz.de
  Topic: AI research updates
  🚀 Invoking research graph...
  ✅ Research completed
  📊 Sections: 4, Evidence: 12
  📤 Sending webhook to: https://app.langdock.com/...
  ✅ Webhook sent successfully
  ✅ Database updated (last_run_at)

[2/2] 🔬 Processing task abc123-...
  ...

============================================================
✅ BATCH EXECUTION COMPLETE: 2 tasks processed
============================================================
```

**What to check:**

| Log Message | What It Means | If Missing/Error |
|-------------|---------------|------------------|
| `📦 Importing research modules...` | Loading core research code | **CRITICAL**: Environment may not have research code installed |
| `✅ Imports successful` | All modules loaded | If shows error → Missing dependencies or wrong Python path |
| `🔧 Registering default adapters...` | Setting up API tools | If fails → API keys for Perplexity/Exa not loaded |
| `🏗️ Building research graph...` | Creating LangGraph workflow | If fails → Configuration issue in graph definition |
| `🚀 Invoking research graph...` | Running actual research | This is the longest step (2-5 min) |
| `✅ Research completed` | Research succeeded | If timeout/error → Check tool API limits/errors |
| `📤 Sending webhook...` | Calling Langdock | Check webhook URL is correct |
| `✅ Webhook sent successfully` | Langdock received payload | If fails → Check webhook logs below |

---

### 4. Webhook Delivery Logging

```
📤 Sending webhook for task 8244fdb6-...
   URL: https://app.langdock.com/api/hooks/workflows/48cfee5a-...
   Payload size: 2847 chars
   Attempt 1/3...
   Response status: 200
   Response body: {"success":true,"message":"Workflow triggered"}
✅ Webhook delivered successfully for task 8244fdb6-...
```

**Common webhook errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `HTTP error: 404` | Webhook URL doesn't exist | Verify webhook URL in Langdock |
| `HTTP error: 401` | Authentication failed | Check if webhook requires auth |
| `HTTP error: 413` | Payload too large (>2MB) | Reduce evidence count (currently top 10) |
| `Connection timeout` | Langdock not responding | Check Langdock service status |
| `Connection refused` | Wrong URL | Double-check callback URL |

---

### 5. Error Handling Logging

**If anything fails:**

```
❌ FATAL: Failed to initialize research environment: No module named 'core.graph'
Full traceback:
  File "/app/api/main.py", line 264
  ...
```

OR per-task errors:

```
❌ Error processing task abc123-...: OpenAI API rate limit exceeded
Full traceback:
  ...
📤 Sending error webhook...
```

---

## How to Test with New Logging

### Step 1: Check Startup Logs

1. Deploy updated code to Replit
2. Check console for environment variable confirmation
3. Verify all keys show ✅

### Step 2: Trigger Batch Execution

**Test call:**
```bash
curl -X POST https://webresearchagent.replit.app/execute/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 60b8a838a2cecf8d40f641e51ff96ab5c813b0c768b4a3b9cae2cb19fc00271b" \
  -d '{
    "frequency": "daily",
    "callback_url": "https://app.langdock.com/api/hooks/workflows/48cfee5a-9a8b-42cf-90de-00b399f9c731"
  }'
```

### Step 3: Watch Logs in Real-Time

In Replit console, you should see:

1. ✅ **Request received** (immediate)
2. ✅ **Tasks found** (immediate)
3. ✅ **Background started** (immediate)
4. ✅ **Modules imported** (5-10 seconds)
5. ✅ **Graph built** (5-10 seconds)
6. ✅ **Research executing** (2-5 minutes per task)
7. ✅ **Webhook sent** (1-2 seconds)
8. ✅ **Database updated** (1 second)

---

## Common Production Issues

### Issue 1: No Background Logs After "Starting background execution"

**Symptoms:**
```
🚀 Starting background execution for 2 tasks
[... nothing after this ...]
```

**Likely causes:**
- Background tasks not working in production (Replit issue)
- Import failures (but caught now with logging)
- Python environment mismatch

**Solution:** Check if you see `📦 Importing research modules...` - if not, background task isn't running

---

### Issue 2: Import Errors

**Symptoms:**
```
❌ FATAL: Failed to initialize research environment: No module named 'core'
```

**Causes:**
- Research code not deployed to Replit
- Wrong working directory
- Missing dependencies

**Solution:**
1. Verify `core/` and `tools/` directories exist in Replit
2. Check `pyproject.toml` is deployed
3. Run `pip install -e .` in Replit console

---

### Issue 3: API Key Errors During Research

**Symptoms:**
```
❌ Error processing task: perplexity.AuthenticationError
```

**Causes:**
- Environment variables not loaded in background task
- API keys expired/invalid

**Solution:**
1. Check startup logs show all keys loaded
2. Verify keys in Replit Secrets match
3. Test API keys directly (curl to Perplexity/Exa APIs)

---

### Issue 4: Webhook Not Reaching Langdock

**Symptoms:**
```
📤 Sending webhook...
❌ HTTP error: 404
```

**Causes:**
- Wrong webhook URL
- Langdock workflow not enabled
- Network issue

**Solution:**
1. Test webhook URL with curl:
   ```bash
   curl -X POST https://app.langdock.com/api/hooks/workflows/48cfee5a-... \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```
2. Check Langdock workflow is active
3. Verify URL has no typos

---

## Next Steps

1. **Deploy to Replit** - Push this code update
2. **Restart API** - Hit Run button to reload with new logging
3. **Check startup logs** - Verify environment variables
4. **Test batch execution** - Trigger with curl command above
5. **Monitor logs** - Watch each step complete
6. **Share logs** - If issues persist, copy relevant log sections

---

## Log Levels

All logs use Python's logging module:
- **INFO** (ℹ️): Normal operation steps
- **WARNING** (⚠️): Potential issues but continuing
- **ERROR** (❌): Failures that prevent task completion
- **EXCEPTION**: Full stack traces for debugging

Set log level in environment:
```bash
LOG_LEVEL=DEBUG  # For more verbose logging
```
