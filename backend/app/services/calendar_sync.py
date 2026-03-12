"""Google Calendar sync — ingests upcoming and recent events for agent queries."""
import logging
from datetime import timedelta

from googleapiclient.discovery import build

from app.services.drive_ingestion import _get_credentials
from app.services.chunker import chunk_and_store
from app.core.timezone import now_utc, now_ist, format_ist, to_ist

logger = logging.getLogger(__name__)

# How far ahead/behind to sync
DAYS_AHEAD = 30
DAYS_BEHIND = 7


def _get_calendar_service():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def _format_event_text(event: dict) -> str:
    """Build a human-readable text block for a calendar event."""
    summary = event.get("summary", "Untitled Event")

    # Parse start/end times
    start = event.get("start", {})
    end = event.get("end", {})
    start_str = start.get("dateTime", start.get("date", ""))
    end_str = end.get("dateTime", end.get("date", ""))

    # Format in IST
    from app.core.timezone import parse_iso
    start_dt = parse_iso(start_str)
    end_dt = parse_iso(end_str)
    start_display = format_ist(start_dt) if start_dt else start_str
    end_display = format_ist(end_dt) if end_dt else end_str

    # All-day event check
    is_all_day = "date" in start and "dateTime" not in start

    lines = [f"Calendar Event: {summary}"]

    if is_all_day:
        lines.append(f"Date: {start_str} (all day)")
    else:
        lines.append(f"Start: {start_display}")
        lines.append(f"End: {end_display}")

    # Status
    status = event.get("status", "confirmed")
    lines.append(f"Status: {status}")

    # Location
    location = event.get("location", "")
    if location:
        lines.append(f"Location: {location}")

    # Description
    description = event.get("description", "")
    if description:
        lines.append(f"Description: {description[:500]}")

    # Organizer
    organizer = event.get("organizer", {})
    org_name = organizer.get("displayName", organizer.get("email", ""))
    if org_name:
        lines.append(f"Organizer: {org_name}")

    # Attendees
    attendees = event.get("attendees", [])
    if attendees:
        attendee_list = []
        for a in attendees:
            name = a.get("displayName", a.get("email", "Unknown"))
            resp = a.get("responseStatus", "needsAction")
            attendee_list.append(f"{name} ({resp})")
        lines.append(f"Attendees: {', '.join(attendee_list)}")

    # Conference/Meet link
    conference = event.get("conferenceData", {})
    entry_points = conference.get("entryPoints", [])
    for ep in entry_points:
        if ep.get("entryPointType") == "video":
            lines.append(f"Meeting Link: {ep.get('uri', '')}")
            break

    # Recurrence
    recurrence = event.get("recurrence", [])
    if recurrence:
        lines.append(f"Recurrence: {'; '.join(recurrence)}")

    return "\n".join(lines)


def fetch_calendar_events(days_ahead: int = DAYS_AHEAD, days_behind: int = DAYS_BEHIND) -> list[dict]:
    """Fetch calendar events from the past N days to the next N days."""
    service = _get_calendar_service()
    now = now_utc()

    time_min = (now - timedelta(days=days_behind)).isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    all_events = []
    page_token = None

    while True:
        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
            maxResults=100,
        ).execute()

        events = result.get("items", [])
        all_events.extend(events)

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    logger.info(f"Fetched {len(all_events)} calendar events ({days_behind}d behind, {days_ahead}d ahead)")
    return all_events


def sync_calendar() -> int:
    """Sync calendar events into the knowledge base."""
    events = fetch_calendar_events()

    count = 0
    for event in events:
        event_id = event.get("id", "")
        summary = event.get("summary", "Untitled Event")
        source_id = f"calendar:{event_id}"

        # Skip cancelled events
        if event.get("status") == "cancelled":
            continue

        # Build text representation
        text = _format_event_text(event)

        # Build ACL from attendees
        acl = ["public"]
        attendees = event.get("attendees", [])
        if attendees:
            acl = [a.get("email", "") for a in attendees if a.get("email")]
            # Also add organizer
            org_email = event.get("organizer", {}).get("email", "")
            if org_email and org_email not in acl:
                acl.append(org_email)

        # URL to the event
        url = event.get("htmlLink", "")

        # Extra metadata for temporal search
        start = event.get("start", {})
        start_str = start.get("dateTime", start.get("date", ""))

        extra_metadata = {
            "event_start": start_str,
            "event_type": "calendar",
            "ingested_at": now_utc().isoformat(),
        }

        try:
            chunk_and_store(
                source="calendar",
                source_id=source_id,
                text=text,
                url=url,
                acl=acl,
                title=summary,
                extra_metadata=extra_metadata,
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to sync calendar event '{summary}': {e}")

    logger.info(f"Calendar sync complete: {count} events synced")
    return count
