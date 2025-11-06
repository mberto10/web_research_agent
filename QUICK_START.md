# Quick Start: Langdock Email Renderer

## 🚀 3-Step Setup

### Step 1: Create Webhook Receiver
1. Add **Webhook** node to Langdock workflow
2. Name it: `webhook1`
3. Copy webhook URL

### Step 2: Add Code Node
1. Add **Code** node (JavaScript)
2. Copy & paste entire `langdock-complete.js` file
3. Save

### Step 3: Add Outlook Email Node
1. Add **Outlook Email** action
2. Configure fields:
   - **To**: `${code1.output.email}`
   - **Subject**: `${code1.output.subject}`
   - **Body**: `${code1.output.htmlContent}`
   - **Body Type**: HTML
3. Save workflow

## ✅ That's it!

Now update your Research Agent API callback URL to the webhook URL from Step 1.

## 📋 Webhook Variable Access

The webhook data is automatically available as `webhook1` in your code node:

```javascript
// Langdock provides this automatically
const webhookPayload = webhook1;

// Access fields:
webhook1.email              // Recipient email
webhook1.research_topic     // Research topic
webhook1.result.sections    // Content sections
webhook1.result.citations   // Source citations
webhook1.result.metadata    // Strategy info
```

## 🎨 Supported Strategies

| Strategy | Email Style |
|----------|-------------|
| `daily_news_briefing` | 📰 Daily Briefing |
| `news/real_time_briefing` | 🔴 Breaking News |
| `general/week_overview` | 📅 Weekly Overview |
| `company/dossier` | 🏢 Company Report |
| `financial_research` | 📈 Financial Analysis |
| `financial_news_reactive` | 💹 Market Alert |
| `news_monitoring` | 📊 News Update |
| `research_paper_analysis` | 🎓 Research Analysis |

All strategies automatically get:
- ✅ Beautiful HTML formatting
- ✅ Clickable source citations
- ✅ Responsive design
- ✅ Professional styling
- ✅ Clear metadata display

## 🧪 Test Payload

Use this in Langdock's "Test Workflow" feature:

```json
{
  "email": "your-email@example.com",
  "research_topic": "Artificial Intelligence",
  "result": {
    "sections": [
      "## Executive Summary\n\nAI developments continue at rapid pace.",
      "## Key Findings\n\n• OpenAI releases GPT-5\n• Google launches Gemini 2.0"
    ],
    "citations": [
      {
        "title": "OpenAI Blog",
        "url": "https://openai.com",
        "snippet": "Major AI breakthrough announced"
      }
    ],
    "metadata": {
      "strategy_slug": "daily_news_briefing",
      "evidence_count": 10,
      "executed_at": "2025-11-05T10:00:00Z"
    }
  }
}
```

## 📁 Files Overview

- **`langdock-complete.js`** → Copy this into Langdock Code node ⭐
- **`email-renderer.js`** → Core renderer (modular version)
- **`langdock-email-sender.js`** → Langdock integration (modular version)
- **`email-renderer-examples.js`** → Local testing examples
- **`LANGDOCK_SETUP_GUIDE.md`** → Detailed documentation
- **`QUICK_START.md`** → This file

## 🔧 Troubleshooting

**"webhook1 is not defined"**
→ Make sure webhook node is named exactly `webhook1`

**"Email body is empty"**
→ Check that code node output is `${code1.output.htmlContent}`

**"Email not sending"**
→ Verify Outlook action is configured correctly

## 📞 Need Help?

Check the detailed guide: `LANGDOCK_SETUP_GUIDE.md`

---

**Ready to send beautiful research emails!** 🎉
