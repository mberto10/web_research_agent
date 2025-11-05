#!/usr/bin/env python3
"""
Filter observations to keep only essential data for config optimization.

This module strips bloat from Langfuse observation data while preserving
essential inputs/outputs needed for analyzing style.yaml, template.yaml,
and tools.yaml configurations.

Key reductions:
- Replace large facts_pack (391KB+) with summary
- Replace validation_report (45KB+) with summary
- Strip unnecessary metadata fields
- Keep core node inputs/outputs intact

Expected size reduction: 95% (4.2MB → ~200KB)
"""

import json
import sys
from typing import Any, Dict, List


def get_size_bytes(obj: Any) -> int:
    """Calculate approximate size of an object in bytes."""
    try:
        return len(json.dumps(obj, default=str))
    except Exception:
        return 0


def summarize_facts_pack(facts_pack: Any) -> Dict[str, Any]:
    """Replace large facts_pack with a compact summary."""
    if not facts_pack:
        return None

    if isinstance(facts_pack, str):
        try:
            facts_pack = json.loads(facts_pack)
        except Exception:
            return {"type": "string", "size_bytes": len(facts_pack)}

    if isinstance(facts_pack, dict):
        facts = facts_pack.get('facts', [])
        return {
            "facts_count": len(facts),
            "total_size_bytes": get_size_bytes(facts_pack),
            "fact_summaries": [
                {
                    "source": fact.get('source', 'unknown'),
                    "size_bytes": get_size_bytes(fact.get('content', ''))
                }
                for fact in facts[:5]  # Keep summary of first 5 facts
            ]
        }

    return {"type": type(facts_pack).__name__, "size_bytes": get_size_bytes(facts_pack)}


def summarize_validation_report(validation_report: Any) -> Dict[str, Any]:
    """Replace large validation_report with a compact summary."""
    if not validation_report:
        return None

    if isinstance(validation_report, str):
        try:
            validation_report = json.loads(validation_report)
        except Exception:
            return {"type": "string", "size_bytes": len(validation_report)}

    if isinstance(validation_report, dict):
        checks = validation_report.get('checks', [])
        return {
            "checks_count": len(checks),
            "total_size_bytes": get_size_bytes(validation_report),
            "failed_checks": [
                check.get('name', 'unknown')
                for check in checks
                if not check.get('passed', True)
            ][:10]  # Keep first 10 failed check names
        }

    return {"type": type(validation_report).__name__, "size_bytes": get_size_bytes(validation_report)}


def summarize_long_text(text: str, max_chars: int = 200) -> Dict[str, Any]:
    """Summarize long text fields with metadata."""
    if not isinstance(text, str):
        return text

    return {
        "length": len(text),
        "word_count": len(text.split()),
        "preview": text[:max_chars] + ("..." if len(text) > max_chars else "")
    }


def summarize_structured_citations(citations: Any) -> Dict[str, Any]:
    """
    Replace large citation list with compact summary.

    Reduces ~34KB of full citation objects to ~450 bytes of useful metadata.
    Keeps: counts, source breakdown, domain list, tools used, fact support count.
    """
    if not citations or not isinstance(citations, list):
        return None

    summary = {
        'total_count': len(citations),
        'total_size_bytes': get_size_bytes(citations),
        'sources': {},  # {source_type: count}
        'domains': [],  # Unique domains
        'tools': [],    # Tools that generated citations
        'fact_support_count': 0
    }

    domains = set()
    tools = set()

    for c in citations:
        # Count by source
        source = c.get('source', 'unknown')
        summary['sources'][source] = summary['sources'].get(source, 0) + 1

        # Extract domain from URL
        url = c.get('url', '')
        if url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                if domain:
                    domains.add(domain)
            except:
                pass

        # Extract tool from provenance
        provenance = c.get('provenance', {})
        if isinstance(provenance, dict):
            tool = provenance.get('tool_name')
            if tool:
                tools.add(tool)

        # Count fact support
        supports_facts = c.get('supports_facts', [])
        if isinstance(supports_facts, list):
            summary['fact_support_count'] += len(supports_facts)

    summary['domains'] = sorted(list(domains))
    summary['tools'] = sorted(list(tools))

    return summary


