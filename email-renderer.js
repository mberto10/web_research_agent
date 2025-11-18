/**
 * Email Renderer for Web Research Agent Strategies
 * Transforms webhook payload into beautiful HTML email templates
 *
 * USAGE:
 * const html = renderEmail(webhookPayload);
 * // Send html via email service
 */

// ============================================================================
// MARKDOWN TO HTML CONVERTER
// ============================================================================

const markdownToHtml = (markdown) => {
    if (!markdown) return '';

    let html = markdown
        // Headers (## → h2, ### → h3)
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')

        // Bold and italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')

        // Links with markdown syntax [text](url)
        .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" style="color: #667eea; text-decoration: none;">$1</a>')

        // Bullet points (• or - or *)
        .replace(/^[•\-\*]\s+(.+)$/gm, '<li>$1</li>')

        // Numbered lists
        .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')

        // Wrap consecutive <li> in <ul>
        .replace(/(<li>.*<\/li>\n?)+/gs, match => `<ul>${match}</ul>`)

        // Paragraphs (double newline)
        .replace(/\n\n/g, '</p><p>')

        // Single line breaks
        .replace(/\n/g, '<br>');

    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<h') && !html.startsWith('<ul') && !html.startsWith('<p')) {
        html = `<p>${html}</p>`;
    }

    return html;
};

// ============================================================================
// BASE EMAIL TEMPLATE WITH PROFESSIONAL STYLING
// ============================================================================

const createEmailHTML = (title, subtitle, contentHTML, footerText = null) => {
    return `</p>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        /* Reset styles */
        body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
        table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
        img { -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }

        body {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f4f5f7;
            color: #2d3748;
        }

        .email-container {
            max-width: 680px;
            margin: 0 auto;
            background-color: #ffffff;
        }

        /* Content area */
        .content {
            padding: 40px 40px 48px 40px;
        }

        .content h1 {
            color: #1a202c;
            font-size: 28px;
            font-weight: 700;
            margin: 32px 0 16px 0;
            padding-bottom: 12px;
            border-bottom: 3px solid #667eea;
        }

        .content h2 {
            color: #2d3748;
            font-size: 22px;
            font-weight: 600;
            margin: 28px 0 14px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
        }

        .content h3 {
            color: #4a5568;
            font-size: 18px;
            font-weight: 600;
            margin: 20px 0 10px 0;
        }

        .content p {
            color: #4a5568;
            font-size: 15px;
            line-height: 1.7;
            margin: 0 0 16px 0;
        }

        .content ul {
            margin: 0 0 20px 0;
            padding-left: 24px;
        }

        .content li {
            color: #4a5568;
            font-size: 15px;
            line-height: 1.7;
            margin-bottom: 10px;
        }

        .content a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }

        .content a:hover {
            text-decoration: underline;
        }

        .content strong {
            color: #2d3748;
            font-weight: 600;
        }

        /* Citation styles */
        .citations-section {
            background: #f7fafc;
            border-left: 4px solid #667eea;
            padding: 24px;
            margin: 32px 0;
            border-radius: 4px;
        }

        .citations-section h2 {
            margin-top: 0;
            color: #2d3748;
            font-size: 20px;
            border-bottom: none;
        }

        .citation-item {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 12px;
        }

        .citation-item:last-child {
            margin-bottom: 0;
        }

        .citation-title {
            font-size: 16px;
            font-weight: 600;
            color: #2d3748;
            margin: 0 0 8px 0;
        }

        .citation-url {
            font-size: 14px;
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
            display: block;
            margin-bottom: 8px;
        }

        .citation-snippet {
            font-size: 14px;
            color: #718096;
            line-height: 1.5;
            margin: 0;
        }

        /* Footer */
        .footer {
            background: #2d3748;
            color: #cbd5e0;
            padding: 32px 40px;
            text-align: center;
        }

        .footer p {
            margin: 6px 0;
            font-size: 14px;
        }

        .footer-brand {
            font-weight: 600;
            color: #ffffff;
            font-size: 16px;
        }

        /* Metadata badge */
        .metadata-badge {
            background: #edf2f7;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 12px 16px;
            margin: 24px 0;
            font-size: 13px;
            color: #718096;
        }

        /* Responsive */
        @media only screen and (max-width: 600px) {
            .content {
                padding: 24px !important;
            }

            .content h1 {
                font-size: 24px !important;
            }

            .content h2 {
                font-size: 20px !important;
            }

            .footer {
                padding: 24px !important;
            }
        }
    </style>
</head>
<body>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f5f7;">
        <tr>
            <td align="center" style="padding: 24px 0;">
                <table role="presentation" class="email-container" cellspacing="0" cellpadding="0" border="0">
                    <!-- Content (metadata card serves as header) -->
                    <tr>
                        <td class="content">
                            ${contentHTML}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td class="footer">
                            <p class="footer-brand">Web Research Agent</p>
                            <p>AI-powered research delivered to your inbox</p>
                            ${footerText ? `<p style="margin-top: 12px;">${footerText}</p>` : ''}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
<p>
    `.trim();
};

