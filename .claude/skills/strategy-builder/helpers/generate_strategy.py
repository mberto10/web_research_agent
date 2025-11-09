#!/usr/bin/env python3
"""
Generate Strategy Template

Creates a valid strategy YAML template based on requirements.
Can generate from query analysis or manual parameters.

USAGE:
======
# From query analysis
python3 generate_strategy.py \
  --from-analysis /tmp/query_analysis.json \
  --output /tmp/new_strategy.yaml

# Manual parameters
python3 generate_strategy.py \
  --slug "legal/court_cases_de" \
  --category "legal" \
  --time-window "month" \
  --depth "comprehensive" \
  --required-vars "topic,jurisdiction" \
  --output /tmp/legal_strategy.yaml
"""

import argparse
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any

TOOL_TEMPLATES = {
    'sonar_search': {
        'name': 'sonar_search',
        'params': {
            'max_results': 10,
            'system_prompt': '{{system_prompt}}',
            'search_mode': 'web',
            'search_recency_filter': '{{recency}}',
            'temperature': 0.1,
            'max_tokens': 2000
        }
    },
    'exa_search_semantic': {
        'name': 'exa_search_semantic',
        'params': {
            'num_results': 10,
            'use_autoprompt': True,
            'type': 'neural',
            'start_published_date': '{{start_date}}',
            'end_published_date': '{{end_date}}'
        }
    },
    'exa_search_keyword': {
        'name': 'exa_search_keyword',
        'params': {
            'num_results': 10,
            'type': 'keyword',
            'start_published_date': '{{start_date}}',
            'end_published_date': '{{end_date}}'
        }
    },
    'exa_contents': {
        'name': 'exa_contents',
        'params': {
            'num_results': 5,
            'text': True
        }
    },
    'exa_answer': {
        'name': 'exa_answer',
        'params': {
            'include_source_text': True
        }
    },
    'llm_analyzer': {
        'name': 'llm_analyzer',
        'phase': 'finalize',
        'params': {
            'system_prompt': '{{synthesis_prompt}}',
            'temperature': 0.2,
            'max_tokens': 2500
        }
    }
}

DOMAIN_SUGGESTIONS = {
    'legal': [
        'bundesverfassungsgericht.de',
        'bundesgerichtshof.de',
        'juris.de',
        'beck-online.de'
    ],
    'financial': [
        'bloomberg.com',
        'reuters.com',
        'wsj.com',
        'ft.com',
        'cnbc.com',
        'marketwatch.com'
    ],
    'academic': [
        'arxiv.org',
        'scholar.google.com',
        'pubmed.ncbi.nlm.nih.gov',
        'sciencedirect.com'
    ],
    'technical': [
        'stackoverflow.com',
        'github.com',
        'docs.python.org',
        'developer.mozilla.org'
    ],
    'news': [
        'reuters.com',
        'apnews.com',
        'bbc.com',
        'nytimes.com'
    ]
}


