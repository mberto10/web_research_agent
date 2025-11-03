# Langdock Integration Code - Research Agent API

Copy-paste ready JavaScript functions for Langdock workflows. Just change the `baseUrl` when deploying to production.

---

## Configuration

```javascript
// 🔧 CHANGE THIS WHEN DEPLOYING TO PRODUCTION
const baseUrl = "https://your-repl-name.your-username.repl.co"; // Development
// const baseUrl = "https://your-production-url.repl.co"; // Production (Reserved VM)

const apiKey = data.auth.apiKey; // Your API secret key from Replit Secrets
```

---

## 1. Create Research Task Subscription

**Use Case:** User signs up for daily/weekly research briefings

```javascript
// 🔧 Configuration
const baseUrl = "https://your-repl-name.your-username.repl.co";
const apiKey = data.auth.apiKey; // Your API secret key

// 📥 Input Variables
const email = data.input.email; // User's email address
const researchTopic = data.input.researchTopic; // What to research (e.g., "AI developments in healthcare")
const frequency = data.input.frequency; // How often to run: "daily", "weekly", or "monthly"
const scheduleTime = data.input.scheduleTime || "09:00"; // Time of day to run (24h format)

// 📤 Return fetch configuration for Langdock
return {
  url: `${baseUrl}/tasks`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  },
  body: {
    email: email,
    research_topic: researchTopic,
    frequency: frequency,
    schedule_time: scheduleTime
  }
};
```

**Variables:**
- `email` - User's email address
- `researchTopic` - Topic to research and report on
- `frequency` - How often to execute: "daily", "weekly", "monthly"
- `scheduleTime` - Preferred time of day (HH:MM format)
- `apiKey` - API authentication secret

---

## 2. Get User's Research Tasks

**Use Case:** Show user their active subscriptions

```javascript
// 🔧 Configuration
const baseUrl = "https://your-repl-name.your-username.repl.co";
const apiKey = data.auth.apiKey; // Your API secret key

// 📥 Input Variables
const email = data.input.email; // Email address to look up

// 📤 Return fetch configuration
return {
  url: `${baseUrl}/tasks?email=${encodeURIComponent(email)}`,
  method: 'GET',
  headers: {
    'X-API-Key': apiKey
  }
};
```

**Variables:**
- `email` - Email address to search for
- `apiKey` - API authentication secret

---

## 3. Update Research Task

**Use Case:** User changes their research topic or pauses subscription

```javascript
// 🔧 Configuration
const baseUrl = "https://your-repl-name.your-username.repl.co";
const apiKey = data.auth.apiKey; // Your API secret key

// 📥 Input Variables
const taskId = data.input.taskId; // UUID of the task to update
const researchTopic = data.input.researchTopic; // New research topic (optional)
const frequency = data.input.frequency; // New frequency (optional)
const isActive = data.input.isActive; // true/false to activate/pause (optional)

// Build update payload (only include fields that are provided)
const updates = {};
if (researchTopic !== undefined) updates.research_topic = researchTopic;
if (frequency !== undefined) updates.frequency = frequency;
if (isActive !== undefined) updates.is_active = isActive;

// 📤 Return fetch configuration
return {
  url: `${baseUrl}/tasks/${taskId}`,
  method: 'PATCH',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  },
  body: updates
};
```

**Variables:**
- `taskId` - Unique identifier of the subscription to update
- `researchTopic` - New research topic (optional)
- `frequency` - New execution frequency (optional)
- `isActive` - Enable (true) or pause (false) the subscription (optional)
- `apiKey` - API authentication secret

---

## 4. Delete Research Task

**Use Case:** User unsubscribes from briefings

```javascript
// 🔧 Configuration
const baseUrl = "https://your-repl-name.your-username.repl.co";
const apiKey = data.auth.apiKey; // Your API secret key

// 📥 Input Variables
const taskId = data.input.taskId; // UUID of task to delete

// 📤 Return fetch configuration
return {
  url: `${baseUrl}/tasks/${taskId}`,
  method: 'DELETE',
  headers: {
    'X-API-Key': apiKey
  }
};
```

