#!/usr/bin/env python3
"""
Delete Research Task

Deletes a research task from the production API.

USAGE:
======
python3 delete_task.py \
  --api-key "$PROD_API_KEY" \
  --task-id "abc123"
"""

import argparse
import os
import sys
import requests

DEFAULT_API_URL = os.getenv("PROD_API_URL", "https://webresearchagent.replit.app")


def delete_task(
    api_key: str,
    api_url: str,
    task_id: str
) -> bool:
    """Delete research task via API."""

    url = f"{api_url}/tasks/{task_id}"
    headers = {
        "X-API-Key": api_key
    }

    print(f"Deleting task...")
    print(f"  API: {url}")
    print(f"  Task ID: {task_id}")

    try:
        response = requests.delete(url, headers=headers, timeout=30)
        response.raise_for_status()

        print(f"\n✓ Task deleted successfully!")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 404:
            print(f"\n⚠️  Task not found (may already be deleted)")
            print(f"  Task ID: {task_id}")
            return False
        else:
            print(f"\n✗ HTTP Error: {e}", file=sys.stderr)
            if e.response:
                print(f"Response: {e.response.text}", file=sys.stderr)
            raise
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Delete research task',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete single task
  %(prog)s --api-key "$PROD_API_KEY" --task-id "abc123"

  # Delete with custom API URL
  %(prog)s --api-key "$KEY" --api-url "http://localhost:8000" --task-id "abc123"
        """
    )

    # Required
    parser.add_argument('--api-key', required=True, help='Production API key')
    parser.add_argument('--task-id', required=True, help='Task ID to delete')

    # Optional
    parser.add_argument('--api-url', default=DEFAULT_API_URL,
                       help=f'API base URL (default: {DEFAULT_API_URL})')

    args = parser.parse_args()

    try:
        success = delete_task(
            api_key=args.api_key,
            api_url=args.api_url,
            task_id=args.task_id
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n✗ Failed to delete task: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
