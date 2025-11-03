#!/usr/bin/env python3
"""Initialize the database schema."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from api.database import db_manager
from api.models import ResearchTask


async def init_db():
    """Initialize the database schema."""
    print("Initializing database...")
    print(f"Database URL: {db_manager.database_url.split('@')[1] if '@' in db_manager.database_url else 'configured'}")
    
    try:
        print("\nCreating tables...")
        await db_manager.create_all_tables()
        print("✓ Tables created successfully")
        
        print("\nDatabase schema initialized!")
        print("\nTables created:")
        print("  - research_tasks")
        print("\nIndexes created:")
        print("  - idx_research_tasks_email")
        print("  - idx_research_tasks_active")
        
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(init_db())