**Variables:**
- `taskId` - Unique identifier of the subscription to delete
- `apiKey` - API authentication secret

---

## 5. Execute Batch Research (Single Frequency)

**Use Case:** Scheduled daily/weekly briefing run

```javascript
// 🔧 Configuration
const baseUrl = "https://your-repl-name.your-username.repl.co";
const apiKey = data.auth.apiKey; // Your API secret key

// 📥 Input Variables
const frequency = data.input.frequency; // Which frequency to execute: "daily", "weekly", or "monthly"
const callbackUrl = data.input.callbackUrl; // Webhook URL to receive research results

// 📤 Return fetch configuration
return {
  url: `${baseUrl}/execute/batch`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  },
  body: {
    frequency: frequency,
    callback_url: callbackUrl
  }
};
```

**Variables:**
- `frequency` - Which tasks to execute: "daily", "weekly", or "monthly"
- `callbackUrl` - Your webhook endpoint to receive completed research results
- `apiKey` - API authentication secret

---

## 6. Execute Multiple Batch Runs (Advanced - Use Custom Code)

**Use Case:** Run all frequencies in one workflow (e.g., every morning)

**Note:** For multiple sequential API calls, use Langdock's workflow orchestration instead of a single action. Create separate actions for each frequency and chain them.

**Alternative Simple Approach:**
Run 3 separate "Execute Batch" actions in parallel with different frequencies.

---

## 7. Smart Batch Scheduler (Advanced - Use Workflow Logic)

**Use Case:** Run daily every day, weekly on Mondays, monthly on 1st of month

**Recommended Approach:**
Use Langdock's conditional logic in workflow:
- Trigger: Schedule (daily at 9 AM)
- Condition 1: Always run "daily" batch
- Condition 2: If Monday → run "weekly" batch
- Condition 3: If day=1 → run "monthly" batch

