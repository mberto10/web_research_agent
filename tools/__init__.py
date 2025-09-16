"""Tool adapter registry and built-in adapters."""

from .registry import register_tool, get_tool, is_registered
from .sonar import SonarAdapter
from .exa import ExaAdapter
from .http import HttpAdapter
from .parse import ParseAdapter
from core.llm_analyzer import LLMAnalyzerAdapter


def register_default_adapters(silent: bool = True) -> None:
    """Attempt to register common adapters. Missing API keys are ignored if silent.

    This helps the architecture work out-of-the-box in constrained environments
    while allowing production to wire real adapters at startup.
    """
    # HTTP / Parse never require keys
    if not is_registered("http"):
        register_tool(HttpAdapter())
    if not is_registered("parse"):
        register_tool(ParseAdapter())

    # These may fail if API keys are not present; suppress if silent
    if not is_registered("sonar"):
        try:
            register_tool(SonarAdapter())
        except Exception:
            if not silent:
                raise
    if not is_registered("exa"):
        try:
            register_tool(ExaAdapter())
        except Exception:
            if not silent:
                raise
    if not is_registered("llm_analyzer"):
        try:
            register_tool(LLMAnalyzerAdapter())
        except Exception:
            if not silent:
                raise


__all__ = [
    "register_tool",
    "get_tool",
    "is_registered",
    "SonarAdapter",
    "ExaAdapter",
    "HttpAdapter",
    "ParseAdapter",
    "LLMAnalyzerAdapter",
    "register_default_adapters",
]
