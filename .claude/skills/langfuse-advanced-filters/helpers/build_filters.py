#!/usr/bin/env python3
"""
Build and Validate Langfuse Advanced Filters

Interactive tool for building filter JSON with validation.

Usage:
    # Interactive mode
    python3 build_filters.py --interactive

    # Programmatic mode
    python3 build_filters.py \
      --add-filter '{"column": "metadata", "operator": "=", "key": "case_id", "value": "0001", "type": "stringObject"}' \
      --add-filter '{"column": "latency", "operator": ">", "value": 5000, "type": "number"}' \
      --validate \
      --output /tmp/my_filters.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any


def validate_filter(filter_obj: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a single filter object.

    Returns:
        (is_valid, error_message)
    """
    # Check required fields
    required_fields = ['column', 'operator', 'value', 'type']
    for field in required_fields:
        if field not in filter_obj:
            return False, f"Missing required field '{field}'"

    # Validate operator
    valid_operators = ['=', '!=', '>', '<', '>=', '<=', 'contains', 'not_contains', 'in', 'not_in']
    if filter_obj['operator'] not in valid_operators:
        return False, f"Invalid operator '{filter_obj['operator']}'. Valid: {valid_operators}"

    # Validate type
    valid_types = ['string', 'number', 'datetime', 'stringObject']
    if filter_obj['type'] not in valid_types:
        return False, f"Invalid type '{filter_obj['type']}'. Valid: {valid_types}"

    # Check for key if filtering on metadata
    if filter_obj['column'] == 'metadata' and 'key' not in filter_obj:
        return False, "Metadata filter requires 'key' field"

    # Type-specific validation
    if filter_obj['type'] == 'number':
        if not isinstance(filter_obj['value'], (int, float)):
            return False, f"Value must be numeric for type 'number', got {type(filter_obj['value'])}"

    return True, ""


def interactive_mode() -> List[Dict[str, Any]]:
    """Interactive filter builder."""
    print("=" * 60)
    print("Langfuse Advanced Filters - Interactive Builder")
    print("=" * 60)
    print()

    filters = []

    while True:
        print(f"\nCurrent filters: {len(filters)}")
        if filters:
            print(json.dumps(filters, indent=2))

        print("\nOptions:")
        print("  1. Add new filter")
        print("  2. Remove filter")
        print("  3. Validate filters")
        print("  4. Save and exit")
        print("  5. Exit without saving")

        choice = input("\nChoice (1-5): ").strip()

        if choice == '1':
            add_filter_interactive(filters)
        elif choice == '2':
            remove_filter_interactive(filters)
        elif choice == '3':
            validate_filters_interactive(filters)
        elif choice == '4':
            if validate_all_filters(filters):
                return filters
            else:
                print("\n❌ Filters have errors. Fix them before saving.")
        elif choice == '5':
            sys.exit(0)
        else:
            print("Invalid choice")


def add_filter_interactive(filters: List[Dict[str, Any]]):
    """Add a filter interactively."""
    print("\n--- Add New Filter ---")

    # Get column
    print("\nColumn to filter on:")
    print("  Common: name, level, metadata, latency, timestamp")
    column = input("Column: ").strip()

    # Get operator
    print("\nOperator:")
    print("  =, !=, >, <, >=, <=, contains, not_contains, in, not_in")
    operator = input("Operator: ").strip()

    # Get type
    print("\nData type:")
    print("  string, number, datetime, stringObject")
    data_type = input("Type: ").strip()

    # Get key (if metadata)
    key = None
    if column == 'metadata':
        print("\nMetadata key (e.g., case_id, profile_name):")
        key = input("Key: ").strip()

    # Get value
    print("\nValue to compare against:")
    value_str = input("Value: ").strip()

    # Parse value based on type
    if data_type == 'number':
        try:
            value = float(value_str) if '.' in value_str else int(value_str)
        except ValueError:
            print(f"❌ Invalid number: {value_str}")
            return
    else:
        value = value_str

    # Build filter
    filter_obj = {
        'column': column,
        'operator': operator,
        'value': value,
        'type': data_type
    }

    if key:
        filter_obj['key'] = key

    # Validate
    is_valid, error = validate_filter(filter_obj)
    if not is_valid:
        print(f"\n❌ Invalid filter: {error}")
        return

    filters.append(filter_obj)
    print(f"\n✓ Filter added")
    print(json.dumps(filter_obj, indent=2))


def remove_filter_interactive(filters: List[Dict[str, Any]]):
    """Remove a filter interactively."""
    if not filters:
        print("\n❌ No filters to remove")
        return

    print("\n--- Remove Filter ---")
    for i, f in enumerate(filters):
        print(f"{i+1}. {f}")

    try:
        index = int(input("\nFilter number to remove: ").strip()) - 1
        if 0 <= index < len(filters):
            removed = filters.pop(index)
            print(f"\n✓ Removed: {removed}")
        else:
            print("❌ Invalid index")
    except ValueError:
        print("❌ Invalid input")


def validate_filters_interactive(filters: List[Dict[str, Any]]):
    """Validate all filters and show results."""
    print("\n--- Validation Results ---")

    if not filters:
        print("⚠️  No filters to validate")
        return

    all_valid = True
    for i, f in enumerate(filters):
        is_valid, error = validate_filter(f)
        if is_valid:
            print(f"✓ Filter #{i+1}: Valid")
        else:
            print(f"❌ Filter #{i+1}: {error}")
            all_valid = False

    if all_valid:
        print(f"\n✓ All {len(filters)} filter(s) are valid")
    else:
        print(f"\n❌ Some filters have errors")


def validate_all_filters(filters: List[Dict[str, Any]]) -> bool:
    """Validate all filters silently."""
    for f in filters:
        is_valid, _ = validate_filter(f)
        if not is_valid:
            return False
    return True


def save_filters(filters: List[Dict[str, Any]], output_path: str):
    """Save filters to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(filters, f, indent=2)

    print(f"\n✓ Filters saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Build and validate Langfuse advanced filters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  %(prog)s --interactive

  # Programmatic mode
  %(prog)s \\
    --add-filter '{"column": "metadata", "operator": "=", "key": "case_id", "value": "0001", "type": "stringObject"}' \\
    --add-filter '{"column": "latency", "operator": ">", "value": 5000, "type": "number"}' \\
    --validate \\
    --output /tmp/my_filters.json
"""
    )

    parser.add_argument('--interactive', action='store_true',
                       help='Run in interactive mode')
    parser.add_argument('--add-filter', action='append',
                       help='Add a filter (JSON string)')
    parser.add_argument('--validate', action='store_true',
                       help='Validate filters')
    parser.add_argument('--output', type=str,
                       default='/tmp/langfuse_queries/filters.json',
                       help='Output file path')

    args = parser.parse_args()

    if args.interactive:
        filters = interactive_mode()
        if filters:
            save_filters(filters, args.output)
    elif args.add_filter:
        filters = []
        for filter_str in args.add_filter:
            try:
                filter_obj = json.loads(filter_str)
                is_valid, error = validate_filter(filter_obj)
                if not is_valid:
                    print(f"❌ Invalid filter: {error}", file=sys.stderr)
                    print(f"   Filter: {filter_str}", file=sys.stderr)
                    sys.exit(1)
                filters.append(filter_obj)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON: {e}", file=sys.stderr)
                sys.exit(1)

        if args.validate:
            print(f"✓ All {len(filters)} filter(s) are valid")
            print(json.dumps(filters, indent=2))

        save_filters(filters, args.output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
