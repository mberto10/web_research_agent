#!/usr/bin/env python3
"""
Validate Strategy YAML

Validates strategy YAML files against the schema and checks for common issues.

USAGE:
======
# Basic validation
python3 validate_strategy.py --strategy /tmp/new_strategy.yaml

# Strict mode (fail on warnings)
python3 validate_strategy.py --strategy /tmp/strategy.yaml --strict

# Save validation report
python3 validate_strategy.py --strategy /tmp/strategy.yaml --output /tmp/validation.json
"""

import argparse
import json
import re
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from jsonschema import validate, ValidationError
    SCHEMA_PATH = PROJECT_ROOT / "strategies" / "schema.json"
    if SCHEMA_PATH.exists():
        with open(SCHEMA_PATH) as f:
            STRATEGY_SCHEMA = json.load(f)
    else:
        STRATEGY_SCHEMA = None
except Exception as e:
    print(f"Warning: Could not load strategy schema: {e}", file=sys.stderr)
    STRATEGY_SCHEMA = None


def load_strategy_yaml(file_path: str) -> Tuple[Dict[str, Any], List[str]]:
    """Load and parse YAML file."""
    errors = []

    try:
        with open(file_path, 'r') as f:
            content = f.read()
            strategy = yaml.safe_load(content)

        if not isinstance(strategy, dict):
            errors.append("Strategy file must contain a YAML dictionary")
            return {}, errors

        return strategy, errors

    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error: {e}")
        return {}, errors
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return {}, errors


def validate_schema(strategy: Dict[str, Any]) -> List[str]:
    """Validate against JSON schema."""
    errors = []

    if not STRATEGY_SCHEMA:
        errors.append("Schema file not found - skipping schema validation")
        return errors

    try:
        validate(instance=strategy, schema=STRATEGY_SCHEMA)
    except ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
        if e.path:
            errors.append(f"  Path: {' > '.join(str(p) for p in e.path)}")

    return errors


def validate_required_fields(strategy: Dict[str, Any]) -> List[str]:
    """Check for required top-level fields."""
    errors = []

    required_fields = ['meta', 'tool_chain']
    for field in required_fields:
        if field not in strategy:
            errors.append(f"Missing required field: {field}")

    # Check meta fields
    if 'meta' in strategy:
        meta = strategy['meta']
        meta_required = ['slug', 'version', 'category', 'time_window', 'depth']
        for field in meta_required:
            if field not in meta:
                errors.append(f"Missing required meta field: {field}")

    return errors


def validate_tool_chain(tool_chain: List[Dict]) -> Tuple[List[str], List[str]]:
    """Validate tool chain structure."""
    errors = []
    warnings = []

    if not tool_chain:
        errors.append("tool_chain is empty - strategy must have at least one tool step")
        return errors, warnings

    for i, step in enumerate(tool_chain):
        step_num = i + 1

        # Check for name or use field
        if 'name' not in step and 'use' not in step:
            errors.append(f"Step {step_num}: Missing 'name' or 'use' field")

        # Check params/inputs
        if 'name' in step and 'params' not in step:
            warnings.append(f"Step {step_num}: 'params' field missing (using defaults)")

        if 'use' in step and 'inputs' not in step:
            warnings.append(f"Step {step_num}: 'inputs' field missing (using defaults)")

    return errors, warnings