Each condition uses the "Execute Batch" action (#5) with different frequency values.

---

## 8. Health Check

**Use Case:** Monitor API availability

```javascript
// 🔧 Configuration
const baseUrl = "https://your-repl-name.your-username.repl.co";

// 📤 Return fetch configuration (no auth needed for health)
return {
  url: `${baseUrl}/health`,
  method: 'GET'
};
```

**Variables:** None required

---

## 9. Webhook Receiver (Process Results)

**Use Case:** Receive research results from API and send via email

```javascript
// 📥 Webhook Data (from previous step/trigger)
const webhookData = data.response; // Response from webhook trigger

// Extract variables
const taskId = webhookData.task_id; // Unique task identifier
const email = webhookData.email; // Recipient email address
const researchTopic = webhookData.research_topic; // Research topic
const status = webhookData.status; // "completed" or "failed"

// ✅ Success - Format email content
if (status === "completed") {
  const result = webhookData.result;
  const sections = result.sections.join("\n\n"); // Research content sections
  const citations = result.citations.map((c, i) => // List of sources
    `${i + 1}. ${c.title}\n   ${c.url}`
  ).join("\n");

  // Format email HTML
  const emailSubject = `Your ${researchTopic} briefing is ready`;
  const emailBody = `
<h2>${researchTopic}</h2>

<h3>Research Findings</h3>
<div style="white-space: pre-wrap;">${sections}</div>

<h3>Sources</h3>
<pre>${citations}</pre>

<p><small>Research completed at ${result.metadata.executed_at}</small></p>
  `;

  // Return email configuration for Resend
  return {
    to: email,
    subject: emailSubject,
    html: emailBody
  };
}

// ❌ Error - Send error notification
if (status === "failed") {
  return {
    to: email,
    subject: `Research briefing failed: ${researchTopic}`,
    html: `
<p>We encountered an error generating your research briefing.</p>
<p><strong>Error:</strong> ${webhookData.error}</p>
<p>Please contact support if this continues.</p>
    `
  };
}

// Default return if neither completed nor failed
return {
  error: "Unknown status received",
  status: status
};
```

**Variables:**
- `taskId` - Unique identifier for the research task
- `email` - Recipient's email address
- `researchTopic` - What was researched
- `status` - Result status: "completed" or "failed"
- `webhookData.result.sections` - Array of research content sections
- `webhookData.result.citations` - Array of source citations
- `webhookData.error` - Error message (if failed)

---

## Input Field Configurations for Langdock

### Create Task Action
```
Action Type: HTTP Request

Input Fields:
  - email (text, required) - User's email address
  - researchTopic (text, required) - Topic to research
  - frequency (select, required) - Options: "daily", "weekly", "monthly"
  - scheduleTime (text, optional) - Time in HH:MM format (default: "09:00")

Authentication:
  - apiKey (secret, required) - Your API secret key
```

### Get Tasks Action
```
Action Type: HTTP Request

Input Fields:
  - email (text, required) - Email address to look up

Authentication:
  - apiKey (secret, required) - Your API secret key
```

### Update Task Action
```
Action Type: HTTP Request

Input Fields:
  - taskId (text, required) - UUID of task to update
  - researchTopic (text, optional) - New research topic
  - frequency (select, optional) - Options: "daily", "weekly", "monthly"
  - isActive (boolean, optional) - Enable/disable subscription

Authentication:
  - apiKey (secret, required) - Your API secret key
```

### Delete Task Action
```
Action Type: HTTP Request

Input Fields:
  - taskId (text, required) - UUID of task to delete

Authentication:
  - apiKey (secret, required) - Your API secret key
```

### Execute Batch Action
```
Action Type: HTTP Request

Input Fields:
  - frequency (select, required) - Options: "daily", "weekly", "monthly"
  - callbackUrl (text, required) - Webhook URL for results

Authentication:
  - apiKey (secret, required) - Your API secret key
```

### Health Check Action
```
Action Type: HTTP Request

Input Fields: None

Authentication: None
```

### Webhook Receiver + Email Action
```
Action Type: Code (then chain to Resend Email action)

Input Fields:
  - (auto) - Data comes from webhook trigger

Next Action: Send Email (Resend)
  - Use output from webhook receiver code
```

---

## Quick Deployment Checklist

1. ✅ Install dependencies: `pip install -e .`
2. ✅ Generate API key: `openssl rand -hex 32`
3. ✅ Add `API_SECRET_KEY` to Replit Secrets
4. ✅ Hit "Run" button in Replit
5. ✅ Copy your Replit URL
6. ✅ Update `baseUrl` in all Langdock actions
7. ✅ Add `apiKey` to Langdock authentication
8. ✅ Test each action individually
9. ✅ Set up webhook receiver workflow
10. ✅ Configure Resend email action
11. ✅ Test end-to-end flow

---

## Example Workflow Setup in Langdock

### Workflow 1: User Signs Up
```
Trigger: Form Submission / API Call
    ↓
Action 1: Create Research Task (#1)
    - Input: email, researchTopic, frequency from form
    ↓
Action 2: Send Confirmation Email
    - To: {email}
    - Subject: "You're subscribed to {researchTopic}"
```

### Workflow 2: Daily Batch Execution
```
Trigger: Schedule (every day at 9 AM)
    ↓
Action 1: Execute Batch (#5)
    - frequency: "daily"
    - callbackUrl: "https://your-langdock-webhook-url"
```

### Workflow 3: Webhook Receiver
```
Trigger: Webhook (receives from API)
    ↓
Action 1: Process Webhook Data (#9)
    - Parses result
    - Formats email
    ↓
Action 2: Send Email (Resend)
    - To: {output.to}
    - Subject: {output.subject}
    - HTML: {output.html}
```

---

## Troubleshooting

**Error: "Invalid response format"**
- ✅ Fixed! Use the return format above: `{url, method, headers, body}`

**Error: "401 Unauthorized"**
- Check API key is set in Langdock authentication
- Verify `API_SECRET_KEY` in Replit Secrets matches

**Error: "Connection refused"**
- Make sure API is running (hit Run button in Replit)
- Verify URL is correct (no trailing slash)

**Webhook not received:**
- Check callback URL is publicly accessible
- Verify Langdock webhook endpoint is configured correctly

Done!
