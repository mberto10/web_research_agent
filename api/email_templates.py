"""
Email Template Engine for Research Agent API.

Generates professional HTML newsletter emails with authentic FAZ (Frankfurter Allgemeine)
brand typography and styling. Optimized for Outlook compatibility via Power Automate.

Design System (FAZ Brand):
- Primary: #1a1a1a (Cod Gray - FAZ official)
- Accent: #8d7420 (Kumera gold - FAZ official)
- Background: #faf9f7 (warm paper white)
- Typography: Source Serif 4 (headlines) + Source Sans 3 (body)
- Signature elements: Black rules, centered headers, editorial spacing

Source: https://brandfetch.com/faz.net, Strichpunkt Design
"""

import re
from datetime import datetime
from typing import Optional
import markdown2


# =============================================================================
# DESIGN TOKENS (Authentic FAZ Brand System)
# Source: https://brandfetch.com/faz.net, Strichpunkt Design
# =============================================================================

COLORS = {
    "primary": "#1a1a1a",      # Cod Gray - FAZ official primary
    "accent": "#8d7420",       # Kumera gold - FAZ official accent
    "accent_light": "#a89245", # Lighter gold for subtle uses
    "text": "#1a1a1a",         # Body text - matches primary
    "text_secondary": "#5c5c5c", # Muted secondary text, timestamps
    "background": "#faf9f7",   # Warm paper white
    "white": "#ffffff",        # Pure white content areas
    "border": "#e8e6e3",       # Warm gray borders
    "rule": "#1a1a1a",         # Black rules (FAZ signature element)
    "notice_border": "#8d7420", # Gold border for notices
}

# Logo - hosted version (globe with quill)
LOGO_URL = "https://webresearchagent.replit.app/static/logo.png"


# =============================================================================
# STRATEGY TEMPLATE CONFIGURATIONS
# =============================================================================

STRATEGY_TEMPLATES = {
    "news/real_time_briefing": {
        "title_template": "Breaking: {topic}",
        "subtitle_template": "Live updates as of {time}",
        "subject_prefix": "Breaking News:",
        "show_breaking_badge": True
    },
    "company/dossier": {
        "title_template": "Company Dossier: {topic}",
        "subtitle_template": "Comprehensive company analysis",
        "subject_prefix": "Company Report:",
        "show_breaking_badge": False
    },
    "financial_research": {
        "title_template": "Financial Research: {topic}",
        "subtitle_template": "Market analysis and insights",
        "subject_prefix": "Financial Analysis:",
        "show_breaking_badge": False
    },
    "daily_news_briefing": {
        "title_template": "Daily Briefing",
        "subtitle_template": "{topic}",
        "subject_prefix": "Daily Briefing:",
        "show_breaking_badge": False
    },
    "weekly_topic_overview": {
        "title_template": "Weekly Overview: {topic}",
        "subtitle_template": "Key developments this week",
        "subject_prefix": "Weekly Overview:",
        "show_breaking_badge": False
    },
    "company_dossier": {
        "title_template": "Company Update: {topic}",
        "subtitle_template": "Weekly developments",
        "subject_prefix": "Company Update:",
        "show_breaking_badge": False
    },
    "market_dossier": {
        "title_template": "Market Update: {topic}",
        "subtitle_template": "Market developments",
        "subject_prefix": "Market Update:",
        "show_breaking_badge": False
    },
}

DEFAULT_TEMPLATE = {
    "title_template": "Research Update: {topic}",
    "subtitle_template": "AI-powered research insights",
    "subject_prefix": "Research Update:",
    "show_breaking_badge": False
}


# =============================================================================
# MARKDOWN TO HTML CONVERSION
# =============================================================================

