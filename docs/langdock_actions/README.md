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
| `07_webhook_receiver.js` | Webhook Receiver | Process research results and format for email |

## Setup Instructions

**Setup Order:**
1. Add apiKey to Langdock auth
2. Create all 7 actions
3. Create webhook receiver workflow → Get webhook URL
4. Add callbackUrl to Langdock auth
5. Create scheduled triggers (daily/weekly/monthly)

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

## Testing Checklist

- [ ] Action #1: Create task successfully returns task ID
- [ ] Action #2: Get tasks returns array for test email
- [ ] Action #3: Update modifies task fields
- [ ] Action #4: Delete removes task from database
- [ ] Action #5: Execute batch returns execution status
- [ ] Action #6: Health check returns {"status": "healthy"}
- [ ] Action #7: Webhook receiver formats email correctly
- [ ] End-to-end: Create → Schedule → Receive email

## API Configuration

**Base URL:** `https://webresearchagent.replit.app`
**API Key:** `60b8a838a2cecf8d40f641e51ff96ab5c813b0c768b4a3b9cae2cb19fc00271b`

All actions use the production URL. No changes needed unless deploying to a different environment.

## Support

For issues or questions, refer to:
- Linear Issue: MB90-112
- Integration Doc: `/docs/langdock_integration_code.md`
- API Docs: `/api/README.md`
