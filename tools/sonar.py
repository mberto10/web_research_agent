from __future__ import annotations

"""Adapter for the Perplexity Sonar API."""

from typing import Any, Dict, List
import os

from core.state import Evidence
from core.langfuse_tracing import get_langfuse_client, observe


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
        
        # Separate OpenAI-compatible params from Perplexity-specific ones
        openai_params = {}
        perplexity_params = {}
        
        for key, value in params.items():
            # These are Perplexity-specific parameters that need to go in extra_body
            if key in ['search_mode', 'search_domain_filter', 'search_recency_filter',
                      'return_images', 'return_related_questions', 'reasoning_effort',
                      'disable_search', 'enable_search_classifier']:
                perplexity_params[key] = value
            # Standard OpenAI parameters
            elif key in ['temperature', 'top_p', 'max_tokens', 'stream']:
                openai_params[key] = value
            else:
                # Unknown params go to Perplexity by default
                perplexity_params[key] = value
        
        # Add Perplexity params via extra_body if any exist
        if perplexity_params:
            openai_params['extra_body'] = perplexity_params
            
        return client.chat.completions.create(
            model=self.model, 
            messages=messages, 
            **openai_params
        )

    @observe(as_type="generation", name="sonar-call")
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
        
        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_generation(
                model=self.model,
                input={"prompt": prompt, "params": api_params},
                metadata={"adapter": "sonar"},
            )

        citations = None
        response = self._chat_completion(messages, **api_params)

        evidence: List[Evidence] = []

        # First check for search_results (new API format with more metadata)
        search_results = None
        if hasattr(response, 'search_results'):
            search_results = response.search_results
        elif isinstance(response, dict) and 'search_results' in response:
            search_results = response['search_results']
        
        # Also extract the message content for potential snippet use
        message_content = None
        try:
            if hasattr(response, 'choices') and response.choices:
                message_content = response.choices[0].message.content
            elif isinstance(response, dict) and 'choices' in response:
                message_content = response['choices'][0]['message']['content']
        except (AttributeError, KeyError, IndexError, TypeError):
            pass
        
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
            
            # If we have message content but no snippets, use a portion of the message
            snippet_fallback = None
            if message_content and citations:
                # Take first 500 chars of the response as a general snippet
                snippet_fallback = message_content[:500] if len(message_content) > 500 else message_content
            
            for i, c in enumerate(citations):
                # Citations from Sonar are just URL strings
                if isinstance(c, str):
                    evidence.append(
                        Evidence(
                            url=c,
                            title=f"Source {i+1}",  # Add generic title
                            publisher=None,
                            date=None,
                            snippet=snippet_fallback if i == 0 else None,  # Add snippet to first citation
                            tool=self.name,
                        )
                    )
                elif isinstance(c, dict):
                    # Handle dict-based citations with more metadata
                    evidence.append(
                        Evidence(
                            url=c.get("url", "") if isinstance(c, dict) else "",
                            title=c.get("title") if isinstance(c, dict) else f"Source {i+1}",
                            publisher=c.get("publisher") if isinstance(c, dict) else None,
                            date=c.get("publishedAt") or c.get("date") if isinstance(c, dict) else None,
                            snippet=c.get("snippet") or c.get("text") or (snippet_fallback if i == 0 else None) if isinstance(c, dict) else None,
                            tool=self.name,
                        )
                    )
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
                output={
                    "search_results": search_results[:5] if isinstance(search_results, list) else search_results,
                    "citations": citations,
                },
                usage_details=usage_details,
            )
        return evidence


# The adapter conforms to ``ToolAdapter`` protocol
__all__ = ["SonarAdapter"]
