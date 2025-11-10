# Manual Research Briefing - Complete Guide

This guide explains how to use the new manual research endpoint and Langdock actions to generate research briefings on-demand without database storage.

## Overview

The manual research feature allows you to:
- Trigger research briefings directly via API without storing tasks in the database
- Execute research synchronously (get results immediately) or asynchronously (via webhook)
- Integrate with Langdock actions for easy workflow automation
- Run the full research architecture just like batch execution

## API Endpoint

### `/execute/manual` - POST

Execute a manual research task without database storage.

#### Request Headers
```
Content-Type: application/json
X-API-Key: your_api_secret_key
```

#### Request Body
```json
{
  "research_topic": "Your research query here",
  "email": "optional@example.com",
  "callback_url": "https://optional-webhook-url.com"
}
```

**Parameters:**
- `research_topic` (required): The research query/topic (max 500 characters)
- `email` (optional): User email for tracking in Langfuse
- `callback_url` (optional): Webhook URL to receive results
  - If **not provided**: Synchronous execution (returns results immediately)
  - If **provided**: Asynchronous execution (results sent to webhook)

#### Response

**Synchronous Mode (no callback_url):**
```json
{
  "status": "completed",
  "research_topic": "Your research query",
  "started_at": "2025-11-10T12:00:00",
  "result": {
    "sections": ["# Section 1", "# Section 2"],
    "citations": [
      {
        "title": "Source Title",
        "url": "https://source-url.com",
        "snippet": "Relevant excerpt"
      }
    ],
    "metadata": {
      "evidence_count": 25,
      "executed_at": "2025-11-10T12:05:00",
      "strategy_slug": "daily_news_briefing"
    }
  }
}
```

**Asynchronous Mode (with callback_url):**
```json
{
  "status": "running",
  "research_topic": "Your research query",
  "started_at": "2025-11-10T12:00:00"
}
```

Results will be sent to your webhook URL when complete.

---

## Langdock Actions

### 1. Synchronous Research Action

**File:** `langdock-manual-research.js`

Use this for immediate results. The action waits for research to complete and returns results directly.

#### Setup in Langdock:

1. Create a new **Code** node
2. Copy contents of `langdock-manual-research.js`
3. Configure inputs:
   - `research_topic`: String - The research query
   - `email`: String (optional) - User email
   - `api_url`: String - Your production API URL
   - `api_key`: String - Your API_SECRET_KEY

4. Connect output to:
   - Email sender (use `webhook_payload` field)
   - Display/formatting node
   - Database storage node

#### Example Flow:
```
[User Input] → [Manual Research Code] → [Email Sender]
```

#### Output Structure:
```javascript
{
  success: true,
  mode: "manual_research",
  webhook_payload: { /* Compatible with existing email sender */ },
  research_topic: "...",
  strategy_used: "daily_news_briefing",
  sections_count: 5,
  citations_count: 10,
  summary: { ... }
}
```

---

### 2. Asynchronous Research Action

**File:** `langdock-manual-research-async.js`

Use this for long-running research. The action triggers research and returns immediately.

#### Setup in Langdock:

1. Create a new **Code** node
2. Copy contents of `langdock-manual-research-async.js`
3. Configure inputs:
   - `research_topic`: String - The research query
   - `email`: String (optional) - User email
   - `webhook_url`: String - Your Langdock webhook URL
   - `api_url`: String - Your production API URL
   - `api_key`: String - Your API_SECRET_KEY

4. Create a separate workflow to receive webhook results
5. Use existing `langdock-email-sender.js` to process results

#### Example Flow:
```
Trigger Workflow:
[User Input] → [Async Research Code] → [Confirmation Message]

Webhook Workflow:
[Webhook Receiver] → [Email Sender] → [Done]
```

---

## Testing

### Using the Test Script

A test script is provided for easy testing:

```bash
# Test synchronous execution
./test_manual_research.sh sync

# Test asynchronous execution (requires webhook URL)
./test_manual_research.sh async
```

### Using curl

**Synchronous:**
```bash
curl -X POST "https://your-api.com/execute/manual" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_secret_key" \
  -d '{
    "research_topic": "Latest AI developments",
    "email": "test@example.com"
  }'
```

**Asynchronous:**
```bash
curl -X POST "https://your-api.com/execute/manual" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_secret_key" \
  -d '{
    "research_topic": "Latest AI developments",
    "email": "test@example.com",
    "callback_url": "https://your-webhook-url.com"
  }'
```

---

## Use Cases

### 1. On-Demand Research via Langdock Chat

Set up a Langdock action that users can trigger via chat:

```
User: "Research the latest developments in quantum computing"
→ Langdock captures topic
→ Triggers manual research action
→ Sends results to user's email
```

### 2. Research API for External Applications

Expose manual research to external apps:

