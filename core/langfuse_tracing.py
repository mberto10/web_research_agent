"""Langfuse tracing helpers for LangGraph workflows.

Provides safe wrappers around the Langfuse v3 SDK so the rest of the codebase can
instrument workflows, generations and spans without littering environment checks.
If Langfuse credentials or the SDK are not present, all helpers degrade to
no-ops so the application continues to function normally.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, Optional
import os

try:  # Langfuse SDK is optional at runtime.
    from langfuse import get_client as _get_client
    from langfuse import observe as _observe
except Exception:  # pragma: no cover - exercised when Langfuse not installed.
    _get_client = None  # type: ignore
    _observe = None  # type: ignore

# LangChain integration is optional even if Langfuse is installed
try:
    from langfuse.langchain import CallbackHandler
except Exception:  # LangChain may not be installed
    CallbackHandler = None  # type: ignore


_CLIENT = None
_CALLBACK_HANDLER = None


def _credentials_present() -> bool:
    required = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
    return all(os.getenv(var) for var in required)


def is_enabled() -> bool:
    """Return True when Langfuse credentials and SDK are available."""

    return _get_client is not None and _credentials_present()


def get_langfuse_client():
    """Return singleton Langfuse client or ``None`` when disabled."""

    global _CLIENT
    if not is_enabled():
        return None
    if _CLIENT is None:
        _CLIENT = _get_client()
    return _CLIENT


def get_langfuse_handler():
    """Return LangChain callback handler or ``None`` if Langfuse is disabled."""

    global _CALLBACK_HANDLER
    if not is_enabled() or CallbackHandler is None:
        return None
    if _CALLBACK_HANDLER is None:
        _CALLBACK_HANDLER = CallbackHandler()
    return _CALLBACK_HANDLER


def observe(*args, **kwargs):  # type: ignore[override]
    """Thin wrapper around :func:`langfuse.observe` with graceful fallback."""

    if _observe is None:
        def passthrough(fn):
            return fn

        return passthrough
    return _observe(*args, **kwargs)


@dataclass
class WorkflowContext:
    """Encapsulates workflow-level span and callback state."""

    span: Any
    handler: Any
    client: Any

    def update_trace(self, **kwargs: Any) -> None:
        if self.span:
            self.span.update_trace(**kwargs)

    def set_output(self, output: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.span:
            return
        payload = {"output": output}
        if metadata:
            payload.setdefault("metadata", metadata)
        self.span.update_trace(**payload)

    def flush(self) -> None:
        if self.client and hasattr(self.client, "flush"):
            self.client.flush()

    def shutdown(self) -> None:
        if self.client and hasattr(self.client, "shutdown"):
            self.client.shutdown()


@contextmanager
def workflow_span(
    name: str,
    trace_input: Optional[Dict[str, Any]] = None,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[WorkflowContext, None, None]:
    """Context manager yielding a :class:`WorkflowContext`.

    When Langfuse is disabled, the context yields a no-op stand-in so callers do not
    need to perform their own guards.
    """

    client = get_langfuse_client()
    handler = get_langfuse_handler()

    if client and hasattr(client, "start_as_current_span"):
        with client.start_as_current_span(name=name) as span:
            ctx = WorkflowContext(span=span, handler=handler, client=client)
            if trace_input is not None or user_id or session_id or tags or metadata:
                span.update_trace(
                    input=trace_input,
                    user_id=user_id,
                    session_id=session_id,
                    tags=list(tags or []),
                    metadata=metadata,
                )
            yield ctx
    else:
        yield WorkflowContext(span=None, handler=handler, client=None)


def flush_traces() -> None:
    client = get_langfuse_client()
    if client and hasattr(client, "flush"):
        client.flush()


__all__ = [
    "WorkflowContext",
    "workflow_span",
    "flush_traces",
    "get_langfuse_client",
    "get_langfuse_handler",
    "observe",
    "is_enabled",
]