// ============================================================================
// CITATION RENDERER
// ============================================================================

const renderCitations = (citations) => {
    if (!citations || citations.length === 0) {
        return '';
    }

    const citationItems = citations.map((citation, index) => {
        const title = citation.title || 'Untitled Source';
        const url = citation.url || '#';
        const snippet = citation.snippet || '';

        return `
            <div class="citation-item">
                <div class="citation-title">[${index + 1}] ${title}</div>
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
// STRATEGY-SPECIFIC RENDERERS
// ============================================================================

/**
 * Daily News Briefing Renderer
 * Sections: Executive Summary, Key Developments, Analysis by Theme, Notable Mentions, Key Sources
 */
const renderDailyNewsBriefing = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    // Convert markdown sections to HTML
    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    // Build content
    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `Daily News Briefing: ${research_topic}`;
    const subtitle = new Date().toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * Real-Time News Briefing Renderer
 * Fast-turnaround breaking news format
 */
const renderRealTimeNewsBriefing = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += `
        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <strong style="color: #78350f;">⚡ BREAKING NEWS ALERT</strong>
        </div>
    `;
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `🔴 Breaking: ${research_topic}`;
    const subtitle = `Live updates as of ${new Date().toLocaleTimeString('en-US')}`;

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * Weekly Overview Renderer
 * Comprehensive week-in-review format
 */
const renderWeekOverview = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `Weekly Overview: ${research_topic}`;
    const subtitle = 'Your comprehensive week in review';

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * Company Dossier Renderer
 * Detailed company research report
 */
const renderCompanyDossier = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += `
        <div style="background: #e0e7ff; border-left: 4px solid #667eea; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <strong style="color: #3730a3;">🏢 Company Research Report</strong>
        </div>
    `;
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `Company Dossier: ${research_topic}`;
    const subtitle = 'Comprehensive company analysis and profile';

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * Financial Research Renderer
 * Financial market analysis and insights
 */
const renderFinancialResearch = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += `
        <div style="background: #dcfce7; border-left: 4px solid #16a34a; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <strong style="color: #14532d;">📈 Financial Market Analysis</strong>
        </div>
    `;
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `Financial Research: ${research_topic}`;
    const subtitle = 'Market analysis and investment insights';

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * Financial News Reactive Renderer
 * Rapid response to market movements
 */
const renderFinancialNewsReactive = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += `
        <div style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <strong style="color: #7f1d1d;">📊 Market Alert</strong>
        </div>
    `;
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `Market Alert: ${research_topic}`;
    const subtitle = 'Rapid response to financial developments';

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * News Monitoring Renderer
 * High-volume continuous updates
 */
const renderNewsMonitoring = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `News Monitoring: ${research_topic}`;
    const subtitle = 'Ongoing coverage and updates';

    return createEmailHTML(title, subtitle, contentHTML);
};

/**
 * Research Paper Analysis Renderer
 * Academic research deep dive
 */
const renderResearchPaperAnalysis = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    const sectionsHTML = sections.map(section => markdownToHtml(section)).join('\n');

    let contentHTML = renderMetadata(metadata, research_topic);
    contentHTML += renderDisclaimerBanner();
    contentHTML += `
        <div style="background: #f3e8ff; border-left: 4px solid #9333ea; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <strong style="color: #581c87;">🎓 Academic Research Analysis</strong>
        </div>
    `;
    contentHTML += sectionsHTML;
    contentHTML += renderCitations(citations);

    const title = `Research Paper Analysis: ${research_topic}`;
    const subtitle = 'Academic literature review and synthesis';

    return createEmailHTML(title, subtitle, contentHTML);
};

// ============================================================================
// MAIN ROUTER FUNCTION
// ============================================================================

/**
 * Main rendering function - routes webhook payload to appropriate renderer
 *
 * @param {Object} payload - Webhook payload from research agent API
 * @param {Object} payload.result - Research results
 * @param {Array<string>} payload.result.sections - Markdown sections
 * @param {Array<Object>} payload.result.citations - Citation objects
 * @param {Object} payload.result.metadata - Metadata including strategy_slug
 * @param {string} payload.research_topic - Research topic
 * @param {string} payload.email - User email
 * @returns {string} - Complete HTML email
 */
const renderEmail = (payload) => {
    const strategy_slug = payload.result?.metadata?.strategy_slug || 'daily_news_briefing';

    // Strategy routing map
    const renderers = {
        'daily_news_briefing': renderDailyNewsBriefing,
        'news/real_time_briefing': renderRealTimeNewsBriefing,
        'news_monitoring': renderNewsMonitoring,
        'general/week_overview': renderWeekOverview,
        'company/dossier': renderCompanyDossier,
        'financial_research': renderFinancialResearch,
        'financial_news_reactive': renderFinancialNewsReactive,
        'research_paper_analysis': renderResearchPaperAnalysis,
    };

    // Get renderer or fallback to daily news briefing
    const renderer = renderers[strategy_slug] || renderDailyNewsBriefing;

    return renderer(payload);
};

// ============================================================================
// PLAIN TEXT FALLBACK GENERATOR
// ============================================================================

/**
 * Generate plain text version for email clients that don't support HTML
 */
const generatePlainText = (payload) => {
    const { result, research_topic } = payload;
    const { sections = [], citations = [], metadata = {} } = result;

    let text = `\n${'='.repeat(70)}\n`;
    text += `${research_topic.toUpperCase()}\n`;
    text += `${'='.repeat(70)}\n\n`;

    // Add sections (strip markdown)
    sections.forEach((section, index) => {
        const plainSection = section
            .replace(/\*\*(.+?)\*\*/g, '$1')
            .replace(/\*(.+?)\*/g, '$1')
            .replace(/\[(.+?)\]\((.+?)\)/g, '$1 ($2)')
            .replace(/^#{1,3}\s+/gm, '')
            .trim();

        text += plainSection + '\n\n';
    });

    // Add citations
    if (citations.length > 0) {
        text += `\n${'-'.repeat(70)}\n`;
        text += `SOURCES & CITATIONS\n`;
        text += `${'-'.repeat(70)}\n\n`;

        citations.forEach((citation, index) => {
            text += `[${index + 1}] ${citation.title || 'Untitled'}\n`;
            text += `    ${citation.url}\n`;
            if (citation.snippet) {
                text += `    ${citation.snippet}\n`;
            }
            text += '\n';
        });
    }

    // Add metadata
    text += `\n${'-'.repeat(70)}\n`;
    text += `Generated: ${new Date(metadata.executed_at).toLocaleString()}\n`;
    text += `Strategy: ${metadata.strategy_slug}\n`;
    text += `Sources: ${metadata.evidence_count}\n`;
    text += `${'-'.repeat(70)}\n`;

    return text;
};

// ============================================================================
// EXPORTS (Node.js) OR BROWSER USAGE
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        renderEmail,
        generatePlainText,
        // Export individual renderers for testing
        renderDailyNewsBriefing,
        renderRealTimeNewsBriefing,
        renderWeekOverview,
        renderCompanyDossier,
        renderFinancialResearch,
        renderFinancialNewsReactive,
        renderNewsMonitoring,
        renderResearchPaperAnalysis,
    };
}

// ============================================================================
// USAGE EXAMPLES
// ============================================================================

/*

// Example webhook payload from API
const webhookPayload = {
    "task_id": "uuid",
    "email": "user@example.com",
    "research_topic": "Artificial Intelligence developments",
    "frequency": "daily",
    "status": "completed",
    "result": {
        "sections": [
            "## Executive Summary\n\nMajor AI breakthroughs announced this week...",
            "## Key Developments\n\n• OpenAI releases GPT-5 with improved reasoning\n• Google announces Gemini 2.0..."
        ],
        "citations": [
            {
                "title": "OpenAI Announces GPT-5",
                "url": "https://openai.com/blog/gpt-5",
                "snippet": "OpenAI today announced the release of GPT-5..."
            },
            {
                "title": "Google Gemini 2.0 Launch",
                "url": "https://blog.google/gemini-2",
                "snippet": "Google's latest AI model features..."
            }
        ],
        "metadata": {
            "strategy_slug": "daily_news_briefing",
            "evidence_count": 15,
            "executed_at": "2025-11-05T10:00:00Z"
        }
    }
};

// Generate HTML email
const htmlEmail = renderEmail(webhookPayload);
console.log(htmlEmail);

// Generate plain text fallback
const plainText = generatePlainText(webhookPayload);
console.log(plainText);

// Send via email service (example with Resend)
async function sendEmail(payload) {
    const html = renderEmail(payload);
    const text = generatePlainText(payload);

    await resend.emails.send({
        from: 'research@yourcompany.com',
        to: payload.email,
        subject: `Research Update: ${payload.research_topic}`,
        html: html,
        text: text
    });
}

*/
