// Action #3: Update Research Task
// Use Case: User changes their research topic or pauses subscription

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key

// Input Variables
const taskId = data.input.taskId; // UUID of the task to update
const researchTopic = data.input.researchTopic; // New research topic (optional)
const frequency = data.input.frequency; // New frequency (optional)
const isActive = data.input.isActive; // true/false to activate/pause (optional)

// Build update payload (only include fields that are provided)
const updates = {};
if (researchTopic !== undefined) updates.research_topic = researchTopic;
if (frequency !== undefined) updates.frequency = frequency;
if (isActive !== undefined) updates.is_active = isActive;

// Execute API request
const options = {
  url: `${baseUrl}/tasks/${taskId}`,
  method: 'PATCH',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  },
  body: updates
};

const response = await ld.request(options);
return response.json;
