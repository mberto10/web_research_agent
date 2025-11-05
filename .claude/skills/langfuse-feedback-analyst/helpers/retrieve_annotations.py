#!/usr/bin/env python3
"""
Retrieve Annotation Queue Items from Langfuse
Fetches annotated items from a specific annotation queue by ID

USAGE:
======
Retrieve all items from a queue:
  python retrieve_annotations.py --queue-id <queue_id>

Retrieve only completed annotations:
  python retrieve_annotations.py --queue-id <queue_id> --status completed

Get full annotation data (scores + comments):
  python retrieve_annotations.py --queue-id <queue_id> --include-annotations

Limit number of items:
  python retrieve_annotations.py --queue-id <queue_id> --limit 50

EXAMPLES:
=========
# Get all annotated items from queue (basic metadata only)
python retrieve_annotations.py --queue-id abc123 --output /tmp/langfuse_analysis/annotations.json

# Get completed annotations WITH full scores and comments
python retrieve_annotations.py --queue-id abc123 --status completed --include-annotations

# Get first 100 items with full annotation data
python retrieve_annotations.py --queue-id abc123 --limit 100 --include-annotations
"""

import argparse
import json
import os
import sys
import requests
from pathlib import Path
from typing import Optional, List, Dict

# Add helpers directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def get_auth():
    """Get authentication credentials from environment variables."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        print("ERROR: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set", file=sys.stderr)
        sys.exit(1)

    return (public_key, secret_key)


def get_host():
    """Get Langfuse host URL from environment."""
    return os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


def retrieve_queue_items(queue_id: str, status: Optional[str] = None, limit: Optional[int] = None,
                         include_annotations: bool = False) -> List[Dict]:
    """
    Retrieve items from an annotation queue with pagination.

    Args:
        queue_id: The annotation queue ID
        status: Optional status filter (e.g., "completed", "pending")
        limit: Maximum number of items to retrieve (None = all items)
        include_annotations: If True, fetch full trace data with scores and comments

    Returns:
        List of annotation queue items (optionally enriched with annotation data)
    """
    host = get_host()
    auth = get_auth()

    print(f"Retrieving annotation queue items...")
    print(f"  Queue ID: {queue_id}")
    if status:
        print(f"  Status filter: {status}")
    if limit:
        print(f"  Limit: {limit}")

    all_items = []
    page = 1
    page_limit = 50  # Fetch 50 items per page

    while True:
        # Build URL and parameters
        url = f"{host}/api/public/annotation-queues/{queue_id}/items"
        params = {
            'page': page,
            'limit': page_limit
        }

        if status:
            params['status'] = status

        try:
            response = requests.get(url, auth=auth, params=params)
            response.raise_for_status()

            data = response.json()

            # Handle pagination response structure
            if 'data' not in data or not data['data']:
                break

            items = data['data']
            all_items.extend(items)

            print(f"  Retrieved page {page} ({len(items)} items)")

            # Check if we've reached the limit
            if limit and len(all_items) >= limit:
                all_items = all_items[:limit]
                break

            # Check if there are more pages
            meta = data.get('meta', {})
            total_pages = meta.get('totalPages', 1)

            if page >= total_pages:
                break

            page += 1

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}", file=sys.stderr)
            print(f"Response: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error retrieving annotation queue items: {e}", file=sys.stderr)
            raise

    print(f"\nTotal items retrieved: {len(all_items)}")

    # Optionally fetch full annotations (scores + comments) for each item
    if include_annotations:
        print("\nFetching full annotation data (scores + comments)...")
        all_items = enrich_with_annotations(all_items)

    return all_items


def enrich_with_annotations(items: List[Dict]) -> List[Dict]:
    """
    Fetch full trace data for each item to get scores and comments.

    Args:
        items: List of annotation queue items

    Returns:
        Items enriched with scores and comments from traces
    """
    host = get_host()
    auth = get_auth()

    enriched_items = []

    for i, item in enumerate(items, 1):
        trace_id = item.get('objectId')
        if not trace_id:
            enriched_items.append(item)
            continue

        try:
            # Fetch trace to get scores and comments
            url = f"{host}/api/public/traces/{trace_id}"
            response = requests.get(url, auth=auth)
            response.raise_for_status()

            trace = response.json()

            # Add annotation data to item
            item['annotations'] = {
                'scores': trace.get('scores', []),
                'comments': trace.get('comments', []),
                'trace_metadata': trace.get('metadata', {})
            }

            # Print progress
            num_scores = len(trace.get('scores', []))
            num_comments = len(trace.get('comments', []))
            print(f"  [{i}/{len(items)}] {trace_id[:8]}... - {num_scores} scores, {num_comments} comments")

            enriched_items.append(item)

        except Exception as e:
            print(f"  Warning: Could not fetch annotations for {trace_id}: {e}", file=sys.stderr)
            enriched_items.append(item)

    return enriched_items


def get_queue_info(queue_id: str) -> Dict:
    """
    Get information about the annotation queue.

    Args:
        queue_id: The annotation queue ID

    Returns:
        Queue metadata
    """
    host = get_host()
    auth = get_auth()

    url = f"{host}/api/public/annotation-queues/{queue_id}"

    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Warning: Could not retrieve queue info: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Warning: Error getting queue info: {e}", file=sys.stderr)
        return {}


def save_annotations(items: List[Dict], output_file: str, queue_info: Optional[Dict] = None):
    """Save annotation items to JSON file with optional queue metadata."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "queue_info": queue_info or {},
        "total_items": len(items),
        "items": items
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"Annotations saved to: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve annotation queue items from Langfuse',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get all items from a queue:
  %(prog)s --queue-id abc123

  # Get only completed annotations:
  %(prog)s --queue-id abc123 --status completed

  # Limit to first 100 items:
  %(prog)s --queue-id abc123 --limit 100

For more information, see the module docstring.
        """
    )

    # Required arguments
    parser.add_argument('--queue-id', required=True,
                       help='Annotation queue ID (required)')

    # Optional filters
    parser.add_argument('--status',
                       help='Filter by status (e.g., "completed", "pending")')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of items to retrieve')
    parser.add_argument('--include-annotations', action='store_true',
                       help='Fetch full annotation data (scores + comments) for each item')

    # Output
    parser.add_argument('--output', default='/tmp/langfuse_analysis/annotations.json',
                       help='Output file path (default: /tmp/langfuse_analysis/annotations.json)')

    args = parser.parse_args()

    try:
        # Get queue info first
        print("Fetching queue information...")
        queue_info = get_queue_info(args.queue_id)
        if queue_info:
            print(f"  Queue name: {queue_info.get('name', 'Unknown')}")
            print(f"  Description: {queue_info.get('description', 'N/A')}")

        # Retrieve annotation items
        items = retrieve_queue_items(
            queue_id=args.queue_id,
            status=args.status,
            limit=args.limit,
            include_annotations=args.include_annotations
        )

        # Save to file
        output_path = save_annotations(items, args.output, queue_info)

        print(f"\n✓ Success! Retrieved {len(items)} annotation items")
        print(f"✓ Output: {output_path}")

        # Print summary
        if items:
            print("\nSummary:")
            statuses = {}
            for item in items:
                status = item.get('status', 'unknown')
                statuses[status] = statuses.get(status, 0) + 1

            for status, count in sorted(statuses.items()):
                print(f"  {status}: {count}")

    except Exception as e:
        print(f"\n✗ Failed to retrieve annotations: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
