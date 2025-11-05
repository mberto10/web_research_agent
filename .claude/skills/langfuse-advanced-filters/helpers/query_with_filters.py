#!/usr/bin/env python3
"""
Query Langfuse Traces/Observations with Advanced Filters

This script uses Langfuse's advanced filtering API to perform precise queries
with operators like >, <, =, contains, etc.

Usage:
    python3 query_with_filters.py \
      --view traces \
      --filters '[{"column": "latency", "operator": ">", "value": 5000, "type": "number"}]' \
      --from-date "2025-11-01" \
      --limit 50

Filter Structure:
    {
      "column": "string",    // Column to filter on
      "operator": "string",  // =, >, <, >=, <=, contains, not_contains, in, not_in
      "value": "any",        // Value to compare against
      "type": "string",      // string, number, datetime, stringObject
      "key": "string"        // Required for metadata filters
    }
"""

import argparse
import json
import os
import sys
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add helpers directory to path
sys.path.insert(0, str(Path(__file__).parent))
from langfuse_client import get_api_base_url, get_auth_headers


def parse_filters(filters_arg: Optional[str], filters_file: Optional[str]) -> List[Dict[str, Any]]:
    """
    Parse filters from command line argument or file.

    Args:
        filters_arg: JSON string of filters
        filters_file: Path to JSON file containing filters

    Returns:
        List of filter dictionaries
    """
    if filters_file:
        try:
            with open(filters_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading filters file: {e}", file=sys.stderr)
            sys.exit(1)
    elif filters_arg:
        try:
            return json.loads(filters_arg)
        except json.JSONDecodeError as e:
            print(f"Error parsing filters JSON: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        return []


def validate_filter(filter_obj: Dict[str, Any]) -> bool:
    """
    Validate a single filter object.

    Args:
        filter_obj: Filter dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = ['column', 'operator', 'value', 'type']

    # Check required fields
    for field in required_fields:
        if field not in filter_obj:
            print(f"Error: Filter missing required field '{field}': {filter_obj}", file=sys.stderr)
            return False

    # Validate operator
    valid_operators = ['=', '>', '<', '>=', '<=', 'contains', 'not_contains', 'in', 'not_in']
    if filter_obj['operator'] not in valid_operators:
        print(f"Error: Invalid operator '{filter_obj['operator']}'. Valid: {valid_operators}", file=sys.stderr)
        return False

    # Validate type
    valid_types = ['string', 'number', 'datetime', 'stringObject']
    if filter_obj['type'] not in valid_types:
        print(f"Error: Invalid type '{filter_obj['type']}'. Valid: {valid_types}", file=sys.stderr)
        return False

    # Check for key if filtering on metadata
    if filter_obj['column'] == 'metadata' and 'key' not in filter_obj:
        print(f"Error: Metadata filter requires 'key' field: {filter_obj}", file=sys.stderr)
        return False

    return True


def validate_filters(filters: List[Dict[str, Any]]) -> bool:
    """Validate all filters in list."""
    if not isinstance(filters, list):
        print(f"Error: Filters must be a list, got {type(filters)}", file=sys.stderr)
        return False

    for i, f in enumerate(filters):
        if not validate_filter(f):
            print(f"Error in filter #{i+1}", file=sys.stderr)
            return False

    return True


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime object."""
    if not date_str:
        return None

    try:
        # Try ISO format first
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        try:
            # Try YYYY-MM-DD format
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            print(f"Error: Invalid date format '{date_str}'. Use ISO format or YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)


def query_traces_with_filters(
    filters: List[Dict[str, Any]],
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Query traces using advanced filters via direct API call.

    Note: The Langfuse Python SDK doesn't currently expose the advanced
    filtering API, so we make direct HTTP requests.

    Args:
        filters: List of filter dictionaries
        from_date: ISO format start date
        to_date: ISO format end date
        limit: Maximum results to return
        name: Filter by trace name
        user_id: Filter by user ID
        session_id: Filter by session ID
        tags: Filter by tags

    Returns:
        List of trace objects matching filters
    """
    base_url = get_api_base_url()
    headers = get_auth_headers()

    # Build query parameters
    params = {
        'limit': min(limit, 500),  # API max is typically 500
        'page': 1
    }

    # Add time range
    if from_date:
        params['from_timestamp'] = parse_date(from_date).isoformat()
    if to_date:
        params['to_timestamp'] = parse_date(to_date).isoformat()

    # Add basic filters
    if name:
        params['name'] = name
    if user_id:
        params['user_id'] = user_id
    if session_id:
        params['session_id'] = session_id
    if tags:
        params['tags'] = tags

    # Add advanced filters as JSON in body
    # Note: This assumes Langfuse API supports filters in request body
    # If not, we'll need to fetch all and filter client-side
    request_body = {}
    if filters:
        request_body['filters'] = filters

    print(f"Querying traces with {len(filters)} filter(s)...")
    print(f"  Time range: {from_date or 'any'} to {to_date or 'now'}")
    print(f"  Limit: {limit}")

    all_traces = []

    try:
        # Try POST request with filters in body
        url = f"{base_url}/api/public/traces"

        # First, try to use filters in query (if API supports it)
        # Otherwise, fetch all and filter client-side
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        traces = data.get('data', [])

        # If advanced filters provided, apply client-side filtering
        if filters:
            traces = apply_client_side_filters(traces, filters)

        all_traces.extend(traces[:limit])

        print(f"  ✓ Retrieved {len(all_traces)} trace(s)")

    except requests.exceptions.RequestException as e:
        print(f"Error querying Langfuse API: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)

    return all_traces


def query_observations_with_filters(
    filters: List[Dict[str, Any]],
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    name: Optional[str] = None,
    trace_id: Optional[str] = None,
    level: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query observations using advanced filters.

    Args:
        filters: List of filter dictionaries
        from_date: ISO format start date
        to_date: ISO format end date
        limit: Maximum results to return
        name: Filter by observation name
        trace_id: Filter by trace ID
        level: Filter by level (DEBUG, DEFAULT, WARNING, ERROR)

    Returns:
        List of observation objects matching filters
    """
    base_url = get_api_base_url()
    headers = get_auth_headers()

    # Build query parameters
    params = {
        'limit': min(limit, 500),
        'page': 1
    }

    # Add time range
    if from_date:
        params['fromStartTime'] = parse_date(from_date).isoformat()
    if to_date:
        params['toStartTime'] = parse_date(to_date).isoformat()

    # Add basic filters
    if name:
        params['name'] = name
    if trace_id:
        params['traceId'] = trace_id
    if level:
        params['level'] = level

    print(f"Querying observations with {len(filters)} filter(s)...")
    print(f"  Time range: {from_date or 'any'} to {to_date or 'now'}")
    print(f"  Limit: {limit}")

    all_observations = []

    try:
        url = f"{base_url}/api/public/observations"

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        observations = data.get('data', [])

        # Apply client-side filtering if filters provided
        if filters:
            observations = apply_client_side_filters(observations, filters)

        all_observations.extend(observations[:limit])

        print(f"  ✓ Retrieved {len(all_observations)} observation(s)")

    except requests.exceptions.RequestException as e:
        print(f"Error querying Langfuse API: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)

    return all_observations


def apply_client_side_filters(items: List[Dict], filters: List[Dict[str, Any]]) -> List[Dict]:
    """
    Apply filters client-side (for when API doesn't support them directly).

    Args:
        items: List of traces or observations
        filters: List of filter dictionaries

    Returns:
        Filtered list of items
    """
    filtered = []

    for item in items:
        if matches_all_filters(item, filters):
            filtered.append(item)

    return filtered


def matches_all_filters(item: Dict, filters: List[Dict[str, Any]]) -> bool:
    """Check if item matches all filters (AND logic)."""
    for f in filters:
        if not matches_filter(item, f):
            return False
    return True


def matches_filter(item: Dict, filter_obj: Dict[str, Any]) -> bool:
    """Check if item matches a single filter."""
    column = filter_obj['column']
    operator = filter_obj['operator']
    value = filter_obj['value']
    filter_type = filter_obj['type']
    key = filter_obj.get('key')

    # Get field value from item
    if column == 'metadata' and key:
        # Metadata filter
        metadata = item.get('metadata', {})
        field_value = metadata.get(key)
    else:
        # Direct field
        field_value = item.get(column)

    # Handle missing field
    if field_value is None:
        return operator in ['!=', 'not_contains', 'not_in']

    # Apply operator
    if operator == '=':
        return field_value == value
    elif operator == '!=':
        return field_value != value
    elif operator == '>':
        return field_value > value
    elif operator == '<':
        return field_value < value
    elif operator == '>=':
        return field_value >= value
    elif operator == '<=':
        return field_value <= value
    elif operator == 'contains':
        return value in str(field_value)
    elif operator == 'not_contains':
        return value not in str(field_value)
    elif operator == 'in':
        return field_value in value
    elif operator == 'not_in':
        return field_value not in value
    else:
        return False


def save_results(results: List[Dict[str, Any]], output_path: str, filters: List[Dict[str, Any]]):
    """Save query results to JSON file."""
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'filters_applied': filters,
        'result_count': len(results),
        'results': results
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"\n✓ Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Query Langfuse with advanced filters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find traces with high latency
  %(prog)s --view traces \\
    --filters '[{"column": "latency", "operator": ">", "value": 5000, "type": "number"}]' \\
    --limit 50

  # Find ERROR observations in edit node
  %(prog)s --view observations \\
    --filters '[
      {"column": "name", "operator": "=", "value": "edit_node", "type": "string"},
      {"column": "level", "operator": "=", "value": "ERROR", "type": "string"}
    ]' \\
    --from-date "2025-11-01"

  # Metadata filter with multiple conditions
  %(prog)s --view traces \\
    --filters '[
      {"column": "metadata", "operator": "=", "key": "case_id", "value": "0001", "type": "stringObject"},
      {"column": "latency", "operator": ">", "value": 3000, "type": "number"}
    ]' \\
    --output /tmp/slow_case_traces.json
"""
    )

    # View selection
    parser.add_argument('--view', choices=['traces', 'observations'], required=True,
                       help='Data view to query')

    # Filters
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument('--filters', type=str,
                             help='JSON array of filter objects')
    filter_group.add_argument('--filters-file', type=str,
                             help='Path to JSON file containing filters')

    # Time range
    parser.add_argument('--from-date', type=str,
                       help='Start date (ISO format or YYYY-MM-DD)')
    parser.add_argument('--to-date', type=str,
                       help='End date (ISO format or YYYY-MM-DD)')

    # Limit
    parser.add_argument('--limit', type=int, default=50,
                       help='Maximum results to return (default: 50)')

    # Trace-specific filters
    parser.add_argument('--name', type=str,
                       help='Filter by trace/observation name')
    parser.add_argument('--user-id', type=str,
                       help='Filter by user ID (traces only)')
    parser.add_argument('--session-id', type=str,
                       help='Filter by session ID (traces only)')
    parser.add_argument('--tags', nargs='+',
                       help='Filter by tags (traces only)')

    # Observation-specific filters
    parser.add_argument('--trace-id', type=str,
                       help='Filter by trace ID (observations only)')
    parser.add_argument('--level', type=str,
                       choices=['DEBUG', 'DEFAULT', 'WARNING', 'ERROR'],
                       help='Filter by level (observations only)')

    # Output
    parser.add_argument('--output', type=str,
                       default='/tmp/langfuse_queries/results.json',
                       help='Output file path')

    # Validation
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate filters without querying')

    args = parser.parse_args()

    # Parse filters
    filters = parse_filters(args.filters, args.filters_file)

    # Validate filters
    if not validate_filters(filters):
        sys.exit(1)

    if args.validate_only:
        print("✓ Filters are valid")
        print(json.dumps(filters, indent=2))
        return

    # Query based on view
    if args.view == 'traces':
        results = query_traces_with_filters(
            filters=filters,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
            name=args.name,
            user_id=args.user_id,
            session_id=args.session_id,
            tags=args.tags
        )
    else:  # observations
        results = query_observations_with_filters(
            filters=filters,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
            name=args.name,
            trace_id=args.trace_id,
            level=args.level
        )

    # Save results
    save_results(results, args.output, filters)

    print(f"\n✓ Query complete: {len(results)} result(s)")


if __name__ == '__main__':
    main()
