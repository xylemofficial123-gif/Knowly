"""Entity extraction + knowledge-graph linking.

Two layers:

1. ``extract_entities(text)`` — fast regex-only extraction (emails, URLs, Slack
   mentions). Used by chunker.py for the Qdrant payload. Cheap, synchronous.

2. ``process_document_entities(document_id)`` — heavy graph-building pass.
   Runs once per document in a Celery worker. Uses a gazetteer-first strategy
   (substring scan against existing entities) and falls back to one LLM call
   for the whole document to discover new entities. Writes Entity +
   EntityMention rows. The LLM call is doc-level, not chunk-level — a 50-chunk
   doc costs 1 LLM call, not 50.
"""
import re
import json
import logging
from typing import Iterable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ENTITY_TYPES = {"project", "person", "feature", "tool", "acronym", "other"}


# ── Layer 1: regex extraction (kept for chunker.py / Qdrant payload) ──────────

def extract_entities(text: str) -> dict:
    entities = {
        "people": [],
        "urls": [],
        "emails": [],
        "projects": [],
    }

    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    entities["emails"] = list(set(emails))

    urls = re.findall(r"https?://[^\s<>\"']+", text)
    entities["urls"] = list(set(urls))

    mentions = re.findall(r"<@([A-Z0-9]+)>", text)
    entities["people"] = list(set(mentions))

    projects = re.findall(r"(?:Project|project|PROJ)[:\s]+([A-Za-z][A-Za-z0-9\s\-]{2,30})", text)
    entities["projects"] = list(set(p.strip() for p in projects))

    return entities


# ── Layer 2: graph-building extraction ────────────────────────────────────────

def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _load_gazetteer(db: Session) -> list[tuple[str, "uuid.UUID", str]]:
    """Return a flat list of (lowercase_name, entity_id, entity_type) covering
    every entity's canonical_name and aliases. Cheap enough to load per-task."""
    from app.models import Entity

    rows = db.query(Entity).all()
    gaz: list[tuple] = []
    for ent in rows:
        gaz.append((_normalize(ent.canonical_name), ent.id, ent.entity_type))
        for alias in (ent.aliases or []):
            if alias:
                gaz.append((_normalize(str(alias)), ent.id, ent.entity_type))
    # Sort longest-first so "Project Atlas" matches before "Atlas"
    gaz.sort(key=lambda x: -len(x[0]))
    return gaz


def _scan_with_gazetteer(text: str, gazetteer) -> set:
    """Find all gazetteer entries that appear in `text`. Returns set of entity_id."""
    if not text or not gazetteer:
        return set()
    lowered = text.lower()
    found = set()
    for name, ent_id, _ in gazetteer:
        if not name or len(name) < 2:
            continue
        # Word-boundary-ish match — avoid matching "atlas" inside "atlasian"
        # by requiring the surrounding chars to be non-alphanumeric.
        idx = 0
        while True:
            pos = lowered.find(name, idx)
            if pos < 0:
                break
            before_ok = pos == 0 or not lowered[pos - 1].isalnum()
            end = pos + len(name)
            after_ok = end >= len(lowered) or not lowered[end].isalnum()
            if before_ok and after_ok:
                found.add(ent_id)
                break
            idx = pos + 1
    return found


_LLM_PROMPT = """Extract distinct named entities from the document below. Only return entities that are clearly named — do NOT invent generic terms.

Return a JSON array. Each entry: {{"name": "<entity name>", "type": "<one of: project, person, feature, tool, acronym>"}}.

Rules:
- "project": named projects, products, initiatives (e.g., "Project Atlas", "Q3 Roadmap")
- "person": real people by name (e.g., "Sachin Kurup"). NOT job titles or pronouns.
- "feature": specific named product features (e.g., "Smart Views", "OAuth Login")
- "tool": named software/platforms (e.g., "Stripe", "Snowflake", "Slack")
- "acronym": company-internal acronyms or codes (e.g., "LSQ", "ICP")
- Skip generic words ("the team", "engineering", "Q3", "next week").
- Deduplicate — same entity, one entry. Use the most complete form (e.g., "Project Atlas" not "Atlas" if both appear).
- If nothing qualifies, return [].

Document:
\"\"\"
{text}
\"\"\"

JSON array:"""


