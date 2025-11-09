#!/usr/bin/env python3
"""
Get Issue Helper
Retrieve a specific Linear issue by ID or identifier.
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from linear_client import LinearClient, LinearAPIError


def get_issue_by_identifier(client: LinearClient, identifier: str, verbose: bool = False) -> Optional[Dict[str, Any]]:
    """
    Get issue by identifier (e.g., 'MB90-285').

    Args:
        client: Linear client
        identifier: Issue identifier (e.g., 'MB90-285')
        verbose: Print verbose output

    Returns:
        Issue dictionary if found, None otherwise
    """
    if verbose:
        print(f"🔍 Searching for issue: {identifier}")

    query = """
    query GetIssueByIdentifier($identifier: String!) {
        issue(id: $identifier) {
            id
            identifier
            title
            description
            priority
            estimate
            state {
                id
                name
                type
            }
            assignee {
                id
                name
                email
            }
            team {
                id
                name
                key
            }
            project {
                id
                name
            }
            labels {
                nodes {
                    id
                    name
                    color
                }
            }
            createdAt
            updatedAt
            completedAt
            url
        }
    }
    """

    try:
        result = client._execute_query(query, {"identifier": identifier})
        issue = result.get("issue")

        if issue and verbose:
            print(f"✓ Found issue: {issue.get('identifier')} - {issue.get('title')}")

        return issue
    except LinearAPIError as e:
        if verbose:
            print(f"❌ Error: {e}")
        return None


def print_issue_details(issue: Dict[str, Any], format: str = "text"):
    """Print issue details in specified format."""
    if format == "json":
        print(json.dumps(issue, indent=2))
        return

    # Text format
    print("\n" + "=" * 80)
    print(f"Issue: {issue.get('identifier')}")
    print("=" * 80)
    print(f"\nTitle: {issue.get('title')}")
    print(f"URL: {issue.get('url')}")
    print(f"\nTeam: {issue.get('team', {}).get('name', 'N/A')}")
    print(f"State: {issue.get('state', {}).get('name', 'N/A')}")

    priority = issue.get('priority', 0)
    priority_names = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
    print(f"Priority: {priority_names.get(priority, 'Unknown')}")

    assignee = issue.get('assignee')
    if assignee:
        print(f"Assignee: {assignee.get('name')} ({assignee.get('email')})")
    else:
        print("Assignee: Unassigned")

    estimate = issue.get('estimate')
    if estimate:
        print(f"Estimate: {estimate} points")

    labels = issue.get('labels', {}).get('nodes', [])
    if labels:
        label_names = [l['name'] for l in labels]
        print(f"Labels: {', '.join(label_names)}")

    project = issue.get('project')
    if project:
        print(f"Project: {project.get('name')}")

    print(f"\nCreated: {issue.get('createdAt')}")
    print(f"Updated: {issue.get('updatedAt')}")

    completed_at = issue.get('completedAt')
    if completed_at:
        print(f"Completed: {completed_at}")

    description = issue.get('description', '')
    if description:
        print(f"\nDescription:\n{'-' * 80}")
        print(description)
        print("-" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve a Linear issue by identifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get issue by identifier
  python get_issue.py MB90-285

  # Get issue with verbose output
  python get_issue.py MB90-285 --verbose

  # Get issue as JSON
  python get_issue.py MB90-285 --format json
        """
    )

    parser.add_argument("identifier", help="Issue identifier (e.g., MB90-285)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        client = LinearClient()
        issue = get_issue_by_identifier(client, args.identifier, args.verbose)

        if issue:
            print_issue_details(issue, args.format)
        else:
            print(f"❌ Issue not found: {args.identifier}", file=sys.stderr)
            sys.exit(1)

    except LinearAPIError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
