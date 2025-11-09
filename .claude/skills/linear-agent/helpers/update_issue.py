#!/usr/bin/env python3
"""
Update Issue Helper
Update existing Linear issues with validation and conflict detection.
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from linear_client import LinearClient, LinearAPIError


def parse_labels(labels_str: Optional[str]) -> List[str]:
    """Parse comma-separated labels string."""
    if not labels_str:
        return []
    return [label.strip() for label in labels_str.split(",") if label.strip()]


def get_label_ids(
    client: LinearClient,
    label_names: List[str],
    team_id: Optional[str] = None
) -> List[str]:
    """Convert label names to IDs."""
    if not label_names:
        return []

    all_labels = client.list_labels(team_id=team_id)
    label_map = {label["name"].lower(): label["id"] for label in all_labels}

    label_ids = []
    missing_labels = []

    for name in label_names:
        label_id = label_map.get(name.lower())
        if label_id:
            label_ids.append(label_id)
        else:
            missing_labels.append(name)

    if missing_labels:
        print(f"⚠ Warning: Labels not found: {', '.join(missing_labels)}")

    return label_ids


def update_issue_interactive(
    client: LinearClient,
    issue_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    labels: Optional[List[str]] = None,
    state: Optional[str] = None,
    assignee_id: Optional[str] = None,
    estimate: Optional[int] = None,
    comment: Optional[str] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Update issue with before/after tracking.

    Args:
        client: Linear client
        issue_id: Issue ID to update
        title: New title
        description: New description
        priority: New priority (0-4)
        labels: List of label names
        state: State name (e.g., "In Progress", "Done")
        assignee_id: New assignee ID
        estimate: New estimate
        comment: Optional comment explaining changes
        verbose: Print verbose output

    Returns:
        Updated issue dictionary
    """
    # Get current issue state
    if verbose:
        print(f"🔍 Fetching current state of {issue_id}...")

    try:
        current_issue = client.get_issue(issue_id)
    except LinearAPIError as e:
        raise LinearAPIError(f"Issue not found: {issue_id}") from e

    if verbose:
        print(f"✓ Found issue: {current_issue.get('identifier')} - {current_issue.get('title')}")
        print(f"  Current state: {current_issue.get('state', {}).get('name', 'Unknown')}")

    # Prepare updates
    updates = {}
    changes_summary = []

    if title:
        updates["title"] = title
        changes_summary.append(f"Title: '{current_issue.get('title')}' → '{title}'")

    if description is not None:
        updates["description"] = description
        old_desc = current_issue.get("description", "")[:50]
        new_desc = description[:50]
        changes_summary.append(f"Description: '{old_desc}...' → '{new_desc}...'")

    if priority is not None:
        updates["priority"] = priority
        priority_names = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
        old_pri = current_issue.get("priority")
        changes_summary.append(
            f"Priority: {priority_names.get(old_pri, old_pri)} → {priority_names.get(priority)}"
        )

    if estimate is not None:
        updates["estimate"] = estimate
        old_est = current_issue.get("estimate")
        changes_summary.append(f"Estimate: {old_est} → {estimate} points")

    if assignee_id:
        updates["assigneeId"] = assignee_id
        old_assignee = current_issue.get("assignee", {}).get("name", "Unassigned")
        changes_summary.append(f"Assignee: {old_assignee} → {assignee_id}")

    # Handle labels
    if labels:
        team_id = current_issue.get("team", {}).get("id")
        label_ids = get_label_ids(client, labels, team_id)
        if label_ids:
            updates["labelIds"] = label_ids
            old_labels = [l["name"] for l in current_issue.get("labels", {}).get("nodes", [])]
            changes_summary.append(f"Labels: {old_labels} → {labels}")

    # Handle state changes
    if state:
        team_id = current_issue.get("team", {}).get("id")
        state_obj = client.get_state_by_name(state, team_id)
        if state_obj:
            updates["stateId"] = state_obj["id"]
            old_state = current_issue.get("state", {}).get("name", "Unknown")
            changes_summary.append(f"State: {old_state} → {state}")
            if verbose:
                print(f"✓ Found state: {state} (ID: {state_obj['id']})")
        else:
            print(f"⚠ Warning: State not found: '{state}'")
            if verbose:
                # Show available states
                states = client.list_workflow_states(team_id)
                state_names = [s["name"] for s in states]
                print(f"  Available states: {', '.join(state_names)}")

    # Apply updates only if there are changes
    if updates:
        # Show changes before applying
        if verbose:
            print("\n📝 Proposed changes:")
            for change in changes_summary:
                print(f"  • {change}")

        # Apply updates
        if verbose:
            print("\n🔄 Applying updates...")

        updated_issue = client.update_issue(issue_id, **updates)
    else:
        if verbose and not comment:
            print("⚠ No changes specified")
        updated_issue = current_issue

    # Add comment if provided (independent of other updates)
    if comment:
        if verbose:
            print(f"💬 Adding comment...")
        client.create_comment(issue_id, comment)
        if verbose:
            print(f"✓ Comment added successfully")

    if verbose:
        print("✓ Update complete!")

    return updated_issue


def main():
    parser = argparse.ArgumentParser(
        description="Update Linear issue with validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update issue title
  python update_issue.py --issue-id ISS-123 --title "New title"

  # Change status and add comment
  python update_issue.py --issue-id ISS-123 --state "In Progress" \\
    --comment "Starting work on this"

  # Update priority and estimate
  python update_issue.py --issue-id ISS-123 --priority 1 --estimate 8

  # Update labels
  python update_issue.py --issue-id ISS-123 --labels "bug,p1,backend"

  # Multiple updates with comment
  python update_issue.py --issue-id ISS-123 \\
    --priority 2 --assignee "user_abc123" \\
    --comment "Reprioritized and assigned" \\
    --verbose
        """
    )

    parser.add_argument("--issue-id", required=True, help="Issue ID to update")
    parser.add_argument("--title", help="New title")
    parser.add_argument("--description", help="New description (supports markdown)")
    parser.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4],
                        help="Priority: 0=None, 1=Urgent, 2=High, 3=Normal, 4=Low")
    parser.add_argument("--labels", help="Comma-separated label names")
    parser.add_argument("--state", help="State name (e.g., 'In Progress', 'Done')")
    parser.add_argument("--assignee", help="Assignee ID")
    parser.add_argument("--estimate", type=int, help="Story point estimate")
    parser.add_argument("--comment", help="Comment explaining changes")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Parse labels
    label_list = parse_labels(args.labels)

    try:
        client = LinearClient()

        issue = update_issue_interactive(
            client=client,
            issue_id=args.issue_id,
            title=args.title,
            description=args.description,
            priority=args.priority,
            labels=label_list,
            state=args.state,
            assignee_id=args.assignee,
            estimate=args.estimate,
            comment=args.comment,
            verbose=args.verbose
        )

        if args.output == "json":
            print(json.dumps(issue, indent=2))
        else:
            print("\n✅ Issue updated successfully!")
            print(f"  ID: {issue.get('identifier')}")
            print(f"  Title: {issue.get('title')}")
            print(f"  URL: {issue.get('url')}")
            if "state" in issue:
                print(f"  State: {issue['state']['name']}")

    except LinearAPIError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
