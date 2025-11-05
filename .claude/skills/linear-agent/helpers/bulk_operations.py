#!/usr/bin/env python3
"""
Bulk Operations Helper
Batch operations for creating and updating multiple issues.
"""

import argparse
import sys
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from linear_client import LinearClient, LinearAPIError
from create_issue import create_issue_with_template, parse_labels


def load_batch_file(file_path: str) -> Dict[str, Any]:
    """
    Load batch operations from YAML or JSON file.

    Args:
        file_path: Path to batch file

    Returns:
        Batch configuration dictionary

    Expected format:
        team: "Backend Team"
        issues:
          - title: "Issue 1"
            description: "Description 1"
            labels: ["bug", "p1"]
          - title: "Issue 2"
            description: "Description 2"
            priority: 2
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Batch file not found: {file_path}")

    with open(path, 'r') as f:
        if path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif path.suffix == '.json':
            return json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")


def create_issues_batch(
    client: LinearClient,
    batch_config: Dict[str, Any],
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Create multiple issues from batch configuration.

    Args:
        client: Linear client
        batch_config: Batch configuration with team and issues list
        verbose: Print verbose output

    Returns:
        List of created issue dictionaries
    """
    team = batch_config.get("team")
    if not team:
        raise ValueError("Batch config must specify 'team' field")

    issues_data = batch_config.get("issues", [])
    if not issues_data:
        raise ValueError("Batch config must contain 'issues' list")

    created_issues = []
    total = len(issues_data)

    print(f"📦 Creating {total} issues in team '{team}'...\n")

    for i, issue_data in enumerate(issues_data, 1):
        try:
            title = issue_data.get("title")
            if not title:
                print(f"⚠ Skipping issue {i}/{total}: No title provided")
                continue

            print(f"[{i}/{total}] Creating: {title[:60]}...")

            # Extract fields
            description = issue_data.get("description")
            priority = issue_data.get("priority")
            estimate = issue_data.get("estimate")
            template_name = issue_data.get("template")
            template_vars = issue_data.get("template_vars", {})

            # Parse labels
            labels = issue_data.get("labels", [])
            if isinstance(labels, str):
                labels = parse_labels(labels)

            # Create issue
            issue = create_issue_with_template(
                client=client,
                team_name_or_id=team,
                title=title,
                description=description,
                template_name=template_name,
                template_vars=template_vars,
                priority=priority,
                labels=labels,
                estimate=estimate,
                verbose=verbose
            )

            created_issues.append(issue)
            print(f"  ✓ Created {issue['identifier']}: {issue['url']}")

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    print(f"\n✅ Created {len(created_issues)}/{total} issues successfully")
    return created_issues


def update_issues_batch(
    client: LinearClient,
    updates: List[Dict[str, Any]],
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Update multiple issues in batch.

    Args:
        client: Linear client
        updates: List of update configs with issue_id and fields to update
        verbose: Print verbose output

    Returns:
        List of updated issue dictionaries

    Expected format:
        - issue_id: "ISS-123"
          state: "In Progress"
          assignee: "user_abc"
        - issue_id: "ISS-124"
          priority: 1
          labels: ["urgent"]
    """
    updated_issues = []
    total = len(updates)

    print(f"📝 Updating {total} issues...\n")

    for i, update_data in enumerate(updates, 1):
        try:
            issue_id = update_data.get("issue_id")
            if not issue_id:
                print(f"⚠ Skipping update {i}/{total}: No issue_id provided")
                continue

            print(f"[{i}/{total}] Updating {issue_id}...")

            # Get current issue
            current = client.get_issue(issue_id)

            # Prepare updates
            updates_dict = {}

            if "title" in update_data:
                updates_dict["title"] = update_data["title"]
            if "description" in update_data:
                updates_dict["description"] = update_data["description"]
            if "priority" in update_data:
                updates_dict["priority"] = update_data["priority"]
            if "estimate" in update_data:
                updates_dict["estimate"] = update_data["estimate"]
            if "assignee_id" in update_data:
                updates_dict["assigneeId"] = update_data["assignee_id"]

            # Handle labels
            if "labels" in update_data:
                labels = update_data["labels"]
                if isinstance(labels, str):
                    labels = parse_labels(labels)
                team_id = current.get("team", {}).get("id")
                # Convert label names to IDs
                all_labels = client.list_labels(team_id=team_id)
                label_map = {l["name"].lower(): l["id"] for l in all_labels}
                label_ids = [label_map.get(name.lower()) for name in labels if name.lower() in label_map]
                if label_ids:
                    updates_dict["labelIds"] = label_ids

            if not updates_dict:
                print(f"  ⚠ No valid updates for {issue_id}")
                continue

            # Apply update
            updated = client.update_issue(issue_id, **updates_dict)
            updated_issues.append(updated)

            print(f"  ✓ Updated {updated['identifier']}")

            # Add comment if provided
            if "comment" in update_data:
                client.create_comment(issue_id, update_data["comment"])
                print(f"    💬 Added comment")

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()

    print(f"\n✅ Updated {len(updated_issues)}/{total} issues successfully")
    return updated_issues


def main():
    parser = argparse.ArgumentParser(
        description="Bulk operations for Linear issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create issues from YAML file
  python bulk_operations.py --action create --input issues_batch.yaml

  # Update issues from JSON file
  python bulk_operations.py --action update --input updates_batch.json

  # Create with verbose output
  python bulk_operations.py --action create --input batch.yaml --verbose

Batch file format (YAML):
  team: "Backend Team"
  issues:
    - title: "Fix authentication bug"
      description: "Users report timeout"
      labels: ["bug", "p1"]
      priority: 2
    - title: "Add rate limiting"
      description: "Implement API rate limits"
      labels: ["feature"]
      estimate: 5

Update file format (YAML):
  - issue_id: "ISS-123"
    state: "In Progress"
    comment: "Starting work"
  - issue_id: "ISS-124"
    priority: 1
    labels: ["urgent"]
        """
    )

    parser.add_argument("--action", required=True, choices=["create", "update"],
                        help="Bulk action to perform")
    parser.add_argument("--input", required=True, help="Input file path (YAML or JSON)")
    parser.add_argument("--output", help="Output file path for results (JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        client = LinearClient()

        if args.action == "create":
            batch_config = load_batch_file(args.input)
            results = create_issues_batch(client, batch_config, args.verbose)

        elif args.action == "update":
            updates_list = load_batch_file(args.input)
            if isinstance(updates_list, dict) and "updates" in updates_list:
                updates_list = updates_list["updates"]
            results = update_issues_batch(client, updates_list, args.verbose)

        # Save results if output specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")

    except (LinearAPIError, ValueError, FileNotFoundError) as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