def markdown_to_html(markdown_text: str, is_daily_briefing: bool = False) -> str:
    """Convert markdown to HTML with professional inline styling.

    Args:
        markdown_text: Markdown text to convert
        is_daily_briefing: If True, apply special styling for daily briefing sections

    Returns:
        HTML string with inline styles applied
    """
    if not markdown_text:
        return ''

    # Remove stray hash-only lines
    cleaned_lines = []
    for line in markdown_text.splitlines():
        if line.strip() in {"#", "##", "###", "####", "#####", "######"}:
            continue
        cleaned_lines.append(line)
    markdown_text = "\n".join(cleaned_lines)

    # Pre-process: Convert citation numbers [1], [2] to superscript format
    processed_text = re.sub(r'\[(\d+)\]', r'<sup>[\1]</sup>', markdown_text)

    # Convert markdown to HTML
    html = markdown2.markdown(
        processed_text,
        extras=['fenced-code-blocks', 'tables', 'strike', 'task_list']
    )

    # Apply inline styles for email client compatibility
    # Authentic FAZ Typography: Source Serif 4 (headlines) + Source Sans 3 (body)
    # Fallbacks for email clients that don't support Google Fonts

    FONT_SERIF = "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif"
    FONT_SANS = "'Source Sans 3', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

    style_mappings = [
        # H1 - Main title (rarely used in content)
        (r'<h1>', f'<h1 style="color: {COLORS["primary"]}; font-family: {FONT_SERIF}; font-size: 28px; font-weight: 700; margin: 0 0 16px 0; letter-spacing: -0.02em; line-height: 1.2;">'),

        # H2 - Section headers (TOP STORY, BREAKING, etc.) - Black rule above, no colored underline
        (r'<h2>', f'<h2 style="color: {COLORS["primary"]}; font-family: {FONT_SANS}; font-size: 11px; font-weight: 600; margin: 36px 0 16px 0; padding-top: 16px; text-transform: uppercase; letter-spacing: 0.12em; border-top: 2px solid {COLORS["rule"]};">'),

        # H3 - Subsection headers (theme names) - Source Serif, tighter tracking
        (r'<h3>', f'<h3 style="color: {COLORS["primary"]}; font-family: {FONT_SERIF}; font-size: 18px; font-weight: 600; margin: 24px 0 10px 0; letter-spacing: -0.01em; line-height: 1.3;">'),

        # H4 - Minor headers
        (r'<h4>', f'<h4 style="color: {COLORS["primary"]}; font-family: {FONT_SERIF}; font-size: 16px; font-weight: 600; margin: 20px 0 8px 0; line-height: 1.3;">'),

        # Paragraphs - Source Sans, generous line height
        (r'<p>', f'<p style="color: {COLORS["text"]}; font-family: {FONT_SANS}; font-size: 15px; line-height: 1.7; margin: 0 0 16px 0;">'),

        # Lists - clean, no colored bullets
        (r'<ul>', f'<ul style="margin: 0 0 20px 0; padding-left: 0; list-style: none;">'),
        (r'<ol>', f'<ol style="margin: 0 0 20px 0; padding-left: 24px;">'),
        (r'<li>', f'<li style="color: {COLORS["text"]}; font-family: {FONT_SANS}; font-size: 15px; line-height: 1.7; margin-bottom: 12px; padding-left: 0;">'),

        # Links - subtle, professional
        (r'<a href="', f'<a style="color: {COLORS["primary"]}; text-decoration: underline; text-decoration-color: {COLORS["accent"]}; text-underline-offset: 2px;" href="'),

        # Strong/Bold - for headlines within content
        (r'<strong>', f'<strong style="color: {COLORS["primary"]}; font-weight: 600;">'),

        # Emphasis
        (r'<em>', '<em style="font-style: italic;">'),

        # Tables
        (r'<table>', f'<table style="border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14px;">'),
        (r'<th>', f'<th style="border-bottom: 2px solid {COLORS["rule"]}; padding: 10px 12px; background: transparent; text-align: left; font-weight: 600; color: {COLORS["primary"]}; font-family: {FONT_SANS};">'),
        (r'<td>', f'<td style="border-bottom: 1px solid {COLORS["border"]}; padding: 10px 12px; color: {COLORS["text"]}; font-family: {FONT_SANS};">'),

        # Code
        (r'<code>', f'<code style="background: {COLORS["background"]}; padding: 2px 6px; border-radius: 2px; font-family: \'SF Mono\', Monaco, \'Consolas\', monospace; font-size: 13px; color: {COLORS["primary"]};">'),
        (r'<pre>', f'<pre style="background: {COLORS["background"]}; padding: 16px; border-radius: 2px; overflow-x: auto; margin: 20px 0; border: 1px solid {COLORS["border"]};">'),

        # Superscripts (citations) - gold accent, refined
        (r'<sup>', f'<sup style="color: {COLORS["accent"]}; font-weight: 600; font-size: 10px; vertical-align: super; margin-left: 1px;">'),

        # Horizontal rules - black, FAZ signature
        (r'<hr>', f'<hr style="border: none; border-top: 1px solid {COLORS["rule"]}; margin: 28px 0;">'),
        (r'<hr />', f'<hr style="border: none; border-top: 1px solid {COLORS["rule"]}; margin: 28px 0;" />'),
    ]

    for pattern, replacement in style_mappings:
        html = re.sub(pattern, replacement, html)

    # Post-process: Add bullet character for unordered list items (black, not gold)
    html = re.sub(
        r'<li style="([^"]+)">',
        f'<li style="\\1"><span style="color: {COLORS["primary"]}; margin-right: 10px; font-size: 8px; vertical-align: middle;">●</span>',
        html
    )

    return html


