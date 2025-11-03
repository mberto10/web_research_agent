#!/usr/bin/env python3
"""Run the Research Agent API server."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
try:
    from dotenv import load_dotenv
    if Path('.env').exists():
        load_dotenv()
        print("[INFO] Loaded environment from .env file")
except ImportError:
    pass

# Check required environment variables
required_vars = [
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "API_SECRET_KEY"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

# Run the server
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"\n{'='*60}")
    print(f"Starting Research Agent API")
    print(f"{'='*60}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Docs: http://localhost:{port}/docs")
    print(f"{'='*60}\n")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
