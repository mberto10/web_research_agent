from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import threading
import json
import os


class DebugLog:
    """Minimal, dependency-free structured debug logger.

    Captures prompts, tool calls, decisions, and arbitrary events in-memory, and
    can flush them to stdout or a file after the run.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.enabled: bool = False

    # Control -----------------------------------------------------------------
    def enable(self, value: bool = True) -> None:
        self.enabled = value

    def maybe_enable_from_env(self) -> None:
        if self.enabled:
            return
        val = os.getenv("DEBUG_LOG") or os.getenv("WEB_RESEARCH_DEBUG")
        if val and str(val).lower() in {"1", "true", "yes", "on"}:
            self.enabled = True

    def is_enabled(self) -> bool:
        return self.enabled

    # Recording ---------------------------------------------------------------
    def event(self, name: str, **fields: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._events.append(
                {
                    "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "type": "event",
                    "name": name,
                    **self._sanitize(fields),
                }
            )

    def prompt(
        self,
        component: str,
        prompt: str,
        *,
        model: Optional[str] = None,
        role: Optional[str] = None,
        **meta: Any,
    ) -> None:
        if not self.enabled:
            return
        payload: Dict[str, Any] = {
            "component": component,
            "prompt": prompt,
        }
        if model:
            payload["model"] = model
        if role:
            payload["role"] = role
        payload.update(meta or {})
        self.event("prompt", **payload)

    def tool_call(self, provider: str, method: str, inputs: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.event(
            "tool_call",
            provider=provider,
            method=method,
            inputs=self._truncate(inputs),
        )

    def tool_result(
        self, provider: str, method: str, *, count: int, sample: Any | None = None
    ) -> None:
        if not self.enabled:
            return
        self.event(
            "tool_result",
            provider=provider,
            method=method,
            count=count,
            sample=self._truncate(sample) if sample is not None else None,
        )

    # Export ------------------------------------------------------------------
    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def dump_json(self) -> str:
        return json.dumps(self._events, ensure_ascii=False, indent=2)

    def dump_text(self) -> str:
        lines: List[str] = []
        for e in self._events:
            meta = {k: v for k, v in e.items() if k not in {"ts", "type", "name"}}
            lines.append(f"[{e['ts']}] {e['name']}: " + json.dumps(meta, ensure_ascii=False))
        return "\n".join(lines)

    def flush_to_file(self, path: str) -> None:
        if not self.enabled:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.dump_json())

    # Helpers -----------------------------------------------------------------
    def _sanitize(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        def scrub(k: str, v: Any) -> Any:
            kl = k.lower()
            if any(token in kl for token in ("api_key", "apikey", "authorization", "secret")):
                return "[redacted]"
            return v
        return {k: scrub(k, v) for k, v in fields.items()}

    def _truncate(self, value: Any, limit: int = 2000) -> Any:
        try:
            s = json.dumps(value, ensure_ascii=False)
            if len(s) > limit:
                return s[:limit] + f"... [truncated {len(s) - limit} chars]"
            return value
        except Exception:
            text = str(value)
            return text[:limit] + (f"... [truncated {len(text) - limit} chars]" if len(text) > limit else "")


# Global singleton
dbg = DebugLog()


__all__ = ["dbg", "DebugLog"]

