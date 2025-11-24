#!/usr/bin/env python3
"""
Migration script to move main strategies and global settings from YAML to database.

Usage:
    python scripts/migrate_main_strategies.py [--dry-run]

Options:
    --dry-run    Show what would be migrated without making changes
"""

import asyncio
import sys
import argparse
from pathlib import Path
import yaml
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.database import db_manager
from sqlalchemy.exc import IntegrityError

from api.crud import create_strategy, update_global_setting, update_strategy as crud_update_strategy

STRATEGIES_DIR = ROOT / "strategies"
SETTINGS_PATH = ROOT / "config" / "settings.yaml"

# Main strategies to migrate (per user requirements)
MAIN_STRATEGIES = [
    "daily_news_briefing",
    "company_dossier",
    "market_dossier",
    "weekly_topic_overview",
]


async def migrate_strategy(db, slug: str, dry_run: bool = False):
    """Migrate a single strategy from YAML to database."""
    try:
        # Load YAML file
        yaml_path = STRATEGIES_DIR / f"{slug}.yaml"
        if not yaml_path.exists():
            print(f"  ⚠️  {slug}: YAML file not found, skipping")
            return False

        with open(yaml_path, 'r') as f:
            yaml_content = yaml.safe_load(f)

        if not yaml_content:
            print(f"  ⚠️  {slug}: Empty YAML file, skipping")
            return False

        # Merge with LLM config from settings.yaml if it exists
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, 'r') as f:
                settings = yaml.safe_load(f)

            # Check if there's strategy-specific LLM config
            if settings and "llm" in settings and "per_strategy" in settings["llm"]:
                strategy_llm_config = settings["llm"]["per_strategy"].get(slug)
                if strategy_llm_config:
                    yaml_content["llm"] = strategy_llm_config
                    print(f"    → Merged LLM config from settings.yaml")

        if dry_run:
            print(f"  ✓ {slug}: Would migrate ({len(str(yaml_content))} bytes)")
            return True

        # Insert or update in database
        try:
            await create_strategy(db, slug, yaml_content)
            print(f"  ✓ {slug}: Migrated successfully")
            return True
        except IntegrityError:
            await db.rollback()
            updated = await crud_update_strategy(db, slug, yaml_content)
            if updated:
                print(f"  ✓ {slug}: Updated existing strategy")
                return True
            print(f"  ✗ {slug}: Failed to update existing strategy")
            return False

    except Exception as e:
        print(f"  ✗ {slug}: Failed to migrate - {e}")
        return False


async def migrate_global_settings(db, dry_run: bool = False):
    """Migrate global LLM defaults and prompts from settings.yaml to database."""
    try:
        if not SETTINGS_PATH.exists():
            print("  ⚠️  config/settings.yaml not found, skipping global settings")
            return False

        with open(SETTINGS_PATH, 'r') as f:
            settings = yaml.safe_load(f)

        if not settings:
            print("  ⚠️  config/settings.yaml is empty, skipping")
            return False

        migrated = 0

        # Migrate LLM defaults
        if "llm" in settings and "defaults" in settings["llm"]:
            if dry_run:
                print(f"  ✓ Would migrate llm_defaults")
            else:
                await update_global_setting(db, "llm_defaults", settings["llm"]["defaults"])
                print(f"  ✓ Migrated llm_defaults")
            migrated += 1

        # Migrate prompts
        if "prompts" in settings:
            if dry_run:
                print(f"  ✓ Would migrate prompts")
            else:
                await update_global_setting(db, "prompts", settings["prompts"])
                print(f"  ✓ Migrated prompts")
            migrated += 1

        return migrated > 0

    except Exception as e:
        print(f"  ✗ Failed to migrate global settings - {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Migrate strategies and settings to database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without making changes")
    args = parser.parse_args()

    print("=" * 70)
    print("STRATEGY & SETTINGS MIGRATION TO DATABASE")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    async for db in db_manager.get_session():
        try:
            # Migrate global settings
            print("Migrating global settings...")
            await migrate_global_settings(db, dry_run=args.dry_run)
            print()

            # Migrate strategies
            print(f"Migrating {len(MAIN_STRATEGIES)} main strategies...")
            success_count = 0
            for slug in MAIN_STRATEGIES:
                success = await migrate_strategy(db, slug, dry_run=args.dry_run)
                if success:
                    success_count += 1

            print()
            print("=" * 70)
            print(f"MIGRATION {'PREVIEW' if args.dry_run else 'COMPLETE'}")
            print("=" * 70)
            print(f"Strategies: {success_count}/{len(MAIN_STRATEGIES)} successful")
            print()

            if args.dry_run:
                print("This was a dry run. Run without --dry-run to perform actual migration.")
            else:
                print("✓ Migration complete!")
                print()
                print("Next steps:")
                print("1. Restart your application to load strategies from database")
                print("2. Test that strategies are working correctly")
                print("3. Optionally delete old YAML strategy files")

        finally:
            break  # Only use one session


if __name__ == "__main__":
    asyncio.run(main())
