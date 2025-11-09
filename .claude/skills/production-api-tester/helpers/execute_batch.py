#!/usr/bin/env python3
"""
Execute Batch Research

Triggers batch execution for all tasks matching a frequency.

USAGE:
======
python3 execute_batch.py \
  --api-key "$PROD_API_KEY" \
  --frequency "daily" \
  --callback-url "$CALLBACK_URL"
"""

import argparse
import json
import os
import sys
import requests
from pathlib import Path

DEFAULT_API_URL = os.getenv("PROD_API_URL", "https://webresearchagent.replit.app")


def execute_batch(
    api_key: str,
    api_url: str,
    frequency: str,
    callback_url: str
) -> dict:
    """Execute batch research via API."""

    url = f"{api_url}/execute/batch"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    payload = {
        "frequency": frequency,
        "callback_url": callback_url
    }

    print(f"Executing batch research...")
    print(f"  API: {url}")
    print(f"  Frequency: {frequency}")
    print(f"  Callback: {callback_url}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        print(f"\n✓ Batch execution started!")
        print(f"  Status: {result.get('status')}")
        print(f"  Tasks found: {result.get('tasks_found')}")
        print(f"  Started at: {result.get('started_at')}")

        if result.get('tasks_found') == 0:
            print(f"\n⚠️  No tasks found for frequency '{frequency}'")
            print(f"Create a task first with create_test_task.py")

        return result

    except requests.exceptions.HTTPError as e:
        print(f"\n✗ HTTP Error: {e}", file=sys.stderr)
        if e.response:
            print(f"Response: {e.response.text}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Execute batch research',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute daily batch
  %(prog)s --api-key "$PROD_API_KEY" --frequency daily --callback-url "https://webhook.site/abc123"

  # Execute weekly batch
  %(prog)s --api-key "$KEY" --frequency weekly --callback-url "$CALLBACK_URL"
        """
    )

    # Required
    parser.add_argument('--api-key', required=True, help='Production API key')
    parser.add_argument('--frequency', required=True, choices=['daily', 'weekly', 'monthly'],
                       help='Frequency to execute')
    parser.add_argument('--callback-url', required=True,
                       help='Webhook URL to receive results')

    # Optional
    parser.add_argument('--api-url', default=DEFAULT_API_URL,
                       help=f'API base URL (default: {DEFAULT_API_URL})')
    parser.add_argument('--output', default='/tmp/api_test/execution.json',
                       help='Output file path')

    args = parser.parse_args()

    try:
        result = execute_batch(
            api_key=args.api_key,
            api_url=args.api_url,
            frequency=args.frequency,
            callback_url=args.callback_url
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"\n✓ Execution details saved to: {output_path}")
        print(f"\nℹ️  Results will be sent to: {args.callback_url}")
        print(f"Check your webhook receiver for completion notifications.")

    except Exception as e:
        print(f"\n✗ Failed to execute batch: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
