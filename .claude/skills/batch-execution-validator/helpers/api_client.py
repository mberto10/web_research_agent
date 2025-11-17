#!/usr/bin/env python3
"""
Batch Execution API Client
Triggers batch execution via production API and retrieves task information.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests


def get_api_key() -> str:
    """Get API key from environment."""
    api_key = os.getenv('API_SECRET_KEY')
    if not api_key:
        print("ERROR: API_SECRET_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    return api_key


def get_tasks_for_frequency(api_url: str, api_key: str, frequency: str) -> List[Dict[str, Any]]:
    """
    Retrieve all active tasks for the given frequency.

    Args:
        api_url: Base API URL
        api_key: API authentication key
        frequency: Task frequency (daily, weekly, monthly)

    Returns:
        List of task dictionaries
    """
    # Note: The API doesn't have a direct endpoint to list tasks by frequency
    # We'll need to query by known test emails or all tasks
    # For now, we'll skip this and rely on the batch execution response
    return []


def trigger_batch_execution(
    api_url: str,
    api_key: str,
    frequency: str,
    callback_url: str = "https://defaulte29fc699127e425da75fed341dc328.38.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/05a44fcda78f472d9943dc52d3e66641/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2l-aB7LtZ7hDnyqUdZg4lccHzr0H_favXxG-VZqSmd8"
) -> Dict[str, Any]:
    """
    Trigger batch execution for specified frequency.

    Args:
        api_url: Base API URL
        api_key: API authentication key
        frequency: Frequency to execute (daily, weekly, monthly)
        callback_url: Webhook callback URL (default: Power Automate webhook)

    Returns:
        Response data with execution metadata
    """
    endpoint = f"{api_url.rstrip('/')}/execute/batch"

    headers = {
        'X-API-Key': api_key,
        'Content-Type': 'application/json'
    }

    payload = {
        'frequency': frequency,
        'callback_url': callback_url
    }

    print(f"Triggering batch execution...")
    print(f"  API URL: {endpoint}")
    print(f"  Frequency: {frequency}")
    print(f"  Callback URL: {callback_url}")

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        print(f"\n✓ Batch execution triggered successfully")
        print(f"  Status: {data.get('status')}")
        print(f"  Tasks found: {data.get('tasks_found')}")
        print(f"  Started at: {data.get('started_at')}")

        return data

    except requests.exceptions.RequestException as e:
        print(f"\n✗ Failed to trigger batch execution: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def get_tasks_by_email(api_url: str, api_key: str, email: str) -> List[Dict[str, Any]]:
    """
    Get tasks for a specific email to extract task IDs.

    Args:
        api_url: Base API URL
        api_key: API authentication key
        email: User email

    Returns:
        List of task dictionaries
    """
    endpoint = f"{api_url.rstrip('/')}/tasks"

    headers = {
        'X-API-Key': api_key,
        'Content-Type': 'application/json'
    }

    params = {'email': email}

    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to retrieve tasks for {email}: {e}", file=sys.stderr)
        return []


def collect_task_ids(api_url: str, api_key: str, test_emails: Optional[List[str]] = None) -> List[str]:
    """
    Collect task IDs from test emails for trace retrieval.

    Args:
        api_url: Base API URL
        api_key: API authentication key
        test_emails: List of test email addresses

    Returns:
        List of task IDs
    """
    if not test_emails:
        # Default test emails
        test_emails = [
            "test@example.com",
            "test1@example.com",
            "test2@example.com"
        ]

    task_ids = []

    print(f"\nCollecting task IDs from test emails...")

    for email in test_emails:
        tasks = get_tasks_by_email(api_url, api_key, email)
        for task in tasks:
            task_id = task.get('id')
            if task_id:
                task_ids.append(task_id)
                print(f"  ✓ {email}: {task_id}")

    if not task_ids:
        print("  Warning: No task IDs collected. Trace retrieval may need manual session_ids.")

    return task_ids


def main():
    parser = argparse.ArgumentParser(
        description='Trigger batch execution and collect metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger daily batch with default wait
  python3 api_client.py --api-url https://api.example.com --frequency daily

  # Trigger with custom callback and wait time
  python3 api_client.py --api-url https://api.example.com --frequency daily \\
    --callback-url https://webhook.site/abc123 --wait 240

  # Collect task IDs from specific emails
  python3 api_client.py --api-url https://api.example.com --frequency daily \\
    --test-emails test1@example.com test2@example.com
        """
    )

    parser.add_argument(
        '--api-url',
        required=True,
        help='Base API URL (e.g., https://research-agent-api.replit.app)'
    )

    parser.add_argument(
        '--frequency',
        required=True,
        choices=['daily', 'weekly', 'monthly'],
        help='Frequency to execute'
    )

    parser.add_argument(
        '--callback-url',
        default='https://defaulte29fc699127e425da75fed341dc328.38.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/05a44fcda78f472d9943dc52d3e66641/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2l-aB7LtZ7hDnyqUdZg4lccHzr0H_favXxG-VZqSmd8',
        help='Webhook callback URL (default: Power Automate webhook)'
    )

    parser.add_argument(
        '--wait',
        type=int,
        default=180,
        help='Seconds to wait for execution completion (default: 180)'
    )

    parser.add_argument(
        '--test-emails',
        nargs='+',
        help='Test email addresses to collect task IDs from'
    )

    parser.add_argument(
        '--output',
        help='Output file for execution metadata (JSON)'
    )

    args = parser.parse_args()

    # Get API key
    api_key = get_api_key()

    # Capture start timestamp
    started_at = datetime.utcnow().isoformat() + 'Z'

    # Trigger batch execution
    batch_response = trigger_batch_execution(
        args.api_url,
        api_key,
        args.frequency,
        args.callback_url
    )

    # Collect task IDs
    task_ids = collect_task_ids(args.api_url, api_key, args.test_emails)

    # Wait for execution
    if args.wait > 0:
        print(f"\nWaiting {args.wait} seconds for execution to complete...")
        time.sleep(args.wait)
        print("✓ Wait complete")

    # Build output metadata
    output = {
        'triggered_at': started_at,
        'frequency': args.frequency,
        'tasks_found': batch_response.get('tasks_found', 0),
        'api_status': batch_response.get('status'),
        'task_ids': task_ids,
        'callback_url': args.callback_url,
        'wait_seconds': args.wait
    }

    # Save or print output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n✓ Execution metadata saved to: {args.output}")
    else:
        print("\n" + "="*60)
        print("EXECUTION METADATA")
        print("="*60)
        print(json.dumps(output, indent=2))
        print("="*60)

    print("\nNext step:")
    print("Run trace_fetcher.py with the following parameters:")
    print(f"  --from-timestamp \"{started_at}\"")
    print(f"  --tags batch_execution {args.frequency}")
    if task_ids:
        print(f"  --session-ids \"{','.join(task_ids)}\"")


if __name__ == '__main__':
    main()
