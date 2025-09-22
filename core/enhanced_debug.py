"""Enhanced debug logging system for comprehensive workflow tracking."""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading
import hashlib


class EnhancedDebugLogger:
    """
    Comprehensive debug logger that captures:
    - All LLM prompts and responses
    - Tool calls and results
    - Decision points and branching logic
    - Performance metrics
    - Error traces
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.events: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        
        # Performance tracking
        self.timers: Dict[str, float] = {}
        self.node_times: Dict[str, List[float]] = {}
        
        # Configuration from environment
        self.enabled = self._check_enabled()
        self.log_level = os.getenv("DEBUG_LEVEL", "INFO").upper()
        self.log_dir = Path(os.getenv("DEBUG_LOG_DIR", "./debug_logs"))
        self.save_prompts = os.getenv("DEBUG_SAVE_PROMPTS", "true").lower() == "true"
        self.save_responses = os.getenv("DEBUG_SAVE_RESPONSES", "true").lower() == "true"
        
        # Create log directory if needed
        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_dir / f"debug_{self.session_id}.jsonl"
            self.summary_file = self.log_dir / f"summary_{self.session_id}.json"
    
    def _check_enabled(self) -> bool:
        """Check if debug logging is enabled via environment variables."""
        debug_vars = ["DEBUG_LOG", "WEB_RESEARCH_DEBUG", "RESEARCH_DEBUG"]
        for var in debug_vars:
            val = os.getenv(var, "").lower()
            if val in {"1", "true", "yes", "on"}:
                return True
        return False
    
    def _get_timestamp(self) -> str:
        """Get ISO timestamp with milliseconds."""
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
    
    def _write_event(self, event: Dict[str, Any]) -> None:
        """Write event to JSONL file immediately."""
        if not self.enabled:
            return
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
    
    # ========== Node Tracking ==========
    
    def node_start(self, node_name: str, state: Dict[str, Any]) -> None:
        """Log when a workflow node starts."""
        if not self.enabled:
            return
            
        start_time = time.time()
        self.timers[f"node_{node_name}"] = start_time
        
        event = {
            "timestamp": self._get_timestamp(),
            "type": "node_start",
            "node": node_name,
            "state_keys": list(state.keys()) if state else [],
            "state_summary": {
                "user_request": str(state.get("user_request", ""))[:200] if state else None,
                "strategy": state.get("strategy_slug") if state else None,
                "evidence_count": len(state.get("evidence", [])) if state else 0,
                "vars_keys": list(state.get("vars", {}).keys()) if state else [],
            }
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
    
    def node_end(self, node_name: str, state: Dict[str, Any], error: Optional[Exception] = None) -> None:
        """Log when a workflow node completes."""
        if not self.enabled:
            return
            
        elapsed = time.time() - self.timers.get(f"node_{node_name}", time.time())
        
        # Track performance
        if node_name not in self.node_times:
            self.node_times[node_name] = []
        self.node_times[node_name].append(elapsed)
        
        event = {
            "timestamp": self._get_timestamp(),
            "type": "node_end",
            "node": node_name,
            "elapsed_seconds": round(elapsed, 3),
            "success": error is None,
            "error": str(error) if error else None,
            "error_trace": traceback.format_exc() if error else None,
            "state_changes": {
                "evidence_count": len(state.get("evidence", [])) if state else 0,
                "sections_count": len(state.get("sections", [])) if state else 0,
                "new_vars": list(state.get("vars", {}).keys())[-5:] if state else [],
            }
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
    
    # ========== Decision Tracking ==========
    
    def decision(self, point: str, condition: str, result: bool, context: Dict[str, Any] = None) -> None:
        """Log a decision point in the workflow."""
        if not self.enabled:
            return
            
        event = {
            "timestamp": self._get_timestamp(),
            "type": "decision",
            "point": point,
            "condition": condition,
            "result": result,
            "context": context or {}
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
    
    # ========== LLM Tracking ==========
    
    def llm_call(self, 
                 component: str,
                 model: str,
                 messages: List[Dict[str, str]],
                 response: Optional[str] = None,
                 tokens: Optional[Dict[str, int]] = None,
                 duration: Optional[float] = None,
                 error: Optional[str] = None) -> str:
        """Log an LLM API call with prompt and response."""
        if not self.enabled:
            return ""
            
        # Generate unique ID for this call
        call_id = hashlib.md5(f"{component}_{time.time()}".encode()).hexdigest()[:8]
        
        # Calculate prompt size
        prompt_text = "\n".join([m.get("content", "") for m in messages])
        prompt_hash = hashlib.md5(prompt_text.encode()).hexdigest()[:8]
        
        event = {
            "timestamp": self._get_timestamp(),
            "type": "llm_call",
            "call_id": call_id,
            "component": component,
            "model": model,
            "prompt_hash": prompt_hash,
            "prompt_length": len(prompt_text),
            "prompt": prompt_text[:5000] if self.save_prompts else "[disabled]",
            "messages_count": len(messages),
            "response_length": len(response) if response else 0,
            "response": response[:5000] if self.save_responses and response else "[disabled]",
            "tokens": tokens,
            "duration_seconds": round(duration, 3) if duration else None,
            "error": error
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
        
        return call_id
    
    # ========== Tool Tracking ==========
    
    def tool_call(self, 
                  provider: str, 
                  method: str, 
                  inputs: Dict[str, Any],
                  output: Optional[Any] = None,
                  duration: Optional[float] = None,
                  error: Optional[str] = None) -> str:
        """Log a tool/API call."""
        if not self.enabled:
            return ""
            
        call_id = hashlib.md5(f"{provider}_{method}_{time.time()}".encode()).hexdigest()[:8]
        
        # Sanitize inputs
        safe_inputs = self._sanitize_dict(inputs)
        
        event = {
            "timestamp": self._get_timestamp(),
            "type": "tool_call",
            "call_id": call_id,
            "provider": provider,
            "method": method,
            "inputs": safe_inputs,
            "output_type": type(output).__name__ if output else None,
            "output_count": len(output) if hasattr(output, "__len__") else None,
            "output_sample": str(output)[:500] if output else None,
            "duration_seconds": round(duration, 3) if duration else None,
            "error": error
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
        
        return call_id
    
    # ========== Evidence Tracking ==========
    
    def evidence_update(self, 
                       source: str,
                       added_count: int,
                       total_count: int,
                       sample: Optional[List[str]] = None) -> None:
        """Log when evidence is added or modified."""
        if not self.enabled:
            return
            
        event = {
            "timestamp": self._get_timestamp(),
            "type": "evidence_update",
            "source": source,
            "added_count": added_count,
            "total_count": total_count,
            "sample_urls": sample[:5] if sample else []
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
    
    # ========== Strategy Tracking ==========
    
    def strategy_selected(self, slug: str, reason: Dict[str, str]) -> None:
        """Log strategy selection."""
        if not self.enabled:
            return
            
        event = {
            "timestamp": self._get_timestamp(),
            "type": "strategy_selected",
            "strategy": slug,
            "category": reason.get("category"),
            "time_window": reason.get("time_window"),
            "depth": reason.get("depth")
        }
        
        with self.lock:
            self.events.append(event)
            self._write_event(event)
    
    # ========== Summary Generation ==========
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of the debug session."""
        if not self.enabled or not self.events:
            return {}
            
        summary = {
            "session_id": self.session_id,
            "start_time": self.events[0]["timestamp"] if self.events else None,
            "end_time": self.events[-1]["timestamp"] if self.events else None,
            "total_events": len(self.events),
            "node_performance": {},
            "llm_usage": {},
            "tool_usage": {},
            "errors": [],
            "decisions": []
        }
        
        # Analyze events
        for event in self.events:
            event_type = event.get("type")
            
            if event_type == "node_end":
                node = event["node"]
                if node not in summary["node_performance"]:
                    summary["node_performance"][node] = {
                        "count": 0,
                        "total_time": 0,
                        "avg_time": 0,
                        "max_time": 0
                    }
                perf = summary["node_performance"][node]
                elapsed = event.get("elapsed_seconds", 0)
                perf["count"] += 1
                perf["total_time"] += elapsed
                perf["avg_time"] = perf["total_time"] / perf["count"]
                perf["max_time"] = max(perf["max_time"], elapsed)
                
                if event.get("error"):
                    summary["errors"].append({
                        "node": node,
                        "error": event["error"],
                        "timestamp": event["timestamp"]
                    })
            
            elif event_type == "llm_call":
                model = event["model"]
                if model not in summary["llm_usage"]:
                    summary["llm_usage"][model] = {
                        "calls": 0,
                        "total_tokens": {"input": 0, "output": 0},
                        "total_time": 0,
                        "errors": 0
                    }
                usage = summary["llm_usage"][model]
                usage["calls"] += 1
                if event.get("tokens"):
                    usage["total_tokens"]["input"] += event["tokens"].get("input_tokens", 0)
                    usage["total_tokens"]["output"] += event["tokens"].get("output_tokens", 0)
                if event.get("duration_seconds"):
                    usage["total_time"] += event["duration_seconds"]
                if event.get("error"):
                    usage["errors"] += 1
            
            elif event_type == "tool_call":
                provider = event["provider"]
                if provider not in summary["tool_usage"]:
                    summary["tool_usage"][provider] = {
                        "calls": 0,
                        "methods": {},
                        "total_time": 0,
                        "errors": 0
                    }
                usage = summary["tool_usage"][provider]
                usage["calls"] += 1
                method = event["method"]
                usage["methods"][method] = usage["methods"].get(method, 0) + 1
                if event.get("duration_seconds"):
                    usage["total_time"] += event["duration_seconds"]
                if event.get("error"):
                    usage["errors"] += 1
            
            elif event_type == "decision":
                summary["decisions"].append({
                    "point": event["point"],
                    "condition": event["condition"],
                    "result": event["result"],
                    "timestamp": event["timestamp"]
                })
        
        # Save summary
        if self.summary_file:
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary
    
    # ========== Utilities ==========
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from dictionaries."""
        sensitive_keys = ["api_key", "apikey", "token", "secret", "password", "auth"]
        safe_data = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_keys):
                safe_data[key] = "[REDACTED]"
            elif isinstance(value, dict):
                safe_data[key] = self._sanitize_dict(value)
            else:
                safe_data[key] = value
        return safe_data
    
    def flush(self) -> None:
        """Generate final summary and close resources."""
        if self.enabled:
            self.generate_summary()
            print(f"[DEBUG] Logs saved to: {self.log_file}")
            print(f"[DEBUG] Summary saved to: {self.summary_file}")


# Global instance
enhanced_logger = EnhancedDebugLogger()


def init_debug_session(session_id: Optional[str] = None) -> EnhancedDebugLogger:
    """Initialize a new debug session."""
    global enhanced_logger
    enhanced_logger = EnhancedDebugLogger(session_id)
    return enhanced_logger


__all__ = ["enhanced_logger", "init_debug_session", "EnhancedDebugLogger"]