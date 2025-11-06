/**
 * Langdock Webhook Receiver & Email Sender
 *
 * This script receives webhook data from the Web Research Agent API
 * and sends beautifully formatted emails via Outlook.
 *
 * Langdock provides webhook data in: webhook1
 */

const { renderEmail, generatePlainText } = require('./email-renderer.js');

// ============================================================================
// MAIN LANGDOCK ACTION
// ============================================================================

/**
 * Access webhook payload from previous node
 * Langdock automatically provides: webhook1
 */
const webhookPayload = webhook1;

// Validate webhook payload
if (!webhookPayload || !webhookPayload.result) {
    throw new Error('Invalid webhook payload: missing result data');
}

// Extract key information
const {
    task_id,
    email: recipientEmail,
    research_topic,
    frequency,
    status,
    result
} = webhookPayload;

const {
    sections = [],
    citations = [],
    metadata = {}
} = result;

console.log(`Processing research results for: ${research_topic}`);
console.log(`Strategy: ${metadata.strategy_slug}`);
console.log(`Sections: ${sections.length}, Citations: ${citations.length}`);

// ============================================================================
// GENERATE EMAIL CONTENT
// ============================================================================

// Generate HTML email using the renderer
const htmlContent = renderEmail(webhookPayload);

// Generate plain text fallback
const plainTextContent = generatePlainText(webhookPayload);

// ============================================================================
// CREATE EMAIL SUBJECT LINE
// ============================================================================

const createSubjectLine = (strategy_slug, topic) => {
    const subjectMap = {
        'daily_news_briefing': `📰 Daily Briefing: ${topic}`,
        'news/real_time_briefing': `🔴 Breaking News: ${topic}`,
        'news_monitoring': `📊 News Update: ${topic}`,
        'general/week_overview': `📅 Weekly Overview: ${topic}`,
        'company/dossier': `🏢 Company Report: ${topic}`,
        'financial_research': `📈 Financial Analysis: ${topic}`,
        'financial_news_reactive': `💹 Market Alert: ${topic}`,
        'research_paper_analysis': `🎓 Research Analysis: ${topic}`
    };

    return subjectMap[strategy_slug] || `Research Update: ${topic}`;
};

const emailSubject = createSubjectLine(metadata.strategy_slug, research_topic);

// ============================================================================
// SEND EMAIL VIA OUTLOOK (LANGDOCK)
// ============================================================================

/**
 * Send email using Langdock's Outlook integration
 *
 * Langdock provides: ld.outlook.sendEmail()
 */
const emailResult = await ld.outlook.sendEmail({
    to: recipientEmail,
    subject: emailSubject,
    body: htmlContent,
    // Optional: attach plain text version
    // Some email clients may use this as fallback
    bodyType: 'HTML',
    importance: frequency === 'daily' && metadata.strategy_slug === 'news/real_time_briefing'
        ? 'High'
        : 'Normal'
});

console.log(`✓ Email sent successfully to: ${recipientEmail}`);
console.log(`  Subject: ${emailSubject}`);
console.log(`  Strategy: ${metadata.strategy_slug}`);
console.log(`  Task ID: ${task_id}`);

// ============================================================================
// RETURN SUCCESS RESPONSE
// ============================================================================

return {
    success: true,
    task_id: task_id,
    email: recipientEmail,
    research_topic: research_topic,
    strategy: metadata.strategy_slug,
    sections_count: sections.length,
    citations_count: citations.length,
    email_sent_at: new Date().toISOString(),
    outlook_result: emailResult
};
