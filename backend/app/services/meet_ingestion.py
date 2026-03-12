import re
import json
import logging

from app.core.config import settings
from app.services.chunker import chunk_and_store
from app.services.llm import generate

logger = logging.getLogger(__name__)

MEETING_SUMMARY_PROMPT = """You are an expert meeting analyst. Analyze this meeting transcript/notes and produce a structured summary.

Return ONLY valid JSON with this structure:
{{
  "summary": "2-4 sentence overview of the meeting",
  "discussion_points": [
    {{
      "topic": "what was discussed",
      "raised_by": "person who raised/mentioned it (use their name, not email)",
      "details": "what they said or the key points discussed",
      "other_contributors": ["names of others who responded or contributed to this point"]
    }}
  ],
  "key_decisions": [
    {{
      "decision": "what was decided",
      "who": "person who made/owns it (use their name)",
      "context": "brief context"
    }}
  ],
  "action_items": [
    {{
      "task": "what needs to be done",
      "assigned_to": "person responsible (use their name, or 'Unassigned')",
      "assigned_by": "person who assigned it (use their name)",
      "deadline": "any mentioned deadline or 'Not specified'",
      "priority": "high/medium/low"
    }}
  ],
  "key_takeaways": [
    "important point 1",
    "important point 2"
  ],
  "follow_ups": [
    {{
      "item": "what needs follow-up",
      "who": "person responsible",
      "reason": "why it matters"
    }}
  ],
  "attendees_mentioned": ["name1", "name2"]
}}

Important:
- SPEAKER ATTRIBUTION IS CRITICAL: For every discussion point, decision, and action item, you MUST attribute it to the person who said/raised/decided it. Use their first name or full name, never just their email.
- If the transcript has speaker labels (e.g., "Sachin:", "Manjula:"), use those names directly.
- If the notes mention someone by name in context (e.g., "Krithin explained that..."), capture that attribution.
- Mark action items as "high" priority if they involve rescheduling, blocking issues, or deadlines
- Extract WHO is responsible for each action item AND who assigned it
- If someone says "let's push this to tomorrow" or "we'll do this next week", that's an action item
- Return ONLY valid JSON. No markdown fences. No explanation.

Meeting title: {title}

Meeting content:
{text}"""


# --- Google Drive transcript auto-discovery (OAuth) ---

def _get_drive_service():
    """Reuse the OAuth credentials from drive_ingestion."""
    from app.services.drive_ingestion import _get_credentials
    from googleapiclient.discovery import build

    creds = _get_credentials()
    return build("drive", "v3", credentials=creds)


def find_meet_transcripts() -> list[dict]:
    service = _get_drive_service()

    # Find Gemini meeting notes and transcripts
    query = (
        "mimeType='application/vnd.google-apps.document' "
        "and (name contains 'Notes by Gemini' or name contains 'transcript') "
        "and trashed=false"
    )

    if settings.GOOGLE_TRANSCRIPTS_FOLDER_ID:
        query = (
            f"mimeType='application/vnd.google-apps.document' "
            f"and (name contains 'Notes by Gemini' or name contains 'transcript' "
            f"or '{settings.GOOGLE_TRANSCRIPTS_FOLDER_ID}' in parents) "
            f"and trashed=false"
        )

    results = []
    page_token = None

    while True:
        resp = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink, lastModifyingUser, owners)",
                pageSize=100,
                pageToken=page_token,
            )
            .execute()
        )
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results


def _export_doc_as_text(file_id: str) -> str:
    service = _get_drive_service()
    content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return str(content)


def _extract_attendees_from_permissions(file_id: str) -> list[str]:
    """Get attendees from file permissions."""
    try:
        service = _get_drive_service()
        resp = service.permissions().list(
            fileId=file_id,
            fields="permissions(emailAddress, displayName, role)",
        ).execute()
        emails = []
        for p in resp.get("permissions", []):
            email = p.get("emailAddress")
            if email:
                emails.append(email)
        return emails
    except Exception as e:
        logger.debug(f"Could not fetch permissions for {file_id}: {e}")
        return []


