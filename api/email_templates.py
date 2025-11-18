"""
Email Template Engine for Research Agent API.

Generates complete, professional HTML newsletter emails with strategy-specific styling.
Power Automate can directly insert the body field into Outlook without additional processing.
"""

import re
from datetime import datetime
from typing import Optional
import markdown2


# =============================================================================
# STRATEGY TEMPLATE CONFIGURATIONS
# =============================================================================

STRATEGY_TEMPLATES = {
    "news/real_time_briefing": {
        "title_template": "Breaking: {topic}",
        "subtitle_template": "Live updates as of {time}",
        "icon": "🔴",
        "subject_prefix": "🔴 Breaking News:",
        "alert_banner": {
            "background": "#fef3c7",
            "border_color": "#f59e0b",
            "text_color": "#78350f",
            "icon": "⚡",
            "label": "BREAKING NEWS ALERT"
        }
    },
    "company/dossier": {
        "title_template": "Company Dossier: {topic}",
        "subtitle_template": "Comprehensive company analysis and profile",
        "icon": "🏢",
        "subject_prefix": "🏢 Company Report:",
        "alert_banner": {
            "background": "#e0e7ff",
            "border_color": "#667eea",
            "text_color": "#3730a3",
            "icon": "🏢",
            "label": "Company Research Report"
        }
    },
    "financial_research": {
        "title_template": "Financial Research: {topic}",
        "subtitle_template": "Market analysis and investment insights",
        "icon": "📈",
        "subject_prefix": "📈 Financial Analysis:",
        "alert_banner": {
            "background": "#dcfce7",
            "border_color": "#16a34a",
            "text_color": "#14532d",
            "icon": "📈",
            "label": "Financial Market Analysis"
        }
    },
    "financial_news_reactive": {
        "title_template": "Market Alert: {topic}",
        "subtitle_template": "Rapid response to financial developments",
        "icon": "💹",
        "subject_prefix": "💹 Market Alert:",
        "alert_banner": {
            "background": "#fee2e2",
            "border_color": "#dc2626",
            "text_color": "#7f1d1d",
            "icon": "📊",
            "label": "Market Alert"
        }
    },
    "research_paper_analysis": {
        "title_template": "Research Analysis: {topic}",
        "subtitle_template": "Academic literature review and synthesis",
        "icon": "🎓",
        "subject_prefix": "🎓 Research Analysis:",
        "alert_banner": {
            "background": "#f3e8ff",
            "border_color": "#9333ea",
            "text_color": "#581c87",
            "icon": "🎓",
            "label": "Academic Research Analysis"
        }
    },
    "general/week_overview": {
        "title_template": "Weekly Overview: {topic}",
        "subtitle_template": "Your comprehensive week in review",
        "icon": "📅",
        "subject_prefix": "📅 Weekly Overview:",
        "alert_banner": None
    },
    "news_monitoring": {
        "title_template": "News Monitoring: {topic}",
        "subtitle_template": "Ongoing coverage and updates",
        "icon": "📊",
        "subject_prefix": "📊 News Update:",
        "alert_banner": None
    },
    "daily_news_briefing": {
        "title_template": "Daily News Briefing: {topic}",
        "subtitle_template": "{date}",
        "icon": "📰",
        "subject_prefix": "📰 Daily Briefing:",
        "alert_banner": None
    }
}

# Default template for unknown strategies
DEFAULT_TEMPLATE = {
    "title_template": "Research Update: {topic}",
    "subtitle_template": "AI-powered research insights",
    "icon": "🔍",
    "subject_prefix": "🔍 Research Update:",
    "alert_banner": None
}


# =============================================================================
# MARKDOWN TO HTML CONVERSION
# =============================================================================

def markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML with professional inline styling.

    Args:
        markdown_text: Markdown text to convert

    Returns:
        HTML string with inline styles applied
    """
    if not markdown_text:
        return ''

    # Pre-process: Convert citation numbers [1], [2] to superscript format
    # This handles cases where LLM outputs plain [N] instead of markdown links
    processed_text = re.sub(r'\[(\d+)\]', r'<sup>[\1]</sup>', markdown_text)

    # Convert markdown to HTML using markdown2
    html = markdown2.markdown(
        processed_text,
        extras=['fenced-code-blocks', 'tables', 'strike', 'task_list']
    )

    # Apply inline styles for email client compatibility
    style_mappings = [
        # Headers
        (r'<h1>', r'<h1 style="color: #1a202c; font-size: 28px; font-weight: 700; margin: 32px 0 16px 0; padding-bottom: 12px; border-bottom: 3px solid #667eea;">'),
        (r'<h2>', r'<h2 style="color: #2d3748; font-size: 22px; font-weight: 600; margin: 28px 0 14px 0; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0;">'),
        (r'<h3>', r'<h3 style="color: #4a5568; font-size: 18px; font-weight: 600; margin: 20px 0 10px 0;">'),
        (r'<h4>', r'<h4 style="color: #4a5568; font-size: 16px; font-weight: 600; margin: 18px 0 8px 0;">'),

        # Paragraphs
        (r'<p>', r'<p style="color: #4a5568; font-size: 15px; line-height: 1.7; margin: 0 0 16px 0;">'),

        # Lists
        (r'<ul>', r'<ul style="margin: 0 0 20px 0; padding-left: 24px;">'),
        (r'<ol>', r'<ol style="margin: 0 0 20px 0; padding-left: 24px;">'),
        (r'<li>', r'<li style="color: #4a5568; font-size: 15px; line-height: 1.7; margin-bottom: 10px;">'),

        # Links
        (r'<a href="', r'<a style="color: #667eea; text-decoration: none; font-weight: 500;" href="'),

        # Text formatting
        (r'<strong>', r'<strong style="color: #2d3748; font-weight: 600;">'),
        (r'<em>', r'<em style="font-style: italic;">'),

        # Tables
        (r'<table>', r'<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">'),
        (r'<th>', r'<th style="border: 1px solid #e2e8f0; padding: 12px; background: #f7fafc; text-align: left; font-weight: 600;">'),
        (r'<td>', r'<td style="border: 1px solid #e2e8f0; padding: 12px;">'),

        # Code
        (r'<code>', r'<code style="background: #f7fafc; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 14px;">'),
        (r'<pre>', r'<pre style="background: #f7fafc; padding: 16px; border-radius: 6px; overflow-x: auto; margin: 16px 0;">'),

        # Superscripts (for citation numbers)
        (r'<sup>', r'<sup style="color: #667eea; font-weight: 600; font-size: 11px;">'),

        # Horizontal rules (section dividers)
        (r'<hr>', r'<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 32px 0;">'),
        (r'<hr />', r'<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 32px 0;" />'),
    ]

    for pattern, replacement in style_mappings:
        html = re.sub(pattern, replacement, html)

    return html


# =============================================================================
# CITATION EXTRACTION AND NUMBERING
# =============================================================================

def extract_and_number_citations(sections: list, evidence: list) -> tuple:
    """Extract citations from markdown, merge with evidence, assign numbers.

    This function:
    1. Finds all markdown links [text](url) in order of appearance
    2. Merges with evidence citations (deduplicating by URL)
    3. Assigns citation numbers in order of first appearance
    4. Replaces markdown links with text<sup>[N]</sup>

    Args:
        sections: List of markdown section strings
        evidence: List of evidence citation dicts/objects

    Returns:
        tuple: (modified_sections, citations_registry)
        - modified_sections: Sections with links replaced by superscripts
        - citations_registry: List of dicts with {number, url, text, snippet, date}
    """
    # Step 1: Find all markdown links in order of appearance
    citations_registry = []
    url_to_number = {}  # For deduplication: url -> citation_number

    for section in sections:
        if not section:
            continue

        # Find all [text](url) patterns
        for match in re.finditer(r'\[([^\]]+)\]\(([^\)]+)\)', section):
            link_text = match.group(1)
            url = match.group(2).strip()

            if url not in url_to_number:
                number = len(citations_registry) + 1
                url_to_number[url] = number
                citations_registry.append({
                    "number": number,
                    "url": url,
                    "text": link_text,
                    "snippet": None,
                    "date": None
                })

    # Step 2: Merge evidence citations
    for ev in evidence:
        # Handle both dict and object formats
        if isinstance(ev, dict):
            url = ev.get('url', '').strip()
            title = ev.get('title', '')
            snippet = ev.get('snippet', '')
            date = ev.get('date', '')
        else:
            url = getattr(ev, 'url', '').strip()
            title = getattr(ev, 'title', '')
            snippet = getattr(ev, 'snippet', '')
            date = getattr(ev, 'date', '')

        if not url:
            continue

        if url in url_to_number:
            # URL already exists from inline link, add snippet and date
            idx = url_to_number[url] - 1
            if not citations_registry[idx]['snippet'] and snippet:
                citations_registry[idx]['snippet'] = snippet
            if not citations_registry[idx]['date'] and date:
                citations_registry[idx]['date'] = date
        else:
            # New URL from evidence
            number = len(citations_registry) + 1
            url_to_number[url] = number
            citations_registry.append({
                "number": number,
                "url": url,
                "text": title,
                "snippet": snippet,
                "date": date
            })

    # Step 3: Replace markdown links with text + superscript
    modified_sections = []
    for section in sections:
        if not section:
            modified_sections.append(section)
            continue

        modified = section

        # Replace each [text](url) with text<sup>[N]</sup>
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2).strip()
            number = url_to_number.get(url, '?')
            return f'{link_text}<sup>[{number}]</sup>'

        modified = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', replace_link, modified)
        modified_sections.append(modified)

    return modified_sections, citations_registry


# =============================================================================
# CITATION RENDERING
# =============================================================================

def render_citations_html(citations: list) -> str:
    """Render citations as styled HTML cards.

    Args:
        citations: List of citation dicts with {number, url, text, date}

    Returns:
        HTML string with citation section
    """
    if not citations or len(citations) == 0:
        return ''

    citation_items = []

    for citation in citations:
        number = citation.get('number', '?')
        url = citation.get('url', '#')
        date = citation.get('date', '')
        title = citation.get('text', citation.get('title', 'Source'))

        # Build citation card with number, URL, and date
        if date:
            citation_html = f'''
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 12px;">
                <div style="font-size: 15px; font-weight: 600; color: #2d3748; margin: 0 0 8px 0;">[{number}] {title}</div>
                <a href="{url}" style="font-size: 14px; color: #667eea; text-decoration: none; word-break: break-all; display: block; margin-bottom: 8px;">{url}</a>
                <p style="font-size: 14px; color: #718096; line-height: 1.5; margin: 0;">{date}</p>
            </div>
            '''
        else:
            citation_html = f'''
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 12px;">
                <div style="font-size: 15px; font-weight: 600; color: #2d3748; margin: 0 0 8px 0;">[{number}] {title}</div>
                <a href="{url}" style="font-size: 14px; color: #667eea; text-decoration: none; word-break: break-all; display: block;">{url}</a>
            </div>
            '''

        citation_items.append(citation_html)

    citations_html = ''.join(citation_items)

    return f'''
        <div style="background: #f7fafc; padding: 24px; margin: 32px 0; border-radius: 4px;">
            <h2 style="margin-top: 0; color: #2d3748; font-size: 20px; border-bottom: none;">Quellensammlung</h2>
            {citations_html}
        </div>
    '''


# =============================================================================
# METADATA RENDERING
# =============================================================================

def render_metadata_badge(
    research_topic: str,
    strategy_slug: str,
    evidence_count: int,
    executed_at: str
) -> str:
    """Render metadata information as a styled header card.

    Args:
        research_topic: The research topic
        strategy_slug: Strategy identifier
        evidence_count: Number of sources analyzed (not displayed)
        executed_at: ISO timestamp of execution

    Returns:
        HTML string with metadata header card
    """
    # Format the execution time
    try:
        dt = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%A, %B %d, %Y at %I:%M %p')
    except (ValueError, AttributeError):
        formatted_date = executed_at

    return f'''
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 24px 28px; margin: 0 0 32px 0; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);">
            <div style="color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1.3; margin: 0 0 12px 0;">{research_topic}</div>
            <div style="color: rgba(255, 255, 255, 0.9); font-size: 14px; line-height: 1.6;">
                <strong style="color: rgba(255, 255, 255, 0.95);">Strategy:</strong> {strategy_slug}<br>
                <strong style="color: rgba(255, 255, 255, 0.95);">Generated:</strong> {formatted_date}
            </div>
        </div>
    '''


# =============================================================================
# BANNER RENDERING
# =============================================================================

def render_disclaimer_banner() -> str:
    """Render standard AI disclaimer banner for all emails.

    Returns:
        HTML string with disclaimer banner
    """
    return '''
        <div style="background: #f8f9fa; border: 1px solid #dee2e6; border-left: 3px solid #6c757d; padding: 14px 18px; margin-bottom: 28px; border-radius: 4px;">
            <p style="margin: 0; color: #495057; font-size: 14px; line-height: 1.6;">
                <strong style="color: #343a40;">ℹ️ Hinweis:</strong> Dieses Briefing wurde von einem KI-Agenten in Eigenrecherche erstellt und kann Ungenauigkeiten oder Fehler enthalten. Bitte prüfen Sie wenn notwendig alle Quellen sorgfältig und kontaktieren Sie das GenAI Team bei auftretenden Fehlern.
            </p>
        </div>
    '''


def render_alert_banner(banner_config: Optional[dict]) -> str:
    """Render a strategy-specific alert banner.

    Args:
        banner_config: Dict with background, border_color, text_color, icon, label

    Returns:
        HTML string with alert banner or empty string if no banner
    """
    if not banner_config:
        return ''

    return f'''
        <div style="background: {banner_config['background']}; border-left: 4px solid {banner_config['border_color']}; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <strong style="color: {banner_config['text_color']};">{banner_config['icon']} {banner_config['label']}</strong>
        </div>
    '''


# =============================================================================
# LOGO CONFIGURATION
# =============================================================================

# Logo URL - hosted version of the research agent logo
# Can be updated to point to your own hosted logo
LOGO_URL = "https://webresearchagent.replit.app/static/logo.png"


# =============================================================================
# COMPLETE EMAIL TEMPLATE WRAPPER
# =============================================================================

def create_email_html(research_topic: str, date_str: str, content_html: str) -> str:
    """Wrap content in a complete, professional email template.

    This creates a full HTML email with:
    - Email-safe structure (MSO tables, Outlook compatibility)
    - Metadata card serves as the header (no separate header)
    - Professional footer with branding
    - Responsive design for mobile
    - Power Automate paragraph wrapper escape

    Args:
        research_topic: The research topic (not used - shown in metadata card)
        date_str: Date string (not used - shown in metadata card)
        content_html: Main content HTML (includes metadata card as first element)

    Returns:
        Complete HTML email ready for Outlook
    """
    return f'''</p>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{research_topic}</title>
    <style>
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f4f5f7; color: #2d3748; }}
        .email-container {{ max-width: 680px; margin: 0 auto; background-color: #ffffff; }}
        .content {{ padding: 40px 40px 48px 40px; }}
        .footer {{ background: #2d3748; color: #cbd5e0; padding: 32px 40px; text-align: center; }}
        .footer p {{ margin: 6px 0; font-size: 14px; }}
        .footer-brand {{ font-weight: 600; color: #ffffff; font-size: 16px; }}
        @media only screen and (max-width: 600px) {{
            .content {{ padding: 24px !important; }}
            .footer {{ padding: 24px !important; }}
        }}
    </style>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f5f7;">
        <tr>
            <td align="center" style="padding: 24px 0;">
                <table role="presentation" class="email-container" cellspacing="0" cellpadding="0" border="0" style="max-width: 680px; margin: 0 auto; background-color: #ffffff;">
                    <tr>
                        <td class="content" style="padding: 40px 40px 48px 40px;">
                            {content_html}
                        </td>
                    </tr>
                    <tr>
                        <td class="footer" style="background: #2d3748; color: #cbd5e0; padding: 32px 40px; text-align: center;">
                            <p class="footer-brand" style="font-weight: 600; color: #ffffff; font-size: 16px; margin: 6px 0;">Web Research Agent</p>
                            <p style="margin: 6px 0; font-size: 14px;">AI-powered research delivered to your inbox</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
<p>'''


# =============================================================================
# MAIN EMAIL RENDERING FUNCTION
# =============================================================================

def render_complete_email(
    research_topic: str,
    sections: list,
    citations: list,
    strategy_slug: str,
    evidence_count: int,
    executed_at: str,
    current_date: Optional[str] = None
) -> str:
    """Render a complete HTML newsletter email with strategy-specific styling.

    This is the main function that should be called from the API.
    It combines all components into a professional, ready-to-send email.

    Args:
        research_topic: The research topic/query
        sections: List of markdown section strings
        citations: List of citation dicts with {number, url, text, snippet}
        strategy_slug: Strategy identifier for template selection
        evidence_count: Number of sources analyzed
        executed_at: ISO timestamp of execution
        current_date: Optional date string for display

    Returns:
        Complete HTML email string
    """
    # Get strategy-specific template configuration
    template_config = STRATEGY_TEMPLATES.get(strategy_slug, DEFAULT_TEMPLATE)

    # Format current date for display
    if not current_date:
        current_date = datetime.utcnow().strftime('%A, %B %d, %Y')

    # Build content HTML
    content_parts = []

    # 1. Metadata badge (serves as header)
    metadata_badge = render_metadata_badge(
        research_topic, strategy_slug, evidence_count, executed_at
    )
    content_parts.append(metadata_badge)

    # 2. Standard disclaimer banner (appears for all emails)
    disclaimer_banner = render_disclaimer_banner()
    content_parts.append(disclaimer_banner)

    # 3. Alert banner (if applicable for strategy)
    alert_banner = render_alert_banner(template_config.get('alert_banner'))
    if alert_banner:
        content_parts.append(alert_banner)

    # 4. Main content sections (markdown to HTML)
    for section in sections:
        if section:
            section_html = markdown_to_html(section)
            content_parts.append(section_html)

    # 5. Citations
    citations_html = render_citations_html(citations)
    if citations_html:
        content_parts.append(citations_html)

    # Combine all content
    content_html = '\n'.join(content_parts)

    # Wrap in complete email template with simplified header
    # Header now shows: Logo (left) + Research Topic + Date
    return create_email_html(research_topic, current_date, content_html)


def generate_strategy_subject_line(
    research_topic: str,
    strategy_slug: str,
    current_date: Optional[str] = None
) -> str:
    """Generate a strategy-aware email subject line.

    Args:
        research_topic: The research topic
        strategy_slug: Strategy identifier
        current_date: Optional date string

    Returns:
        Formatted subject line with strategy-specific prefix
    """
    template_config = STRATEGY_TEMPLATES.get(strategy_slug, DEFAULT_TEMPLATE)
    prefix = template_config['subject_prefix']

    if not current_date:
        current_date = datetime.utcnow().strftime('%B %d, %Y')

    # For daily briefings, include date in subject
    if strategy_slug == 'daily_news_briefing':
        return f"{prefix} {research_topic} ({current_date})"

    return f"{prefix} {research_topic}"
