# Environment Setup Checklist for Production

## Current Issues from Logs

Based on the production execution logs, here are the issues and solutions:

---

## ✅ Issue #1: Result Format Bug - FIXED

**Error:**
```
AttributeError: 'dict' object has no attribute 'sections'
```

**Root Cause:** LangGraph with checkpointing returns state as a dict, not a State object.

**Fix Applied:** Updated `api/main.py:310-336` to handle both dict and State object formats.

**Status:** ✅ Fixed - Deploy to production

---

## ⚠️ Issue #2: Environment Variables Not Loaded

**Warnings:**
```
WARNING - Langfuse client initialized without public_key
```

**Required Environment Variables:**

You need to add these to **Replit Secrets**:

| Variable | Purpose | Where to Get |
|----------|---------|--------------|
| `LANGFUSE_PUBLIC_KEY` | Tracing/observability | Langfuse dashboard |
| `LANGFUSE_SECRET_KEY` | Tracing/observability | Langfuse dashboard |
| `LANGFUSE_HOST` | Tracing endpoint | Usually `https://cloud.langfuse.com` |
| `EXA_API_KEY` | Search API | Exa dashboard (after topping up) |
| `PERPLEXITY_API_KEY` | Search API | Perplexity dashboard |
| `OPENAI_API_KEY` | LLM API | OpenAI dashboard |
| `DATABASE_URL` | PostgreSQL connection | Neon/Replit database |
| `API_SECRET_KEY` | API authentication | Already set |

### How to Add to Replit:

1. Go to your Replit project
2. Click on "Secrets" (lock icon) in left sidebar
3. Add each variable as key-value pair
4. **IMPORTANT:** Click "Run" button to restart API
5. Check startup logs for confirmation

### Verification After Restart:

You should see in logs:
```
✅ LANGFUSE_PUBLIC_KEY: sk-lf-... (length: 56)
✅ LANGFUSE_SECRET_KEY: sk-lf-... (length: 56)
✅ LANGFUSE_HOST: https://... (length: 35)
✅ EXA_API_KEY: exa-... (length: 48)
✅ PERPLEXITY_API_KEY: pplx-... (length: 56)
✅ OPENAI_API_KEY: sk-proj-... (length: 89)
✅ DATABASE_URL: postgres://... (length: 120)
```

**Status:** ⚠️ Action Required - Add secrets and restart

---

## ❌ Issue #3: Exa API Credits Exhausted

**Error:**
```
ValueError: Request failed with status code 402
"You have exceeded your credits limit. Please top up to keep using Exa"
```

**Action Required:**

1. Go to https://dashboard.exa.ai
2. Log in with your account
3. Add credits/upgrade plan
4. Exa is critical for high-quality search results

**Good News:** Research still completed! The system fell back to Perplexity after Exa failed. But for best results, top up Exa credits.

**Status:** ❌ Action Required - Top up Exa credits

---

## Deployment Checklist

### Step 1: Fix Code (Done ✅)
- [x] Result format bug fixed in `api/main.py`
- [x] Handles both dict and State object
- [x] Evidence handling improved

### Step 2: Add Environment Variables
- [ ] Add `LANGFUSE_PUBLIC_KEY` to Replit Secrets
- [ ] Add `LANGFUSE_SECRET_KEY` to Replit Secrets
- [ ] Add `LANGFUSE_HOST` to Replit Secrets (use `https://cloud.langfuse.com`)
- [ ] Verify `EXA_API_KEY` is set
- [ ] Verify `PERPLEXITY_API_KEY` is set
- [ ] Verify `OPENAI_API_KEY` is set
- [ ] Verify `DATABASE_URL` is set

### Step 3: Top Up Exa Credits
- [ ] Go to https://dashboard.exa.ai
- [ ] Add credits to account
- [ ] Test Exa API key works

### Step 4: Deploy & Restart
- [ ] Commit and push code changes
- [ ] Restart API in Replit (click "Run" button)
- [ ] Check startup logs for environment variable confirmation

### Step 5: Test End-to-End
- [ ] Trigger batch execution with curl
- [ ] Monitor logs for successful completion
- [ ] Verify webhook delivery (200 status)
- [ ] Check email inbox for research briefing
- [ ] Validate email formatting

---

## Expected Logs After Fixes

### Startup (with environment variables):
```
🔑 API Key loaded: 60b8a838... (length: 64)
✅ DATABASE_URL: postgres:... (length: 120)
✅ PERPLEXITY_API_KEY: pplx-... (length: 56)
✅ EXA_API_KEY: exa-... (length: 48)
✅ OPENAI_API_KEY: sk-proj-... (length: 89)
✅ LANGFUSE_PUBLIC_KEY: sk-lf-... (length: 56)
✅ LANGFUSE_SECRET_KEY: sk-lf-... (length: 56)
✅ LANGFUSE_HOST: https://cloud.langfuse.com (length: 29)
```

### Batch Execution (success):
```
[1/1] 🔬 Processing task abc-123...
  Email: m.bruhn@faz.de
  Topic: Everything about AI agents
  🚀 Invoking research graph...
  ✅ Research completed
  📊 Sections: 4, Evidence: 12
  📤 Sending webhook to: https://app.langdock.com/...
  Attempt 1/3...
  Response status: 200
  Response body: {"success":true}
  ✅ Webhook delivered successfully
  ✅ Database updated (last_run_at)
```

### No More Errors:
- ❌ ~~Langfuse authentication warnings~~ → ✅ Silent (working)
- ❌ ~~Exa credits exhausted~~ → ✅ Successful searches
- ❌ ~~AttributeError: 'dict' object has no attribute 'sections'~~ → ✅ Handled correctly

---

## Quick Test Commands

### 1. Test API Health
```bash
curl https://webresearchagent.replit.app/health
```

### 2. Create Test Task
```bash
curl -X POST https://webresearchagent.replit.app/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 60b8a838a2cecf8d40f641e51ff96ab5c813b0c768b4a3b9cae2cb19fc00271b" \
  -d '{
    "email": "m.bruhn@faz.de",
    "research_topic": "Latest AI agent developments",
    "frequency": "daily"
  }'
```

### 3. Trigger Batch Execution
```bash
curl -X POST https://webresearchagent.replit.app/execute/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 60b8a838a2cecf8d40f641e51ff96ab5c813b0c768b4a3b9cae2cb19fc00271b" \
  -d '{
    "frequency": "daily",
    "callback_url": "https://app.langdock.com/api/hooks/workflows/48cfee5a-9a8b-42cf-90de-00b399f9c731"
  }'
```

### 4. Monitor Logs
Watch Replit console for real-time execution logs.

---

## Summary

| Issue | Status | Action |
|-------|--------|--------|
| Result format bug | ✅ Fixed | Deploy code |
| Environment variables | ⚠️ Missing | Add to Replit Secrets + restart |
| Exa API credits | ❌ Exhausted | Top up at dashboard.exa.ai |
| Webhook workflow | ✅ Configured | No action needed |

## Next Steps:

1. ✅ Deploy fixed code to Replit
2. ⚠️ Add Langfuse environment variables to Replit Secrets
3. ⚠️ Restart API to load new environment variables
4. ❌ Top up Exa credits at dashboard.exa.ai
5. ✅ Test end-to-end with curl commands above
6. ✅ Verify email delivery

Once all steps are complete, the system should work end-to-end! 🎉
