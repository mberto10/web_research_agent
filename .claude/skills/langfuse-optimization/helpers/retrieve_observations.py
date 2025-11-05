#!/usr/bin/env python3
"""
Retrieve observations from Langfuse traces

TWO MODES OF OPERATION:
========================

MODE 1: DIRECT TRACE ID INPUT (RECOMMENDED - EFFICIENT)
--------------------------------------------------------
Use when you already know the trace IDs (e.g., from retrieve_traces.py output)

BENEFITS:
- Fast: No search required, direct API lookup
- Efficient: Avoids searching all observations then filtering
- Connects Steps: Reads output from retrieve_traces.py

OPTIONS:
1. --trace-ids-file: Read trace IDs from traces.json file
   Example: --trace-ids-file /tmp/langfuse_analysis/traces.json

2. --trace-id: Specify one or more trace IDs directly
   Example: --trace-id abc123def456
   Example: --trace-id abc123 def456 ghi789

MODE 2: SEARCH BY NAME (LEGACY - LESS EFFICIENT)
-------------------------------------------------
Use when you don't have trace IDs and need to search for them

DEFAULT: Searches for 'writing-workflow' pattern by default (configurable via --trace-name)

HOW IT WORKS:
Step 1: Find all observations matching the trace name pattern
Step 2: Extract unique trace IDs from those observations
Step 3: For each trace, retrieve ALL observations (not just the named one)
Step 4: Combine and save all observations

Note: This is inefficient if you already have trace IDs!

CONTROLLING OUTPUT SIZE (Mode 2 only):
--------------------------------------
1. LIMIT NUMBER OF TRACES (--limit):
   Limits how many traces to process, reducing total observations returned
   Example: --limit 10  # Process only 10 traces (but get ALL observations from those 10)
   Default: No limit (processes ALL matching traces)

2. TIME RANGE FILTERING:
   Narrow the search window to find fewer matching traces
   - From time: --from-start-time "2025-10-22T00:00:00Z"
   - To time: --to-start-time "2025-10-23T00:00:00Z"

USAGE EXAMPLES:
===============

MODE 1 Examples (Direct - Efficient):
--------------------------------------
# RECOMMENDED: Connect Step 2 → Step 3 (reads traces.json from retrieve_traces.py)
python retrieve_observations.py --trace-ids-file /tmp/langfuse_analysis/traces.json

# Direct lookup for single trace analysis:
python retrieve_observations.py --trace-id abc123def456

# Direct lookup for multiple specific traces:
python retrieve_observations.py --trace-id abc123 def456 ghi789

# With custom output location:
python retrieve_observations.py --trace-ids-file traces.json --output /tmp/my_obs.json

MODE 2 Examples (Search - Legacy):
-----------------------------------
# Get observations from 10 most recent matching traces:
python retrieve_observations.py --limit 10

# Get observations from traces in a specific date range (limit to 20 traces):
python retrieve_observations.py \
  --from-start-time "2025-10-22T00:00:00Z" \
  --to-start-time "2025-10-23T00:00:00Z" \
  --limit 20

# Get ALL observations from ALL matching traces (WARNING: may be large):
python retrieve_observations.py

IMPORTANT NOTES:
================
- Time filters are IGNORED when using --trace-id or --trace-ids-file
- Cannot combine --trace-id and --trace-ids-file (mutually exclusive)
- Mode 1 is MUCH faster when you already have trace IDs
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add helpers directory to path
sys.path.insert(0, str(Path(__file__).parent))
from langfuse_client import get_langfuse_client
from filter_observations import filter_observations_payload


def extract_essential_fields_observation(obs):
    """Extract only fields needed for config optimization analysis."""
    return {
        'id': obs.get('id'),
        'name': obs.get('name'),
        'type': obs.get('type'),
        'input': obs.get('input'),
        'output': obs.get('output'),
        'metadata': obs.get('metadata'),
        'status_message': obs.get('status_message'),
        'trace_id': obs.get('trace_id'),
        'level': obs.get('level'),
        'parent_observation_id': obs.get('parent_observation_id'),
        'start_time': obs.get('start_time'),
        'end_time': obs.get('end_time')
    }


def should_keep_observation(obs):
    """
    Filter observations to only those needed for config optimization.

    Config optimization only needs:
    - Main workflow nodes (research, writer, editor)
    - Push/delivery nodes
    - Memory retrieval

    We don't need:
    - Individual check spans (editor output has aggregated results)
    - Internal API spans (tool selection visible in research output)
    - Deep tracing spans

    Args:
        obs: Observation dict

    Returns:
        bool: True if observation should be kept for analysis
    """
    name = obs.get('name', '').lower()

    # Essential node patterns for config analysis
    essential_patterns = [
        'research',           # Research node (tool selection)
        'writer',            # Writer node (content generation)
        'editor',            # Editor node (check results)
        'push',              # Push/delivery
        'retrieve_memories'  # Memory retrieval
    ]

    return any(pattern in name for pattern in essential_patterns)


def retrieve_observations_from_api(name=None, trace_ids=None, from_start_time=None, to_start_time=None, rate_limit_delay=0.1):
    """
    Retrieve observations from Langfuse API with pagination.

    NOTE: Automatically filters to keep only essential workflow nodes
    (research, writer, editor, push, retrieve_memories).
    Individual check spans and internal traces are excluded.

    Args:
        name: Filter by observation name
        trace_ids: List of trace IDs to filter by
        from_start_time: ISO 8601 datetime string for start range
        to_start_time: ISO 8601 datetime string for end range
        rate_limit_delay: Delay between requests (not currently used)

    Returns:
        dict: {'data': list of filtered observation objects}
    """
    client = get_langfuse_client()

    all_observations = []
    page = 1
    page_limit = 100

    while True:
        params = {
            'limit': page_limit,
            'page': page
        }

        if name:
            params['name'] = name
        if trace_ids:
            params['trace_id'] = trace_ids[0] if len(trace_ids) == 1 else trace_ids
        if from_start_time:
            params['from_start_time'] = from_start_time
        if to_start_time:
            params['to_start_time'] = to_start_time

        response = client.api.observations.get_many(**params)

        if not hasattr(response, 'data') or not response.data:
            break

        # Extract essential fields AND filter to keep only main workflow nodes
        all_observations.extend([
            extract_essential_fields_observation(obs.__dict__)
            for obs in response.data
            if should_keep_observation(obs.__dict__)
        ])

        # Check if there are more pages
        if hasattr(response, 'meta') and page >= response.meta.total_pages:
            break
        if len(response.data) < page_limit:
            break

        page += 1

    return {'data': all_observations}


def extract_trace_ids_from_file(file_path):
    """
    Extract trace IDs from a traces.json file (output from retrieve_traces.py).

    Args:
        file_path: Path to traces.json file

    Returns:
        list: List of trace ID strings

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
        KeyError: If traces don't have 'id' field
    """
    try:
        with open(file_path, 'r') as f:
            traces = json.load(f)

        if not isinstance(traces, list):
            raise ValueError(f"Expected list of traces, got {type(traces).__name__}")

        if len(traces) == 0:
            print(f"⚠️  Warning: No traces found in {file_path}")
            return []

        trace_ids = [trace['id'] for trace in traces]
        print(f"✓ Extracted {len(trace_ids)} trace IDs from {file_path}")
        return trace_ids

    except FileNotFoundError:
        print(f"✗ Error: File not found: {file_path}", file=sys.stderr)
        raise
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        raise
    except KeyError as e:
        print(f"✗ Error: Trace missing 'id' field in {file_path}", file=sys.stderr)
        raise


def retrieve_observations_for_traces(trace_ids, output_file=None):
    """
    Efficiently retrieve observations for known trace IDs.

    This is the DIRECT path - skips search, goes straight to observation fetching.
    Use when you already have trace IDs (e.g., from retrieve_traces.py or direct input).

    Args:
        trace_ids: List of trace ID strings
        output_file: Optional path to save results (JSON format)

    Returns:
        dict: Observations with essential fields only:
              - observations: List of observation objects (pruned to essential fields)
              - total_observations: Count of observations
              - trace_ids: List of trace IDs queried
    """
    from collections import defaultdict

    if not trace_ids or len(trace_ids) == 0:
        print("\n✗ No trace IDs provided")
        return {
            'observations': [],
            'total_observations': 0,
            'trace_ids': []
        }

    print(f"\n🎯 Direct retrieval for {len(trace_ids)} trace(s)")
    print(f"  Fetching ALL observations for these traces...\n")

    all_observations = []

    # Fetch observations for each trace ID
    for i, trace_id in enumerate(trace_ids, 1):
        print(f"  [{i}/{len(trace_ids)}] Fetching trace: {trace_id}")

        try:
            trace_result = retrieve_observations_from_api(
                trace_ids=[trace_id],
                rate_limit_delay=0.05
            )

            obs_count = len(trace_result['data'])
            all_observations.extend(trace_result['data'])
            print(f"      → Retrieved {obs_count} observations")

        except Exception as e:
            print(f"      ✗ Error fetching trace {trace_id}: {e}", file=sys.stderr)
            # Continue with other traces

    print(f"\n✓ Retrieved {len(all_observations)} total observations across {len(trace_ids)} traces")

    # Group by trace for summary
    traces = defaultdict(list)
    for obs in all_observations:
        traces[obs.get('trace_id')].append(obs)

    print("\nTrace breakdown:")
    for trace_id, obs_list in sorted(traces.items(), key=lambda x: len(x[1]), reverse=True):
        trace_id_display = trace_id[:32] + "..." if len(trace_id) > 32 else trace_id
        print(f"  • {trace_id_display} : {len(obs_list)} observations")

    # Build result
    result = {
        'observations': all_observations,
        'total_observations': len(all_observations),
        'trace_ids': trace_ids
    }

    # Save if output file specified
    if output_file:
        save_observations(result, output_file)

    return result


def save_observations(result, output_file):
    """
    Save observations to JSON file.

    Args:
        result: Dictionary containing observations and metadata
        output_file: Path where the JSON file should be saved

    Returns:
        None (prints confirmation message)
    """
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    print(f"\n✓ Output saved to: {output_file}")

# NO DEFAULT TRACE NAME - must be explicitly provided or use tags
DEFAULT_TRACE_NAME = None


def filter_observations_by_trace_name(
    trace_name: str,
    from_start_time: str = None,
    to_start_time: str = None,
    output_file: str = None,
    limit: int = None
):
    """
    Get all observations from traces that contain an observation with the given name.

    This is a two-step process:
    1. Find observations with the specified name
    2. Get ALL observations for the traces containing those observations

    Args:
        trace_name: Name of observation to search for (e.g., 'writing-workflow')
        from_start_time: ISO 8601 datetime string for start range (e.g., "2025-10-22T00:00:00Z")
        to_start_time: ISO 8601 datetime string for end range (e.g., "2025-10-23T00:00:00Z")
        output_file: Path to save results (JSON format)
        limit: IMPORTANT - Maximum number of TRACES to process (not observations).
               This limits how many traces are retrieved, but ALL observations from
               those traces will be included in the output.
               Example: limit=5 retrieves ALL observations from 5 traces
               Default: None (processes all matching traces)

    Returns:
        dict: Filtered observations with essential fields only:
              - observations: List of observation objects (pruned to essential fields)
              - total_observations: Count of observations
              - trace_ids: List of trace IDs found
    """
    print(f"Step 1: Finding observations with name '{trace_name}'...")

    # Step 1: Get observations with this name
    result = retrieve_observations_from_api(
        name=trace_name,
        from_start_time=from_start_time,
        to_start_time=to_start_time
    )

    matching_obs = result['data']
    print(f"  Found {len(matching_obs)} observations with name '{trace_name}'")

    if not matching_obs:
        print("\n✗ No observations found with that name")
        return {
            'observations': [],
            'total_observations': 0,
            'trace_ids': []
        }

    # Step 2: Extract unique trace IDs
    trace_ids = list(set(obs.get('trace_id') for obs in matching_obs if obs.get('trace_id')))

    # Apply limit if specified
    total_traces_found = len(trace_ids)
    if limit and len(trace_ids) > limit:
        trace_ids = trace_ids[:limit]
        print(f"\nStep 2: Found {total_traces_found} unique traces, limiting to {limit} most recent")
    else:
        print(f"\nStep 2: Found {len(trace_ids)} unique traces containing '{trace_name}'")

    print(f"  Retrieving ALL observations for these {len(trace_ids)} traces...")

    # Step 3: Get all observations for these trace IDs
    all_observations = []

    for i, trace_id in enumerate(trace_ids, 1):
        print(f"  Fetching trace {i}/{len(trace_ids)}: {trace_id}")

        trace_result = retrieve_observations_from_api(
            trace_ids=[trace_id],
            rate_limit_delay=0.05  # Faster for single trace queries
        )

        all_observations.extend(trace_result['data'])

    print(f"\nStep 3: Retrieved {len(all_observations)} total observations across {len(trace_ids)} traces")

    # Group by trace for summary
    from collections import defaultdict
    traces = defaultdict(list)
    for obs in all_observations:
        traces[obs.get('trace_id')].append(obs)

    print("\nTrace breakdown:")
    for trace_id, obs_list in sorted(traces.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  • {trace_id[:32]}... : {len(obs_list)} observations")

    # Build result
    result = {
        'observations': all_observations,
        'total_observations': len(all_observations),
        'trace_ids': trace_ids
    }

    # Save if output file specified
    if output_file:
        save_observations(result, output_file)

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve observations from Langfuse traces (use tags or direct trace IDs)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
RECOMMENDED: Use --trace-ids-file with output from retrieve_traces.py (with --tags filter).

This script NO LONGER has a default trace name filter.

IMPORTANT: This script retrieves ALL observations from matching traces.
Use --limit to control how many traces are processed.

Examples:
  # Get observations from 10 most recent traces
  %(prog)s --limit 10

  # Get observations from 5 traces in a specific time range
  %(prog)s \\
    --from-start-time "2025-10-22T00:00:00Z" \\
    --to-start-time "2025-10-23T00:00:00Z" \\
    --limit 5

  # Get ALL observations from ALL matching traces (WARNING: may be large)
  %(prog)s

  # Custom output location with limit
  %(prog)s --limit 20 --output /tmp/my_traces.json

For more information, see the module docstring.
        """
    )

    # Direct trace ID input (RECOMMENDED - most efficient)
    direct_group = parser.add_argument_group('Direct Trace ID Input (RECOMMENDED - Efficient)')
    direct_group.add_argument('--trace-id', nargs='+', metavar='ID',
                             help='One or more trace IDs to retrieve observations for. '
                                  'Fast direct lookup, no search required. '
                                  'Example: --trace-id abc123def456 '
                                  'or --trace-id id1 id2 id3. '
                                  'Mutually exclusive with --trace-ids-file and search mode.')
    direct_group.add_argument('--trace-ids-file', metavar='PATH',
                             help='Path to traces.json file (from retrieve_traces.py). '
                                  'Extracts trace IDs from file and retrieves observations. '
                                  'RECOMMENDED for connecting Step 2 → Step 3. '
                                  'Example: --trace-ids-file /tmp/langfuse_analysis/traces.json. '
                                  'Mutually exclusive with --trace-id and search mode.')

    # Output control
    output_group = parser.add_argument_group('Output Control')
    output_group.add_argument('--output', default='/tmp/langfuse_analysis/news_workflow_traces.json',
                             help='Output file path (default: /tmp/langfuse_analysis/news_workflow_traces.json)')
    output_group.add_argument('--filter-essential', action='store_true',
                             help='Strip bloat from observations (facts_pack, validation_report) for 95%% size reduction. '
                                  'Keeps only essential node inputs/outputs needed for config optimization.')
    output_group.add_argument('--filter-research-details', action='store_true',
                             help='Strip research node bloat (structured_citations, step_status) for additional 70%% reduction. '
                                  'Use when citation details are not needed for analysis. Can combine with --filter-essential.')
    output_group.add_argument('--filter-all', action='store_true',
                             help='Convenience flag: enables both --filter-essential and --filter-research-details for maximum reduction (99%%).')

    # Search by name filters (LEGACY - only used when no trace IDs provided)
    search_group = parser.add_argument_group('Search by Name Filters (LEGACY - Less Efficient)')
    search_group.add_argument('--limit', type=int,
                             help='[SEARCH MODE ONLY] Maximum number of TRACES to process. '
                                  'Retrieves ALL observations from these traces. '
                                  'Example: --limit 10 processes 10 traces (but may return 100+ observations). '
                                  'Ignored when using --trace-id or --trace-ids-file.')
    search_group.add_argument('--from-start-time',
                             help='[SEARCH MODE ONLY] ISO 8601 datetime - get observations on/after this time. '
                                  'Example: "2025-10-22T00:00:00Z". '
                                  'Ignored when using --trace-id or --trace-ids-file.')
    search_group.add_argument('--to-start-time',
                             help='[SEARCH MODE ONLY] ISO 8601 datetime - get observations before this time. '
                                  'Example: "2025-10-23T00:00:00Z". '
                                  'Ignored when using --trace-id or --trace-ids-file.')

    args = parser.parse_args()

    # Handle --filter-all convenience flag
    if args.filter_all:
        args.filter_essential = True
        args.filter_research_details = True

    try:
        # === VALIDATION: Check for mutually exclusive options ===
        if args.trace_id and args.trace_ids_file:
            print("✗ Error: Cannot use both --trace-id and --trace-ids-file", file=sys.stderr)
            print("  Use one or the other, not both.", file=sys.stderr)
            sys.exit(1)

        # === DETERMINE MODE: Direct trace IDs or search by name ===
        using_direct_mode = args.trace_id or args.trace_ids_file

        # Warn if time filters used with direct mode (they'll be ignored)
        if using_direct_mode and (args.from_start_time or args.to_start_time or args.limit):
            print("⚠️  Note: Time range filters and --limit are ignored when using direct trace ID input\n")

        # === MODE 1: DIRECT TRACE ID INPUT (Efficient) ===
        if using_direct_mode:
            if args.trace_id:
                # Direct CLI input
                trace_ids = args.trace_id
                print(f"🎯 MODE: Direct trace ID lookup")
                print(f"  Trace IDs provided: {len(trace_ids)}")
                for i, tid in enumerate(trace_ids, 1):
                    print(f"    {i}. {tid}")
                print()
            else:
                # Read from file
                print(f"📁 MODE: Reading trace IDs from file")
                print(f"  File: {args.trace_ids_file}\n")
                trace_ids = extract_trace_ids_from_file(args.trace_ids_file)

                if not trace_ids:
                    print("\n✗ No trace IDs found in file", file=sys.stderr)
                    sys.exit(1)

            # Retrieve observations for the trace IDs (don't save yet)
            result = retrieve_observations_for_traces(
                trace_ids=trace_ids,
                output_file=None
            )

            # Apply filtering if requested
            if args.filter_essential:
                print("\nℹ️  Applying filtering to strip bloat...")
                if args.filter_research_details:
                    print("   → Essential + Research details filtering enabled")
                else:
                    print("   → Essential filtering enabled")
                original_size = len(json.dumps(result, default=str))
                result = filter_observations_payload(result, args.filter_research_details)
                filtered_size = len(json.dumps(result, default=str))
                reduction_pct = ((original_size - filtered_size) / original_size * 100) if original_size > 0 else 0
                print(f"  Size reduction: {original_size:,} → {filtered_size:,} bytes ({reduction_pct:.1f}% reduction)")

            # Save the result
            save_observations(result, args.output)

            # Print summary
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(f"Mode: Direct trace ID input")
            print(f"Trace IDs provided: {len(result['trace_ids'])}")
            print(f"Total observations retrieved: {result['total_observations']}")
            print(f"Filtered: {'Yes' if args.filter_essential else 'No'}")
            print(f"\n✓ Output saved to: {args.output}")
            print("="*70)

        # === MODE 2: SEARCH BY NAME (Legacy) ===
        else:
            if not DEFAULT_TRACE_NAME:
                print("✗ Error: No trace identification method provided", file=sys.stderr)
                print("  Please use one of:", file=sys.stderr)
                print("    --trace-id <id>           (direct trace ID lookup)", file=sys.stderr)
                print("    --trace-ids-file <path>   (read from retrieve_traces.py output)", file=sys.stderr)
                print("  ", file=sys.stderr)
                print("  Or use retrieve_traces.py first with --tags filter:", file=sys.stderr)
                print("    python retrieve_traces.py --tags case:0004 --output traces.json", file=sys.stderr)
                print("    python retrieve_observations.py --trace-ids-file traces.json", file=sys.stderr)
                sys.exit(1)

            print(f"🔍 MODE: Search by trace name (LEGACY)")
            print(f"  Searching for traces with name: '{DEFAULT_TRACE_NAME}'\n")

            # Retrieve observations by name (don't save yet)
            result = filter_observations_by_trace_name(
                trace_name=DEFAULT_TRACE_NAME,
                from_start_time=args.from_start_time,
                to_start_time=args.to_start_time,
                output_file=None,
                limit=args.limit
            )

            # Apply filtering if requested
            if args.filter_essential:
                print("\nℹ️  Applying filtering to strip bloat...")
                if args.filter_research_details:
                    print("   → Essential + Research details filtering enabled")
                else:
                    print("   → Essential filtering enabled")
                original_size = len(json.dumps(result, default=str))
                result = filter_observations_payload(result, args.filter_research_details)
                filtered_size = len(json.dumps(result, default=str))
                reduction_pct = ((original_size - filtered_size) / original_size * 100) if original_size > 0 else 0
                print(f"  Size reduction: {original_size:,} → {filtered_size:,} bytes ({reduction_pct:.1f}% reduction)")

            # Save the result
            save_observations(result, args.output)

            # Print summary (this code path should never execute due to check above)
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(f"Mode: Search by trace name (DEPRECATED)")
            print(f"Unique traces found: {len(result['trace_ids'])}")
            print(f"Total observations retrieved: {result['total_observations']}")
            print(f"Filtered: {'Yes' if args.filter_essential else 'No'}")
            print(f"\n✓ Output saved to: {args.output}")
            print("="*70)

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