# =============================================================================
# CITATION HANDLING
# =============================================================================

def extract_and_number_citations(sections: list, evidence: list) -> tuple:
    """Extract citations from markdown, merge with evidence, assign numbers.

    Args:
        sections: List of markdown section strings
        evidence: List of evidence citation dicts/objects

    Returns:
        tuple: (modified_sections, citations_registry)
    """
    citations_registry = []
    url_to_number = {}

    for section in sections:
        if not section:
            continue

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

    for ev in evidence:
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
            idx = url_to_number[url] - 1
            if not citations_registry[idx]['snippet'] and snippet:
                citations_registry[idx]['snippet'] = snippet
            if not citations_registry[idx]['date'] and date:
                citations_registry[idx]['date'] = date
        else:
            number = len(citations_registry) + 1
            url_to_number[url] = number
            citations_registry.append({
                "number": number,
                "url": url,
                "text": title,
                "snippet": snippet,
                "date": date
            })

    modified_sections = []
    for section in sections:
        if not section:
            modified_sections.append(section)
            continue

        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2).strip()
            number = url_to_number.get(url, '?')
            return f'{link_text}<sup>[{number}]</sup>'

        modified = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', replace_link, section)
        modified_sections.append(modified)

    return modified_sections, citations_registry


def render_citations_html(citations: list) -> str:
    """Render citations as a clean, editorial sources list - FAZ style.

    Args:
        citations: List of citation dicts

    Returns:
        HTML string with sources section
    """
    if not citations:
        return ''

    FONT_SERIF = "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif"
    FONT_SANS = "'Source Sans 3', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

    citation_rows = []
    for citation in citations:
        number = citation.get('number', '?')
        url = citation.get('url', '#')
        date = citation.get('date', '')
        title = citation.get('text', citation.get('title', 'Source'))

        # Extract domain for display (clean format)
        domain = ''
        if url.startswith('http') and len(url.split('/')) > 2:
            domain = url.split('/')[2].replace('www.', '')

        date_str = f'&nbsp;&nbsp;·&nbsp;&nbsp;{date}' if date else ''

        citation_rows.append(f'''
            <tr>
                <td style="padding: 12px 16px 12px 0; vertical-align: top; width: 36px; color: {COLORS["accent"]}; font-weight: 600; font-size: 12px; font-family: {FONT_SANS};">[{number}]</td>
                <td style="padding: 12px 0; vertical-align: top; border-bottom: 1px solid {COLORS["border"]};">
                    <div style="font-family: {FONT_SANS}; font-size: 12px; color: {COLORS["text_secondary"]}; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em;">{domain}{date_str}</div>
                    <a href="{url}" style="font-family: {FONT_SERIF}; font-size: 15px; color: {COLORS["primary"]}; text-decoration: none; font-weight: 500; line-height: 1.4;">{title}</a>
                </td>
            </tr>
        ''')

    return f'''
        <div style="margin-top: 40px;">
            <!-- Double rule top -->
            <div style="border-top: 2px solid {COLORS["rule"]}; margin-bottom: 4px;"></div>
            <div style="border-top: 1px solid {COLORS["rule"]}; margin-bottom: 20px;"></div>

            <h2 style="color: {COLORS["primary"]}; font-family: {FONT_SANS}; font-size: 11px; font-weight: 600; margin: 0 0 20px 0; text-transform: uppercase; letter-spacing: 0.12em;">Quellen</h2>

            <table style="width: 100%; border-collapse: collapse;">
                {''.join(citation_rows)}
            </table>
        </div>
    '''