```javascript
// External app calls your API
const response = await fetch('https://api.example.com/execute/manual', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  },
  body: JSON.stringify({
    research_topic: 'User query',
    email: 'user@example.com'
  })
});

const results = await response.json();
```

### 3. Quick Research Testing

Test research strategies without setting up database tasks:

```bash
# Test a new research topic
./test_manual_research.sh sync
```

---

## Architecture

### Flow Diagram

**Synchronous:**
```
User/Langdock → API → Research Graph → Response → User
```

**Asynchronous:**
```
User/Langdock → API → Background Task → Webhook → Email Sender
```

### Key Differences from Batch Execution

| Feature | Batch Execution | Manual Research |
|---------|----------------|-----------------|
| Storage | Requires database task | No database storage |
| Triggering | Scheduled (cron) | On-demand |
| Topic Source | Database | API request |
| Use Case | Recurring briefings | Ad-hoc research |
| Tracing | Tag: `batch_execution` | Tag: `manual_execution` |

### Tracing in Langfuse

All manual research is traced in Langfuse with:
- **Tag:** `manual_execution`
- **User ID:** Email or "manual_user"
- **Metadata:** Mode (sync/async), callback URL
- **Session ID:** Unique per request

---

## Error Handling

### Synchronous Mode

Errors are returned immediately:

```json
{
  "status": "failed",
  "research_topic": "Your query",
  "started_at": "2025-11-10T12:00:00",
  "error": "Error message here"
}
```

### Asynchronous Mode

Errors are sent to webhook:

```json
{
  "email": "user@example.com",
  "research_topic": "Your query",
  "frequency": "manual",
  "status": "failed",
  "error": "Error message here",
  "executed_at": "2025-11-10T12:00:00"
}
```

---

## Best Practices

1. **Choose the Right Mode:**
   - Use **sync** for quick queries (<2 min expected)
   - Use **async** for complex research (>2 min expected)

2. **Provide Email:**
   - Always include email for better tracking in Langfuse
   - Helps with debugging and analytics

3. **Webhook URLs:**
   - Use Langdock webhook URLs for production
   - Use webhook.site for testing
   - Ensure webhooks are secured

4. **Rate Limiting:**
   - Be mindful of API rate limits
   - Use async mode for bulk requests

5. **Testing:**
   - Always test with the test script first
   - Verify webhook delivery before production use

---

## Security

- API key required in `X-API-Key` header
- Stored securely in environment variables
- Rate limiting recommended (add middleware if needed)
- Validate webhook URLs before use

---

## Monitoring

Monitor manual research in:

1. **Langfuse Dashboard:**
   - Filter by tag: `manual_execution`
   - Track costs, latency, and quality

2. **API Logs:**
   - Check application logs for execution details
   - Monitor success/failure rates

3. **Webhook Delivery:**
   - Verify webhook callbacks are received
   - Check for delivery failures

---

## Troubleshooting

### Issue: Synchronous request times out

**Solution:** Use async mode instead:
```json
{
  "research_topic": "...",
  "callback_url": "your-webhook-url"
}
```

### Issue: Webhook not received

**Check:**
1. Webhook URL is accessible
2. API logs show webhook was sent
3. Firewall/security settings allow incoming webhooks

### Issue: Research returns no results

**Check:**
1. Research topic is specific enough
2. API keys (Perplexity, Exa, OpenAI) are valid
3. Langfuse logs for errors

---

## Examples

### Langdock Workflow Example

```javascript
// Node 1: User Input
const userTopic = await getUserInput("What would you like to research?");
const userEmail = await getUserEmail();

// Node 2: Manual Research (this file)
const research = await executeManualResearch(userTopic, userEmail);

// Node 3: Email Results
await sendEmail(research.webhook_payload);
```

### Integration with Existing Email Sender

The manual research action outputs a `webhook_payload` field that is 100% compatible with your existing `langdock-email-sender.js`:

```javascript
// Manual research output
const manualResult = await runManualResearch();

// Pass to existing email sender (no changes needed!)
const emailResult = await sendResearchEmail(manualResult.webhook_payload);
```

---

## Future Enhancements

Potential improvements:
- [ ] Strategy selection in request
- [ ] Custom LLM model selection
- [ ] Batch manual research (multiple topics)
- [ ] Priority queue for manual requests
- [ ] Caching for duplicate topics

---

## Support

For issues or questions:
1. Check API logs: `/var/log/api.log`
2. Review Langfuse traces
3. Test with provided test script
4. Check environment variables are set

---

## Summary

The manual research feature provides a flexible way to generate research briefings on-demand:

✅ No database storage needed
✅ Works with existing email infrastructure
✅ Supports both sync and async modes
✅ Full Langfuse tracing
✅ Compatible with Langdock workflows

**Quick Start:**
1. Use `test_manual_research.sh` to verify API works
2. Set up Langdock action with `langdock-manual-research.js`
3. Connect to your existing email sender
4. Start researching!
