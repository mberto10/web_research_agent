from __future__ import annotations

"""LLM Analyzer tool for structured analysis and synthesis."""

from typing import Any, Dict, List
import os
import json

from core.state import Evidence


class LLMAnalyzerAdapter:
    """Analyze and synthesize information using an LLM."""
    
    name = "llm_analyzer"
    
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        # Get model from config if not provided
        if model is None:
            try:
                from core.config import get_llm_config
                cfg = get_llm_config("analyzer")
                model = cfg.get("model", "gpt-4o-mini")
            except Exception:
                model = "gpt-4o-mini"
        
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required for LLM analyzer")
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM and return plain text response."""
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        
        messages = [
            {"role": "system", "content": "You are a research analyst that provides clear, structured analysis."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # gpt-5-mini only supports default temperature
            if self.model == "gpt-5-mini":
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
            else:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3
                )
            return response.choices[0].message.content or ""
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