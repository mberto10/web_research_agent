// Action #4: Delete Research Task
// Use Case: User unsubscribes from briefings

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key

// Input Variables
const taskId = data.input.taskId; // UUID of task to delete

// Execute API request
const options = {
  url: `${baseUrl}/tasks/${taskId}`,
  method: 'DELETE',
  headers: {
    'X-API-Key': apiKey
  }
};

const response = await ld.request(options);
return response.json;