def generate_strategy_yaml(
    slug: str,
    category: str,
    time_window: str,
    depth: str,
    required_vars: List[str],
    tools: List[str],
    language: str = 'en',
    domain_hints: List[str] = None
) -> str:
    """Generate strategy YAML content."""

    # Build metadata
    meta = {
        'slug': slug,
        'version': 1,
        'category': category,
        'time_window': time_window,
        'depth': depth
    }

    # Build queries
    queries = {}
    topic_var = required_vars[0] if required_vars else 'topic'
    if 'sonar' in tools or 'sonar_search' in tools:
        queries['sonar'] = f"{{{{{topic_var}}}}} {category} research"
    if 'exa' in tools or 'exa_search_semantic' in tools:
        queries['exa_search'] = f"{{{{{topic_var}}}}} {category}"

    # Build tool chain
    tool_chain = []
    for i, tool in enumerate(tools, 1):
        tool_name = tool.replace('_', ' ').title().replace(' ', '')

        if tool in ['sonar', 'sonar_search']:
            # Build system prompt based on category
            if category == 'legal':
                system_prompt = "You are a legal research assistant. Focus on court cases, legislation, legal precedents, and statutory references."
            elif category == 'financial':
                system_prompt = "You are a financial analyst. Focus on quantitative data, market movements, earnings reports, and financial metrics."
            elif category == 'academic':
                system_prompt = "You are an academic researcher. Focus on peer-reviewed papers, research methodology, and scholarly citations."
            elif category == 'technical':
                system_prompt = "You are a technical documentation expert. Focus on implementation details, code examples, and best practices."
            else:
                system_prompt = f"You are a {category} research specialist. Provide comprehensive, factual information."

            tool_step = {
                'name': f'sonar_{category}',
                'params': {
                    'max_results': 10 if depth in ['brief', 'overview'] else 15,
                    'system_prompt': system_prompt,
                    'search_mode': 'web',
                    'search_recency_filter': time_window,
                    'temperature': 0.1,
                    'max_tokens': 2000
                }
            }

            # Add domain filter if available
            if domain_hints or category in DOMAIN_SUGGESTIONS:
                domains = domain_hints or DOMAIN_SUGGESTIONS.get(category, [])
                tool_step['params']['search_domain_filter'] = domains

            tool_chain.append(tool_step)

        elif tool in ['exa_search_semantic', 'exa_search_keyword']:
            tool_step = {
                'name': tool,
                'params': {
                    'num_results': 10 if depth in ['brief', 'overview'] else 15,
                    'use_autoprompt': True,
                    'type': 'neural' if 'semantic' in tool else 'keyword',
                    'start_published_date': '{{start_date}}',
                    'end_published_date': '{{end_date}}'
                }
            }

            # Add domain inclusions
            if domain_hints:
                tool_step['params']['include_domains'] = domain_hints[:5]  # Limit to 5

            tool_chain.append(tool_step)

        elif tool == 'exa_contents':
            tool_chain.append({
                'name': 'exa_contents',
                'params': {
                    'num_results': 5,
                    'text': True
                }
            })

        elif tool == 'exa_answer':
            tool_chain.append({
                'name': 'exa_answer',
                'params': {
                    'include_source_text': True
                }
            })

        elif tool in ['llm_analyzer', 'llm_synthesis']:
            # Build synthesis prompt
            if category == 'legal':
                synthesis = "Create a legal analysis with: 1) Legal Summary, 2) Relevant Cases, 3) Statutory Basis, 4) Practice Notes, 5) Sources"
            elif category == 'financial':
                synthesis = "Create a financial briefing with: 1) Market Summary, 2) Key Financial News, 3) Earnings & Metrics, 4) Analyst Views, 5) Sources"
            elif category == 'academic':
                synthesis = "Create a research summary with: 1) Overview, 2) Key Findings, 3) Methodology, 4) Implications, 5) Citations"
            else:
                synthesis = f"Create a comprehensive {category} report with relevant sections and sources"

            tool_chain.append({
                'name': 'llm_analyzer',
                'phase': 'finalize',
                'params': {
                    'system_prompt': synthesis,
                    'temperature': 0.2,
                    'max_tokens': 2500
                }
            })

    # Limits
    max_results_map = {
        'brief': 10,
        'overview': 15,
        'deep': 20,
        'comprehensive': 25
    }
    limits = {
        'max_results': max_results_map.get(depth, 20),
        'max_llm_queries': 2 if depth in ['brief', 'overview'] else 3
    }

    # Build complete strategy
    strategy = {
        'meta': meta,
        'queries': queries,
        'tool_chain': tool_chain,
        'limits': limits
    }

    # Convert to YAML
    yaml_content = yaml.dump(strategy, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return yaml_content


def main():
    parser = argparse.ArgumentParser(
        description='Generate strategy YAML template',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From analysis
  %(prog)s --from-analysis /tmp/query_analysis.json

  # Manual
  %(prog)s --slug "legal/court_cases" --category "legal" --time-window "month" --depth "deep" --required-vars "topic,jurisdiction"
        """
    )

    # Input mode
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--from-analysis', help='Path to query analysis JSON file')
    input_group.add_argument('--slug', help='Strategy slug (e.g., "legal/court_cases")')

    # Manual parameters (required if --slug is used)
    manual_group = parser.add_argument_group('Manual Parameters (required with --slug)')
    manual_group.add_argument('--category', help='Strategy category')
    manual_group.add_argument('--time-window', choices=['day', 'week', 'month', 'year'], help='Time window')
    manual_group.add_argument('--depth', choices=['brief', 'overview', 'deep', 'comprehensive'], help='Research depth')
    manual_group.add_argument('--required-vars', help='Comma-separated required variables')
    manual_group.add_argument('--tools', help='Comma-separated tool list (e.g., "sonar_search,exa_search_semantic,llm_analyzer")')
    manual_group.add_argument('--language', default='en', help='Language code (en, de, es, fr)')
    manual_group.add_argument('--domains', help='Comma-separated domain hints')

    # Output
    parser.add_argument('--output', default='/tmp/strategy_analysis/generated_strategy.yaml',
                       help='Output file path')

    args = parser.parse_args()

    try:
        # Load parameters
        if args.from_analysis:
            # From analysis file
            with open(args.from_analysis, 'r') as f:
                analysis = json.load(f)

            slug = analysis.get('suggested_slug', 'custom/research')
            classification = analysis['classification']
            category = classification['category']
            time_window = classification['time_window']
            depth = classification['depth']
            language = classification.get('language', 'en')
            required_vars = [v['name'] for v in classification.get('required_variables', [])]
            tools = classification.get('suggested_tools', ['sonar_search', 'exa_search_semantic', 'llm_analyzer'])
            domain_hints = classification.get('domain_hints', [])

        else:
            # From manual parameters
            if not all([args.category, args.time_window, args.depth]):
                parser.error("--category, --time-window, and --depth are required when using --slug")

            slug = args.slug
            category = args.category
            time_window = args.time_window
            depth = args.depth
            language = args.language
            required_vars = args.required_vars.split(',') if args.required_vars else ['topic']
            tools = args.tools.split(',') if args.tools else ['sonar_search', 'exa_search_semantic', 'llm_analyzer']
            domain_hints = args.domains.split(',') if args.domains else []

        # Generate strategy
        print(f"Generating strategy: {slug}")
        print(f"  Category: {category}")
        print(f"  Time window: {time_window}")
        print(f"  Depth: {depth}")
        print(f"  Tools: {', '.join(tools)}")

        yaml_content = generate_strategy_yaml(
            slug=slug,
            category=category,
            time_window=time_window,
            depth=depth,
            required_vars=required_vars,
            tools=tools,
            language=language,
            domain_hints=domain_hints if domain_hints else None
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(yaml_content)

        print(f"\n✓ Strategy template generated: {output_path}")
        print("\nNext steps:")
        print(f"  1. Review and customize: {output_path}")
        print(f"  2. Validate: python3 validate_strategy.py --strategy {output_path}")
        print(f"  3. Save to: /home/user/web_research_agent/strategies/{slug.replace('/', '_')}.yaml")
        print(f"  4. Add to index.yaml")
        print(f"  5. Migrate to database: python scripts/migrate_strategies.py")

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