# =============================================================================
# HEADER COMPONENTS
# =============================================================================

def render_header(
    research_topic: str,
    strategy_slug: str,
    executed_at: str
) -> str:
    """Render the briefing header - centered, symmetrical FAZ editorial style.

    Args:
        research_topic: The research topic
        strategy_slug: Strategy identifier
        executed_at: ISO timestamp

    Returns:
        HTML string for header
    """
    FONT_SERIF = "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif"
    FONT_SANS = "'Source Sans 3', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

    # Format date
    try:
        dt = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%d. %B %Y')
        formatted_time = dt.strftime('%H:%M')
    except (ValueError, AttributeError):
        formatted_date = executed_at
        formatted_time = ""

    return f'''
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 32px;">
            <tr>
                <td align="center" style="padding: 0 0 20px 0;">
                    <!-- Top rule -->
                    <div style="width: 120px; height: 2px; background: {COLORS["rule"]}; margin: 0 auto 20px auto;"></div>

                    <!-- Category label -->
                    <div style="font-family: {FONT_SANS}; font-size: 11px; font-weight: 600; color: {COLORS["text_secondary"]}; text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 12px;">Daily Briefing</div>

                    <!-- Main headline -->
                    <h1 style="font-family: {FONT_SERIF}; font-size: 32px; font-weight: 700; color: {COLORS["primary"]}; margin: 0 0 16px 0; letter-spacing: -0.02em; line-height: 1.15; max-width: 480px;">{research_topic}</h1>

                    <!-- Bottom rule -->
                    <div style="width: 120px; height: 2px; background: {COLORS["rule"]}; margin: 0 auto 16px auto;"></div>

                    <!-- Meta line -->
                    <div style="font-family: {FONT_SANS}; font-size: 12px; color: {COLORS["text_secondary"]}; letter-spacing: 0.02em;">
                        {formatted_date}&nbsp;&nbsp;·&nbsp;&nbsp;{formatted_time} Uhr
                    </div>
                </td>
            </tr>
        </table>
    '''


def render_ai_notice() -> str:
    """Render the AI-generated content notice - subtle, inline, professional.

    Returns:
        HTML string for notice
    """
    FONT_SANS = "'Source Sans 3', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

    return f'''
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 28px;">
            <tr>
                <td align="center">
                    <div style="display: inline-block; border: 1px solid {COLORS["border"]}; padding: 10px 20px; font-family: {FONT_SANS}; font-size: 12px; color: {COLORS["text_secondary"]}; letter-spacing: 0.02em;">
                        <span style="color: {COLORS["accent"]}; margin-right: 6px;">✦</span>
                        KI-generierte Recherche&nbsp;&nbsp;·&nbsp;&nbsp;Quellen prüfen
                    </div>
                </td>
            </tr>
        </table>
    '''


# =============================================================================
# FOOTER
# =============================================================================

