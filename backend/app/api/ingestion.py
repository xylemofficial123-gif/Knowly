from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


class TriggerRequest(BaseModel):
    source: str = "all"
    team_id: str = ""
    folder_ids: list[str] | None = None


@router.post("/trigger")
def trigger_ingestion(req: TriggerRequest):
    results = {}

    try:
        if req.source in ("slack", "all"):
            from app.services.slack_ingestion import backfill_all_channels

            try:
                count = backfill_all_channels()
                results["slack"] = {"status": "ok", "messages_ingested": count}
            except Exception as e:
                results["slack"] = {"status": "error", "detail": str(e)}

        if req.source in ("clickup", "all"):
            from app.services.clickup_ingestion import ingest_all_clickup

            try:
                count = ingest_all_clickup(req.team_id or None)
                results["clickup"] = {"status": "ok", "tasks_ingested": count}
            except Exception as e:
                results["clickup"] = {"status": "error", "detail": str(e)}

        if req.source in ("meet", "all"):
            from app.services.meet_ingestion import ingest_drive_transcripts

            try:
                count = ingest_drive_transcripts()
                results["meet"] = {"status": "ok", "transcripts_ingested": count}
            except Exception as e:
                results["meet"] = {"status": "error", "detail": str(e)}

        if req.source in ("drive", "all"):
            from app.services.drive_ingestion import ingest_all_drive

            try:
                count = ingest_all_drive(folder_ids=req.folder_ids)
                results["drive"] = {"status": "ok", "files_ingested": count}
            except Exception as e:
                results["drive"] = {"status": "error", "detail": str(e)}

        if req.source in ("calendar", "all"):
            from app.services.calendar_sync import sync_calendar

            try:
                count = sync_calendar()
                results["calendar"] = {"status": "ok", "events_synced": count}
            except Exception as e:
                results["calendar"] = {"status": "error", "detail": str(e)}

        if req.source not in ("slack", "clickup", "meet", "drive", "calendar", "all"):
            raise HTTPException(status_code=400, detail=f"Unknown source: {req.source}")

        return {"status": "triggered", "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/drive/folders")
def list_folders():
    """List available Google Drive folders for selection."""
    from app.services.drive_ingestion import list_drive_folders

    try:
        folders = list_drive_folders()
        return {"status": "ok", "folders": folders}
    except Exception as e:
        logger.error(f"Failed to list Drive folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
