from __future__ import annotations

"""LLM Analyzer tool for structured analysis and synthesis."""

from typing import Any, Dict, List
import os
import json

from core.config import get_llm_config, get_node_llm_config, get_node_prompt
from core.langfuse_tracing import get_langfuse_client, observe
from core.state import Evidence


DEFAULT_ANALYZER_SYSTEM_PROMPT = "You are a research analyst that provides clear, structured analysis."


def _prompt_text(value: Any, default: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("system", "template", "prompt", "text"):
            text = value.get(key)
            if isinstance(text, str):
                return text
    return default


class LLMAnalyzerAdapter:
    """Analyze and synthesize information using an LLM."""
    
    name = "llm_analyzer"
    
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        node_cfg = get_node_llm_config("llm_analyzer")
        node_model = node_cfg.get("model")
        stage_cfg = get_llm_config("analyzer")

        resolved_model = model or node_model or stage_cfg.get("model") or "gpt-4o-mini"
        self.model = resolved_model
        self.temperature = node_cfg.get("temperature", stage_cfg.get("temperature"))
        self.call_kwargs = {
            k: v for k, v in {**stage_cfg, **node_cfg}.items() if k not in {"model", "temperature"}
        }

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required for LLM analyzer")

        prompt_cfg = get_node_prompt("llm_analyzer_system")
        self.system_message = _prompt_text(prompt_cfg, DEFAULT_ANALYZER_SYSTEM_PROMPT)
    
    @observe(as_type="generation", name="llm-analyzer")
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM and return plain text response."""
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        lf_client = get_langfuse_client()
        
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": prompt}
        ]
        
        try:
            call_kwargs = dict(self.call_kwargs)
            if self.temperature is not None and self.model != "gpt-5-mini":
                call_kwargs.setdefault("temperature", self.temperature)
            elif self.model == "gpt-5-mini":
                call_kwargs.pop("temperature", None)

            if lf_client:
                lf_client.update_current_generation(
                    model=self.model,
                    input={"messages": messages},
                    metadata={"component": "llm_analyzer"},
                )

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                **call_kwargs,
            )
            content = response.choices[0].message.content or ""
            if lf_client:
                usage = getattr(response, "usage", None)
                usage_details = None
                if usage:
                    usage_details = {
                        "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                        "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                    }
                lf_client.update_current_generation(
                    output=content,
                    usage_details=usage_details,
                )
            return content
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
            return f"Error generating briefing: {str(e)}"
    
    def call(self, prompt: str, **params: Any) -> List[Evidence]:
        """Analyze content with an LLM and return as Evidence."""
        # Debug: Print prompt length to understand what's being sent
        print(f"[DEBUG] LLM Analyzer called with prompt of {len(prompt)} characters")
        
        result = self._call_llm(prompt)
        
        # Debug: Print result length
        print(f"[DEBUG] LLM Analyzer returned {len(result)} characters")
        
        # Always return as Evidence for consistency with other tools
        return [Evidence(
            url="llm_analysis_result",
            title="Synthesized Briefing",
            snippet=result,
            tool=self.name
        )]


__all__ = ["LLMAnalyzerAdapter"]
