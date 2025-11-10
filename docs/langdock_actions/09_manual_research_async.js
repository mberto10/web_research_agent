// Action: Execute Manual Research (Asynchronous)
// Use Case: On-demand research without database storage, results sent to webhook

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key
const callbackUrl = data.auth.callbackUrl; // Webhook URL to receive research results (from auth)

// Input Variables
const researchTopic = data.input.researchTopic; // What to research (e.g., "Latest AI developments")
const email = data.input.email || null; // Optional: User email for Langfuse tracking

// Execute API request (asynchronous - with callback_url)
const options = {
  url: `${baseUrl}/execute/manual`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  },
  body: {
    research_topic: researchTopic,
    email: email,
    callback_url: callbackUrl // This triggers async mode
  }
};

const response = await ld.request(options);
return response.json;
