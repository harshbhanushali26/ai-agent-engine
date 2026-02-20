"""
Web Search Tool Handlers

Provides web search capabilities and result processing.

Tools:
- web_search: Search the web and return structured results
- combine_search_results: Merge search results into text
- extract_from_text: Extract specific data from text
"""

from ddgs import DDGS

from tools.responses import tool_response
from tools.schemas import (
    WebSearchInput,
    CombineSearchResults
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


TIME_RANGE_MAP = {
    "past_week": "w",
    "past_month": "m",
    "past_year": "y",
    "any": None
}


# ═══════════════════════════════════════════════════════════════════════════════
# WEB SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

def web_search(data: WebSearchInput):
    """
    Search the web for information.
    
    Uses DuckDuckGo to find relevant results based on query.
    Results include title, URL, snippet, and publication date.
    
    Args:
        data: WebSearchInput with query, num_results, and time_range
        
    Returns:
        tool_response with list of search results
    """
    try:
        # Resolve time filter
        timelimit = TIME_RANGE_MAP.get(data.time_range)
        
        # Execute search
        results = _execute_search(
            query=data.query,
            max_results=data.num_results,
            timelimit=timelimit
        )
        
        return tool_response(
            tool="web_search",
            success=True,
            data=results,
            meta={
                "query": data.query,
                "count": len(results)
            }
        )
        
    except TimeoutError:
        return tool_response(
            tool="web_search",
            success=False,
            error="Search request timed out. Please try again with a more specific query."
        )
        
    except Exception as e:
        return tool_response(
            tool="web_search",
            success=False,
            error=str(e)
        )


def _execute_search(query: str, max_results: int, timelimit: str | None) -> list:
    """
    Execute the actual search using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        timelimit: Time filter (w, m, y, or None)
        
    Returns:
        List of formatted search result dictionaries
    """
    results = []
    
    with DDGS() as ddgs:
        search_results = ddgs.text(
            query=query,
            max_results=max_results,
            timelimit=timelimit,
            safesearch="moderate",
            region="wt-wt",
            backend="duckduckgo" 
        )
        
        for idx, result in enumerate(search_results, start=1):
            formatted_result = _format_search_result(result, idx)
            if formatted_result:  # Only add non-empty results
                results.append(formatted_result)
    
    return results


def _format_search_result(result: dict, position: int) -> dict | None:
    """
    Format a raw search result into standardized structure.
    
    Args:
        result: Raw result from search engine
        position: Position in search results (1-indexed)
        
    Returns:
        Formatted result dict or None if result is invalid
    """
    title = result.get("title", "").strip()
    url = result.get("href", "").strip()
    snippet = result.get("body", "").strip()
    published = result.get("date")
    
    # Skip results with no useful content
    if not title and not snippet:
        return None
    
    return {
        "position": position,
        "title": title or "No title",
        "url": url,
        "snippet": snippet or "No snippet available",
        "published": published
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINE SEARCH RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

def combine_search_results(data: CombineSearchResults):
    """
    Combine multiple search results into a single text string.
    
    Takes a list of search result objects and merges their snippets
    into a unified text block suitable for extraction or analysis.
    
    Format: "[Title]: [Snippet]" for each result, separated by newlines.
    
    Args:
        data: CombineSearchResults with results list
        
    Returns:
        tool_response with combined text string
    """
    try:
        if not data.results or not isinstance(data.results, list):
            return tool_response(
                tool="combine_search_results",
                success=True,
                data=""
            )
        
        combined_text = _merge_results(data.results)
        
        return tool_response(
            tool="combine_search_results",
            success=True,
            data=combined_text,
            meta={"result_count": len(data.results)}
        )
        
    except Exception as e:
        return tool_response(
            tool="combine_search_results",
            success=False,
            error=str(e)
        )


# def _merge_results(results: list) -> str:
#     """
#     Merge search results into formatted text.
    
#     Args:
#         results: List of search result dictionaries
        
#     Returns:
#         Combined text string
#     """
#     combined_text = []
    
#     for item in results:
#         if not isinstance(item, dict):
#             continue
        
#         snippet = item.get("snippet", "").strip()
#         if not snippet:
#             continue
        
#         title = item.get("title", "").strip()
        
#         if title:
#             combined_text.append(f"{title}: {snippet}")
#         else:
#             combined_text.append(snippet)
    
#     return "\n".join(combined_text)


def _merge_results(results: list) -> str:
    """
    Merge search results with better structure.
    
    Improvements:
    - Sort by relevance (position)
    - Add source URLs for context
    - Limit to top 5 results
    - Better formatting
    """
    combined_text = []
    
    # Sort by position (lower = more relevant)
    sorted_results = sorted(results, key=lambda x: x.get('position', 999))
    
    # Take only top 5 most relevant results
    for item in sorted_results[:5]:
        if not isinstance(item, dict):
            continue
        
        snippet = item.get("snippet", "").strip()
        if not snippet:
            continue
        
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        
        # Format with clear structure
        if title:
            combined_text.append(f"[Source: {title}]")
        
        combined_text.append(snippet)
        
        if url:
            combined_text.append(f"(URL: {url})")
        
        combined_text.append("")  # Blank line separator
    
    return "\n".join(combined_text)