def _llm_extract_entities(text: str, max_chars: int = 6000) -> list[dict]:
    """Call the LLM once per document to discover new entities. Returns
    list of {"name": ..., "type": ...}. Returns [] on any failure — entity
    extraction is best-effort and must never break ingestion."""
    from app.services.llm import generate

    if not text or len(text.strip()) < 50:
        return []
    truncated = text[:max_chars]
    try:
        raw = generate(_LLM_PROMPT.format(text=truncated), max_tokens=512).strip()
    except Exception as e:
        logger.warning(f"Entity LLM extraction failed: {e}")
        return []

    # Strip code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage — find the first JSON array
        match = re.search(r"\[[\s\S]*\]", raw)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except Exception:
            return []

    if not isinstance(data, list):
        return []

    cleaned = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        ent_type = (item.get("type") or "other").strip().lower()
        if not name or len(name) < 2 or len(name) > 80:
            continue
        if ent_type not in ENTITY_TYPES:
            ent_type = "other"
        key = (_normalize(name), ent_type)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"name": name, "type": ent_type})
    return cleaned


def _find_or_create_entity(db: Session, name: str, entity_type: str) -> "uuid.UUID":
    """Match by canonical_name or alias; create if absent. Adds new surface form
    as an alias when the canonical form differs."""
    from app.models import Entity

    norm = _normalize(name)
    # Exact canonical match
    existing = (
        db.query(Entity)
        .filter(Entity.entity_type == entity_type)
        .all()
    )
    for ent in existing:
        if _normalize(ent.canonical_name) == norm:
            return ent.id
        for alias in (ent.aliases or []):
            if _normalize(str(alias)) == norm:
                return ent.id

    # Create new
    ent = Entity(
        canonical_name=name,
        entity_type=entity_type,
        aliases=[],
        created_by="ingestion",
    )
    db.add(ent)
    db.flush()
    return ent.id


def process_document_entities(document_id: str) -> int:
    """Build the entity graph for a single document.

    Strategy:
    1. Load all chunks for the document.
    2. Load gazetteer (existing entity names + aliases) once.
    3. Run one LLM extraction over the full doc text to discover new entities.
    4. For each chunk: gazetteer scan + intersect with LLM-discovered names that
       appear in this chunk. Write EntityMention rows.

    Returns total mentions written.
    """
    from app.core.database import SessionLocal
    from app.models import Document, Chunk, EntityMention

    db = SessionLocal()
    written = 0
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning(f"process_document_entities: doc {document_id} not found")
            return 0
        chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
        if not chunks:
            return 0

        gazetteer = _load_gazetteer(db)

        # One LLM call for the entire document (cheap on token cost vs per-chunk)
        full_text = (doc.content or "") or "\n\n".join(c.text or "" for c in chunks)
        llm_entities = _llm_extract_entities(full_text)

        # Resolve each LLM-discovered entity to an entity_id (create if new),
        # remembering the surface form so we can match it inside individual chunks.
        llm_resolved: list[tuple[str, "uuid.UUID"]] = []  # (lowercase_name, entity_id)
        for item in llm_entities:
            try:
                ent_id = _find_or_create_entity(db, item["name"], item["type"])
                llm_resolved.append((_normalize(item["name"]), ent_id))
            except Exception as e:
                logger.warning(f"Entity persist failed for {item}: {e}")
                continue
        db.commit()

        # Refresh gazetteer with newly created entities so per-chunk scan finds them
        if llm_resolved:
            gazetteer = _load_gazetteer(db)

        # Per-chunk mentions
        existing_mention_keys = set(
            (m.entity_id, m.chunk_id)
            for m in db.query(EntityMention)
            .filter(EntityMention.document_id == document_id)
            .all()
        )

        # Track per-chunk entity sets so we can compute pairwise co-occurrences
        # for the knowledge-graph edges after writing the mentions.
        chunk_entity_sets: list[set] = []

        for chunk in chunks:
            chunk_text = chunk.text or ""
            if not chunk_text.strip():
                continue
            entity_ids = _scan_with_gazetteer(chunk_text, gazetteer)
            chunk_entity_sets.append(entity_ids)
            for ent_id in entity_ids:
                if (ent_id, chunk.id) in existing_mention_keys:
                    continue
                mention = EntityMention(
                    entity_id=ent_id,
                    chunk_id=chunk.id,
                    document_id=document_id,
                    source=doc.source,
                )
                db.add(mention)
                existing_mention_keys.add((ent_id, chunk.id))
                written += 1
        db.commit()

        # Co-occurrence edges — every pair of entities that appears together
        # in any chunk gets +1 weight. Pair order is canonicalized
        # (smaller UUID string first) so the unique constraint holds.
        try:
            _update_cooccurrences(db, chunk_entity_sets)
        except Exception as e:
            logger.warning(f"Cooccurrence update failed for {document_id}: {e}")
            db.rollback()
        logger.info(
            f"Entity graph: doc={document_id} chunks={len(chunks)} "
            f"llm_found={len(llm_entities)} mentions_written={written}"
        )
        return written
    except Exception as e:
        db.rollback()
        logger.error(f"process_document_entities failed for {document_id}: {e}")
        return 0
    finally:
        db.close()


