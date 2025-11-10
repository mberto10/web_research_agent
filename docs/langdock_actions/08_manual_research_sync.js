// Action: Execute Manual Research (Synchronous)
// Use Case: On-demand research without database storage, returns results immediately

// Configuration
const baseUrl = "https://webresearchagent.replit.app";
const apiKey = data.auth.apiKey; // Your API secret key

// Input Variables
const researchTopic = data.input.researchTopic; // What to research (e.g., "Latest AI developments")
const email = data.input.email || null; // Optional: User email for Langfuse tracking

// Execute API request (synchronous - no callback_url)
const options = {
  url: `${baseUrl}/execute/manual`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  },
  body: {
    research_topic: researchTopic,
    email: email
    // No callback_url = synchronous execution with direct response
  }
};

const response = await ld.request(options);
const apiResponse = response.json;

// Check if research completed successfully
if (apiResponse.status !== "completed") {
  throw new Error(`Research failed with status: ${apiResponse.status}. Error: ${apiResponse.error || 'Unknown error'}`);
}

// Extract results
const { result, research_topic, started_at } = apiResponse;

if (!result) {
  throw new Error("No results returned from API");
}

const { sections, citations, metadata } = result;

// Format the response to match the webhook payload structure
// This allows it to work with existing email sender nodes
const webhookFormattedPayload = {
  task_id: `manual-${Date.now()}`, // Generate a pseudo task ID
  email: email || "manual_user@example.com",
  research_topic: research_topic,
  frequency: "manual",
  status: "completed",
  result: {
    sections: sections,
    citations: citations,
    metadata: {
      evidence_count: metadata.evidence_count,
      executed_at: metadata.executed_at,
      strategy_slug: metadata.strategy_slug
    }
  }
};

// Return output compatible with existing email sender
return {
  success: true,
  mode: "manual_research",
  webhook_payload: webhookFormattedPayload,

  // Quick access fields
  research_topic: research_topic,
  strategy_used: metadata.strategy_slug,
  sections_count: sections.length,
  citations_count: citations.length,
  executed_at: metadata.executed_at
};
