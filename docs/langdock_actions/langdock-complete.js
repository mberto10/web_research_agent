/**
 * ============================================================================
 * COMPLETE LANGDOCK EMAIL RENDERER
 * ============================================================================
 *
 * INSTRUCTIONS:
 * 1. Copy this ENTIRE file into your Langdock Code node
 * 2. Ensure the previous node (webhook receiver) is named: webhook1
 * 3. The script will automatically access webhook1 and process the data
 * 4. Connect output to Outlook Email action
 *
 * USAGE IN OUTLOOK NODE:
 * - To: ${code1.output.email}
 * - Subject: ${code1.output.subject}
 * - Body: ${code1.output.htmlContent}
 * - Body Type: HTML
 *
 * ============================================================================
 */

// ============================================================================
// MARKDOWN TO HTML CONVERTER
// ============================================================================

const markdownToHtml = (markdown) => {
    if (!markdown) return '';

    let html = markdown
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" style="color: #667eea; text-decoration: none;">$1</a>')
        .replace(/^[•\-\*]\s+(.+)$/gm, '<li>$1</li>')
        .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/gs, match => `<ul>${match}</ul>`)
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<p')) {
        html = `<p>${html}</p>`;
    }

    return html;
};

// ============================================================================
// BASE EMAIL TEMPLATE
// ============================================================================

