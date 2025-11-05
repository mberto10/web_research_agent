#!/usr/bin/env python3
"""
Retrieve traces and their observations from Langfuse in one command.

This script combines the functionality of retrieve_traces.py and
retrieve_observations.py so analysts can pull both datasets in a single step.

Key capabilities:
  - Time-based trace retrieval (last N days or explicit date range)
  - Filtering by workflow name, user ID, tags, session ID
  - Metadata filtering (e.g., genre=biographical)
  - Optional observation retrieval toggle (--no-observations)
  - Unified JSON bundle output with traces + observations grouped by trace
  - Optional separate output files for traces and observations

Example:
  python retrieve_traces_and_observations.py \\
    --limit 5 \\
    --metadata genre=biographical \\
    --output /tmp/langfuse_analysis/biographical_bundle.json
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure imports work whether we run from helpers directory or repo root
HELPERS_DIR = Path(__file__).parent
sys.path.insert(0, str(HELPERS_DIR))

from retrieve_traces import retrieve_traces, save_traces
from retrieve_observations import retrieve_observations_for_traces
from filter_observations import filter_bundle


def parse_metadata_filters_args(metadata_args):
    """
    Parse metadata filter arguments into a dict of sets.

    Args:
        metadata_args: List of "key=value" strings (e.g., ["genre=biographical", "case_id=0001"])

    Returns:
        dict: {key: {value1, value2, ...}} for each metadata filter

    Example:
        parse_metadata_filters_args(["genre=biographical", "genre=tech", "case_id=0001"])
        -> {"genre": {"biographical", "tech"}, "case_id": {"0001"}}
    """
    if not metadata_args:
        return {}

    filters = defaultdict(set)

    for arg in metadata_args:
        if '=' not in arg:
            raise ValueError(f"Invalid metadata filter format: '{arg}'. Expected 'key=value'")

        key, value = arg.split('=', 1)
        key = key.strip()
        value = value.strip()

        if not key or not value:
            raise ValueError(f"Invalid metadata filter: '{arg}'. Both key and value required")

        filters[key].add(value)

    return dict(filters)


def filter_traces_by_metadata(traces, metadata_filters):
    """
    Client-side filtering of traces by metadata.

    Args:
        traces: List of trace dicts
        metadata_filters: Dict of {key: {value1, value2, ...}}

    Returns:
        list: Filtered traces that match ALL metadata criteria
    """
    if not metadata_filters:
        return traces

    filtered = []
    for trace in traces:
        metadata = trace.get('metadata', {})

        # Check if trace matches all filters
        matches = True
        for key, allowed_values in metadata_filters.items():
            trace_value = str(metadata.get(key, ''))
            if trace_value not in allowed_values:
                matches = False
                break

        if matches:
            filtered.append(trace)

    return filtered


def save_json(data, output_file):
    """Write bundled data to disk."""
    if not output_file:
        return None

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"\n✓ Bundle saved to: {output_path}")
    return str(output_path)


def group_observations_by_trace(observations, trace_ids):
    """Group observation records by trace ID."""
    grouped = defaultdict(list)

    for obs in observations:
        trace_id = obs.get('trace_id')
        if trace_id in trace_ids:
            grouped[trace_id].append(obs)

    # Convert defaultdict to regular dict for JSON serialization
    return {trace_id: grouped.get(trace_id, []) for trace_id in trace_ids}


def build_query_summary(args, metadata_filters):
    """Capture the query parameters used for retrieval."""
    summary = {
        'limit': args.limit,
        'days': args.days if args.days is not None else None,
        'start_date': args.start_date,
        'end_date': args.end_date,
        'project': args.project,
        'name': args.name,
        'user_id': args.user_id,
        'session_id': args.session_id,
        'tags': args.tags,
        'include_observations': not args.no_observations,
    }

    if metadata_filters:
        summary['metadata_filters'] = {
            key: sorted(list(values))
            for key, values in metadata_filters.items()
        }

    return summary


def parse_args():
    parser = argparse.ArgumentParser(
        description='Retrieve Langfuse traces with their observations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze last 3 traces (default workflow name)
  %(prog)s --limit 3

  # Analyze last 2 biographical traces (metadata filter)
  %(prog)s --limit 2 --metadata genre=biographical

  # Analyze traces from explicit date range and skip observations
  %(prog)s --start-date 2025-01-01 --end-date 2025-01-07 --no-observations

  # Save combined bundle + individual trace/observation files
  %(prog)s --limit 5 --output bundle.json --traces-output traces.json --observations-output observations.json
""")

    # Output options
    output_group = parser.add_argument_group('Output')
    output_group.add_argument(
        '--output',
        default='/tmp/langfuse_analysis/traces_bundle.json',
        help='Path for combined JSON bundle (default: /tmp/langfuse_analysis/traces_bundle.json)'
    )
    output_group.add_argument(
        '--traces-output',
        help='Optional path to save traces JSON separately (same structure as retrieve_traces.py output)'
    )
    output_group.add_argument(
        '--observations-output',
        help='Optional path to save raw observations JSON (same structure as retrieve_observations.py output)'
    )
    output_group.add_argument(
        '--no-observations',
        action='store_true',
        help='Skip retrieving observations (traces only)')
    output_group.add_argument(
        '--filter-essential',
        action='store_true',
        help='Strip bloat from observations (facts_pack, validation_report) for 95%% size reduction. '
             'Keeps only essential node inputs/outputs needed for config optimization.')
    output_group.add_argument(
        '--filter-research-details',
        action='store_true',
        help='Strip research node bloat (structured_citations, step_status) for additional 70%% reduction. '
             'Use when citation details are not needed for analysis. Can combine with --filter-essential.')
    output_group.add_argument(
        '--filter-all',
        action='store_true',
        help='Convenience flag: enables both --filter-essential and --filter-research-details for maximum reduction (99%%).')

    # Trace retrieval controls
    trace_group = parser.add_argument_group('Trace Retrieval')
    trace_group.add_argument('--limit',
                             type=int,
                             help='Maximum number of traces to return')
    trace_group.add_argument('--days',
                             type=int,
                             default=7,
                             help='Lookback window in days (default: 7). Ignored if start/end date provided.')
    trace_group.add_argument('--start-date',
                             help='ISO date (YYYY-MM-DD) for range start')
    trace_group.add_argument('--end-date',
                             help='ISO date (YYYY-MM-DD) for range end')
    trace_group.add_argument('--project', help='Project name filter')
    trace_group.add_argument(
        '--name',
        default=None,
        help='Trace name filter (default: None - no filtering, use --name "pattern" to filter)'
    )
    trace_group.add_argument('--user-id', help='Trace user_id filter')
    trace_group.add_argument('--session-id', help='Trace session_id filter')
    trace_group.add_argument('--tags',
                             nargs='+',
                             help='Trace tags filter (space separated)')
    trace_group.add_argument(
        '--metadata',
        nargs='+',
        help=
        'Metadata key=value filters (e.g., --metadata genre=biographical). Use dot notation for nested keys.'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Handle --filter-all convenience flag
    if args.filter_all:
        args.filter_essential = True
        args.filter_research_details = True

    # Derive days parameter (skip when explicit dates provided)
    days_param = args.days if not (args.start_date or args.end_date) else None

    try:
        metadata_filters = parse_metadata_filters_args(args.metadata)
    except ValueError as e:
        print(f"\n✗ {e}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Retrieve traces (leverages existing helper)
    # Note: We retrieve more traces than limit if metadata filtering is active,
    # since filtering happens client-side after retrieval
    retrieval_limit = None if metadata_filters else args.limit

    all_traces = retrieve_traces(project_name=args.project,
                                  days=days_param,
                                  start_date=args.start_date,
                                  end_date=args.end_date,
                                  user_id=args.user_id,
                                  tags=args.tags,
                                  session_id=args.session_id,
                                  name=args.name,
                                  limit=retrieval_limit)

    # Step 1.5: Apply client-side metadata filtering if requested
    if metadata_filters:
        print(f"\nApplying metadata filters:")
        for key, values in metadata_filters.items():
            print(f"  - {key}: {', '.join(sorted(values))}")

        pre_filter_count = len(all_traces)
        traces = filter_traces_by_metadata(all_traces, metadata_filters)
        print(f"  Filtered: {pre_filter_count} → {len(traces)} traces")

        # Apply limit after filtering
        if args.limit and len(traces) > args.limit:
            traces = traces[:args.limit]
            print(f"  Limited to: {args.limit} traces")
    else:
        traces = all_traces

    if args.traces_output:
        save_traces(traces, args.traces_output)

    trace_ids = [trace['id'] for trace in traces if trace.get('id')]
    observations_payload = None

    # Step 2: Optionally retrieve observations for the selected traces
    if trace_ids and not args.no_observations:
        observations_payload = retrieve_observations_for_traces(
            trace_ids=trace_ids, output_file=args.observations_output)
    elif not trace_ids:
        print("\n⚠️  No traces matched the filters. Skipping observations.")
    else:
        print("\nℹ️  Skipping observation retrieval (--no-observations set)")

    # Bundle results for downstream analysis
    bundle = {
        'generated_at':
        datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'query': build_query_summary(args, metadata_filters),
        'trace_count': len(traces),
        'trace_ids': trace_ids,
        'traces': traces,
    }

    if observations_payload:
        grouped = group_observations_by_trace(observations_payload['observations'],
                                              trace_ids)
        bundle['observations'] = {
            'total_observations':
            observations_payload['total_observations'],
            'by_trace':
            grouped
        }
    else:
        bundle['observations'] = None

    # Apply filtering if requested
    if args.filter_essential and bundle['observations']:
        print("\nℹ️  Applying filtering to strip bloat...")
        if args.filter_research_details:
            print("   → Essential + Research details filtering enabled")
        else:
            print("   → Essential filtering enabled")
        original_size = len(json.dumps(bundle, default=str))
        bundle = filter_bundle(bundle, args.filter_research_details)
        filtered_size = len(json.dumps(bundle, default=str))
        reduction_pct = ((original_size - filtered_size) / original_size * 100) if original_size > 0 else 0
        print(f"  Size reduction: {original_size:,} → {filtered_size:,} bytes ({reduction_pct:.1f}% reduction)")

    bundle_path = save_json(bundle, args.output)

    # Console summary for quick reference
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Traces retrieved: {len(traces)}")
    if metadata_filters:
        print("Metadata filters:")
        for key, values in metadata_filters.items():
            print(f"  - {key}: {', '.join(sorted(values))}")

    if bundle['observations']:
        print(
            f"Observations retrieved: {bundle['observations']['total_observations']}"
        )
    elif trace_ids and args.no_observations:
        print("Observations retrieved: 0 (skipped by user request)")
    else:
        print("Observations retrieved: 0")

    # Show filtering status
    if args.filter_essential or args.filter_research_details:
        filtering_status = []
        if args.filter_essential:
            filtering_status.append("essential")
        if args.filter_research_details:
            filtering_status.append("research-details")
        print(f"Filtering applied: {', '.join(filtering_status)}")

    if bundle_path:
        print(f"\nBundle saved to: {bundle_path}")
    if args.traces_output:
        print(f"Traces JSON saved to: {args.traces_output}")
    if args.observations_output:
        print(f"Observations JSON saved to: {args.observations_output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