def generate_meeting_summary(text: str, title: str) -> dict:
    """Use Gemini to generate a structured meeting summary."""
    prompt = MEETING_SUMMARY_PROMPT.format(title=title, text=text[:15000])

    try:
        raw = generate(prompt).strip()

        # Clean up markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Meeting summary generation failed: {e}")
        return {
            "summary": "Failed to generate summary.",
            "key_decisions": [],
            "action_items": [],
            "key_takeaways": [],
            "follow_ups": [],
            "attendees_mentioned": [],
        }


def _build_enriched_text(original_text: str, title: str, summary_data: dict) -> str:
    """Combine original transcript with structured summary for storage."""
    parts = [f"Meeting: {title}", ""]

    # Summary section
    parts.append("=== MEETING SUMMARY ===")
    parts.append(summary_data.get("summary", ""))
    parts.append("")

    # Discussion points (with speaker attribution)
    discussions = summary_data.get("discussion_points", [])
    if discussions:
        parts.append("=== DISCUSSION POINTS ===")
        for dp in discussions:
            raised_by = dp.get("raised_by", "")
            topic = dp.get("topic", "")
            details = dp.get("details", "")
            contributors = dp.get("other_contributors", [])
            line = f"- {raised_by} raised: {topic}" if raised_by else f"- {topic}"
            if details:
                line += f" — {details}"
            if contributors:
                line += f" (also: {', '.join(contributors)})"
            parts.append(line)
        parts.append("")

    # Key decisions
    decisions = summary_data.get("key_decisions", [])
    if decisions:
        parts.append("=== KEY DECISIONS ===")
        for d in decisions:
            who = d.get("who", "")
            parts.append(f"- Decision: {d['decision']}" + (f" (by {who})" if who else ""))
        parts.append("")

    # Action items
    actions = summary_data.get("action_items", [])
    if actions:
        parts.append("=== ACTION ITEMS ===")
        for a in actions:
            assigned = a.get("assigned_to", "Unassigned")
            deadline = a.get("deadline", "Not specified")
            priority = a.get("priority", "medium")
            parts.append(f"- [{priority.upper()}] {a['task']} → Assigned to: {assigned} | Deadline: {deadline}")
        parts.append("")

    # Key takeaways
    takeaways = summary_data.get("key_takeaways", [])
    if takeaways:
        parts.append("=== KEY TAKEAWAYS ===")
        for t in takeaways:
            parts.append(f"- {t}")
        parts.append("")

    # Follow-ups
    follow_ups = summary_data.get("follow_ups", [])
    if follow_ups:
        parts.append("=== FOLLOW-UPS NEEDED ===")
        for f in follow_ups:
            parts.append(f"- {f['item']} → {f.get('who', '?')}: {f.get('reason', '')}")
        parts.append("")

    # Original transcript
    parts.append("=== FULL TRANSCRIPT/NOTES ===")
    parts.append(original_text)

    return "\n".join(parts)


def _store_action_items(summary_data: dict, meeting_title: str, source_url: str):
    """Store high-priority action items in the review queue for visibility."""
    from app.core.database import SessionLocal
    from app.models.review_queue import ReviewQueueItem

    actions = summary_data.get("action_items", [])
    decisions = summary_data.get("key_decisions", [])

    db = SessionLocal()
    try:
        for action in actions:
            if action.get("priority") == "high":
                item = ReviewQueueItem(
                    raw_text=f"Meeting: {meeting_title}\nAction: {action['task']}",
                    proposed_decision=f"Action item: {action['task']}",
                    proposed_rationale=f"Assigned to {action.get('assigned_to', 'Unassigned')}. Deadline: {action.get('deadline', 'Not specified')}",
                    confidence=0.85,
                    decision_type="explicit",
                    trigger_phrase=f"From meeting: {meeting_title}",
                    source_chunk_id="",
                    source_url=source_url,
                    status="pending",
                )
                db.add(item)

        for dec in decisions:
            from app.models import DecisionRecord
            import datetime

            record = DecisionRecord(
                decision=dec["decision"],
                rationale=dec.get("context", ""),
                options_considered=[],
                status="active",
                source_chunk_ids=[],
                participants=[dec.get("who", "")],
                decided_at=datetime.datetime.utcnow(),
            )
            db.add(record)

        db.commit()
        logger.info(f"Stored {len(actions)} action items and {len(decisions)} decisions from {meeting_title}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to store action items: {e}")
    finally:
        db.close()


