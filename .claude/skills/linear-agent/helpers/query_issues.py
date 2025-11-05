#!/usr/bin/env python3
"""
Query Issues Helper
Advanced querying and filtering of Linear issues.
"""

import argparse
import sys
import json
import csv
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from linear_client import LinearClient, LinearAPIError


def query_issues(
    client: LinearClient,
    team_name: Optional[str] = None,
    state_name: Optional[str] = None,
    assignee_id: Optional[str] = None,
    priority: Optional[int] = None,
    labels: Optional[List[str]] = None,
    search: Optional[str] = None,
    limit: int = 50,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Query issues with filters.

    Args:
        client: Linear client
        team_name: Filter by team name
        state_name: Filter by state name
        assignee_id: Filter by assignee ID
        priority: Filter by priority
        labels: Filter by labels
        search: Search in title/description
        limit: Maximum issues to return
        verbose: Print verbose output

    Returns:
        List of matching issues
    """
    # Build GraphQL query with filters
    filter_parts = []
    variables = {}

    if team_name:
        team = client.get_team_by_name(team_name)
        if not team:
            raise LinearAPIError(f"Team not found: {team_name}")
        filter_parts.append("team: { name: { eq: $teamName } }")
        variables["teamName"] = team_name
        if verbose:
            print(f"🔍 Filtering by team: {team_name}")

    if state_name:
        filter_parts.append("state: { name: { eq: $stateName } }")
        variables["stateName"] = state_name
        if verbose:
            print(f"🔍 Filtering by state: {state_name}")

    if priority is not None:
        filter_parts.append("priority: { eq: $priority }")
        variables["priority"] = priority
        if verbose:
            priority_names = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
            print(f"🔍 Filtering by priority: {priority_names.get(priority, priority)}")

    if assignee_id:
        filter_parts.append("assignee: { id: { eq: $assigneeId } }")
        variables["assigneeId"] = assignee_id
        if verbose:
            print(f"🔍 Filtering by assignee: {assignee_id}")

    # Build filter object
    filter_str = ""
    if filter_parts:
        filter_str = f"filter: {{ {', '.join(filter_parts)} }}"

    # Build query
    query = f"""
    query Issues($first: Int{', $' + ', $'.join(f'{k}: {get_graphql_type(k)}' for k in variables.keys()) if variables else ''}) {{
        issues(first: $first{', ' + filter_str if filter_str else ''}) {{
            nodes {{
                id
                identifier
                title
                description
                priority
                estimate
                state {{
                    id
                    name
                    type
                }}
                assignee {{
                    id
                    name
                    email
                }}
                team {{
                    id
                    name
                    key
                }}
                project {{
                    id
                    name
                }}
                labels {{
                    nodes {{
                        id
                        name
                        color
                    }}
                }}
                createdAt
                updatedAt
                completedAt
                url
            }}
        }}
    }}
    """

    variables["first"] = limit
    result = client._execute_query(query, variables)
    issues = result.get("issues", {}).get("nodes", [])

    # Apply client-side filters (for features not supported in GraphQL filter)
    filtered_issues = issues

    if search:
        search_lower = search.lower()
        filtered_issues = [
            issue for issue in filtered_issues
            if (search_lower in (issue.get("title") or "").lower() or
                search_lower in (issue.get("description") or "").lower())
        ]
        if verbose:
            print(f"🔍 Searching for: '{search}'")

    if labels:
        filtered_issues = [
            issue for issue in filtered_issues
            if any(
                label["name"].lower() in [l.lower() for l in labels]
                for label in issue.get("labels", {}).get("nodes", [])
            )
        ]
        if verbose:
            print(f"🔍 Filtering by labels: {', '.join(labels)}")

    if verbose:
        print(f"✓ Found {len(filtered_issues)} matching issues")

    return filtered_issues


def get_graphql_type(var_name: str) -> str:
    """Get GraphQL type for variable name."""
    type_map = {
        "teamName": "String",
        "stateName": "String",
        "priority": "Int",
        "assigneeId": "String"
    }
    return type_map.get(var_name, "String")


def format_issues_table(issues: List[Dict[str, Any]]) -> str:
    """Format issues as text table."""
    if not issues:
        return "No issues found."

    lines = []
    lines.append(f"\n{'ID':<12} {'Title':<50} {'State':<15} {'Priority':<10}")
    lines.append("-" * 90)

    for issue in issues:
        identifier = issue.get("identifier", "N/A")
        title = issue.get("title", "N/A")[:48]
        state = issue.get("state", {}).get("name", "N/A")
        priority = issue.get("priority", 0)
        priority_names = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
        priority_str = priority_names.get(priority, str(priority))

        lines.append(f"{identifier:<12} {title:<50} {state:<15} {priority_str:<10}")

    return "\n".join(lines)


def export_to_csv(issues: List[Dict[str, Any]], output_path: str):
    """Export issues to CSV file."""
    if not issues:
        print("No issues to export")
        return

    fieldnames = [
        "identifier", "title", "state", "priority", "assignee",
        "team", "labels", "estimate", "created_at", "url"
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for issue in issues:
            row = {
                "identifier": issue.get("identifier", ""),
                "title": issue.get("title", ""),
                "state": issue.get("state", {}).get("name", ""),
                "priority": issue.get("priority", ""),
                "assignee": issue.get("assignee", {}).get("name", "Unassigned"),
                "team": issue.get("team", {}).get("name", ""),
                "labels": ", ".join([l["name"] for l in issue.get("labels", {}).get("nodes", [])]),
                "estimate": issue.get("estimate", ""),
                "created_at": issue.get("createdAt", ""),
                "url": issue.get("url", "")
            }
            writer.writerow(row)

    print(f"✓ Exported {len(issues)} issues to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Query and filter Linear issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all issues for a team
  python query_issues.py --team "Backend Team"

  # Find in-progress bugs
  python query_issues.py --team "Backend" --state "In Progress" --labels "bug"

  # Search by keyword
  python query_issues.py --search "authentication" --limit 20

  # High priority issues
  python query_issues.py --team "Backend" --priority 2

  # Export to CSV
  python query_issues.py --team "Backend" --output issues.csv --format csv

  # Export to JSON
  python query_issues.py --team "Backend" --output issues.json --format json
        """
    )

    parser.add_argument("--team", help="Filter by team name")
    parser.add_argument("--state", help="Filter by state name (e.g., 'In Progress', 'Done')")
    parser.add_argument("--assignee", help="Filter by assignee ID")
    parser.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4],
                        help="Filter by priority")
    parser.add_argument("--labels", help="Comma-separated label names to filter by")
    parser.add_argument("--search", help="Search in title/description")
    parser.add_argument("--limit", type=int, default=50, help="Maximum issues to return")
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text",
                        help="Output format")
    parser.add_argument("--output", help="Output file path (for csv/json formats)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Parse labels
    label_list = []
    if args.labels:
        label_list = [l.strip() for l in args.labels.split(",") if l.strip()]

    try:
        client = LinearClient()

        issues = query_issues(
            client=client,
            team_name=args.team,
            state_name=args.state,
            assignee_id=args.assignee,
            priority=args.priority,
            labels=label_list,
            search=args.search,
            limit=args.limit,
            verbose=args.verbose
        )

        if args.format == "json":
            output = json.dumps(issues, indent=2)
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
                print(f"✓ Exported {len(issues)} issues to {args.output}")
            else:
                print(output)

        elif args.format == "csv":
            if not args.output:
                print("Error: --output required for CSV format", file=sys.stderr)
                sys.exit(1)
            export_to_csv(issues, args.output)

        else:  # text
            print(format_issues_table(issues))
            print(f"\nTotal: {len(issues)} issues")

    except LinearAPIError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
