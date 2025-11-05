#!/usr/bin/env python3
"""
Langfuse Client for Advanced Filters Skill
Shared client configuration for accessing Langfuse API
"""

import os
import sys
from typing import Optional


def get_langfuse_client():
    """
    Get configured Langfuse client instance.

    Returns:
        Langfuse client instance

    Raises:
        SystemExit if Langfuse package not installed or credentials missing
    """
    try:
        from langfuse import Langfuse
    except ImportError:
        print("ERROR: langfuse package not installed", file=sys.stderr)
        print("Install with: pip install langfuse", file=sys.stderr)
        sys.exit(1)

    # Check for required environment variables
    public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
    secret_key = os.getenv('LANGFUSE_SECRET_KEY')
    host = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')

    if not public_key or not secret_key:
        print("ERROR: Missing Langfuse credentials", file=sys.stderr)
        print("Required environment variables:", file=sys.stderr)
        print("  - LANGFUSE_PUBLIC_KEY", file=sys.stderr)
        print("  - LANGFUSE_SECRET_KEY", file=sys.stderr)
        print("  - LANGFUSE_HOST (optional, default: https://cloud.langfuse.com)", file=sys.stderr)
        sys.exit(1)

    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host
    )


def get_api_base_url() -> str:
    """Get the base URL for direct API calls."""
    return os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')


def get_auth_headers() -> dict:
    """Get authentication headers for direct API calls."""
    import base64

    public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
    secret_key = os.getenv('LANGFUSE_SECRET_KEY')

    if not public_key or not secret_key:
        print("ERROR: Missing Langfuse credentials", file=sys.stderr)
        sys.exit(1)

    # Basic auth: base64(public_key:secret_key)
    credentials = f"{public_key}:{secret_key}"
    encoded = base64.b64encode(credentials.encode()).decode()

    return {
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/json'
    }
