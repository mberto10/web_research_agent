// Action #7: Webhook Receiver (Process Results)
// Use Case: Receive research results from API and send via email

// Webhook Data (from webhook trigger)
// Try different possible data locations depending on Langdock's structure
const webhookData = data.response || data.input || data;

// Log what we received for debugging
console.log("Webhook data received:", JSON.stringify(webhookData, null, 2));

// Extract variables
const taskId = webhookData.task_id; // Unique task identifier
const email = webhookData.email; // Recipient email address
const researchTopic = webhookData.research_topic; // Research topic
const status = webhookData.status; // "completed" or "failed"

// Success - Format email content
if (status === "completed") {
  const result = webhookData.result || {};

  // Safely handle sections
  const sectionsArray = result.sections || [];
  const sections = sectionsArray.length > 0
    ? sectionsArray.join("\n\n")
    : "No research content available.";

  // Safely handle citations
  const citationsArray = result.citations || [];
  const citations = citationsArray.length > 0
    ? citationsArray.map((c, i) =>
        `${i + 1}. ${c.title || "No title"}\n   ${c.url || ""}`
      ).join("\n")
    : "No citations available.";

  // Safely get metadata
  const metadata = result.metadata || {};
  const executedAt = metadata.executed_at || new Date().toISOString();

  // Format email HTML
  const emailSubject = `Your ${researchTopic} briefing is ready`;
  const emailBody = `
<h2>${researchTopic}</h2>

<h3>Research Findings</h3>
<div style="white-space: pre-wrap;">${sections}</div>

<h3>Sources</h3>
<pre>${citations}</pre>

<p><small>Research completed at ${executedAt}</small></p>
  `;

  // Return email configuration for Outlook action
  return {
    to: email,
    subject: emailSubject,
    body: emailBody
  };
}

// Error - Send error notification
if (status === "failed") {
  return {
    to: email,
    subject: `Research briefing failed: ${researchTopic}`,
    body: `
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
