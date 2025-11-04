// Action #6: Health Check
// Use Case: Monitor API availability

// Configuration
const baseUrl = "https://webresearchagent.replit.app";

// Execute API request (no auth needed for health)
const options = {
  url: `${baseUrl}/health`,
  method: 'GET'
};

const response = await ld.request(options);
return response.json;
