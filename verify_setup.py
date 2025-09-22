#!/usr/bin/env python3
"""Verify that the web research agent is properly configured."""

import sys
import os
from pathlib import Path

def check_python_version():
    """Check Python version is 3.12+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 12):
        return False, f"Python 3.12+ required, found {version.major}.{version.minor}.{version.micro}"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"

def check_dependencies():
    """Check required packages are installed."""
    required = {
        'langgraph': 'Core workflow engine',
        'pydantic': 'Data validation',
        'yaml': 'YAML parsing',
        'jsonschema': 'Schema validation',
    }
    
    optional = {
        'openai': 'OpenAI/Sonar API',
        'exa_py': 'Exa search API',
    }
    
    missing_required = []
    missing_optional = []
    
    for pkg, desc in required.items():
        try:
            __import__(pkg)
        except ImportError:
            missing_required.append(f"{pkg} ({desc})")
    
    for pkg, desc in optional.items():
        try:
            __import__(pkg)
        except ImportError:
            missing_optional.append(f"{pkg} ({desc})")
    
    return missing_required, missing_optional

def check_api_keys():
    """Check which API keys are configured.

    Requirements for daily briefing:
    - OPENAI_API_KEY (LLM analyzer/scoping)
    - EXA_API_KEY (Exa search)
    - SONAR_API_KEY or PERPLEXITY_API_KEY (Perplexity Sonar)
    """
    configured = []
    missing = []

    # Required singles
    if os.getenv('OPENAI_API_KEY'):
        configured.append('OPENAI_API_KEY (OpenAI/LLM Analysis)')
    else:
        missing.append('OPENAI_API_KEY (OpenAI/LLM Analysis)')

    if os.getenv('EXA_API_KEY'):
        configured.append('EXA_API_KEY (Exa Search)')
    else:
        missing.append('EXA_API_KEY (Exa Search)')

    # One-of pair for Perplexity Sonar
    sonar = os.getenv('SONAR_API_KEY')
    perplexity = os.getenv('PERPLEXITY_API_KEY')
    if sonar or perplexity:
        if sonar:
            configured.append('SONAR_API_KEY (Perplexity Sonar)')
        if perplexity:
            configured.append('PERPLEXITY_API_KEY (Perplexity Sonar)')
    else:
        missing.append('SONAR_API_KEY or PERPLEXITY_API_KEY (Perplexity Sonar)')

    return configured, missing

def check_tools():
    """Check if tools can be initialized."""
    results = []
    
    try:
        from tools import SonarAdapter
        try:
            adapter = SonarAdapter()
            results.append(("Sonar", True, "Configured"))
        except Exception as e:
            results.append(("Sonar", False, str(e)))
    except ImportError as e:
        results.append(("Sonar", False, f"Import error: {e}"))
    
    try:
        from tools import ExaAdapter
        try:
            adapter = ExaAdapter()
            results.append(("Exa", True, "Configured"))
        except Exception as e:
            results.append(("Exa", False, str(e)))
    except ImportError as e:
        results.append(("Exa", False, f"Import error: {e}"))
    
    try:
        from core.llm_analyzer import LLMAnalyzerAdapter
        try:
            adapter = LLMAnalyzerAdapter()
            results.append(("LLM Analyzer", True, "Configured"))
        except Exception as e:
            results.append(("LLM Analyzer", False, str(e)))
    except ImportError as e:
        results.append(("LLM Analyzer", False, f"Import error: {e}"))
    
    return results

def check_strategies():
    """Check if strategies can be loaded."""
    results = []
    
    try:
        from strategies import load_strategy
        
        strategies_to_check = [
            "daily_news_briefing",
            "news/real_time_briefing",
            "company/dossier",
        ]
        
        for strategy_name in strategies_to_check:
            try:
                strategy = load_strategy(strategy_name)
                results.append((strategy_name, True, f"{len(strategy.tool_chain)} steps"))
            except Exception as e:
                results.append((strategy_name, False, str(e)))
    except ImportError as e:
        results.append(("Strategy loader", False, f"Import error: {e}"))
    
    return results

def main():
    # Try to load .env file first
    try:
        from dotenv import load_dotenv
        if Path('.env').exists():
            load_dotenv()
            print("[INFO] Loaded .env file")
    except ImportError:
        print("[WARNING] python-dotenv not installed, .env file won't be loaded")
        print("         Install with: pip install python-dotenv")
    
    print("=" * 60)
    print("WEB RESEARCH AGENT - SETUP VERIFICATION")
    print("=" * 60)
    print()
    
    # Check Python version
    print("1. Python Version")
    print("-" * 40)
    ok, msg = check_python_version()
    status = "[OK]" if ok else "[ERROR]"
    print(f"  {status} {msg}")
    print()
    
    # Check dependencies
    print("2. Dependencies")
    print("-" * 40)
    missing_req, missing_opt = check_dependencies()
    
    if not missing_req:
        print("  [OK] All required packages installed")
    else:
        print("  [ERROR] Missing required packages:")
        for pkg in missing_req:
            print(f"    - {pkg}")
    
    if missing_opt:
        print("  [WARNING] Missing optional packages:")
        for pkg in missing_opt:
            print(f"    - {pkg}")
    else:
        print("  [OK] All optional packages installed")
    print()
    
    # Check API keys
    print("3. API Keys")
    print("-" * 40)
    configured, missing = check_api_keys()
    
    if configured:
        print("  Configured:")
        for key in configured:
            print(f"    [OK] {key}")
    
    if missing:
        print("  Missing:")
        for key in missing:
            print(f"    [ERROR] {key}")
    
    if not configured:
        print("  [ERROR] No API keys configured")
    print()
    
    # Check tools
    print("4. Tool Adapters")
    print("-" * 40)
    tool_results = check_tools()
    for tool, ok, msg in tool_results:
        status = "[OK]" if ok else "[ERROR]"
        print(f"  {status} {tool}: {msg}")
    print()
    
    # Check strategies
    print("5. Strategies")
    print("-" * 40)
    strategy_results = check_strategies()
    for strategy, ok, msg in strategy_results:
        status = "[OK]" if ok else "[ERROR]"
        print(f"  {status} {strategy}: {msg}")
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_good = True
    
    if not ok:
        print("[ERROR] Python version check failed")
        all_good = False
    
    if missing_req:
        print(f"[ERROR] {len(missing_req)} required packages missing")
        print("  Run: pip install langgraph pydantic pyyaml jsonschema")
        all_good = False
    
    if missing_opt:
        print(f"[WARNING] {len(missing_opt)} optional packages missing")
        print("  Run: pip install openai exa-py")
    
    if missing:
        print(f"[ERROR] {len(missing)} API keys missing")
        print("  Set environment variables or create .env file")
        all_good = False
    
    failed_tools = [t for t, ok, _ in tool_results if not ok]
    if failed_tools:
        print(f"[ERROR] {len(failed_tools)} tools failed to initialize")
        all_good = False
    
    failed_strategies = [s for s, ok, _ in strategy_results if not ok]
    if failed_strategies:
        print(f"[WARNING] {len(failed_strategies)} strategies failed to load")
    
    if all_good:
        print("[OK] System is properly configured and ready to use!")
        print()
        print("Next step: Run a test briefing")
        print("  python run_daily_briefing.py --topic 'artificial intelligence'")
    else:
        print()
        print("Please fix the errors above before running the system.")
        print("See SETUP_GUIDE.md for detailed instructions.")
    
    print()

if __name__ == "__main__":
    main()
