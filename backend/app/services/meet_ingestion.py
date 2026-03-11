import re
import logging

from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)


# --- Path A: Google Drive transcript auto-discovery ---

def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from app.core.config import settings

    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def find_meet_transcripts() -> list[dict]:
    from app.core.config import settings

    service = _get_drive_service()
    query_parts = ["mimeType='application/vnd.google-apps.document'"]

    if settings.GOOGLE_TRANSCRIPTS_FOLDER_ID:
        query_parts.append(
            f"(name contains 'transcript' or '{settings.GOOGLE_TRANSCRIPTS_FOLDER_ID}' in parents)"
        )
    else:
        query_parts.append("name contains 'transcript'")

    query = " and ".join(query_parts)

    results = []
    page_token = None

    while True:
        resp = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, createdTime, permissions)",
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


def _extract_attendees_from_permissions(file_info: dict) -> list[str]:
    permissions = file_info.get("permissions", [])
    emails = []
    for p in permissions:
        email = p.get("emailAddress")
        if email:
            emails.append(email)
    return emails


def _parse_speaker_turns(text: str) -> list[dict]:
    pattern = r"^([A-Z][a-z]+ [A-Z][a-z]+): (.+)"
    turns = []
    for line in text.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            turns.append({"speaker": match.group(1), "text": match.group(2)})
        elif turns and line.strip():
            turns[-1]["text"] += " " + line.strip()
    return turns


def ingest_drive_transcripts():
    transcripts = find_meet_transcripts()
    count = 0

    for file_info in transcripts:
        file_id = file_info["id"]
        title = file_info.get("name", f"Transcript {file_id}")

        try:
            text = _export_doc_as_text(file_id)
            attendees = _extract_attendees_from_permissions(file_info)

            chunk_and_store(
                source="meet",
                source_id=f"meet:drive:{file_id}",
                text=text,
                url=f"https://docs.google.com/document/d/{file_id}",
                acl=attendees,
                title=title,
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to ingest transcript {file_id}: {e}")

    logger.info(f"Ingested {count} Drive transcripts")
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

    source_id = f"meet:upload:{title.replace(' ', '_')}"

    chunk_and_store(
        source="meet",
        source_id=source_id,
        text=full_text,
        url=url,
        acl=attendees,
        title=title,
    )

    logger.info(f"Ingested transcript '{title}' with {len(turns)} turns")
    return len(turns)