def summarize_step_status(steps: Any) -> Dict[str, Any]:
    """
    Replace large step execution log with compact summary.

    Reduces ~8KB of detailed step logs to ~250 bytes of useful metadata.
    Keeps: counts, success/failure breakdown, tools used, citation counts.
    """
    if not steps or not isinstance(steps, list):
        return None

    summary = {
        'total_count': len(steps),
        'total_size_bytes': get_size_bytes(steps),
        'success_count': 0,
        'failure_count': 0,
        'tools_used': [],
        'total_citation_count': 0
    }

    tools = set()

    for s in steps:
        # Success/failure tracking
        if s.get('success'):
            summary['success_count'] += 1
        else:
            summary['failure_count'] += 1

        # Tool tracking
        tool = s.get('registry', 'unknown')
        if tool:
            tools.add(tool)

        # Citation count
        citation_count = s.get('structured_citation_count', 0)
        if citation_count:
            summary['total_citation_count'] += citation_count

    summary['tools_used'] = sorted(list(tools))

    return summary


def filter_input_output(data: Any, field_name: str, filter_research_details: bool = False) -> Any:
    """
    Filter input or output field, stripping bloat while keeping essential data.

    Args:
        data: Input/output data to filter
        field_name: Name of the field being filtered (for logging)
        filter_research_details: If True, also filter structured_citations and step_status

    Returns:
        Filtered data with bloat replaced by summaries
    """
    if not data:
        return data

    # Handle string-encoded JSON
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            # Not JSON, keep as-is (but check if it's a long text)
            if len(data) > 500:
                return summarize_long_text(data)
            return data

    # If not a dict, keep as-is
    if not isinstance(data, dict):
        return data

    # Create filtered copy
    filtered = {}

    # Long text fields to summarize (not needed for config analysis)
    long_text_fields = {'draft', 'final_article', 'edited_article', 'mainbody', 'article', 'content'}

    for key, value in data.items():
        # Always filter these (essential filtering)
        if key == 'facts_pack':
            filtered[key] = summarize_facts_pack(value)
        elif key == 'validation_report':
            filtered[key] = summarize_validation_report(value)
        # Conditionally filter research data
        elif filter_research_details and key == 'structured_citations':
            filtered[key] = summarize_structured_citations(value)
        elif filter_research_details and key == 'step_status':
            filtered[key] = summarize_step_status(value)
        # Summarize long text fields (draft, final_article, etc.)
        elif key in long_text_fields and isinstance(value, str) and len(value) > 500:
            filtered[key] = summarize_long_text(value)
        # Handle nested structures that might contain bloat
        elif isinstance(value, dict):
            # Recursively check nested dicts
            if 'facts_pack' in value or 'validation_report' in value or \
               (filter_research_details and ('structured_citations' in value or 'step_status' in value)) or \
               any(k in long_text_fields for k in value.keys()):
                filtered[key] = filter_input_output(value, f"{field_name}.{key}", filter_research_details)
            else:
                filtered[key] = value
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Check if list items contain bloat
            if any('facts_pack' in item or 'validation_report' in item or \
                   (filter_research_details and ('structured_citations' in item or 'step_status' in item)) \
                   for item in value):
                filtered[key] = [filter_input_output(item, f"{field_name}.{key}[]", filter_research_details) for item in value]
            else:
                filtered[key] = value
        else:
            # Keep primitive values as-is
            filtered[key] = value

    return filtered


