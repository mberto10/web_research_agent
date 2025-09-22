from __future__ import annotations

"""Adapter for the Exa search API."""

from typing import Any, List
import os

from core.state import Evidence
from core.langfuse_tracing import get_langfuse_client, observe


class ExaAdapter:
    """Wrapper around ``exa-py`` client that normalizes outputs."""

    name = "exa"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        if not self.api_key:
            raise ValueError("Exa API key required")

    def _client(self):
        from exa_py import Exa  # Imported lazily

        return Exa(self.api_key)

    @observe(as_type="span", name="exa-search")
    def search(self, query: str, **params: Any) -> List[Evidence]:
        """Execute a search with full parameter support.
        
        Supports all Exa API parameters:
        - type: "keyword", "neural", "fast", "auto" (default: "auto")
        - category: Filter by content type (e.g., "company", "research paper", "news")
        - num_results: Number of results (1-100, default: 10)
        - start_crawl_date: Links crawled after this date (ISO 8601)
        - end_crawl_date: Links crawled before this date (ISO 8601)
        - start_published_date: Links published after this date (ISO 8601)
        - end_published_date: Links published before this date (ISO 8601)
        - include_domains: List of domains to include
        - exclude_domains: List of domains to exclude
        - include_text: Text that must be present (1 string, max 5 words)
        - exclude_text: Text that must not be present (1 string, max 5 words)
        - use_autoprompt: Auto-optimize query (for neural search)
        - user_location: Two-letter country code for location bias
        - moderation: Filter unsafe content (default: false)
        - context: Format results for LLM consumption
        """
        client = self._client()
        
        # Map common parameter names to Exa API parameter names
        param_mappings = {
            "start_date": "start_published_date",
            "end_date": "end_published_date",
            "domains": "include_domains",
            "exclude": "exclude_domains",
            "autoprompt": "use_autoprompt",
            "location": "user_location",
            "max_results": "num_results"
        }
        
        # Apply parameter mappings
        for old_name, new_name in param_mappings.items():
            if old_name in params:
                params[new_name] = params.pop(old_name)
        
        # Validate and process parameters
        api_params = {}
        
        # Direct mappings (these match API parameter names)
        for param in ["type", "category", "num_results", 
                     "start_crawl_date", "end_crawl_date",
                     "start_published_date", "end_published_date",
                     "include_domains", "exclude_domains",
                     "include_text", "exclude_text",
                     "use_autoprompt", "user_location", 
                     "moderation", "context"]:
            if param in params:
                api_params[param] = params[param]
        
        # Handle any other params that might be passed
        for key, value in params.items():
            if key not in api_params:
                api_params[key] = value
        
        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_span(
                name="exa-search",
                input={"query": query, "params": api_params},
                metadata={"adapter": "exa", "method": "search"},
            )

        response = client.search(query, **api_params)
        results = response.get("results") if isinstance(response, dict) else getattr(response, "results", [])
        evidence: List[Evidence] = []
        for r in results:
            url = r.get("url") if isinstance(r, dict) else getattr(r, "url", None)
            evidence.append(
                Evidence(
                    url=url or "",
                    title=(
                        r.get("title") if isinstance(r, dict) else getattr(r, "title", None)
                    ),
                    publisher=(
                        (r.get("author") or r.get("source")) if isinstance(r, dict)
                        else (getattr(r, "author", None) or getattr(r, "source", None))
                    ),
                    date=(
                        (r.get("published_date") or r.get("publishedDate")) if isinstance(r, dict)
                        else (getattr(r, "published_date", None) or getattr(r, "publishedDate", None))
                    ),
                    snippet=(
                        (r.get("text") or r.get("snippet")) if isinstance(r, dict)
                        else (getattr(r, "text", None) or getattr(r, "snippet", None))
                    ),
                    tool=self.name,
                    score=r.get("score") if isinstance(r, dict) else getattr(r, "score", None),
                )
            )
        if lf_client:
            preview = results[:5] if isinstance(results, list) else results
            lf_client.update_current_span(
                output={
                    "sample": preview,
                    "total_results": len(results) if isinstance(results, list) else None,
                },
                metadata={"status": "success", "response_size": len(str(results))},
            )
        return evidence

    @observe(as_type="span", name="exa-contents")
    def contents(self, urls: str | List[str], **params: Any) -> List[Evidence]:
        """Retrieve contents from URLs with full parameter support.
        
        Supports all Exa contents parameters:
        - text: Boolean or dict with options:
          - include_html_tags: Include HTML tags
          - max_characters: Limit text length
        - highlights: Get most relevant text snippets
        - summary: Generate webpage summary
        - livecrawl: "never", "fallback", "always", "preferred"
        - livecrawl_timeout: Timeout in ms (default: 10000)
        - subpages: Number of subpages to crawl
        - subpage_target: Keywords to find specific subpages
        - context: Format for LLM consumption
        """
        client = self._client()
        
        # Ensure urls is a list
        if isinstance(urls, str):
            urls = [urls]
        
        # Map parameters
        api_params = {}
        for param in ["text", "highlights", "summary", "livecrawl",
                     "livecrawl_timeout", "subpages", "subpage_target",
                     "extras", "context"]:
            if param in params:
                api_params[param] = params[param]
        
        # Add any other params
        for key, value in params.items():
            if key not in api_params:
                api_params[key] = value
        
        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_span(
                name="exa-contents",
                input={"urls": urls, "params": api_params},
                metadata={"adapter": "exa", "method": "contents"},
            )

        response = client.get_contents(urls, **api_params)
        
        # Handle response based on structure
        evidence = []
        if hasattr(response, 'results'):
            results = response.results
        elif isinstance(response, dict) and 'results' in response:
            results = response['results']
        else:
            # Single result
            results = [response]
        
        for result in results:
            text = None
            title = None
            url = None
            
            if hasattr(result, 'text'):
                text = result.text
            elif isinstance(result, dict) and 'text' in result:
                text = result['text']
            elif isinstance(result, dict) and 'content' in result:
                text = result['content']
            
            if hasattr(result, 'title'):
                title = result.title
            elif isinstance(result, dict) and 'title' in result:
                title = result['title']
            
            if hasattr(result, 'url'):
                url = result.url
            elif isinstance(result, dict) and 'url' in result:
                url = result['url']
            else:
                url = urls[0] if len(urls) == 1 else None
            
            evidence.append(Evidence(
                url=url or "",
                title=title,
                snippet=text,
                tool=self.name
            ))
        if lf_client:
            preview = results[:3] if isinstance(results, list) else results
            lf_client.update_current_span(
                output={"sample": preview},
                metadata={"status": "success"},
            )
        return evidence

    @observe(as_type="span", name="exa-find-similar")
    def find_similar(self, url: str, **params: Any) -> List[Evidence]:
        """Find similar pages with full parameter support.
        
        Supports all Exa findSimilar parameters:
        - num_results: Number of results (1-100, default: 10)
        - include_domains: List of domains to include
        - exclude_domains: List of domains to exclude
        - start_crawl_date: Links crawled after this date
        - end_crawl_date: Links crawled before this date
        - start_published_date: Links published after this date
        - end_published_date: Links published before this date
        - include_text: Required text (1 string, max 5 words)
        - exclude_text: Excluded text (1 string, max 5 words)
        - exclude_source_domain: Exclude the source domain
        - category: Filter by content type
        - moderation: Filter unsafe content
        - context: Format for LLM consumption
        """
        client = self._client()
        
        # Map common parameters
        param_mappings = {
            "max_results": "num_results",
            "start_date": "start_published_date",
            "end_date": "end_published_date"
        }
        
        for old_name, new_name in param_mappings.items():
            if old_name in params:
                params[new_name] = params.pop(old_name)
        
        # Validate and process parameters
        api_params = {}
        for param in ["num_results", "include_domains", "exclude_domains",
                     "start_crawl_date", "end_crawl_date",
                     "start_published_date", "end_published_date",
                     "include_text", "exclude_text",
                     "exclude_source_domain", "category",
                     "moderation", "context"]:
            if param in params:
                api_params[param] = params[param]
        
        # Add any other params
        for key, value in params.items():
            if key not in api_params:
                api_params[key] = value
        
        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_span(
                name="exa-find-similar",
                input={"url": url, "params": api_params},
                metadata={"adapter": "exa", "method": "find_similar"},
            )

        response = client.find_similar(url, **api_params)
        results = response.get("results") if isinstance(response, dict) else getattr(response, "results", [])
        
        evidence: List[Evidence] = []
        for r in results:
            u = r.get("url") if isinstance(r, dict) else getattr(r, "url", None)
            title = r.get("title") if isinstance(r, dict) else getattr(r, "title", None)
            published_date = (
                (r.get("published_date") or r.get("publishedDate")) if isinstance(r, dict)
                else (getattr(r, "published_date", None) or getattr(r, "publishedDate", None))
            )
            author = (
                (r.get("author") or r.get("source")) if isinstance(r, dict)
                else (getattr(r, "author", None) or getattr(r, "source", None))
            )
            text = (
                (r.get("text") or r.get("snippet")) if isinstance(r, dict)
                else (getattr(r, "text", None) or getattr(r, "snippet", None))
            )
            score = r.get("score") if isinstance(r, dict) else getattr(r, "score", None)
            
            evidence.append(
                Evidence(
                    url=u or "",
                    title=title,
                    publisher=author,
                    date=published_date,
                    snippet=text,
                    tool=self.name,
                    score=score
                )
            )
        if lf_client:
            lf_client.update_current_span(
                output={
                    "sample": results[:5] if isinstance(results, list) else results,
                    "total_results": len(results) if isinstance(results, list) else None,
                },
                metadata={"status": "success"},
            )
        return evidence

    @observe(as_type="span", name="exa-answer")
    def answer(self, query: str, **params: Any) -> str:
        """Get direct answers to questions.
        
        Supports Exa answer parameters:
        - stream: Return as server-sent events stream (default: false)
        - text: Include full text content in results (default: false)
        """
        client = self._client()
        
        # Process parameters
        api_params = {}
        for param in ["stream", "text"]:
            if param in params:
                api_params[param] = params[param]
        
        # Add any other params
        for key, value in params.items():
            if key not in api_params:
                api_params[key] = value
        
        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_span(
                name="exa-answer",
                input={"query": query, "params": api_params},
                metadata={"adapter": "exa", "method": "answer"},
            )

        response = client.answer(query, **api_params)
        answer_text = response.get("answer") if isinstance(response, dict) else getattr(response, "answer", "")
        if lf_client:
            lf_client.update_current_span(
                output={"answer": answer_text},
                metadata={"status": "success"},
            )
        return answer_text

    def call(self, *args: Any, **kwargs: Any) -> List[Evidence]:
        """Default call proxies to ``search`` for registry uniformity."""
        return self.search(*args, **kwargs)


__all__ = ["ExaAdapter"]
