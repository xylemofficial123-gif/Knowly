import logging

from app.core.config import settings
from app.services.embeddings import embed_text, search_chunks
from app.services.llm import generate

logger = logging.getLogger(__name__)

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
