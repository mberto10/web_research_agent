# Langdock Actions - Research Agent API

Copy-paste ready JavaScript files for Langdock integration. Each file is a standalone action.

## Files Overview

| File | Action | Purpose |
|------|--------|---------|
| `01_create_research_task.js` | Create Research Task | User subscribes to daily/weekly/monthly briefings |
| `02_get_user_tasks.js` | Get User Tasks | Retrieve all subscriptions for a user by email |
| `03_update_research_task.js` | Update Task | Change topic, frequency, or pause subscription |
| `04_delete_research_task.js` | Delete Task | Unsubscribe/remove a research task |
| `05_execute_batch_research.js` | Execute Batch | Trigger research for all tasks (used by schedulers) |
| `06_health_check.js` | Health Check | Monitor API availability |
| `07_webhook_receiver.js` | Webhook Receiver | Process research results and format for email (simple) |
| `08_manual_research_sync.js` | Manual Research (Sync) | On-demand research without database, returns results immediately |
| `09_manual_research_async.js` | Manual Research (Async) | On-demand research without database, sends results to webhook |
| `10_email_renderer_complete.js` | Complete Email Renderer | Advanced HTML email formatter with strategy-specific templates |

## Setup Instructions

**Setup Order:**
1. Add apiKey to Langdock auth
2. Create actions 1-7 (core subscription system)
3. Create webhook receiver workflow → Get webhook URL
4. Add callbackUrl to Langdock auth
5. Create scheduled triggers (daily/weekly/monthly)
6. (Optional) Create actions 8-9 for on-demand manual research

### 1. Add Authentication to Langdock

Store these values in Langdock's authentication/secrets:
- **apiKey** (secret): `60b8a838a2cecf8d40f641e51ff96ab5c813b0c768b4a3b9cae2cb19fc00271b`
- **callbackUrl** (text): Set this AFTER creating the webhook receiver workflow (step 3)

### 2. Create Each Action in Langdock

For each JavaScript file:

1. Create a new **Code Action** in Langdock
2. Copy the entire contents of the `.js` file
3. Paste into Langdock's code editor
4. Configure input fields (see below)

### 3. Input Field Configurations

#### Action #1: Create Research Task
```
Input Fields:
  - email (text, required)
  - researchTopic (text, required)
  - frequency (select, required) - Options: daily, weekly, monthly
  - scheduleTime (text, optional) - Default: "09:00"

Authentication:
  - apiKey (secret, required)
```

#### Action #2: Get User Tasks
```
Input Fields:
  - email (text, required)

Authentication:
  - apiKey (secret, required)
```

#### Action #3: Update Research Task
```
Input Fields:
  - taskId (text, required)
  - researchTopic (text, optional)
  - frequency (select, optional) - Options: daily, weekly, monthly
  - isActive (boolean, optional)

Authentication:
  - apiKey (secret, required)
```

#### Action #4: Delete Research Task
```
Input Fields:
  - taskId (text, required)

Authentication:
  - apiKey (secret, required)
```

#### Action #5: Execute Batch Research
```
Input Fields:
  - frequency (select, required) - Options: daily, weekly, monthly

Authentication:
  - apiKey (secret, required)
  - callbackUrl (text, required) - Webhook URL for receiving results
```

#### Action #6: Health Check
```
Input Fields: None

Authentication: None
```

#### Action #7: Webhook Receiver
```
Input Fields:
  - (auto) - Receives data from webhook trigger

Output: {to, subject, body}

Next Action: Chain to Outlook Send Email
  - To: {output.to}
  - Subject: {output.subject}
  - Body: {output.body}
  - Body Type: HTML
```

#### Action #8: Manual Research (Synchronous)
```
Input Fields:
  - researchTopic (text, required)
  - email (text, optional) - For Langfuse tracking

Authentication:
  - apiKey (secret, required)

Output: Formatted webhook payload compatible with email sender

Use Case: On-demand research without database storage, returns results immediately
```

#### Action #9: Manual Research (Asynchronous)
```
Input Fields:
  - researchTopic (text, required)
  - email (text, optional) - For Langfuse tracking

Authentication:
  - apiKey (secret, required)
  - callbackUrl (text, required) - Webhook URL for receiving results

Output: Confirmation that research started

Use Case: On-demand research for long-running queries, results sent to webhook
```

