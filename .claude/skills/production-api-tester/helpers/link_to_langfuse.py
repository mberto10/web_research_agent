#!/usr/bin/env python3
"""
Link to Langfuse Trace

Finds the Langfuse trace for a completed task execution.

USAGE:
======
python3 link_to_langfuse.py \
  --task-id "abc123" \
  --email "test@example.com" \
  --output /tmp/langfuse_link.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlencode

# Add langfuse helpers to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
LANGFUSE_HELPERS = PROJECT_ROOT / ".claude/skills/langfuse-optimization/helpers"
sys.path.insert(0, str(LANGFUSE_HELPERS))

try:
    from langfuse_client import get_langfuse_client
except ImportError:
    print(f"Error: Could not import langfuse helpers", file=sys.stderr)
    print(f"Expected path: {LANGFUSE_HELPERS}", file=sys.stderr)
    sys.exit(1)


def find_trace(
    task_id: str,
    email: str,
    time_range: str = "last_1_hour",
    topic: str = None
) -> dict:
    """Find Langfuse trace for task execution."""

    client = get_langfuse_client()

    # Calculate time range
    time_ranges = {
        "last_15_min": timedelta(minutes=15),
        "last_30_min": timedelta(minutes=30),
        "last_1_hour": timedelta(hours=1),
        "last_6_hours": timedelta(hours=6),
        "last_1_day": timedelta(days=1)
    }
    delta = time_ranges.get(time_range, timedelta(hours=1))
    end_time = datetime.now()
    start_time = end_time - delta

    print(f"Searching for Langfuse trace...")
    print(f"  Task ID: {task_id}")
    print(f"  Email: {email}")
    print(f"  Time range: {start_time} to {end_time}")

    # Build input filter (email and research_topic are stored in trace input, not metadata)
    input_filter = {
        "email": email
    }
    if topic:
        input_filter["research_topic"] = topic

    # Search traces
    try:
        all_traces = []
        page = 1

        while len(all_traces) < 10:  # Limit to 10 traces
            params = {
                'limit': 10,
                'page': page,
                'from_timestamp': start_time,
                'to_timestamp': end_time
            }

            traces_response = client.api.trace.list(**params)
            if not hasattr(traces_response, 'data') or not traces_response.data:
                break

            # Filter by input data (email and research_topic are in input, not metadata)
            for trace in traces_response.data:
                trace_dict = trace.dict() if hasattr(trace, 'dict') else trace
                input_data = trace_dict.get('input', {})

                # Check if input email matches
                if input_data.get('email') == email:
                    # If topic filter is provided, also check research_topic
                    if topic:
                        if input_data.get('research_topic') == topic:
                            all_traces.append(trace_dict)
                    else:
                        all_traces.append(trace_dict)

            if len(traces_response.data) < 10:
                break

            page += 1

        print(f"\n✓ Found {len(all_traces)} matching traces")

        if not all_traces:
            print(f"\n⚠️  No traces found. Possible reasons:")
            print(f"  1. Execution not complete yet (wait 30-60s)")
            print(f"  2. Time range too narrow (try --time-range last_1_day)")
            print(f"  3. Email doesn't match (check email in trace input)")
            print(f"  4. Langfuse not enabled in API")

            return {
                "task_id": task_id,
                "trace_count": 0,
                "traces": [],
                "query": {
                    "input_filter": input_filter,
                    "time_range": time_range,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
            }

        # Get latest trace
        latest_trace = sorted(all_traces, key=lambda t: t.get('timestamp', ''), reverse=True)[0]

        # Build Langfuse dashboard URL
        langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        project_id = os.getenv("LANGFUSE_PROJECT_ID", "default")  # User can set this
        trace_id = latest_trace['id']

        dashboard_url = f"{langfuse_host}/project/{project_id}/traces/{trace_id}"

        result = {
            "task_id": task_id,
            "trace_count": len(all_traces),
            "latest_trace_id": trace_id,
            "latest_trace_timestamp": latest_trace.get('timestamp'),
            "langfuse_url": dashboard_url,
            "query": {
                "input_filter": input_filter,
                "time_range": time_range,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "all_trace_ids": [t['id'] for t in all_traces]
        }

        print(f"\nLatest trace:")
        print(f"  Trace ID: {trace_id}")
        print(f"  Timestamp: {latest_trace.get('timestamp')}")
        print(f"  Langfuse URL: {dashboard_url}")

        return result

    except Exception as e:
        print(f"Error searching Langfuse: {e}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Find Langfuse trace for task execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find trace for recent task
  %(prog)s --task-id "abc123" --email "test@example.com"

  # Wider time range
  %(prog)s --task-id "abc123" --email "test@example.com" --time-range last_1_day

  # With topic filter
  %(prog)s --task-id "abc123" --email "test@example.com" --topic "AI news"
        """
    )

    # Required
    parser.add_argument('--task-id', required=True, help='Task ID from create_test_task.py')
    parser.add_argument('--email', required=True, help='Email used for task')

    # Optional
    parser.add_argument('--time-range', default='last_1_hour',
                       choices=['last_15_min', 'last_30_min', 'last_1_hour', 'last_6_hours', 'last_1_day'],
                       help='Time range to search (default: last_1_hour)')
    parser.add_argument('--topic', help='Research topic (for additional filtering)')
    parser.add_argument('--output', default='/tmp/api_test/langfuse_link.json',
                       help='Output file path')

    args = parser.parse_args()

    try:
        result = find_trace(
            task_id=args.task_id,
            email=args.email,
            time_range=args.time_range,
            topic=args.topic
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n✓ Trace link saved to: {output_path}")

        if result['trace_count'] > 0:
            print(f"\nNext steps:")
            print(f"1. View in browser: {result['langfuse_url']}")
            print(f"2. Retrieve trace data:")
            print(f"   python3 ../../langfuse-optimization/helpers/retrieve_single_trace.py {result['latest_trace_id']} --filter-essential")
            print(f"3. Analyze performance:")
            print(f"   python3 ../../strategy-builder/helpers/analyze_strategy_performance.py --traces <trace_file>")

    except Exception as e:
        print(f"\n✗ Failed to find trace: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
