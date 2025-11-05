// Action #2: Get User's Research Tasks
// Use Case: Show user their active subscriptions

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key

// Input Variables
const email = data.input.email; // Email address to look up

// Execute API request
const options = {
  url: `${baseUrl}/tasks?email=${encodeURIComponent(email)}`,
  method: 'GET',
  headers: {
    'X-API-Key': apiKey
  }
};

const response = await ld.request(options);
return response.json;
