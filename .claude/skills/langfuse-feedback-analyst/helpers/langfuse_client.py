#!/usr/bin/env python3
"""
Langfuse Client Initialization
Shared client setup for all helper scripts
"""

import os
import sys
from typing import Optional

def get_langfuse_client():
    """
    Initialize and return a Langfuse client using environment variables.

    Returns:
        Langfuse client instance

    Raises:
        ValueError: If required environment variables are not set
        ImportError: If langfuse package is not installed
    """
    try:
        from langfuse import Langfuse
    except ImportError:
        print("ERROR: langfuse package not installed", file=sys.stderr)
        print("Install with: pip install langfuse", file=sys.stderr)
        sys.exit(1)

    # Check for required environment variables
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key:
        print("ERROR: LANGFUSE_PUBLIC_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    if not secret_key:
        print("ERROR: LANGFUSE_SECRET_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
        return client
    except Exception as e:
        print(f"ERROR: Failed to initialize Langfuse client: {e}", file=sys.stderr)
        sys.exit(1)


def test_connection():
    """Test the Langfuse connection by attempting to list traces."""
    print("Testing Langfuse connection...")
    client = get_langfuse_client()

    try:
        # Try to fetch a small number of traces to test connection
        # Using the api.trace.list() method as per Langfuse SDK documentation
        traces = client.api.trace.list(limit=1)
        print(f"✓ Connection successful!")
        print(f"✓ Host: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
        print(f"✓ Test query executed successfully")
        if hasattr(traces, 'data'):
            print(f"✓ Retrieved {len(traces.data)} trace(s)")
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    # Run connection test when script is executed directly
    success = test_connection()
    sys.exit(0 if success else 1)