def _update_cooccurrences(db: Session, chunk_entity_sets: list[set]) -> None:
    """Increment pair weights for every entity pair that co-occurs in any chunk.

    Tally locally first (one pass through chunks), then merge into the DB with
    a single get-or-create per pair. Pair order canonicalized by str(uuid) so
    `uq_entity_cooccurrence_pair` holds.
    """
    from app.models import EntityCooccurrence

    pair_increments: dict = {}  # (a_id, b_id) -> count
    for ent_ids in chunk_entity_sets:
        if len(ent_ids) < 2:
            continue
        ids = sorted(ent_ids, key=str)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                key = (ids[i], ids[j])
                pair_increments[key] = pair_increments.get(key, 0) + 1

    if not pair_increments:
        return

    # Look up existing rows for these pairs in one query
    pair_keys = list(pair_increments.keys())
    a_ids = [p[0] for p in pair_keys]
    b_ids = [p[1] for p in pair_keys]
    existing = (
        db.query(EntityCooccurrence)
        .filter(
            EntityCooccurrence.entity_a_id.in_(a_ids),
            EntityCooccurrence.entity_b_id.in_(b_ids),
        )
        .all()
    )
    existing_by_pair = {(r.entity_a_id, r.entity_b_id): r for r in existing}

    for (a, b), inc in pair_increments.items():
        row = existing_by_pair.get((a, b))
        if row:
            row.weight = (row.weight or 0.0) + float(inc)
        else:
            db.add(EntityCooccurrence(entity_a_id=a, entity_b_id=b, weight=float(inc)))
    db.commit()


def find_entities_in_query(query: str) -> list[dict]:
    """Match a user query against the entity gazetteer. Returns list of
    {"id": uuid, "canonical_name": str, "entity_type": str} for graph traversal."""
    from app.core.database import SessionLocal
    from app.models import Entity

    db = SessionLocal()
    try:
        gazetteer = _load_gazetteer(db)
        matched_ids = _scan_with_gazetteer(query, gazetteer)
        if not matched_ids:
            return []
        entities = db.query(Entity).filter(Entity.id.in_(matched_ids)).all()
        return [
            {
                "id": e.id,
                "canonical_name": e.canonical_name,
                "entity_type": e.entity_type,
            }
            for e in entities
        ]
    finally:
        db.close()


def get_chunks_for_entities(entity_ids: list, limit_per_entity: int = 12) -> list[str]:
    """Return chunk_ids that mention any of the given entities, capped per entity
    to avoid one popular project drowning out the rest."""
    from app.core.database import SessionLocal
    from app.models import EntityMention

    if not entity_ids:
        return []
    db = SessionLocal()
    try:
        out: list[str] = []
        seen = set()
        for ent_id in entity_ids:
            mentions = (
                db.query(EntityMention)
                .filter(EntityMention.entity_id == ent_id)
                .order_by(EntityMention.created_at.desc())
                .limit(limit_per_entity)
                .all()
            )
            for m in mentions:
                cid = str(m.chunk_id)
                if cid not in seen:
                    seen.add(cid)
                    out.append(cid)
        return out
    finally:
        db.close()


def tag_all_chunks():
    """Legacy entry point — kept for backward compat with any callers."""
    from app.core.database import SessionLocal
    from app.models import Chunk

    db = SessionLocal()
    try:
        chunks = db.query(Chunk).all()
        for chunk in chunks:
            if chunk.text:
                extract_entities(chunk.text)
        logger.info(f"Tagged {len(chunks)} chunks with entities")
    finally:
        db.close()
