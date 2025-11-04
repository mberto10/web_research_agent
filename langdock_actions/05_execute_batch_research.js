// Action #5: Execute Batch Research (Single Frequency)
// Use Case: Scheduled daily/weekly briefing run

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key
const callbackUrl = data.auth.callbackUrl; // Webhook URL to receive research results (from auth)

// Input Variables
const frequency = data.input.frequency; // Which frequency to execute: "daily", "weekly", or "monthly"

// Execute API request
const options = {
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

const response = await ld.request(options);
return response.json;
