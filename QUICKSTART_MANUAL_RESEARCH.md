# Quick Start: Manual Research Briefing

## What's New?

You now have a **manual research endpoint** that lets you trigger research briefings on-demand without storing them in the database!

## 🎯 Use Cases

- **Ad-hoc research requests** from users via Langdock chat
- **Testing research strategies** without creating database tasks
- **API integrations** for external applications
- **Quick one-off briefings** that don't need scheduling

## 📦 What Was Created

### 1. API Endpoint: `/execute/manual`

**Location:** `api/main.py` (lines 405-549)

**Features:**
- ✅ Synchronous mode: Returns results immediately
- ✅ Asynchronous mode: Sends results to webhook
- ✅ Full Langfuse tracing
- ✅ Same research architecture as batch execution
- ✅ No database storage required

### 2. Langdock Actions

#### `langdock-manual-research.js` (Synchronous)
- Calls API and waits for results
- Returns formatted payload for email sender
- Compatible with existing `langdock-email-sender.js`

#### `langdock-manual-research-async.js` (Asynchronous)
- Triggers research in background
- Results sent to webhook
- Better for long-running research

### 3. Test Script

**File:** `test_manual_research.sh`

```bash
# Test synchronous execution
./test_manual_research.sh sync

# Test asynchronous execution
./test_manual_research.sh async
```

### 4. Documentation

**File:** `MANUAL_RESEARCH_GUIDE.md`
- Complete API reference
- Langdock integration guide
- Examples and troubleshooting

---

## 🚀 Quick Start

### Option 1: Test with curl

```bash
curl -X POST "https://your-api.com/execute/manual" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_SECRET_KEY" \
  -d '{
    "research_topic": "Latest AI developments",
    "email": "test@example.com"
  }'
```

### Option 2: Use Test Script

```bash
./test_manual_research.sh sync
```

### Option 3: Set Up Langdock Action

1. Open Langdock
2. Create new Code node
3. Copy `langdock-manual-research.js`
4. Configure inputs:
   - `research_topic`: Your research query
   - `api_url`: Your production API URL
   - `api_key`: Your API_SECRET_KEY
5. Connect to email sender
6. Run!

---

## 📝 API Request Examples

### Synchronous (Returns results immediately)

```json
POST /execute/manual

{
  "research_topic": "Latest quantum computing breakthroughs",
  "email": "user@example.com"
}

Response:
{
  "status": "completed",
  "research_topic": "...",
  "result": {
    "sections": [...],
    "citations": [...],
    "metadata": {...}
  }
}
```

### Asynchronous (Results sent to webhook)

```json
POST /execute/manual

{
  "research_topic": "Latest quantum computing breakthroughs",
  "email": "user@example.com",
  "callback_url": "https://your-webhook-url.com"
}

Response:
{
  "status": "running",
  "research_topic": "...",
  "started_at": "..."
}
```

---

## 🔗 Integration with Existing System

The manual research endpoint is 100% compatible with your existing email infrastructure:

```
Manual Research → Same payload format → Existing Email Sender ✅
```

**Example Langdock Flow:**

```
[User Input]
    ↓
[Manual Research Code Node]
    ↓
[Email Sender] (existing - no changes needed!)
    ↓
[User receives email]
```

---

## 🎨 Example Langdock Workflows

### Workflow 1: Instant Research via Chat

```
User: "Research the latest in AI safety"
  ↓
Langdock captures topic
  ↓
Manual Research Action (sync)
  ↓
Email sent to user
```

### Workflow 2: Scheduled Manual Research

```
Daily trigger at 9 AM
  ↓
Fetch topics from Google Sheet
  ↓
For each topic → Manual Research Action (async)
  ↓
Results webhook → Email Sender
```

### Workflow 3: Slack Integration

```
User posts in #research channel
  ↓
Slack webhook → Langdock
  ↓
Manual Research Action
  ↓
Post results back to Slack
```

---

## 🔧 Configuration

### Required Environment Variables

Already set (same as batch execution):
- ✅ `API_SECRET_KEY` - API authentication
- ✅ `DATABASE_URL` - Database connection
- ✅ `PERPLEXITY_API_KEY` - Research API
- ✅ `EXA_API_KEY` - Research API
- ✅ `OPENAI_API_KEY` - LLM API
- ✅ `LANGFUSE_PUBLIC_KEY` - Tracing
- ✅ `LANGFUSE_SECRET_KEY` - Tracing

### Langdock Setup

Set these in your Langdock environment:
- `api_url` - Your production API URL
- `api_key` - Your API_SECRET_KEY

---

## 📊 Monitoring

### In Langfuse

Filter traces by:
- **Tag:** `manual_execution`
- **Tag:** `synchronous` or `asynchronous`
- **User ID:** Email provided in request

### In API Logs

Look for:
```
🎯 MANUAL RESEARCH STARTED
   Topic: [your topic]
...
✅ MANUAL RESEARCH COMPLETE
```

---

## 🐛 Troubleshooting

### "API_SECRET_KEY is required"
→ Set `api_key` in Langdock or pass as parameter

### Request times out (sync mode)
→ Use async mode instead with webhook

### Webhook not received (async mode)
→ Check webhook URL is accessible
→ Check API logs to verify webhook was sent

### Research returns empty results
→ Check API keys are valid
→ Review Langfuse traces for errors
→ Verify research topic is specific enough

---

## 📈 Next Steps

1. **Test the endpoint** with the test script
   ```bash
   ./test_manual_research.sh sync
   ```

2. **Set up Langdock action** using `langdock-manual-research.js`

3. **Connect to email sender** (existing one works!)

4. **Monitor in Langfuse** to track usage and quality

5. **Create custom workflows** for your use cases

---

## 🎉 Benefits

✅ **No database clutter** - Research doesn't persist
✅ **Fast setup** - Use existing infrastructure
✅ **Flexible** - Sync or async execution
✅ **Traceable** - Full Langfuse integration
✅ **Reusable** - Works with existing email sender

---

## 📚 Full Documentation

See `MANUAL_RESEARCH_GUIDE.md` for:
- Complete API reference
- Advanced examples
- Security best practices
- Architecture details
- Error handling guide

---

## Summary

You can now generate research briefings on-demand without touching the database!

**Files Created:**
1. `api/schemas.py` - Request/response schemas
2. `api/main.py` - `/execute/manual` endpoint
3. `langdock-manual-research.js` - Sync Langdock action
4. `langdock-manual-research-async.js` - Async Langdock action
5. `test_manual_research.sh` - Testing script
6. `MANUAL_RESEARCH_GUIDE.md` - Full documentation
7. `QUICKSTART_MANUAL_RESEARCH.md` - This file

**Ready to use! 🚀**