def ingest_meet_transcript(file_info: dict) -> dict:
    """Ingest a single meeting transcript with AI summary."""
    file_id = file_info["id"]
    title = file_info.get("name", f"Meeting {file_id}")
    url = file_info.get("webViewLink", f"https://docs.google.com/document/d/{file_id}")

    # Get transcript text
    text = _export_doc_as_text(file_id)
    if not text or len(text.strip()) < 30:
        logger.debug(f"Skipping empty transcript: {title}")
        return {}

    # Get attendees
    attendees = _extract_attendees_from_permissions(file_id)

    # Generate AI summary
    logger.info(f"Generating summary for: {title}")
    summary_data = generate_meeting_summary(text, title)

    # Build enriched text with summary + original
    enriched_text = _build_enriched_text(text, title, summary_data)

    # Build metadata
    last_editor = file_info.get("lastModifyingUser", {})
    owners = file_info.get("owners", [])
    metadata = {
        "meeting_title": title,
        "summary": summary_data.get("summary", ""),
        "action_items": summary_data.get("action_items", []),
        "key_decisions": summary_data.get("key_decisions", []),
        "key_takeaways": summary_data.get("key_takeaways", []),
        "follow_ups": summary_data.get("follow_ups", []),
        "attendees": attendees,
        "attendees_mentioned": summary_data.get("attendees_mentioned", []),
        "owner": owners[0].get("displayName", "") if owners else "",
        "owner_email": owners[0].get("emailAddress", "") if owners else "",
        "last_edited_by": last_editor.get("displayName", ""),
        "last_edited_at": file_info.get("modifiedTime", ""),
        "created_at": file_info.get("createdTime", ""),
    }

    # Store in knowledge base
    acl = attendees if attendees else ["public"]

    chunk_and_store(
        source="meet",
        source_id=f"meet:{file_id}",
        text=enriched_text,
        url=url,
        acl=acl,
        title=title,
        extra_metadata=metadata,
    )

    # Store action items and decisions in the review queue / decision records
    _store_action_items(summary_data, title, url)

    return summary_data


def ingest_drive_transcripts() -> int:
    """Auto-discover and ingest all meeting transcripts from Drive."""
    from app.core.database import SessionLocal
    from app.models import Document
    from datetime import datetime, timezone

    transcripts = find_meet_transcripts()
    logger.info(f"Found {len(transcripts)} meeting transcripts in Drive")

    # Check which ones we already have
    db = SessionLocal()
    try:
        existing = {
            doc.source_id: doc.updated_at
            for doc in db.query(Document.source_id, Document.updated_at)
            .filter(Document.source == "meet")
            .all()
        }
    finally:
        db.close()

    count = 0
    skipped = 0
    for file_info in transcripts:
        file_id = file_info["id"]
        source_id = f"meet:{file_id}"
        modified_time = file_info.get("modifiedTime", "")

        # Skip unchanged files
        if source_id in existing and existing[source_id]:
            try:
                drive_modified = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
                our_updated = existing[source_id].replace(tzinfo=timezone.utc)
                if drive_modified <= our_updated:
                    skipped += 1
                    continue
            except (ValueError, AttributeError):
                pass

        try:
            summary = ingest_meet_transcript(file_info)
            if summary:
                count += 1
                title = file_info.get("name", file_id)
                n_actions = len(summary.get("action_items", []))
                n_decisions = len(summary.get("key_decisions", []))
                logger.info(f"  Ingested: {title} ({n_actions} actions, {n_decisions} decisions)")
        except Exception as e:
            logger.error(f"Failed to ingest transcript {file_info.get('name', file_id)}: {e}")

    logger.info(f"Meeting sync complete: {count} new/updated, {skipped} unchanged")
    return count


