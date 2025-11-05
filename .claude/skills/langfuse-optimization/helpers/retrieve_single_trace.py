#!/usr/bin/env python3
"""
Retrieve a single trace and its observations from Langfuse.

This is a specialized helper for analyzing individual traces in detail.
Uses the same filtering mechanisms as retrieve_traces_and_observations.py.

Usage:
    # Basic retrieval
    python retrieve_single_trace.py 8fda46d7ac626327396d1a7962690807

    # With filtering (95% size reduction)
    python retrieve_single_trace.py 8fda46d7ac626327396d1a7962690807 --filter-essential

    # Custom output location
    python retrieve_single_trace.py abc123 --output /tmp/my_trace.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add helpers directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from langfuse_client import get_langfuse_client
from retrieve_observations import retrieve_observations_for_traces
from filter_observations import filter_bundle


def retrieve_single_trace(trace_id, filter_essential=False, filter_research_details=False):
    """
    Retrieve a single trace and its observations from Langfuse.

    Args:
        trace_id: The trace ID to fetch
        filter_essential: Whether to apply essential filtering (facts_pack, validation_report)
        filter_research_details: Whether to also filter research data (structured_citations, step_status)

    Returns:
        dict: Bundle with trace and observations in the same structure as
              retrieve_traces_and_observations.py (compatible with filter_bundle)

    Raises:
        SystemExit: If trace not found or API error occurs
    """
    client = get_langfuse_client()

    # Step 1: Fetch the trace
    print(f"Fetching trace: {trace_id}")
    try:
        trace = client.api.trace.get(trace_id)

        if not trace:
            print(f"❌ Trace not found: {trace_id}", file=sys.stderr)
            sys.exit(1)

        # Convert to dict for easier handling
        trace_dict = trace.dict() if hasattr(trace, 'dict') else trace

        # Extract essential trace fields
        trace_data = {
            'id': trace_dict.get('id'),
            'name': trace_dict.get('name'),
            'timestamp': str(trace_dict.get('timestamp')),
            'metadata': trace_dict.get('metadata'),
            'tags': trace_dict.get('tags'),
            'input': trace_dict.get('input'),
            'output': trace_dict.get('output'),
            'session_id': trace_dict.get('session_id'),
            'user_id': trace_dict.get('user_id'),
        }

        print(f"✓ Trace retrieved: {trace_data.get('name')}")
        print(f"  Timestamp: {trace_data.get('timestamp')}")
        if trace_data.get('metadata'):
            case_id = trace_data.get('metadata', {}).get('case_id')
            profile = trace_data.get('metadata', {}).get('profile_name')
            if case_id:
                print(f"  Case ID: {case_id}")
            if profile:
                print(f"  Profile: {profile}")

    except Exception as e:
        print(f"❌ Error fetching trace: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 2: Fetch observations using existing helper
    print(f"\nFetching observations for trace...")
    try:
        obs_payload = retrieve_observations_for_traces(
            trace_ids=[trace_id],
            output_file=None  # Don't save separately, we'll include in bundle
        )

        print(f"✓ Retrieved {obs_payload['total_observations']} observations")

    except Exception as e:
        print(f"❌ Error fetching observations: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 3: Build bundle (compatible with filter_bundle structure)
    bundle = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'query': {
            'trace_id': trace_id,
            'single_trace_mode': True
        },
        'trace_count': 1,
        'trace_ids': [trace_id],
        'traces': [trace_data],
        'observations': {
            'total_observations': obs_payload['total_observations'],
            'by_trace': {
                trace_id: obs_payload['observations']
            }
        }
    }

    # Step 4: Apply filtering if requested
    if filter_essential:
        print("\nℹ️  Applying filtering to strip bloat...")
        if filter_research_details:
            print("   → Essential + Research details filtering enabled")
        else:
            print("   → Essential filtering enabled")
        original_size = len(json.dumps(bundle, default=str))
        bundle = filter_bundle(bundle, filter_research_details)
        filtered_size = len(json.dumps(bundle, default=str))
        reduction_pct = ((original_size - filtered_size) / original_size * 100) if original_size > 0 else 0
        print(f"  Size reduction: {original_size:,} → {filtered_size:,} bytes ({reduction_pct:.1f}% reduction)")

    return bundle


def save_bundle(bundle, output_file):
    """Save bundle to JSON file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(bundle, f, indent=2, default=str)

    print(f"\n✓ Bundle saved to: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve a single trace and its observations from Langfuse',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic retrieval
  %(prog)s 8fda46d7ac626327396d1a7962690807

  # With essential filtering (95%% size reduction)
  %(prog)s 8fda46d7ac626327396d1a7962690807 --filter-essential

  # With research details filtering (additional 70%% reduction)
  %(prog)s 8fda46d7ac626327396d1a7962690807 --filter-essential --filter-research-details

  # Maximum filtering (99%% total reduction)
  %(prog)s abc123 --filter-all

  # Custom output location
  %(prog)s abc123 --output /tmp/my_analysis/trace.json --filter-all
"""
    )

    parser.add_argument('trace_id',
                       help='Trace ID to retrieve (e.g., 8fda46d7ac626327396d1a7962690807)')
    parser.add_argument('--output',
                       default='/tmp/langfuse_analysis/single_trace.json',
                       help='Output file path (default: /tmp/langfuse_analysis/single_trace.json)')
    parser.add_argument('--filter-essential',
                       action='store_true',
                       help='Strip bloat (facts_pack, validation_report, long text) for 95%% size reduction. '
                            'Keeps only essential data needed for config optimization.')
    parser.add_argument('--filter-research-details',
                       action='store_true',
                       help='Strip research node bloat (structured_citations, step_status) for additional 70%% reduction. '
                            'Use when citation details are not needed for analysis. Can combine with --filter-essential.')
    parser.add_argument('--filter-all',
                       action='store_true',
                       help='Convenience flag: enables both --filter-essential and --filter-research-details for maximum reduction (99%%).')

    args = parser.parse_args()

    # Handle --filter-all convenience flag
    if args.filter_all:
        args.filter_essential = True
        args.filter_research_details = True

    try:
        # Retrieve trace and observations
        bundle = retrieve_single_trace(args.trace_id, args.filter_essential, args.filter_research_details)

        # Save to file
        output_path = save_bundle(bundle, args.output)

        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Trace ID: {args.trace_id}")
        print(f"Trace name: {bundle['traces'][0]['name']}")
        print(f"Observations: {bundle['observations']['total_observations']}")
        filtering_status = []
        if args.filter_essential:
            filtering_status.append("essential")
        if args.filter_research_details:
            filtering_status.append("research-details")
        print(f"Filtering: {', '.join(filtering_status) if filtering_status else 'None'}")
        print(f"Output: {output_path}")
        print("=" * 70)

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Failed to retrieve trace: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
