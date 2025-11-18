#!/usr/bin/env python3
"""One-off test runner for the daily_parallel_briefing strategy."""

import sys
import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    try:
        from dotenv import load_dotenv
        env_file = ROOT / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass

    from tools import register_default_adapters
    from core.graph import build_graph
    from core.state import State

    topic = (
        os.getenv(
            "TEST_PARALLEL_TOPIC",
            "Finde alle Nachrichten zu den Neuigkeiten über die großen AI Labs wie OpenAI und Anthropic der vergangenen 24 Stunden",
        )
        .strip()
    )
    recipient = os.getenv("TEST_PARALLEL_RECIPIENT", "m.bruhn@faz.de").strip()

    print("=" * 72)
    print("DAILY NEWS BRIEFING – TEST RUN")
    print("=" * 72)
    print(f"Strategy: daily_news_briefing")
    print(f"Topic   : {topic}")
    print(f"Send to : {recipient}")
    print("=" * 72)

    print("\n[1/3] Registering tool adapters...")
    register_default_adapters(silent=False)
    print("  ✅ Tools ready")

    print("[2/3] Building graph...")
    graph = build_graph()
    print("  ✅ Graph ready")

    print("[3/3] Executing strategy...\n")
    thread_id = f"daily-parallel-test-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    state = State(
        user_request=topic,
        strategy_slug="daily_news_briefing",
        time_window="day",
        vars={
            "topic": topic,
            "timeframe": "last 24 hours",
            "recipient_email": recipient,
            "email": recipient,
            "send_email_to": recipient,
        },
    )

    result = asyncio.run(
        graph.ainvoke(state, {"configurable": {"thread_id": thread_id}})
    )

    vars_dict = result.vars if hasattr(result, "vars") else result.get("vars", {})
    sections = result.sections if hasattr(result, "sections") else result.get("sections", [])
    evidence = result.evidence if hasattr(result, "evidence") else result.get("evidence", [])

    print("✅ Research finished")
    print(f"- Evidence items: {len(evidence)}")
    print(f"- Sections: {len(sections)}")
    if "briefing_content" in vars_dict:
        print("\n--- BRIEFING CONTENT (RAW) ---\n")
        briefing = vars_dict["briefing_content"]
        if isinstance(briefing, list) and briefing:
            content = getattr(briefing[0], "snippet", str(briefing[0]))
        else:
            content = str(briefing)
        print(content)
        print("\n--- END ---")
    else:
        print("\n(No synthesized briefing content found in vars_dict)")

    print("\nNext steps:")
    print("1. Feed the output into the email sender of your choice.")
    print("2. Verify that the generated content includes the expected sections.")
    print("3. Manually forward or automate delivery to", recipient)


if __name__ == "__main__":
    main()
