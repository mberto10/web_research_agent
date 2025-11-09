#!/usr/bin/env python3
"""
Health Check

Checks production API health status.

USAGE:
======
python3 health_check.py
python3 health_check.py --api-url "http://localhost:8000"
python3 health_check.py --continuous --interval 60
"""

import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime

DEFAULT_API_URL = os.getenv("PROD_API_URL", "https://webresearchagent.replit.app")


def check_health(api_url: str) -> dict:
    """Check API health."""

    url = f"{api_url}/health"

    try:
        start_time = time.time()
        response = requests.get(url, timeout=10)
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        response.raise_for_status()
        health = response.json()

        health['response_time_ms'] = round(response_time, 2)
        health['healthy'] = health.get('status') == 'online'

        return health

    except requests.exceptions.ConnectionError:
        return {
            'healthy': False,
            'status': 'offline',
            'error': 'Connection failed - API not reachable'
        }
    except requests.exceptions.Timeout:
        return {
            'healthy': False,
            'status': 'timeout',
            'error': 'Request timed out after 10s'
        }
    except Exception as e:
        return {
            'healthy': False,
            'status': 'error',
            'error': str(e)
        }


def print_health_status(health: dict, timestamp: str = None):
    """Print health status in readable format."""

    if timestamp:
        print(f"[{timestamp}]", end=" ")

    if health.get('healthy'):
        print("✓ API is healthy")
        print(f"  Status: {health.get('status', 'unknown')}")
        if 'database' in health:
            print(f"  Database: {health['database']}")
        if 'langfuse' in health:
            print(f"  Langfuse: {health['langfuse']}")
        if 'response_time_ms' in health:
            print(f"  Response time: {health['response_time_ms']}ms")
    else:
        print("✗ API is unhealthy")
        print(f"  Status: {health.get('status', 'unknown')}")
        if 'error' in health:
            print(f"  Error: {health['error']}")


def main():
    parser = argparse.ArgumentParser(
        description='Check production API health',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single check
  %(prog)s

  # Check custom URL
  %(prog)s --api-url "http://localhost:8000"

  # Continuous monitoring (check every 60s for 1 hour)
  %(prog)s --continuous --interval 60 --duration 3600
        """
    )

    parser.add_argument('--api-url', default=DEFAULT_API_URL,
                       help=f'API base URL (default: {DEFAULT_API_URL})')
    parser.add_argument('--continuous', action='store_true',
                       help='Continuously monitor health')
    parser.add_argument('--interval', type=int, default=60,
                       help='Check interval in seconds (default: 60)')
    parser.add_argument('--duration', type=int, default=0,
                       help='Monitor duration in seconds (0 = infinite, default: 0)')
    parser.add_argument('--output', help='Output file for health logs (JSON lines)')

    args = parser.parse_args()

    output_file = None
    if args.output:
        output_file = open(args.output, 'a')

    try:
        if args.continuous:
            print(f"Monitoring API health: {args.api_url}")
            print(f"Interval: {args.interval}s")
            if args.duration > 0:
                print(f"Duration: {args.duration}s")
            else:
                print(f"Duration: Infinite (Ctrl+C to stop)")
            print("="*60)

            start_time = time.time()
            iteration = 0

            while True:
                iteration += 1
                timestamp = datetime.now().isoformat()

                health = check_health(args.api_url)
                print_health_status(health, timestamp)

                if output_file:
                    log_entry = {
                        'timestamp': timestamp,
                        'iteration': iteration,
                        **health
                    }
                    output_file.write(json.dumps(log_entry) + '\n')
                    output_file.flush()

                # Check duration
                if args.duration > 0:
                    elapsed = time.time() - start_time
                    if elapsed >= args.duration:
                        print(f"\nMonitoring complete ({args.duration}s elapsed)")
                        break

                # Wait for next check
                print()  # Blank line
                time.sleep(args.interval)

        else:
            # Single check
            health = check_health(args.api_url)
            print_health_status(health)

            if args.output:
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    **health
                }
                output_file.write(json.dumps(log_entry) + '\n')

            # Exit code based on health
            sys.exit(0 if health.get('healthy') else 1)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    finally:
        if output_file:
            output_file.close()
            print(f"\nHealth logs saved to: {args.output}")


if __name__ == "__main__":
    main()
