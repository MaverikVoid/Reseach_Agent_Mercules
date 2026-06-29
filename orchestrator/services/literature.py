"""
Literature search service — direct API calls to arXiv and Semantic Scholar.

No LLM-memory novelty judgment: all claims must be grounded in actually
retrieved papers.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import requests
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# ── arXiv API ──────────────────────────────────────────────────────────

def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    """
    Search arXiv for papers matching the query.

    Returns list of dicts with: title, authors, abstract, url, published, source.
    """
    # Clean query for arXiv API
    clean_query = re.sub(r"[^\w\s]", " ", query)
    clean_query = " ".join(clean_query.split()[:20])  # Limit query length

    params = {
        "search_query": f"all:{clean_query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        response = requests.get(
            "http://export.arxiv.org/api/query",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"arXiv API error: {e}")
        return []

    # Parse Atom XML
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        logger.error(f"arXiv XML parse error: {e}")
        return []

    papers = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        id_el = entry.find("atom:id", ns)
        published_el = entry.find("atom:published", ns)

        # Get authors
        authors = []
        for author in entry.findall("atom:author", ns):
            name_el = author.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        title = title_el.text.strip() if title_el is not None and title_el.text else "Unknown"
        # Clean up whitespace in title
        title = " ".join(title.split())

        abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
        abstract = " ".join(abstract.split())

        url = id_el.text.strip() if id_el is not None and id_el.text else ""
        published = published_el.text.strip() if published_el is not None and published_el.text else ""

        papers.append({
            "title": title,
            "authors": ", ".join(authors[:5]),  # Limit to first 5 authors
            "abstract": abstract[:1000],  # Truncate very long abstracts
            "url": url,
            "published": published[:10],  # Just the date part
            "source": "arxiv",
        })

    logger.info(f"arXiv returned {len(papers)} papers for query: {query[:50]}")
    return papers


# ── Semantic Scholar API ───────────────────────────────────────────────

def search_semantic_scholar(
    query: str,
    max_results: int = 10,
    api_key: Optional[str] = None,
) -> list[dict]:
    """
    Search Semantic Scholar for papers matching the query.

    Returns list of dicts with: title, authors, abstract, url, year,
    citation_count, source.
    """
    fields = "title,authors,abstract,citationCount,year,url,tldr"
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    import time

    for attempt in range(3):
        try:
            response = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query[:200],  # API has query length limits
                    "limit": min(max_results, 100),
                    "fields": fields,
                },
                headers=headers,
                timeout=30,
            )
            if response.status_code == 429:
                wait = (attempt + 1) * 10  # 10s, 20s, 30s
                logger.warning(f"Semantic Scholar rate limited, waiting {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
                continue
            response.raise_for_status()
            break
        except requests.RequestException as e:
            logger.error(f"Semantic Scholar API error: {e}")
            if attempt < 2:
                time.sleep((attempt + 1) * 5)
                continue
            return []
    else:
        logger.error("Semantic Scholar API exhausted all retries")
        return []

    data = response.json()
    raw_papers = data.get("data", [])

    papers = []
    for p in raw_papers:
        authors_list = p.get("authors", [])
        author_names = [a.get("name", "") for a in authors_list[:5]]

        abstract = p.get("abstract", "")
        if not abstract:
            # Use TLDR as fallback
            tldr = p.get("tldr")
            if tldr and isinstance(tldr, dict):
                abstract = tldr.get("text", "")

        paper_id = p.get("paperId", "")
        url = p.get("url", "")
        if not url and paper_id:
            url = f"https://www.semanticscholar.org/paper/{paper_id}"

        papers.append({
            "title": p.get("title", "Unknown"),
            "authors": ", ".join(author_names),
            "abstract": (abstract or "")[:1000],
            "url": url,
            "year": p.get("year"),
            "citation_count": p.get("citationCount", 0),
            "source": "semantic_scholar",
        })

    logger.info(f"Semantic Scholar returned {len(papers)} papers for query: {query[:50]}")
    return papers


# ── Combined search ────────────────────────────────────────────────────

def search_papers(
    idea_text: str,
    max_results: int = 20,
    semantic_scholar_api_key: Optional[str] = None,
) -> list[dict]:
    """
    Search both arXiv and Semantic Scholar, combine and deduplicate results.

    Parameters
    ----------
    idea_text : str
        The research idea to search for.
    max_results : int
        Total max results (split between sources).

    Returns
    -------
    list[dict]
        Combined, deduplicated papers sorted by relevance.
    """
    per_source = max(max_results // 2, 5)

    # Search both sources
    arxiv_papers = search_arxiv(idea_text, max_results=per_source)
    ss_papers = search_semantic_scholar(
        idea_text,
        max_results=per_source,
        api_key=semantic_scholar_api_key,
    )

    # Combine
    all_papers = arxiv_papers + ss_papers

    # Deduplicate by title similarity (simple lowercase comparison)
    seen_titles = set()
    unique_papers = []
    for p in all_papers:
        # Normalize title for comparison
        norm_title = p["title"].lower().strip()
        # Remove common suffixes/prefixes
        norm_title = re.sub(r"[^\w\s]", "", norm_title)

        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            unique_papers.append(p)

    # Sort by citation count (where available), then by source preference
    def sort_key(p):
        citations = p.get("citation_count", 0) or 0
        return -citations  # Higher citations first

    unique_papers.sort(key=sort_key)

    logger.info(
        f"Combined search: {len(arxiv_papers)} arXiv + {len(ss_papers)} SS = "
        f"{len(unique_papers)} unique papers"
    )

    return unique_papers[:max_results]