#### Action #10: Complete Email Renderer
```
Input Fields:
  - (auto) - Receives data from webhook trigger (webhook1.body)

Output: {success, email, subject, htmlContent, ...metadata}

Features:
  - Markdown to HTML conversion
  - Strategy-specific email templates (breaking news, financial alerts, etc.)
  - Professional gradient header design
  - Formatted citations with snippets
  - Responsive mobile-friendly layout
  - Error handling with fallback emails

Next Action: Chain to Outlook Send Email
  - To: {output.email}
  - Subject: {output.subject}
  - Body: {output.htmlContent}
  - Body Type: HTML

Use Case: Advanced email formatting for all research types with beautiful HTML templates
```

## Workflow Examples

### User Subscription Flow
```
Trigger: Form/API
  ↓
Action: 01_create_research_task.js
  ↓
Action: Send confirmation email
```

### Scheduled Daily Batch
```
Trigger: Schedule (9:00 AM daily)
  ↓
Action: 05_execute_batch_research.js
  - frequency: "daily"
  - (callbackUrl is set in auth configuration)
```

### Webhook Receiver + Email
```
Trigger: Webhook
  ↓
Action: 07_webhook_receiver.js
  ↓
Action: Outlook Send Email
  - To: {previousStep.to}
  - Subject: {previousStep.subject}
  - Body: {previousStep.body}
  - Body Type: HTML
```

### On-Demand Research (Sync)
```
Trigger: Chat/Form
  ↓
Action: 08_manual_research_sync.js
  - researchTopic: {user input}
  ↓
Action: 07_webhook_receiver.js
  - Use output.webhook_payload as input
  ↓
Action: Outlook Send Email
```

### On-Demand Research (Async)
```
Trigger: Chat/Form
  ↓
Action: 09_manual_research_async.js
  - researchTopic: {user input}
  ↓
Action: Send "Research started" message

Webhook Workflow:
Trigger: Webhook
  ↓
Action: 07_webhook_receiver.js
  ↓
Action: Outlook Send Email
```

### Complete Email with HTML Templates
```
Trigger: Webhook (from batch or manual research)
  ↓
Action: 10_email_renderer_complete.js
  - Automatically processes webhook1.body
  - Applies strategy-specific templates
  - Converts markdown to beautiful HTML
  ↓
Action: Outlook Send Email
  - To: {previousStep.email}
  - Subject: {previousStep.subject}
  - Body: {previousStep.htmlContent}
  - Body Type: HTML
```

## Testing Checklist

### Core Actions (1-7)
- [ ] Action #1: Create task successfully returns task ID
- [ ] Action #2: Get tasks returns array for test email
- [ ] Action #3: Update modifies task fields
- [ ] Action #4: Delete removes task from database
- [ ] Action #5: Execute batch returns execution status
- [ ] Action #6: Health check returns {"status": "healthy"}
- [ ] Action #7: Webhook receiver formats email correctly
- [ ] End-to-end: Create → Schedule → Receive email

### Manual Research Actions (8-9)
- [ ] Action #8: Manual sync returns results with webhook_payload
- [ ] Action #9: Manual async triggers and sends to webhook
- [ ] Manual sync → Email sender works correctly
- [ ] Manual async → Webhook → Email sender works correctly

### Advanced Email Renderer (10)
- [ ] Action #10: Processes webhook1.body correctly
- [ ] Action #10: Renders HTML email with proper formatting
- [ ] Action #10: Applies correct strategy-specific templates
- [ ] Action #10: Handles failed research status gracefully
- [ ] Action #10: Citations display with proper styling
- [ ] Webhook → Email renderer → Outlook works end-to-end

## API Configuration

**Base URL:** `https://webresearchagent.replit.app`
**API Key:** `60b8a838a2cecf8d40f641e51ff96ab5c813b0c768b4a3b9cae2cb19fc00271b`

All actions use the production URL. No changes needed unless deploying to a different environment.

## Support

For issues or questions, refer to:
- Linear Issue: MB90-112
- Integration Doc: `/docs/langdock_integration_code.md`
- API Docs: `/api/README.md`
