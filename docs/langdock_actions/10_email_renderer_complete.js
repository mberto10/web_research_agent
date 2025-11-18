/**
 * ============================================================================
 * Action #10: Complete Email Renderer with HTML Formatting
 * ============================================================================
 *
 * INSTRUCTIONS:
 * 1. Copy this ENTIRE file into your Langdock Code node
 * 2. Previous node must be a Webhook trigger that receives research results
 * 3. The webhook data will be in webhook1 variable
 * 4. Connect output to Outlook Email action
 *
 * USAGE IN OUTLOOK NODE:
 * - To: ${previousStep.email}
 * - Subject: ${previousStep.subject}
 * - Body: ${previousStep.htmlContent}
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
        // Headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // Bold and italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Links
        .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" style="color: #667eea; text-decoration: none;">$1</a>')
        // Source citations in the Sources section: [1] Source Name... -> anchored links
        .replace(/^\[(\d+)\]\s+(.+?)(https?:\/\/[^\s]+)$/gm, (match, num, source, url) => {
            return `<span id="cite-${num}" style="display: block; margin-bottom: 8px;"><strong style="color: #667eea;">[${num}]</strong> ${source.trim()}<a href="${url}" style="color: #667eea; text-decoration: none; word-break: break-all;">${url}</a></span>`;
        })
        // Inline citations: [1] or [2][3] -> superscript links to sources
        .replace(/\[(\d+)\]/g, '<sup><a href="#cite-$1" style="color: #667eea; text-decoration: none; font-weight: 600;">[$1]</a></sup>')
        // Lists
        .replace(/^[•\-\*]\s+(.+)$/gm, '<li>$1</li>')
        .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/gs, match => `<ul>${match}</ul>`)
        // Horizontal rules
        .replace(/^---$/gm, '<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">')
        // Paragraphs
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
    return `</p>
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
        @media only screen and (max-width: 600px) {
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
</html>
<p>`.trim();
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
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 24px 28px; margin: 0 0 32px 0; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);">
            <div style="color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1.3; margin: 0 0 12px 0;">${research_topic}</div>
            <div style="color: rgba(255, 255, 255, 0.9); font-size: 14px; line-height: 1.6;">
                <strong style="color: rgba(255, 255, 255, 0.95);">Strategy:</strong> ${strategy_slug}<br>
                <strong style="color: rgba(255, 255, 255, 0.95);">Generated:</strong> ${date}
            </div>
        </div>
    `;
};

// ============================================================================
// DISCLAIMER BANNER
// ============================================================================

const renderDisclaimerBanner = () => {
    return `
        <div style="background: #f8f9fa; border: 1px solid #dee2e6; border-left: 3px solid #6c757d; padding: 14px 18px; margin-bottom: 28px; border-radius: 4px;">
            <p style="margin: 0; color: #495057; font-size: 14px; line-height: 1.6;">
                <strong style="color: #343a40;">ℹ️ Hinweis:</strong> Dieses Briefing wurde von einem KI-Agenten in Eigenrecherche erstellt und kann Ungenauigkeiten oder Fehler enthalten. Bitte prüfen Sie wenn notwendig alle Quellen sorgfältig und kontaktieren Sie das GenAI Team bei auftretenden Fehlern.
            </p>
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
    // 1. Metadata header
    contentHTML += renderMetadata(metadata, research_topic);
    // 2. Standard disclaimer banner (always shown)
    contentHTML += renderDisclaimerBanner();
    // 3. Strategy-specific alert banner (optional)
    if (alertBanner) {
        contentHTML += alertBanner;
    }
    // 4. Main content
    contentHTML += sectionsHTML;
    // 5. Citations
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
    // Debug: Log what we received
    console.log('Raw webhook1 received:', JSON.stringify(webhook1, null, 2));

    // Handle different webhook structures
    let webhookPayload;

    // Check if webhook1 has a body property
    if (webhook1?.body) {
        console.log('✓ Using webhook1.body');
        webhookPayload = webhook1.body;
    } else if (webhook1) {
        console.log('✓ Using webhook1 directly');
        webhookPayload = webhook1;
    } else {
        throw new Error('No webhook data received (webhook1 is null or undefined)');
    }

    console.log('Extracted payload:', JSON.stringify(webhookPayload, null, 2));

    // Validate payload structure
    if (!webhookPayload.result) {
        // Provide detailed error for debugging
        const availableKeys = Object.keys(webhookPayload || {}).join(', ');
        throw new Error(`Invalid webhook payload: missing result data. Available keys: ${availableKeys}`);
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

    // Validate required fields
    if (!recipientEmail) {
        throw new Error('Missing recipient email address');
    }

    if (!research_topic) {
        throw new Error('Missing research topic');
    }

    const {
        sections = [],
        citations = [],
        metadata = {}
    } = result;

    // Handle failed status
    if (status === 'failed') {
        const errorMessage = webhookPayload.error || 'Unknown error occurred';

        return {
            success: false,
            email: recipientEmail,
            subject: `❌ Research Failed: ${research_topic}`,
            htmlContent: `
                <div style="padding: 20px; background: #fee2e2; border-left: 4px solid #dc2626; border-radius: 4px;">
                    <h3 style="margin-top: 0; color: #991b1b;">Research Generation Failed</h3>
                    <p style="color: #7f1d1d;"><strong>Topic:</strong> ${research_topic}</p>
                    <p style="color: #7f1d1d;"><strong>Error:</strong> ${errorMessage}</p>
                    <p style="color: #7f1d1d; margin-bottom: 0;">Please try again or contact support if this issue persists.</p>
                </div>
            `,
            error: errorMessage,
            generated_at: new Date().toISOString()
        };
    }

    // Generate HTML email
    const htmlContent = renderEmail(webhookPayload);

    // Create subject line
    const emailSubject = createSubjectLine(metadata.strategy_slug, research_topic);

    // Return output for Outlook/email node
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
    // Return error response with safe fallback
    return {
        success: false,
        email: 'error@example.com',
        subject: 'Error Processing Research',
        htmlContent: `
            <div style="padding: 20px; background: #fee2e2; border-left: 4px solid #dc2626; border-radius: 4px;">
                <h3 style="margin-top: 0; color: #991b1b;">Email Processing Error</h3>
                <p style="color: #7f1d1d;"><strong>Error:</strong> ${error.message}</p>
                <p style="color: #7f1d1d; margin-bottom: 0;">Please check the webhook payload structure and try again.</p>
            </div>
        `,
        error: error.message,
        generated_at: new Date().toISOString()
    };
}
