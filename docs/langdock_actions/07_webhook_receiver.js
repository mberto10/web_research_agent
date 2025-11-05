// Action #7: Webhook Receiver (Process Results)
// Use Case: Receive research results from API and send via email

// Input Variables - Pass the full webhook result object
const webhookResult = data.input.result; // The complete webhook payload/result object

// Log what we received for debugging
console.log("Webhook result received:", JSON.stringify(webhookResult, null, 2));

// Parse all fields from the result object
const taskId = webhookResult.task_id || webhookResult.taskId || "unknown";
const email = webhookResult.email || webhookResult.recipient_email || "";
const researchTopic = webhookResult.research_topic || webhookResult.topic || "Research Briefing";
const status = webhookResult.status || "unknown";

// Success - Format email content
if (status === "completed") {
  const result = webhookResult.result || {};

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
<p><strong>Error:</strong> ${webhookResult.error}</p>
<p>Please contact support if this continues.</p>
    `
  };
}

// Default return if neither completed nor failed
return {
  error: "Unknown status received",
  status: status
};