# --- Path B: Manual VTT/SRT upload ---

def parse_vtt(content: str) -> list[dict]:
    segments = []
    lines = content.strip().split("\n")
    current_speaker = ""
    current_text = ""
    current_timestamp = ""

    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT" or line.startswith("NOTE"):
            continue

        if "-->" in line:
            if current_text and current_speaker:
                segments.append(
                    {"speaker": current_speaker, "timestamp": current_timestamp, "text": current_text.strip()}
                )
                current_text = ""
            current_timestamp = line.split("-->")[0].strip()
            continue

        if line.isdigit():
            continue

        speaker_match = re.match(r"<v\s+([^>]+)>(.*)", line)
        if speaker_match:
            if current_text and current_speaker:
                segments.append(
                    {"speaker": current_speaker, "timestamp": current_timestamp, "text": current_text.strip()}
                )
                current_text = ""
            current_speaker = speaker_match.group(1).strip()
            current_text = speaker_match.group(2).strip()
        else:
            current_text += " " + line

    if current_text and current_speaker:
        segments.append({"speaker": current_speaker, "timestamp": current_timestamp, "text": current_text.strip()})

    return segments


def parse_srt(content: str) -> list[dict]:
    segments = []
    blocks = re.split(r"\n\n+", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        timestamp = lines[1].split("-->")[0].strip() if "-->" in lines[1] else ""
        text_lines = lines[2:]
        text = " ".join(text_lines)

        speaker_match = re.match(r"([A-Za-z ]+):\s*(.*)", text)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            text = speaker_match.group(2).strip()
        else:
            speaker = "Unknown"

        segments.append({"speaker": speaker, "timestamp": timestamp, "text": text})

    return segments


def group_into_turns(segments: list[dict]) -> list[dict]:
    if not segments:
        return []

    turns = [segments[0].copy()]
    for seg in segments[1:]:
        if seg["speaker"] == turns[-1]["speaker"]:
            turns[-1]["text"] += " " + seg["text"]
        else:
            turns.append(seg.copy())

    return turns


def ingest_transcript(content: str, title: str, url: str, attendees: list[str], file_type: str = "vtt"):
    if file_type == "vtt":
        segments = parse_vtt(content)
    elif file_type == "srt":
        segments = parse_srt(content)
    else:
        segments = [{"speaker": "Unknown", "timestamp": "", "text": content}]

    turns = group_into_turns(segments)

    text_parts = [f"Meeting: {title}", ""]
    for turn in turns:
        text_parts.append(f"{turn['speaker']}: {turn['text']}")

    full_text = "\n".join(text_parts)

    # Generate AI summary
    summary_data = generate_meeting_summary(full_text, title)
    enriched_text = _build_enriched_text(full_text, title, summary_data)

    source_id = f"meet:upload:{title.replace(' ', '_')}"

    metadata = {
        "meeting_title": title,
        "summary": summary_data.get("summary", ""),
        "action_items": summary_data.get("action_items", []),
        "key_decisions": summary_data.get("key_decisions", []),
        "attendees_mentioned": summary_data.get("attendees_mentioned", []),
    }

    chunk_and_store(
        source="meet",
        source_id=source_id,
        text=enriched_text,
        url=url,
        acl=attendees if attendees else ["public"],
        title=title,
        extra_metadata=metadata,
    )

    _store_action_items(summary_data, title, url)

    logger.info(f"Ingested transcript '{title}' with {len(turns)} turns")
    return summary_data