def render_footer() -> str:
    """Render the email footer - minimal, centered, elegant.

    Returns:
        HTML string for footer
    """
    FONT_SERIF = "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif"
    FONT_SANS = "'Source Sans 3', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

    return f'''
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top: 48px;">
            <tr>
                <td align="center" style="padding: 24px 0;">
                    <!-- Decorative separator -->
                    <div style="color: {COLORS["text_secondary"]}; font-size: 10px; letter-spacing: 8px; margin-bottom: 20px;">·&nbsp;&nbsp;·&nbsp;&nbsp;·</div>

                    <!-- Brand -->
                    <div style="font-family: {FONT_SERIF}; font-size: 14px; font-weight: 600; color: {COLORS["primary"]}; margin-bottom: 4px;">Web Research Agent</div>
                    <div style="font-family: {FONT_SANS}; font-size: 12px; color: {COLORS["text_secondary"]}; margin-bottom: 16px;">Automatisierte Recherche</div>

                    <!-- Bottom rule -->
                    <div style="width: 80px; height: 1px; background: {COLORS["rule"]}; margin: 0 auto;"></div>
                </td>
            </tr>
        </table>
    '''


# =============================================================================
# COMPLETE EMAIL WRAPPER
# =============================================================================

def create_email_html(research_topic: str, date_str: str, content_html: str) -> str:
    """Wrap content in complete email template - FAZ editorial style.

    Args:
        research_topic: The research topic
        date_str: Date string
        content_html: Main content HTML

    Returns:
        Complete HTML email
    """
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{research_topic} - Daily Briefing</title>
    <!-- Google Fonts: Source Serif 4 + Source Sans 3 (FAZ brand fonts) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600&family=Source+Serif+4:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; background-color: {COLORS["background"]}; }}
        .email-container {{ max-width: 640px; margin: 0 auto; background-color: {COLORS["white"]}; }}
        @media only screen and (max-width: 600px) {{
            .content {{ padding: 24px 20px !important; }}
        }}
    </style>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{ font-family: Georgia, 'Times New Roman', serif !important; }}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: {COLORS["background"]};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLORS["background"]};">
        <tr>
            <td align="center" style="padding: 32px 16px;">
                <table role="presentation" class="email-container" cellspacing="0" cellpadding="0" border="0" style="max-width: 640px; width: 100%; margin: 0 auto; background-color: {COLORS["white"]};">
                    <tr>
                        <td class="content" style="padding: 40px 48px;">
                            {content_html}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''


# =============================================================================
# MAIN RENDERING FUNCTION
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
    """Render a complete HTML newsletter email.

    This is the main function called from the API.

    Args:
        research_topic: The research topic/query
        sections: List of markdown section strings
        citations: List of citation dicts
        strategy_slug: Strategy identifier
        evidence_count: Number of sources analyzed
        executed_at: ISO timestamp
        current_date: Optional date string

    Returns:
        Complete HTML email string
    """
    if not current_date:
        current_date = datetime.utcnow().strftime('%d. %B %Y')

    is_daily_briefing = strategy_slug == 'daily_news_briefing'

    # Build content
    content_parts = []

    # 1. Header with logo, topic, metadata
    header_html = render_header(research_topic, strategy_slug, executed_at)
    content_parts.append(header_html)

    # 2. AI notice
    ai_notice = render_ai_notice()
    content_parts.append(ai_notice)

    # 3. Main content sections
    for section in sections:
        if section:
            section_html = markdown_to_html(section, is_daily_briefing)
            content_parts.append(section_html)

    # 4. Citations/Sources
    citations_html = render_citations_html(citations)
    if citations_html:
        content_parts.append(citations_html)

    # 5. Footer
    footer_html = render_footer()
    content_parts.append(footer_html)

    content_html = '\n'.join(content_parts)

    return create_email_html(research_topic, current_date, content_html)


def generate_strategy_subject_line(
    research_topic: str,
    strategy_slug: str,
    current_date: Optional[str] = None
) -> str:
    """Generate email subject line.

    Args:
        research_topic: The research topic
        strategy_slug: Strategy identifier
        current_date: Optional date string

    Returns:
        Formatted subject line
    """
    template_config = STRATEGY_TEMPLATES.get(strategy_slug, DEFAULT_TEMPLATE)
    prefix = template_config['subject_prefix']

    if not current_date:
        current_date = datetime.utcnow().strftime('%d.%m.%Y')

    if strategy_slug == 'daily_news_briefing':
        return f"{prefix} {research_topic} ({current_date})"

    return f"{prefix} {research_topic}"
