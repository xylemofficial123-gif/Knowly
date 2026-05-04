import logging
import re
from functools import lru_cache
from typing import Optional

from app.core.config import settings
from app.services.embeddings import embed_text, search_chunks
from app.services.llm import generate

logger = logging.getLogger(__name__)

# Acronyms that are universally understood — skip the lookup, never inject
# definitions for these. Saves cost and avoids being patronizing in answers.
_UNIVERSAL_ACRONYMS = {
    "AI", "API", "URL", "URI", "HTTP", "HTTPS", "JSON", "XML", "HTML", "CSS",
    "SQL", "DB", "UI", "UX", "OS", "PR", "QA", "ID", "USA", "UK", "EU",
    "PDF", "CSV", "PNG", "JPG", "GIF", "SVG", "PM", "AM", "CEO", "CTO", "CFO",
    "COO", "VP", "HR", "IT", "FAQ", "TBD", "ASAP", "FYI", "BTW", "AKA",
    "LLM", "ML", "AI", "GPU", "CPU", "RAM", "USB", "WIFI", "VPN", "SDK",
    "IDE", "TS", "JS", "PY", "GO", "RFC",
}

# Match standalone uppercase tokens 2-6 chars long, optionally with digits.
# Examples: LSQ, ICP, K8s (mixed-case kept), B2B, SOC2, ICP-3
_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,5}\b")

GLOSSARY = {
    "API": "Application Programming Interface",
    "MVP": "Minimum Viable Product",
    "PR": "Pull Request",
    "CI": "Continuous Integration",
    "CD": "Continuous Deployment",
    "OKR": "Objectives and Key Results",
    "KPI": "Key Performance Indicator",
    "SLA": "Service Level Agreement",
    "EOD": "End of Day",
    "ETA": "Estimated Time of Arrival",
    "LGTM": "Looks Good To Me",
    "TL;DR": "Too Long; Didn't Read",
    "POC": "Proof of Concept",
    "ROI": "Return on Investment",
    "B2B": "Business to Business",
    "B2C": "Business to Consumer",
    "ARR": "Annual Recurring Revenue",
    "MRR": "Monthly Recurring Revenue",
    "CAC": "Customer Acquisition Cost",
    "LTV": "Lifetime Value",
}


def extract_acronyms_from_query(query: str) -> list[str]:
    """Find candidate acronyms in a user query.

    Returns deduplicated uppercase tokens 2-6 chars long, excluding universal
    ones the LLM already knows. Order preserved (first occurrence first).
    """
    seen: set[str] = set()
    out: list[str] = []
    for match in _ACRONYM_RE.findall(query or ""):
        upper = match.upper()
        if upper in _UNIVERSAL_ACRONYMS:
            continue
        if upper in seen:
            continue
        seen.add(upper)
        out.append(upper)
    return out


@lru_cache(maxsize=512)
def _cached_definition(term: str) -> Optional[str]:
    """Return a definition string for `term` or None if unknown.

    Hot path — called once per acronym per query. Cached for the process
    lifetime; cache resets on worker restart. The returned string is the body
    only (no formatting), kept short for prompt injection.
    """
    upper = term.upper().strip()
    if upper in GLOSSARY:
        return GLOSSARY[upper]

    try:
        # Embedding + search + LLM call — only runs on cache miss.
        query_vector = embed_text(f"what does {term} mean? definition of {term}")
        results = search_chunks(query_vector, limit=5)
        if not results:
            return None
        context = "\n".join(r.payload.get("text_preview", "") for r in results[:3])
        if not context.strip():
            return None
        definition = generate(
            f"Define '{term}' in one short sentence based on this company context. "
            f"If the context doesn't define it, reply exactly: UNKNOWN.\n\n"
            f"Context:\n{context}\n\nDefinition:"
        ).strip()
        if not definition or definition.upper().startswith("UNKNOWN"):
            return None
        # Strip markdown / quote artifacts the LLM may add
        return definition.strip(' "\'*`')
    except Exception as e:
        logger.debug(f"Acronym lookup failed for '{term}': {e}")
        return None


def glossary_for_query(query: str, max_terms: int = 5) -> dict[str, str]:
    """Return {term: definition} for all known acronyms in the query.

    Skips unknowns silently. Capped at `max_terms` to bound latency on
    queries that incidentally mention many uppercase tokens.
    """
    candidates = extract_acronyms_from_query(query)[:max_terms]
    out: dict[str, str] = {}
    for term in candidates:
        definition = _cached_definition(term)
        if definition:
            out[term] = definition
    return out


def bust_acronym(term: str) -> str:
    upper_term = term.upper().strip()

    if upper_term in GLOSSARY:
        return f"*{upper_term}*: {GLOSSARY[upper_term]}"

    try:
        query_vector = embed_text(f"what does {term} mean? definition of {term}")
        results = search_chunks(query_vector, limit=5)

        if not results:
            return f"*{upper_term}*: No definition found in the knowledge base."

        context = "\n".join(r.payload.get("text_preview", "") for r in results[:3])

        definition = generate(
            f"Based on this company context, define '{term}' in one sentence.\n\nContext:\n{context}\n\nDefinition:"
        ).strip()
        return f"*{upper_term}*: {definition}"

    except Exception as e:
        logger.error(f"Acronym buster failed for '{term}': {e}")
        return f"*{upper_term}*: Unable to find a definition at this time."
