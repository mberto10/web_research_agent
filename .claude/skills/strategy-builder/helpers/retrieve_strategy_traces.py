#!/usr/bin/env python3
"""
Retrieve Strategy Traces

Fetches Langfuse traces for a specific research strategy.
Wrapper around langfuse-optimization helpers with strategy-specific filtering.

USAGE:
======
# Get traces for strategy (last 7 days)
python3 retrieve_strategy_traces.py --strategy "daily_news_briefing" --limit 50

# Custom date range
python3 retrieve_strategy_traces.py \
  --strategy "financial_research" \
  --start-date "2025-11-01" \
  --end-date "2025-11-08" \
  --limit 100

# Filter by errors only
python3 retrieve_strategy_traces.py \
  --strategy "company/dossier" \
  --days 30 \
  --errors-only

# With size optimization
python3 retrieve_strategy_traces.py \
  --strategy "daily_news_briefing" \
  --filter-essential \
  --output /tmp/traces.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root and langfuse-optimization helpers to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LANGFUSE_HELPERS = PROJECT_ROOT / ".claude/skills/langfuse-optimization/helpers"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(LANGFUSE_HELPERS))

try:
    from langfuse_client import get_langfuse_client
except ImportError as e:
    print(f"Error: Could not import langfuse helpers: {e}", file=sys.stderr)
    print(f"Expected path: {LANGFUSE_HELPERS}", file=sys.stderr)
    sys.exit(1)


def parse_time_range(days=None, start_date=None, end_date=None):
    """Parse time range into datetime objects."""
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


def filter_essential_fields(trace_data):
    """Strip large fields from trace data for size reduction."""

    def clean_trace(trace):
        """Clean a single trace."""
        cleaned = {
            'id': trace.get('id'),
            'name': trace.get('name'),
            'timestamp': trace.get('timestamp'),
            'metadata': trace.get('metadata'),
            'input': trace.get('input'),
            'output': trace.get('output'),
            'latency': trace.get('latency'),
            'level': trace.get('level'),
            'status_message': trace.get('status_message'),
        }

        # Strip large output fields
        if isinstance(cleaned.get('output'), dict):
            output = cleaned['output']
            # Keep only essential fields
            if 'facts_pack' in output:
                # Replace with summary
                facts = output['facts_pack']
                output['facts_pack'] = {
                    '_stripped': True,
                    'count': len(facts) if isinstance(facts, list) else 0,
                    'size_kb': len(str(facts)) // 1024 if facts else 0
                }
            if 'validation_report' in output:
                # Replace with summary
                report = output['validation_report']
                output['validation_report'] = {
                    '_stripped': True,
                    'failed_checks': [c.get('name', 'unknown') for c in report.get('failed', [])[:5]] if isinstance(report, dict) else []
                }

        return cleaned

    def clean_observation(obs):
        """Clean a single observation."""
        cleaned = {
            'id': obs.get('id'),
            'trace_id': obs.get('trace_id'),
            'name': obs.get('name'),
            'type': obs.get('type'),
            'start_time': obs.get('start_time'),
            'end_time': obs.get('end_time'),
            'latency': obs.get('latency'),
            'level': obs.get('level'),
            'status_message': obs.get('status_message'),
            'metadata': obs.get('metadata'),
            'input': obs.get('input'),
            'output': obs.get('output'),
        }

        # Strip large fields from output
        if isinstance(cleaned.get('output'), dict):
            output = cleaned['output']
            # Evidence summaries instead of full content
            if 'evidence' in output:
                evidence = output['evidence']
                if isinstance(evidence, list):
                    output['evidence'] = {
                        '_stripped': True,
                        'count': len(evidence),
                        'tools_used': list(set(e.get('tool') for e in evidence if e.get('tool')))
                    }

        return cleaned

    # Clean traces
    if 'traces' in trace_data:
        trace_data['traces'] = [clean_trace(t) for t in trace_data['traces']]

    # Clean observations
    if 'observations' in trace_data:
        cleaned_obs = {}
        for trace_id, obs_list in trace_data['observations'].items():
            cleaned_obs[trace_id] = [clean_observation(o) for o in obs_list]
        trace_data['observations'] = cleaned_obs

    return trace_data


def retrieve_strategy_traces(
    strategy_slug: str,
    days: int = 7,
    start_date: str = None,
    end_date: str = None,
    limit: int = 50,
    filter_essential: bool = False,
    filter_all: bool = False,
    errors_only: bool = False
):
    """Retrieve traces for a specific strategy."""

    client = get_langfuse_client()
    start_time, end_time = parse_time_range(days, start_date, end_date)

    print(f"Retrieving traces for strategy: {strategy_slug}")
    print(f"  Time range: {start_time} to {end_time}")
    print(f"  Limit: {limit} traces")
    if filter_essential:
        print(f"  Size optimization: Essential fields only (~95% reduction)")
    if filter_all:
        print(f"  Size optimization: Maximum (~96% reduction)")
    if errors_only:
        print(f"  Filter: Errors only")

    all_traces = []
    all_observations = {}
    page = 1
    page_limit = min(limit, 50) if limit else 50

    while True:
        # Calculate remaining traces to fetch
        remaining = limit - len(all_traces) if limit else page_limit
        fetch_size = min(remaining, page_limit) if limit else page_limit

        # Build query parameters
        params = {
            'limit': fetch_size,
            'page': page,
            'from_timestamp': start_time,
            'to_timestamp': end_time,
        }

        # Filter by strategy in metadata
        # Note: Langfuse API may not support metadata filtering server-side,
        # so we'll filter client-side after retrieval

        try:
            traces_response = client.api.trace.list(**params)

            if not hasattr(traces_response, 'data') or not traces_response.data:
                break

            # Filter traces by strategy
            for trace in traces_response.data:
                trace_dict = trace.dict() if hasattr(trace, 'dict') else trace

                # Check if trace belongs to this strategy
                metadata = trace_dict.get('metadata', {})
                trace_strategy = metadata.get('strategy_slug')

                # Match by strategy slug
                if trace_strategy != strategy_slug:
                    continue

                # Filter by errors if requested
                if errors_only:
                    level = trace_dict.get('level', 'DEFAULT')
                    if level != 'ERROR':
                        # Also check observations for errors
                        has_error = False
                        try:
                            obs_response = client.api.observations.list(trace_id=trace_dict['id'])
                            if hasattr(obs_response, 'data'):
                                for obs in obs_response.data:
                                    obs_dict = obs.dict() if hasattr(obs, 'dict') else obs
                                    if obs_dict.get('level') == 'ERROR':
                                        has_error = True
                                        break
                        except:
                            pass
                        if not has_error:
                            continue

                all_traces.append(trace_dict)

                # Retrieve observations for this trace
                try:
                    obs_response = client.api.observations.list(trace_id=trace_dict['id'])
                    if hasattr(obs_response, 'data'):
                        all_observations[trace_dict['id']] = [
                            obs.dict() if hasattr(obs, 'dict') else obs
                            for obs in obs_response.data
                        ]
                except Exception as e:
                    print(f"  Warning: Could not retrieve observations for trace {trace_dict['id']}: {e}", file=sys.stderr)

            fetched_count = len(traces_response.data)
            print(f"  Page {page}: fetched {fetched_count} traces, {len(all_traces)} match strategy (total: {len(all_traces)})")

            # Check if we've reached the limit
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

    if not all_traces:
        print(f"\n⚠️  No traces found for strategy '{strategy_slug}'", file=sys.stderr)
        print(f"Verify that:", file=sys.stderr)
        print(f"  1. Strategy slug is correct", file=sys.stderr)
        print(f"  2. Strategy has been executed (traces exist)", file=sys.stderr)
        print(f"  3. Traces have metadata.strategy_slug field", file=sys.stderr)
        print(f"  4. Time range covers execution period", file=sys.stderr)

    print(f"\n✓ Retrieved {len(all_traces)} traces for strategy '{strategy_slug}'")
    print(f"✓ Retrieved observations for {len(all_observations)} traces")

    # Build bundle
    bundle = {
        'query_params': {
            'strategy_slug': strategy_slug,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'limit': limit,
            'filter_essential': filter_essential,
            'filter_all': filter_all,
            'errors_only': errors_only,
        },
        'traces': all_traces,
        'observations': all_observations,
        'trace_count': len(all_traces),
        'trace_ids': [t['id'] for t in all_traces]
    }

    # Apply size optimization if requested
    if filter_essential or filter_all:
        bundle = filter_essential_fields(bundle)
        print(f"✓ Applied size optimization")

    return bundle


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve Langfuse traces for a specific strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get last 50 traces for daily news briefing
  %(prog)s --strategy "daily_news_briefing" --limit 50

  # Custom date range for financial research
  %(prog)s --strategy "financial_research" --start-date "2025-11-01" --end-date "2025-11-08"

  # Errors only with size optimization
  %(prog)s --strategy "company/dossier" --errors-only --filter-essential
        """
    )

    parser.add_argument('--strategy', required=True, help='Strategy slug (e.g., "daily_news_briefing")')

    # Time range
    time_group = parser.add_argument_group('Time Range')
    time_group.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    time_group.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    time_group.add_argument('--end-date', help='End date (YYYY-MM-DD)')

    # Filtering
    filter_group = parser.add_argument_group('Filtering')
    filter_group.add_argument('--limit', type=int, default=50, help='Max traces to retrieve (default: 50)')
    filter_group.add_argument('--errors-only', action='store_true', help='Only retrieve traces with errors')

    # Size optimization
    size_group = parser.add_argument_group('Size Optimization')
    size_group.add_argument('--filter-essential', action='store_true',
                           help='Strip large fields for 95%% size reduction')
    size_group.add_argument('--filter-all', action='store_true',
                           help='Maximum compression (96%% reduction)')

    # Output
    parser.add_argument('--output', default='/tmp/strategy_analysis/strategy_traces.json',
                       help='Output file path')

    args = parser.parse_args()

    # Use explicit dates if provided
    days_param = None if (args.start_date or args.end_date) else args.days

    try:
        bundle = retrieve_strategy_traces(
            strategy_slug=args.strategy,
            days=days_param,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            filter_essential=args.filter_essential,
            filter_all=args.filter_all,
            errors_only=args.errors_only
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(bundle, f, indent=2, default=str)

        print(f"\n✓ Output saved to: {output_path}")
        print(f"✓ {bundle['trace_count']} traces, {len(bundle['observations'])} with observations")

        # Print summary
        if bundle['traces']:
            print(f"\nSample trace IDs:")
            for trace_id in bundle['trace_ids'][:5]:
                print(f"  - {trace_id}")

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
