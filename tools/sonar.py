from __future__ import annotations

"""Adapter for the Perplexity Sonar API."""

from typing import Any, Dict, List
import os

from core.state import Evidence


class SonarAdapter:
    """Call the Sonar (Perplexity) chat completions API and normalize citations."""

    name = "sonar"

    def __init__(self, model: str = "sonar", api_key: str | None = None) -> None:
        self.model = model
        # Try SONAR_API_KEY first, then PERPLEXITY_API_KEY as fallback
        self.api_key = api_key or os.getenv("SONAR_API_KEY") or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("Sonar API key required (set SONAR_API_KEY or PERPLEXITY_API_KEY)")

    # Separate network call for easier testing
    def _chat_completion(self, messages: List[Dict[str, str]], **params: Any) -> Any:
        from openai import OpenAI  # Imported lazily to keep optional dependency
        import httpx
        
        # Set explicit timeout for Perplexity API (required to avoid hanging)
        timeout = httpx.Timeout(30.0, connect=10.0)
        
        # Perplexity's Sonar API uses their own base URL
        client = OpenAI(
            api_key=self.api_key, 
            base_url="https://api.perplexity.ai",
            timeout=timeout,
            max_retries=2
        )
        return client.chat.completions.create(model=self.model, messages=messages, **params)

    def call(self, prompt: str, **params: Any) -> List[Evidence]:
        """Execute a chat completion and return normalized citation evidence.
        
        Supports all Sonar API parameters:
        - system_prompt: System message to guide responses
        - search_mode: "web" (default) or "academic"
        - search_domain_filter: List of domains to search (max 20)
        - search_recency_filter: Time filter ("day", "week", "month", "year")
        - return_images: Include images in results
        - return_related_questions: Include related questions
        - max_tokens: Maximum response tokens
        - temperature: Response randomness (0-2)
        - top_p: Nucleus sampling parameter
        - stream: Enable streaming (default false)
        """
        # Build messages array with optional system prompt
        messages = []
        if "system_prompt" in params:
            messages.append({"role": "system", "content": params.pop("system_prompt")})
        messages.append({"role": "user", "content": prompt})
        
        # Map strategy parameters to Sonar API parameters
        api_params = {}
        
        # Direct mappings (these match API parameter names)
        for param in ["search_mode", "search_domain_filter", "search_recency_filter",
                     "return_images", "return_related_questions", "max_tokens",
                     "temperature", "top_p", "stream", "reasoning_effort",
                     "disable_search", "enable_search_classifier"]:
            if param in params:
                api_params[param] = params[param]
        
        # Handle any other params that might be passed
        for key, value in params.items():
            if key not in api_params and key != "system_prompt":
                api_params[key] = value
        
        response = self._chat_completion(messages, **api_params)
        
        evidence: List[Evidence] = []
        
        # First check for search_results (new API format with more metadata)
        search_results = None
        if hasattr(response, 'search_results'):
            search_results = response.search_results
        elif isinstance(response, dict) and 'search_results' in response:
            search_results = response['search_results']
        
        if search_results:
            # Use search_results which has richer metadata
            for result in search_results:
                if isinstance(result, dict):
                    evidence.append(
                        Evidence(
                            url=result.get("url", ""),
                            title=result.get("title"),
                            publisher=result.get("publisher"),
                            date=result.get("date"),
                            snippet=result.get("snippet") or result.get("text"),
                            tool=self.name,
                        )
                    )
        else:
            # Fallback to citations (deprecated but still returned)
            citations = response.get("citations", []) if isinstance(response, dict) else getattr(response, "citations", [])
            
            for c in citations:
                # Citations from Sonar are just URL strings
                if isinstance(c, str):
                    evidence.append(
                        Evidence(
                            url=c,
                            title=None,  # Sonar doesn't provide titles in citations
                            publisher=None,  # Sonar doesn't provide publishers
                            date=None,  # Sonar doesn't provide dates
                            snippet=None,  # Sonar doesn't provide snippets in citations
                            tool=self.name,
                        )
                    )
                elif isinstance(c, dict):
                    # Fallback for potential future API changes
                    evidence.append(
                        Evidence(
                            url=c.get("url", "") if isinstance(c, dict) else "",
                            title=c.get("title") if isinstance(c, dict) else None,
                            publisher=c.get("publisher") if isinstance(c, dict) else None,
                            date=c.get("publishedAt") if isinstance(c, dict) else None,
                            snippet=c.get("snippet") if isinstance(c, dict) else None,
                            tool=self.name,
                        )
                    )
        return evidence


# The adapter conforms to ``ToolAdapter`` protocol
__all__ = ["SonarAdapter"]