const createEmailHTML = (title, subtitle, contentHTML) => {
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <style>
        body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
        table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
        img { -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }
        body { margin: 0 !important; padding: 0 !important; width: 100% !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f4f5f7; color: #2d3748; }
        .email-container { max-width: 680px; margin: 0 auto; background-color: #ffffff; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 48px 40px; text-align: center; }
        .header h1 { margin: 0 0 8px 0; color: #ffffff; font-size: 32px; font-weight: 700; line-height: 1.2; }
        .header .subtitle { margin: 0; color: rgba(255, 255, 255, 0.95); font-size: 16px; font-weight: 400; }
        .content { padding: 40px 40px 48px 40px; }
        .content h1 { color: #1a202c; font-size: 28px; font-weight: 700; margin: 32px 0 16px 0; padding-bottom: 12px; border-bottom: 3px solid #667eea; }
        .content h2 { color: #2d3748; font-size: 22px; font-weight: 600; margin: 28px 0 14px 0; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; }
        .content h3 { color: #4a5568; font-size: 18px; font-weight: 600; margin: 20px 0 10px 0; }
        .content p { color: #4a5568; font-size: 15px; line-height: 1.7; margin: 0 0 16px 0; }
        .content ul { margin: 0 0 20px 0; padding-left: 24px; }
        .content li { color: #4a5568; font-size: 15px; line-height: 1.7; margin-bottom: 10px; }
        .content a { color: #667eea; text-decoration: none; font-weight: 500; }
        .content a:hover { text-decoration: underline; }
        .content strong { color: #2d3748; font-weight: 600; }
        .citations-section { background: #f7fafc; border-left: 4px solid #667eea; padding: 24px; margin: 32px 0; border-radius: 4px; }
        .citations-section h2 { margin-top: 0; color: #2d3748; font-size: 20px; border-bottom: none; }
        .citation-item { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 12px; }
        .citation-item:last-child { margin-bottom: 0; }
        .citation-title { font-size: 16px; font-weight: 600; color: #2d3748; margin: 0 0 8px 0; }
        .citation-url { font-size: 14px; color: #667eea; text-decoration: none; word-break: break-all; display: block; margin-bottom: 8px; }
        .citation-snippet { font-size: 14px; color: #718096; line-height: 1.5; margin: 0; }
        .footer { background: #2d3748; color: #cbd5e0; padding: 32px 40px; text-align: center; }
        .footer p { margin: 6px 0; font-size: 14px; }
        .footer-brand { font-weight: 600; color: #ffffff; font-size: 16px; }
        .metadata-badge { background: #edf2f7; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 16px; margin: 24px 0; font-size: 13px; color: #718096; }
        @media only screen and (max-width: 600px) {
            .header { padding: 32px 24px !important; }
            .header h1 { font-size: 26px !important; }
            .content { padding: 24px !important; }
            .content h1 { font-size: 24px !important; }
            .content h2 { font-size: 20px !important; }
            .footer { padding: 24px !important; }
        }
    </style>
</head>
<body>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f5f7;">
        <tr>
            <td align="center" style="padding: 24px 0;">
                <table role="presentation" class="email-container" cellspacing="0" cellpadding="0" border="0">
                    <tr>
                        <td class="header">
                            <h1>${title}</h1>
                            ${subtitle ? `<p class="subtitle">${subtitle}</p>` : ''}
                        </td>
                    </tr>
                    <tr>
                        <td class="content">
                            ${contentHTML}
                        </td>
                    </tr>
                    <tr>
                        <td class="footer">
                            <p class="footer-brand">Web Research Agent</p>
                            <p>AI-powered research delivered to your inbox</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>`.trim();
};

// ============================================================================
// CITATION RENDERER
// ============================================================================

const renderCitations = (citations) => {
    if (!citations || citations.length === 0) return '';

    const citationItems = citations.map((citation, idx) => {
        const title = citation.title || 'Untitled Source';
        const url = citation.url || '#';
        const snippet = citation.snippet || '';

        return `
            <div class="citation-item">
                <div class="citation-title">[${idx + 1}] ${title}</div>
                <a href="${url}" class="citation-url">${url}</a>
                ${snippet ? `<p class="citation-snippet">${snippet}</p>` : ''}
            </div>
        `;
    }).join('');

    return `
        <div class="citations-section">
            <h2>📚 Sources & Citations</h2>
            ${citationItems}
        </div>
    `;
};

// ============================================================================
// METADATA RENDERER
// ============================================================================

const renderMetadata = (metadata, research_topic) => {
    const evidence_count = metadata?.evidence_count || 0;
    const executed_at = metadata?.executed_at || new Date().toISOString();
    const strategy_slug = metadata?.strategy_slug || 'unknown';

    const date = new Date(executed_at).toLocaleString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    return `
        <div class="metadata-badge">
            <strong>Research Topic:</strong> ${research_topic}<br>
            <strong>Strategy:</strong> ${strategy_slug}<br>
            <strong>Sources Analyzed:</strong> ${evidence_count}<br>
            <strong>Generated:</strong> ${date}
        </div>
    `;
};

// ============================================================================
// STRATEGY RENDERERS
// ============================================================================

const renderDefault = (payload, alertBanner = null) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = '';
    if (alertBanner) {
        contentHTML += alertBanner;
    }
    contentHTML += renderMetadata(metadata, research_topic);
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    return contentHTML;
};

const renderEmail = (payload) => {
    const { result, research_topic } = payload;
    const { metadata = {} } = result;
    const strategy_slug = metadata.strategy_slug || 'daily_news_briefing';

    let title, subtitle, contentHTML, alertBanner;

    // Strategy-specific configurations
    switch (strategy_slug) {
        case 'news/real_time_briefing':
            alertBanner = `
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                    <strong style="color: #78350f;">⚡ BREAKING NEWS ALERT</strong>
                </div>
            `;
            title = `🔴 Breaking: ${research_topic}`;
            subtitle = `Live updates as of ${new Date().toLocaleTimeString('en-US')}`;
            break;

        case 'company/dossier':
            alertBanner = `
                <div style="background: #e0e7ff; border-left: 4px solid #667eea; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                    <strong style="color: #3730a3;">🏢 Company Research Report</strong>
                </div>
            `;
            title = `Company Dossier: ${research_topic}`;
            subtitle = 'Comprehensive company analysis and profile';
            break;

        case 'financial_research':
            alertBanner = `
                <div style="background: #dcfce7; border-left: 4px solid #16a34a; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                    <strong style="color: #14532d;">📈 Financial Market Analysis</strong>
                </div>
            `;
            title = `Financial Research: ${research_topic}`;
            subtitle = 'Market analysis and investment insights';
            break;

        case 'financial_news_reactive':
            alertBanner = `
                <div style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                    <strong style="color: #7f1d1d;">📊 Market Alert</strong>
                </div>
            `;
            title = `Market Alert: ${research_topic}`;
            subtitle = 'Rapid response to financial developments';
            break;

        case 'research_paper_analysis':
            alertBanner = `
                <div style="background: #f3e8ff; border-left: 4px solid #9333ea; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
                    <strong style="color: #581c87;">🎓 Academic Research Analysis</strong>
                </div>
            `;
            title = `Research Paper Analysis: ${research_topic}`;
            subtitle = 'Academic literature review and synthesis';
            break;

        case 'general/week_overview':
            title = `Weekly Overview: ${research_topic}`;
            subtitle = 'Your comprehensive week in review';
            break;

        case 'news_monitoring':
            title = `News Monitoring: ${research_topic}`;
            subtitle = 'Ongoing coverage and updates';
            break;

        case 'daily_news_briefing':
        default:
            title = `Daily News Briefing: ${research_topic}`;
            subtitle = new Date().toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            break;
    }

    contentHTML = renderDefault(payload, alertBanner);
    return createEmailHTML(title, subtitle, contentHTML);
};

// ============================================================================
// SUBJECT LINE GENERATOR
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

// ============================================================================
// MAIN EXECUTION (LANGDOCK)
// ============================================================================

try {
    // Access webhook data from previous node
    const webhookPayload = webhook1;

    // Validate payload
    if (!webhookPayload || !webhookPayload.result) {
        throw new Error('Invalid webhook payload: missing result data');
    }

    // Extract data
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

    console.log(`✓ Processing research: ${research_topic}`);
    console.log(`  Strategy: ${metadata.strategy_slug}`);
    console.log(`  Sections: ${sections.length}, Citations: ${citations.length}`);

    // Generate HTML email
    const htmlContent = renderEmail(webhookPayload);

    // Create subject line
    const emailSubject = createSubjectLine(metadata.strategy_slug, research_topic);

    console.log(`✓ Email rendered successfully`);
    console.log(`  Subject: ${emailSubject}`);
    console.log(`  Size: ${htmlContent.length} characters`);

    // Return output for Outlook node
    return {
        success: true,
        task_id: task_id,
        email: recipientEmail,
        subject: emailSubject,
        htmlContent: htmlContent,
        research_topic: research_topic,
        strategy: metadata.strategy_slug,
        sections_count: sections.length,
        citations_count: citations.length,
        generated_at: new Date().toISOString()
    };

} catch (error) {
    console.error('❌ Error processing webhook:', error.message);

    // Return error response
    return {
        success: false,
        error: error.message,
        generated_at: new Date().toISOString()
    };
}