def validate_variable_interpolation(strategy: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Check variable interpolation syntax."""
    errors = []
    warnings = []

    # Common variable patterns
    var_pattern = re.compile(r'\{\{(\w+)\}\}')

    # Extract all used variables
    used_vars = set()

    def extract_vars(obj, path=""):
        """Recursively extract variable names."""
        if isinstance(obj, str):
            matches = var_pattern.findall(obj)
            for match in matches:
                used_vars.add(match)
        elif isinstance(obj, dict):
            for key, value in obj.items():
                extract_vars(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                extract_vars(item, f"{path}[{idx}]")

    extract_vars(strategy)

    # Check for common variables
    expected_vars = {'topic', 'start_date', 'end_date', 'current_date', 'search_recency_filter'}
    unexpected_vars = used_vars - expected_vars

    if unexpected_vars:
        warnings.append(f"Uncommon variables used: {', '.join(unexpected_vars)}")
        warnings.append("  Ensure these are defined in strategy index or filled at runtime")

    # Check for malformed interpolation
    strategy_str = json.dumps(strategy)
    malformed = re.findall(r'\{(?!\{)(\w+)\}(?!\})', strategy_str)
    if malformed:
        errors.append(f"Malformed variable interpolation (use {{{{var}}}} not {{var}}): {', '.join(set(malformed))}")

    return errors, warnings


def validate_limits(strategy: Dict[str, Any]) -> List[str]:
    """Validate limits configuration."""
    warnings = []

    limits = strategy.get('limits', {})

    if not limits:
        warnings.append("No 'limits' defined - using defaults")
        return warnings

    max_results = limits.get('max_results')
    if max_results and max_results > 30:
        warnings.append(f"max_results={max_results} is high - may cause context length issues")

    max_llm_queries = limits.get('max_llm_queries')
    if max_llm_queries and max_llm_queries > 5:
        warnings.append(f"max_llm_queries={max_llm_queries} is high - may be slow and expensive")

    return warnings


def validate_domains(strategy: Dict[str, Any]) -> List[str]:
    """Check domain filter configuration."""
    warnings = []

    def check_domains(obj, path=""):
        """Recursively check domain filters."""
        if isinstance(obj, dict):
            # Check for domain filter fields
            if 'search_domain_filter' in obj:
                domains = obj['search_domain_filter']
                if isinstance(domains, list) and len(domains) > 20:
                    warnings.append(f"{path}: search_domain_filter has {len(domains)} domains (max 20 for Sonar)")

            if 'include_domains' in obj:
                domains = obj['include_domains']
                if isinstance(domains, list) and len(domains) > 10:
                    warnings.append(f"{path}: include_domains has {len(domains)} domains (recommend max 10)")

            for key, value in obj.items():
                check_domains(value, f"{path}.{key}" if path else key)

        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                check_domains(item, f"{path}[{idx}]")

    check_domains(strategy)
    return warnings


def run_validation(file_path: str, strict: bool = False) -> Dict[str, Any]:
    """Run all validation checks."""

    result = {
        'file_path': file_path,
        'valid': True,
        'errors': [],
        'warnings': []
    }

    # Load YAML
    strategy, load_errors = load_strategy_yaml(file_path)
    result['errors'].extend(load_errors)

    if load_errors:
        result['valid'] = False
        return result

    # Schema validation
    schema_errors = validate_schema(strategy)
    result['errors'].extend(schema_errors)

    # Required fields
    field_errors = validate_required_fields(strategy)
    result['errors'].extend(field_errors)

    # Tool chain
    if 'tool_chain' in strategy:
        tc_errors, tc_warnings = validate_tool_chain(strategy['tool_chain'])
        result['errors'].extend(tc_errors)
        result['warnings'].extend(tc_warnings)

    # Variable interpolation
    var_errors, var_warnings = validate_variable_interpolation(strategy)
    result['errors'].extend(var_errors)
    result['warnings'].extend(var_warnings)

    # Limits
    limit_warnings = validate_limits(strategy)
    result['warnings'].extend(limit_warnings)

    # Domains
    domain_warnings = validate_domains(strategy)
    result['warnings'].extend(domain_warnings)

    # Determine validity
    if result['errors']:
        result['valid'] = False
    elif strict and result['warnings']:
        result['valid'] = False

    # Add summary
    result['summary'] = {
        'total_errors': len(result['errors']),
        'total_warnings': len(result['warnings']),
        'has_meta': 'meta' in strategy,
        'has_tool_chain': 'tool_chain' in strategy,
        'tool_count': len(strategy.get('tool_chain', [])),
        'has_limits': 'limits' in strategy,
        'has_queries': 'queries' in strategy
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Validate strategy YAML file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic validation
  %(prog)s --strategy /tmp/new_strategy.yaml

  # Strict mode (warnings = errors)
  %(prog)s --strategy /tmp/strategy.yaml --strict

  # Save report
  %(prog)s --strategy /tmp/strategy.yaml --output /tmp/validation.json
        """
    )

    parser.add_argument('--strategy', required=True, help='Path to strategy YAML file')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    parser.add_argument('--output', help='Output file for validation report (JSON)')

    args = parser.parse_args()

    try:
        result = run_validation(args.strategy, args.strict)

        # Save output if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Validation report saved to: {output_path}\n")

        # Print summary
        print("="*60)
        print("STRATEGY VALIDATION REPORT")
        print("="*60)
        print(f"\nFile: {args.strategy}")
        print(f"Valid: {'✓ YES' if result['valid'] else '✗ NO'}")

        summary = result['summary']
        print(f"\nSummary:")
        print(f"  Errors: {summary['total_errors']}")
        print(f"  Warnings: {summary['total_warnings']}")
        print(f"  Tool steps: {summary['tool_count']}")

        if result['errors']:
            print(f"\n❌ Errors ({len(result['errors'])}):")
            for i, error in enumerate(result['errors'], 1):
                print(f"  {i}. {error}")

        if result['warnings']:
            print(f"\n⚠️  Warnings ({len(result['warnings'])}):")
            for i, warning in enumerate(result['warnings'], 1):
                print(f"  {i}. {warning}")

        if result['valid']:
            print("\n✓ Strategy is valid!")
            print("\nNext steps:")
            print("  1. Review any warnings above")
            print("  2. Save to strategies/ directory")
            print("  3. Add to strategies/index.yaml")
            print("  4. Migrate to database")
        else:
            print("\n✗ Strategy has validation errors - fix them before deployment")

        print("="*60 + "\n")

        # Exit code
        sys.exit(0 if result['valid'] else 1)

    except Exception as e:
        print(f"\n✗ Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
