#!/usr/bin/env python3
"""
Langfuse Trace Fetcher and Analyzer
Retrieves batch execution traces and performs architecture + quality analysis.
"""

import argparse
import json
import os
import sys
import requests
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict


def get_langfuse_credentials() -> Tuple[str, str, str]:
    """Get Langfuse credentials from environment."""
    public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
    secret_key = os.getenv('LANGFUSE_SECRET_KEY')
    host = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')

    if not public_key or not secret_key:
        print("ERROR: Missing Langfuse credentials", file=sys.stderr)
        print("Required: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY", file=sys.stderr)
        sys.exit(1)

    return public_key, secret_key, host


def get_auth_headers(public_key: str, secret_key: str) -> Dict[str, str]:
    """Generate basic auth headers for Langfuse API."""
    credentials = f"{public_key}:{secret_key}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/json'
    }


def query_traces_with_filters(
    host: str,
    headers: Dict[str, str],
    from_timestamp: Optional[str] = None,
    tags: Optional[List[str]] = None,
    session_ids: Optional[List[str]] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Query Langfuse traces using advanced filters.

    Args:
        host: Langfuse host URL
        headers: Auth headers
        from_timestamp: Start timestamp (ISO 8601)
        tags: List of tags to filter by
        session_ids: List of session IDs (task IDs)
        limit: Max number of traces to retrieve

    Returns:
        List of trace dictionaries
    """
    endpoint = f"{host.rstrip('/')}/api/public/traces"

    # Build filters
    filters = []

    # Tag filters (AND logic - trace must have all tags)
    if tags:
        for tag in tags:
            filters.append({
                "column": "tags",
                "operator": "contains",
                "value": tag,
                "type": "string"
            })

    # Timestamp filter
    if from_timestamp:
        filters.append({
            "column": "timestamp",
            "operator": ">=",
            "value": from_timestamp,
            "type": "datetime"
        })

    # Session ID filter (if provided)
    if session_ids:
        filters.append({
            "column": "session_id",
            "operator": "in",
            "value": session_ids,
            "type": "string"
        })

    params = {
        'limit': limit,
        'page': 1
    }

    if filters:
        params['filter'] = json.dumps(filters)

    print(f"Querying Langfuse traces...")
    print(f"  Endpoint: {endpoint}")
    print(f"  Filters: {len(filters)} filter(s) applied")
    if tags:
        print(f"  Tags: {', '.join(tags)}")
    if from_timestamp:
        print(f"  From: {from_timestamp}")
    if session_ids:
        print(f"  Session IDs: {len(session_ids)} ID(s)")

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        traces = data.get('data', [])

        print(f"\n✓ Retrieved {len(traces)} trace(s)")

        return traces

    except requests.exceptions.RequestException as e:
        print(f"\n✗ Failed to query traces: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def get_trace_details(host: str, headers: Dict[str, str], trace_id: str) -> Dict[str, Any]:
    """
    Get full trace details including observations.

    Args:
        host: Langfuse host URL
        headers: Auth headers
        trace_id: Trace ID

    Returns:
        Trace details dictionary
    """
    endpoint = f"{host.rstrip('/')}/api/public/traces/{trace_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to get details for trace {trace_id}: {e}", file=sys.stderr)
        return {}


def get_trace_observations(host: str, headers: Dict[str, str], trace_id: str) -> List[Dict[str, Any]]:
    """
    Get all observations for a trace.

    Args:
        host: Langfuse host URL
        headers: Auth headers
        trace_id: Trace ID

    Returns:
        List of observation dictionaries
    """
    endpoint = f"{host.rstrip('/')}/api/public/observations"

    params = {
        'traceId': trace_id,
        'limit': 100
    }

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to get observations for trace {trace_id}: {e}", file=sys.stderr)
        return []


def analyze_architecture(trace: Dict[str, Any], observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze trace architecture for completeness and correctness.

    Args:
        trace: Trace dictionary
        observations: List of observations

    Returns:
        Architecture analysis result
    """
    expected_nodes = ['router', 'research', 'write', 'edit']
    found_nodes = []
    errors = []
    warnings = []

    # Extract node names from observations
    for obs in observations:
        name = obs.get('name', '')
        if name:
            found_nodes.append(name)

        # Check for errors
        level = obs.get('level')
        if level == 'ERROR':
            errors.append({
                'observation': name,
                'message': obs.get('statusMessage', 'Unknown error')
            })

    # Check node coverage
    missing_nodes = []
    for expected in expected_nodes:
        # Check if any observation name contains the expected node name
        if not any(expected in node.lower() for node in found_nodes):
            missing_nodes.append(expected)

    # Check metadata completeness
    metadata = trace.get('metadata', {})
    required_metadata = ['task_id', 'frequency']
    missing_metadata = [key for key in required_metadata if key not in metadata]

    if missing_metadata:
        warnings.append(f"Missing metadata: {', '.join(missing_metadata)}")

    # Check tags
    tags = trace.get('tags', [])
    expected_tags = ['batch_execution']
    missing_tags = [tag for tag in expected_tags if tag not in tags]

    if missing_tags:
        warnings.append(f"Missing tags: {', '.join(missing_tags)}")

    # Determine status
    status = 'PASS'
    if errors or missing_nodes:
        status = 'FAIL'
    elif warnings:
        status = 'WARNING'

    return {
        'status': status,
        'nodes_found': list(set(found_nodes)),
        'missing_nodes': missing_nodes,
        'metadata_complete': len(missing_metadata) == 0,
        'tags': tags,
        'observation_count': len(observations),
        'errors': errors,
        'warnings': warnings
    }


def analyze_quality(trace: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze result quality based on output structure and content.

    Args:
        trace: Trace dictionary

    Returns:
        Quality analysis result
    """
    output = trace.get('output', {})
    issues = []

    # Extract result data
    result = output.get('result', {}) if isinstance(output, dict) else {}
    sections = result.get('sections', []) if isinstance(result, dict) else []
    citations = result.get('citations', []) if isinstance(result, dict) else []
    metadata = result.get('metadata', {}) if isinstance(result, dict) else {}

    # Check sections
    sections_count = len(sections) if isinstance(sections, list) else 0
    if sections_count == 0:
        issues.append("No sections in output")
    elif sections_count < 2:
        issues.append(f"Only {sections_count} section (expected 2+)")

    # Check citations
    citations_count = len(citations) if isinstance(citations, list) else 0
    if citations_count == 0:
        issues.append("No citations in output")
    elif citations_count < 3:
        issues.append(f"Only {citations_count} citations (expected 3-10)")
    elif citations_count > 10:
        issues.append(f"Too many citations: {citations_count} (expected 3-10)")

    # Analyze section content
    avg_section_words = 0
    if sections and isinstance(sections, list):
        total_words = 0
        for section in sections:
            if isinstance(section, dict):
                content = section.get('content', '')
                if isinstance(content, str):
                    total_words += len(content.split())
        if sections_count > 0:
            avg_section_words = total_words // sections_count

    if avg_section_words > 0 and avg_section_words < 100:
        issues.append(f"Thin content: avg {avg_section_words} words/section (expected >100)")

    # Check performance
    latency_ms = trace.get('latency')
    if latency_ms:
        if latency_ms > 90000:
            issues.append(f"Slow performance: {latency_ms/1000:.1f}s (expected <90s)")
        elif latency_ms > 60000:
            issues.append(f"Performance warning: {latency_ms/1000:.1f}s (target <60s)")

    # Determine quality status
    if not issues:
        status = 'HIGH'
    elif len(issues) <= 2:
        status = 'MEDIUM'
    else:
        status = 'LOW'

    # Override to LOW if critical issues
    if sections_count == 0 or citations_count == 0:
        status = 'LOW'

    return {
        'status': status,
        'sections_count': sections_count,
        'citations_count': citations_count,
        'avg_section_words': avg_section_words,
        'total_latency_ms': latency_ms,
        'strategy_slug': metadata.get('strategy_slug') if isinstance(metadata, dict) else None,
        'issues': issues
    }


def generate_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics across all traces.

    Args:
        results: List of analyzed trace results

    Returns:
        Summary dictionary
    """
    total = len(results)
    arch_pass = sum(1 for r in results if r['architecture']['status'] == 'PASS')
    arch_fail = sum(1 for r in results if r['architecture']['status'] == 'FAIL')
    arch_warning = sum(1 for r in results if r['architecture']['status'] == 'WARNING')

    quality_high = sum(1 for r in results if r['quality']['status'] == 'HIGH')
    quality_medium = sum(1 for r in results if r['quality']['status'] == 'MEDIUM')
    quality_low = sum(1 for r in results if r['quality']['status'] == 'LOW')

    # Collect all issues
    all_warnings = []
    all_errors = []

    for r in results:
        for warning in r['architecture'].get('warnings', []):
            all_warnings.append(f"[{r['trace_id']}] {warning}")
        for error in r['architecture'].get('errors', []):
            all_errors.append(f"[{r['trace_id']}] {error}")
        for issue in r['quality'].get('issues', []):
            all_warnings.append(f"[{r['trace_id']}] {issue}")

    return {
        'total_traces': total,
        'architecture_pass': arch_pass,
        'architecture_fail': arch_fail,
        'architecture_warning': arch_warning,
        'quality_high': quality_high,
        'quality_medium': quality_medium,
        'quality_low': quality_low,
        'warnings': all_warnings,
        'errors': all_errors
    }


def generate_recommendations(summary: Dict[str, Any]) -> List[str]:
    """
    Generate actionable recommendations based on analysis.

    Args:
        summary: Summary statistics

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Architecture recommendations
    if summary['architecture_fail'] == 0:
        recommendations.append("✓ All traces passed architecture validation")
    else:
        recommendations.append(
            f"⚠ {summary['architecture_fail']}/{summary['total_traces']} traces failed architecture validation - review errors"
        )

    # Quality recommendations
    if summary['quality_high'] >= summary['total_traces'] * 0.8:
        recommendations.append(
            f"✓ Quality is consistently high ({summary['quality_high']}/{summary['total_traces']} HIGH)"
        )
    elif summary['quality_low'] > 0:
        recommendations.append(
            f"⚠ {summary['quality_low']} trace(s) have LOW quality - investigate content generation"
        )

    # Specific issues
    if summary['warnings']:
        recommendations.append(
            f"⚠ {len(summary['warnings'])} warning(s) detected - review details"
        )

    if summary['errors']:
        recommendations.append(
            f"✗ {len(summary['errors'])} error(s) detected - immediate attention required"
        )

    # Overall status
    if summary['architecture_fail'] == 0 and summary['quality_low'] == 0:
        recommendations.append("✓ System is healthy and ready for optimization")
    else:
        recommendations.append("⚠ Address issues before proceeding to optimization")

    return recommendations


def main():
    parser = argparse.ArgumentParser(
        description='Fetch and analyze Langfuse traces for batch execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch traces from timestamp with tags
  python3 trace_fetcher.py --from-timestamp "2025-11-07T14:30:00Z" \\
    --tags batch_execution daily --output results.json

  # Fetch traces for specific task IDs
  python3 trace_fetcher.py --from-timestamp "2025-11-07T14:30:00Z" \\
    --session-ids "task-1,task-2,task-3" --output results.json

  # Fetch and analyze recent daily batch runs
  python3 trace_fetcher.py --tags batch_execution daily \\
    --limit 10 --output recent_results.json
        """
    )

    parser.add_argument(
        '--from-timestamp',
        help='Start timestamp in ISO 8601 format (e.g., 2025-11-07T14:30:00Z)'
    )

    parser.add_argument(
        '--tags',
        nargs='+',
        help='Tags to filter by (e.g., batch_execution daily)'
    )

    parser.add_argument(
        '--session-ids',
        help='Comma-separated session IDs (task IDs) to filter by'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of traces to retrieve (default: 50)'
    )

    parser.add_argument(
        '--output',
        help='Output file for analysis results (JSON)'
    )

    args = parser.parse_args()

    # Get credentials
    public_key, secret_key, host = get_langfuse_credentials()
    headers = get_auth_headers(public_key, secret_key)

    # Parse session IDs
    session_ids = None
    if args.session_ids:
        session_ids = [s.strip() for s in args.session_ids.split(',')]

    # Query traces
    traces = query_traces_with_filters(
        host,
        headers,
        from_timestamp=args.from_timestamp,
        tags=args.tags,
        session_ids=session_ids,
        limit=args.limit
    )

    if not traces:
        print("\n⚠ No traces found matching criteria")
        sys.exit(0)

    # Analyze each trace
    print("\nAnalyzing traces...")
    results = []

    for i, trace in enumerate(traces, 1):
        trace_id = trace.get('id')
        print(f"  [{i}/{len(traces)}] Analyzing trace {trace_id}...")

        # Get full trace details
        trace_details = get_trace_details(host, headers, trace_id)

        # Get observations
        observations = get_trace_observations(host, headers, trace_id)

        # Analyze
        architecture = analyze_architecture(trace_details, observations)
        quality = analyze_quality(trace_details)

        results.append({
            'trace_id': trace_id,
            'user_id': trace_details.get('userId'),
            'session_id': trace_details.get('sessionId'),
            'name': trace_details.get('name'),
            'timestamp': trace_details.get('timestamp'),
            'architecture': architecture,
            'quality': quality
        })

    # Generate summary
    summary = generate_summary(results)
    recommendations = generate_recommendations(summary)

    # Build output
    output = {
        'execution_metadata': {
            'analyzed_at': datetime.utcnow().isoformat() + 'Z',
            'from_timestamp': args.from_timestamp,
            'tags': args.tags,
            'session_ids': session_ids
        },
        'traces': results,
        'summary': summary,
        'recommendations': recommendations
    }

    # Save or print output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n✓ Analysis results saved to: {args.output}")
    else:
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)
        print(json.dumps(output, indent=2))

    # Print summary to console
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total traces analyzed: {summary['total_traces']}")
    print(f"\nArchitecture:")
    print(f"  ✓ PASS: {summary['architecture_pass']}")
    print(f"  ⚠ WARNING: {summary['architecture_warning']}")
    print(f"  ✗ FAIL: {summary['architecture_fail']}")
    print(f"\nQuality:")
    print(f"  ✓ HIGH: {summary['quality_high']}")
    print(f"  ⚠ MEDIUM: {summary['quality_medium']}")
    print(f"  ✗ LOW: {summary['quality_low']}")
    print(f"\nIssues:")
    print(f"  Warnings: {len(summary['warnings'])}")
    print(f"  Errors: {len(summary['errors'])}")
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    for rec in recommendations:
        print(f"  {rec}")
    print("="*60)


if __name__ == '__main__':
    main()
