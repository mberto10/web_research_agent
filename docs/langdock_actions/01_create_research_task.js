// Action #1: Create Research Task Subscription
// Use Case: User signs up for daily/weekly research briefings

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key

// Input Variables
const email = data.input.email; // User's email address
const researchTopic = data.input.researchTopic; // What to research (e.g., "AI developments in healthcare")
const frequency = data.input.frequency; // How often to run: "daily", "weekly", or "monthly"
const scheduleTime = data.input.scheduleTime || "09:00"; // Time of day to run (24h format)

// Execute API request
const options = {
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

const response = await ld.request(options);
return response.json;