def filter_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only essential metadata fields."""
    if not metadata:
        return metadata

    # Fields to keep
    keep_fields = {
        'langgraph_step',
        'langgraph_node',
        'topic',
        'style_id',
        'case_id',
        'profile_name',
        'workflow_version',
        'ticker',
        'audience'
    }

    filtered = {}

    for key, value in metadata.items():
        if key in keep_fields:
            filtered[key] = value

    return filtered


def filter_observation_essential(observation: Dict[str, Any], filter_research_details: bool = False) -> Dict[str, Any]:
    """
    Filter a single observation to keep only essential data.

    Keeps:
    - Core identifiers (id, name, type, trace_id, etc.)
    - Start/end times
    - Essential metadata (langgraph_step, topic, style_id, etc.)
    - Input/output with bloat stripped

    Removes:
    - facts_pack (replaced with summary)
    - validation_report (replaced with summary)
    - structured_citations (if filter_research_details=True, replaced with summary)
    - step_status (if filter_research_details=True, replaced with summary)
    - resourceAttributes, scope
    - Extra langgraph metadata

    Args:
        observation: Raw observation dict from Langfuse
        filter_research_details: If True, also filter structured_citations and step_status

    Returns:
        Filtered observation dict with ~95% size reduction (or ~99% with filter_research_details=True)
    """
    filtered = {}

    # Core fields (always keep)
    core_fields = [
        'id', 'name', 'type', 'trace_id', 'parent_observation_id',
        'start_time', 'end_time', 'level', 'status_message'
    ]

    for field in core_fields:
        if field in observation:
            filtered[field] = observation[field]

    # Filter input/output
    if 'input' in observation:
        filtered['input'] = filter_input_output(observation['input'], 'input', filter_research_details)

    if 'output' in observation:
        filtered['output'] = filter_input_output(observation['output'], 'output', filter_research_details)

    # Filter metadata
    if 'metadata' in observation:
        filtered['metadata'] = filter_metadata(observation['metadata'])

    return filtered


def filter_observations_list(observations: List[Dict[str, Any]], filter_research_details: bool = False) -> List[Dict[str, Any]]:
    """
    Filter a list of observations to keep only essential data.

    Args:
        observations: List of raw observation dicts
        filter_research_details: If True, also filter structured_citations and step_status

    Returns:
        List of filtered observation dicts
    """
    return [filter_observation_essential(obs, filter_research_details) for obs in observations]


def filter_observations_payload(payload: Dict[str, Any], filter_research_details: bool = False) -> Dict[str, Any]:
    """
    Filter observation payload structure (from retrieve_observations.py output).

    Args:
        payload: Dict with 'observations', 'total_observations', 'trace_ids' keys
        filter_research_details: If True, also filter structured_citations and step_status

    Returns:
        Filtered payload with same structure
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dict")

    filtered = {
        'total_observations': payload.get('total_observations', 0),
        'trace_ids': payload.get('trace_ids', [])
    }

    if 'observations' in payload:
        observations = payload['observations']
        filtered['observations'] = filter_observations_list(observations, filter_research_details)

    return filtered


def filter_bundle(bundle: Dict[str, Any], filter_research_details: bool = False) -> Dict[str, Any]:
    """
    Filter bundle structure (from retrieve_traces_and_observations.py output).

    Args:
        bundle: Dict with traces, observations, query metadata
        filter_research_details: If True, also filter structured_citations and step_status

    Returns:
        Filtered bundle with same structure
    """
    if not isinstance(bundle, dict):
        raise ValueError("Bundle must be a dict")

    filtered = {
        'generated_at': bundle.get('generated_at'),
        'query': bundle.get('query'),
        'trace_count': bundle.get('trace_count', 0),
        'trace_ids': bundle.get('trace_ids', []),
        'traces': bundle.get('traces', [])  # Traces don't need filtering
    }

    # Filter observations if present
    if 'observations' in bundle and bundle['observations']:
        obs_data = bundle['observations']

        if isinstance(obs_data, dict):
            filtered_obs = {
                'total_observations': obs_data.get('total_observations', 0)
            }

            # Filter observations grouped by trace
            if 'by_trace' in obs_data:
                filtered_obs['by_trace'] = {
                    trace_id: filter_observations_list(obs_list, filter_research_details)
                    for trace_id, obs_list in obs_data['by_trace'].items()
                }

            filtered['observations'] = filtered_obs
        else:
            filtered['observations'] = None
    else:
        filtered['observations'] = bundle.get('observations')

    return filtered


def main():
    """CLI for filtering observation files."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Filter observations to keep only essential data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Filter observations file
  %(prog)s --input observations.json --output filtered_observations.json

  # Filter bundle file
  %(prog)s --input bundle.json --output filtered_bundle.json --type bundle
"""
    )

    parser.add_argument('--input', required=True, help='Input JSON file path')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--type', choices=['payload', 'bundle'], default='payload',
                       help='Input file type (default: payload)')

    args = parser.parse_args()

    # Load input
    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter based on type
    try:
        if args.type == 'bundle':
            filtered = filter_bundle(data)
        else:
            filtered = filter_observations_payload(data)
    except Exception as e:
        print(f"Error filtering data: {e}", file=sys.stderr)
        sys.exit(1)

    # Save output
    try:
        with open(args.output, 'w') as f:
            json.dump(filtered, f, indent=2, default=str)
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Report size reduction
    input_size = get_size_bytes(data)
    output_size = get_size_bytes(filtered)
    reduction_pct = ((input_size - output_size) / input_size * 100) if input_size > 0 else 0

    print(f"✓ Filtering complete")
    print(f"  Input size: {input_size:,} bytes ({input_size / 1024 / 1024:.2f} MB)")
    print(f"  Output size: {output_size:,} bytes ({output_size / 1024:.2f} KB)")
    print(f"  Reduction: {reduction_pct:.1f}%")
    print(f"  Output: {args.output}")


if __name__ == '__main__':
    main()
