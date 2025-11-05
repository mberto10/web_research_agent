#!/usr/bin/env python3
"""
Query Langfuse Metrics API with Advanced Filters

This script uses Langfuse's Metrics API to retrieve aggregated data
with advanced filtering capabilities.

Usage:
    python3 query_metrics.py \
      --view traces \
      --metrics '[{"measure": "latency", "aggregation": "avg"}]' \
      --dimensions '[{"field": "metadata.case_id"}]' \
      --filters '[{"column": "metadata", "operator": "=", "key": "case_id", "value": "0001", "type": "stringObject"}]' \
      --from-date "2025-11-01" \
      --to-date "2025-11-04"
"""

import argparse
import json
import sys
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))
from langfuse_client import get_api_base_url, get_auth_headers


def parse_json_arg(arg: Optional[str], arg_name: str) -> Any:
    """Parse JSON argument."""
    if not arg:
        return None

    try:
        return json.loads(arg)
    except json.JSONDecodeError as e:
        print(f"Error parsing {arg_name} JSON: {e}", file=sys.stderr)
        sys.exit(1)


def query_metrics(
    view: str,
    metrics: List[Dict[str, str]],
    dimensions: Optional[List[Dict[str, str]]] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    time_granularity: Optional[str] = None,
    order_by: Optional[List[Dict[str, str]]] = None,
    row_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Query Langfuse Metrics API with filters.

    Args:
        view: 'traces' or 'observations'
        metrics: List of metric definitions
        dimensions: List of dimension definitions (optional)
        filters: List of filter dictionaries (optional)
        from_date: ISO format start date (required)
        to_date: ISO format end date (required)
        time_granularity: Time grouping (minute, hour, day, week, month, auto)
        order_by: List of order-by definitions
        row_limit: Max rows to return

    Returns:
        Metrics API response data
    """
    base_url = get_api_base_url()
    headers = get_auth_headers()

    # Build request body
    request_body = {
        'view': view,
        'metrics': metrics,
        'fromTimestamp': from_date,
        'toTimestamp': to_date
    }

    # Add optional fields
    if dimensions:
        request_body['dimensions'] = dimensions
    if filters:
        request_body['filters'] = filters
    if time_granularity:
        request_body['timeDimension'] = {'granularity': time_granularity}
    if order_by:
        request_body['orderBy'] = order_by
    if row_limit:
        request_body['config'] = {'row_limit': row_limit}

    print(f"Querying metrics...")
    print(f"  View: {view}")
    print(f"  Metrics: {len(metrics)}")
    print(f"  Dimensions: {len(dimensions) if dimensions else 0}")
    print(f"  Filters: {len(filters) if filters else 0}")
    print(f"  Time range: {from_date} to {to_date}")

    try:
        url = f"{base_url}/api/public/metrics"

        response = requests.post(
            url,
            headers=headers,
            json=request_body,
            timeout=60
        )
        response.raise_for_status()

        data = response.json()
        print(f"  ✓ Query successful")

        return data

    except requests.exceptions.RequestException as e:
        print(f"Error querying Langfuse Metrics API: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def save_results(results: Dict[str, Any], output_path: str, request_body: Dict[str, Any]):
    """Save metrics query results to JSON file."""
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'query': request_body,
        'results': results
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"\n✓ Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Query Langfuse Metrics API with advanced filters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Average latency by case_id
  %(prog)s --view traces \\
    --metrics '[{"measure": "latency", "aggregation": "avg"}]' \\
    --dimensions '[{"field": "metadata.case_id"}]' \\
    --from-date "2025-11-01" --to-date "2025-11-04"

  # Error count by observation name
  %(prog)s --view observations \\
    --metrics '[{"measure": "count", "aggregation": "count"}]' \\
    --dimensions '[{"field": "name"}]' \\
    --filters '[{"column": "level", "operator": "=", "value": "ERROR", "type": "string"}]' \\
    --from-date "2025-11-01" --to-date "2025-11-04"

  # P95 latency trend over time
  %(prog)s --view traces \\
    --metrics '[{"measure": "latency", "aggregation": "p95"}]' \\
    --filters '[{"column": "metadata", "operator": "=", "key": "case_id", "value": "0001", "type": "stringObject"}]' \\
    --time-granularity day \\
    --from-date "2025-10-01" --to-date "2025-11-04"
"""
    )

    # Required arguments
    parser.add_argument('--view', choices=['traces', 'observations'], required=True,
                       help='Data view to query')
    parser.add_argument('--metrics', type=str, required=True,
                       help='JSON array of metric definitions: [{"measure": "...", "aggregation": "..."}]')
    parser.add_argument('--from-date', type=str, required=True,
                       help='Start date (ISO format, e.g., 2025-11-01T00:00:00Z)')
    parser.add_argument('--to-date', type=str, required=True,
                       help='End date (ISO format, e.g., 2025-11-04T23:59:59Z)')

    # Optional arguments
    parser.add_argument('--dimensions', type=str,
                       help='JSON array of dimension definitions: [{"field": "..."}]')
    parser.add_argument('--filters', type=str,
                       help='JSON array of filter objects (same format as query_with_filters.py)')
    parser.add_argument('--time-granularity', type=str,
                       choices=['minute', 'hour', 'day', 'week', 'month', 'auto'],
                       help='Time grouping granularity')
    parser.add_argument('--order-by', type=str,
                       help='JSON array of order-by definitions: [{"field": "...", "direction": "asc|desc"}]')
    parser.add_argument('--row-limit', type=int,
                       help='Maximum rows to return (1-1000)')

    # Output
    parser.add_argument('--output', type=str,
                       default='/tmp/langfuse_queries/metrics.json',
                       help='Output file path')

    args = parser.parse_args()

    # Parse JSON arguments
    metrics = parse_json_arg(args.metrics, 'metrics')
    dimensions = parse_json_arg(args.dimensions, 'dimensions')
    filters = parse_json_arg(args.filters, 'filters')
    order_by = parse_json_arg(args.order_by, 'order_by')

    # Validate metrics
    if not isinstance(metrics, list) or len(metrics) == 0:
        print("Error: metrics must be a non-empty list", file=sys.stderr)
        sys.exit(1)

    # Query metrics
    request_body = {
        'view': args.view,
        'metrics': metrics,
        'fromTimestamp': args.from_date,
        'toTimestamp': args.to_date
    }

    if dimensions:
        request_body['dimensions'] = dimensions
    if filters:
        request_body['filters'] = filters
    if args.time_granularity:
        request_body['timeDimension'] = {'granularity': args.time_granularity}
    if order_by:
        request_body['orderBy'] = order_by
    if args.row_limit:
        request_body['config'] = {'row_limit': args.row_limit}

    results = query_metrics(
        view=args.view,
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
        from_date=args.from_date,
        to_date=args.to_date,
        time_granularity=args.time_granularity,
        order_by=order_by,
        row_limit=args.row_limit
    )

    # Save results
    save_results(results, args.output, request_body)

    print(f"\n✓ Query complete")


if __name__ == '__main__':
    main()
