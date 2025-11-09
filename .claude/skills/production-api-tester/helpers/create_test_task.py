#!/usr/bin/env python3
"""
Create Test Research Task

Creates a research task subscription in the production API.

USAGE:
======
python3 create_test_task.py \
  --api-key "$PROD_API_KEY" \
  --email "test@example.com" \
  --topic "AI developments" \
  --frequency "daily" \
  --output /tmp/task.json
"""

import argparse
import json
import os
import sys
import requests
from pathlib import Path

DEFAULT_API_URL = os.getenv("PROD_API_URL", "https://webresearchagent.replit.app")


def create_task(
    api_key: str,
    api_url: str,
    email: str,
    topic: str,
    frequency: str,
    schedule_time: str = "09:00"
) -> dict:
    """Create research task via API."""

    url = f"{api_url}/tasks"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    payload = {
        "email": email,
        "research_topic": topic,
        "frequency": frequency,
        "schedule_time": schedule_time
    }

    print(f"Creating task...")
    print(f"  API: {url}")
    print(f"  Email: {email}")
    print(f"  Topic: {topic}")
    print(f"  Frequency: {frequency}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        task = response.json()
        print(f"\n✓ Task created successfully!")
        print(f"  Task ID: {task.get('id')}")
        print(f"  Status: Active")

        return task

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
        description='Create research task subscription',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s --api-key "$PROD_API_KEY" --email "test@example.com" --topic "AI news" --frequency daily

  # With custom schedule time
  %(prog)s --api-key "$KEY" --email "test@example.com" --topic "Market analysis" --frequency weekly --schedule-time "14:30"
        """
    )

    # Required
    parser.add_argument('--api-key', required=True, help='Production API key')
    parser.add_argument('--email', required=True, help='Test email address')
    parser.add_argument('--topic', required=True, help='Research topic')
    parser.add_argument('--frequency', required=True, choices=['daily', 'weekly', 'monthly'],
                       help='Execution frequency')

    # Optional
    parser.add_argument('--api-url', default=DEFAULT_API_URL, help=f'API base URL (default: {DEFAULT_API_URL})')
    parser.add_argument('--schedule-time', default='09:00',
                       help='Schedule time in HH:MM format (default: 09:00)')
    parser.add_argument('--output', default='/tmp/api_test/task.json',
                       help='Output file path')

    args = parser.parse_args()

    try:
        task = create_task(
            api_key=args.api_key,
            api_url=args.api_url,
            email=args.email,
            topic=args.topic,
            frequency=args.frequency,
            schedule_time=args.schedule_time
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(task, f, indent=2)

        print(f"\n✓ Task details saved to: {output_path}")

    except Exception as e:
        print(f"\n✗ Failed to create task: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
