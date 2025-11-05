#!/usr/bin/env python3
"""
Retrieve Traces from Langfuse
Fetches traces based on project, time range, and optional filters

FILTERING TRACES OUTPUT:
========================
This script provides multiple ways to control how many traces are retrieved:

1. LIMIT THE NUMBER OF TRACES (--limit):
   Use --limit to cap the maximum number of traces returned
   Example: --limit 100  # Retrieve maximum of 100 traces
   Default: No limit (retrieves all matching traces)

2. TIME RANGE FILTERING:
   - By days: --days 7  # Last 7 days (default)
   - By date range: --start-date 2025-01-01 --end-date 2025-01-31
   - Start date only: --start-date 2025-01-01  # From date to now

3. ADDITIONAL FILTERS:
   - By trace name: --name "writing-workflow-*" (optional, no default)
   - By user: --user-id "user123"
   - By session: --session-id "session456"
   - By tags: --tags tag1 tag2

USAGE EXAMPLES:
===============
# Get last 50 traces from the past 3 days:
python retrieve_traces.py --days 3 --limit 50

# Get 100 traces from a specific date range:
python retrieve_traces.py --start-date 2025-01-01 --end-date 2025-01-31 --limit 100

# Get all traces for a specific user (no limit):
python retrieve_traces.py --user-id "user123"

# Get 25 most recent traces with specific tags:
python retrieve_traces.py --tags production error --limit 25
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add helpers directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from langfuse_client import get_langfuse_client


def extract_essential_fields_trace(trace):
    """Extract only fields needed for config optimization analysis."""
    return {
        'id': trace.get('id'),
        'name': trace.get('name'),
        'timestamp': trace.get('timestamp'),
        'input': trace.get('input'),
        'output': trace.get('output'),
        'metadata': trace.get('metadata')
    }


def parse_time_range(days=None, start_date=None, end_date=None):
    """
    Parse time range parameters into start and end datetime objects.

    Args:
        days: Number of days to look back from now
        start_date: ISO format start date string
        end_date: ISO format end date string

    Returns:
        tuple: (start_datetime, end_datetime) as datetime objects
    """
    if days:
        end = datetime.now()
        start = end - timedelta(days=int(days))
        return start, end
    elif start_date and end_date:
        return datetime.fromisoformat(start_date), datetime.fromisoformat(end_date)
    elif start_date:
        return datetime.fromisoformat(start_date), datetime.now()
    else:
        # Default: last 7 days
        end = datetime.now()
        start = end - timedelta(days=7)
        return start, end


def retrieve_traces(project_name=None, days=7, start_date=None, end_date=None,
                    user_id=None, tags=None, session_id=None, name=None, limit=None):
    """
    Retrieve traces from Langfuse with pagination.

    Args:
        project_name: Project name to filter by (optional)
        days: Number of days to look back (default: 7)
        start_date: ISO format start date (e.g., "2025-01-01")
        end_date: ISO format end date (e.g., "2025-01-31")
        user_id: Filter by user ID
        tags: List of tags to filter by
        session_id: Filter by session ID
        name: Filter by trace name (default: None - no filtering)
        limit: IMPORTANT - Maximum number of traces to retrieve.
               Use this to control output size. None = retrieve all matching traces.
               Example: limit=50 retrieves at most 50 traces

    Returns:
        list: List of trace objects (up to 'limit' traces if specified)
    """
    client = get_langfuse_client()

    start_time, end_time = parse_time_range(days, start_date, end_date)

    print(f"Retrieving traces...")
    print(f"  Time range: {start_time} to {end_time}")
    if limit:
        print(f"  Limit: {limit} traces (max)")
    if user_id:
        print(f"  User ID: {user_id}")
    if tags:
        print(f"  Tags: {tags}")
    if session_id:
        print(f"  Session ID: {session_id}")
    if name:
        print(f"  Name: {name}")

    all_traces = []
    page = 1
    # Smart page limit: if user wants only N traces, don't fetch more than that
    page_limit = min(limit, 50) if limit else 50

    while True:
        # Calculate how many more traces we need to fetch
        remaining = limit - len(all_traces) if limit else page_limit
        fetch_size = min(remaining, page_limit) if limit else page_limit

        # Build query parameters
        params = {
            'limit': fetch_size,
            'page': page,
            'from_timestamp': start_time,
            'to_timestamp': end_time
        }

        if user_id:
            params['user_id'] = user_id
        if session_id:
            params['session_id'] = session_id
        if name:
            params['name'] = name
        if tags:
            params['tags'] = tags

        try:
            traces_response = client.api.trace.list(**params)

            if not hasattr(traces_response, 'data') or not traces_response.data:
                break

            for trace in traces_response.data:
                # Convert trace to dict for easier handling
                trace_dict = trace.dict() if hasattr(trace, 'dict') else trace
                # Extract only essential fields for config optimization
                all_traces.append(extract_essential_fields_trace(trace_dict))

            fetched_count = len(traces_response.data)
            print(f"  Page {page}: fetched {fetched_count} traces (total: {len(all_traces)})")

            # Check if we've reached the limit or no more data
            if limit and len(all_traces) >= limit:
                print(f"  ✓ Limit of {limit} traces reached")
                break

            # Check if there are more pages
            if fetched_count < fetch_size:
                break

            page += 1

        except Exception as e:
            print(f"Error retrieving traces: {e}", file=sys.stderr)
            raise

    if limit and len(all_traces) == limit:
        print(f"\n✓ Retrieved {len(all_traces)} traces (limit reached)")
    else:
        print(f"\n✓ Retrieved {len(all_traces)} traces (all matching traces)")
    return all_traces


def save_traces(traces, output_file):
    """Save traces to JSON file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(traces, f, indent=2, default=str)

    print(f"Traces saved to: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve traces from Langfuse',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get last 50 traces from the past 3 days:
  %(prog)s --days 3 --limit 50

  # Get 100 traces from a specific date range:
  %(prog)s --start-date 2025-01-01 --end-date 2025-01-31 --limit 100

  # Get all traces for a specific user (no limit):
  %(prog)s --user-id "user123"

For more information, see the module docstring.
        """
    )

    # Output control (most important)
    output_group = parser.add_argument_group('Output Control')
    output_group.add_argument('--limit', type=int,
                             help='[RECOMMENDED] Maximum number of traces to retrieve. '
                                  'Use this to control output size. '
                                  'If not specified, retrieves ALL matching traces. '
                                  'Example: --limit 100')
    output_group.add_argument('--output', default='/tmp/langfuse_analysis/traces.json',
                             help='Output file path (default: /tmp/langfuse_analysis/traces.json)')

    # Time range filters
    time_group = parser.add_argument_group('Time Range Filters')
    time_group.add_argument('--days', type=int, default=7,
                           help='Number of days to look back (default: 7)')
    time_group.add_argument('--start-date',
                           help='Start date in ISO format (e.g., 2025-01-01)')
    time_group.add_argument('--end-date',
                           help='End date in ISO format (e.g., 2025-01-31)')

    # Content filters
    filter_group = parser.add_argument_group('Content Filters')
    filter_group.add_argument('--project', help='Project name to filter by')
    filter_group.add_argument('--name', default=None,
                             help='Filter by trace name (default: None - no filtering, '
                                  'use --name "pattern" to filter by specific name)')
    filter_group.add_argument('--user-id', help='Filter by user ID')
    filter_group.add_argument('--session-id', help='Filter by session ID')
    filter_group.add_argument('--tags', nargs='+', help='Filter by tags (space-separated)')

    args = parser.parse_args()

    # If explicit dates are provided, don't use the default days value
    days_param = args.days if not (args.start_date or args.end_date) else None

    try:
        traces = retrieve_traces(
            project_name=args.project,
            days=days_param,
            start_date=args.start_date,
            end_date=args.end_date,
            user_id=args.user_id,
            tags=args.tags,
            session_id=args.session_id,
            name=args.name,
            limit=args.limit
        )

        output_path = save_traces(traces, args.output)

        print(f"\n✓ Success! Retrieved {len(traces)} traces")
        print(f"✓ Output: {output_path}")

    except Exception as e:
        print(f"\n✗ Failed to retrieve traces: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
