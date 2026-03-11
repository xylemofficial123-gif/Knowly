from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])


@router.post("/upload")
async def upload_transcript(
    file: UploadFile = File(...),
    meeting_title: str = Form(...),
    attendees: str = Form(""),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    filename = file.filename.lower()
    if filename.endswith(".vtt"):
        file_type = "vtt"
    elif filename.endswith(".srt"):
        file_type = "srt"
    else:
        raise HTTPException(status_code=400, detail="Only .vtt and .srt files are supported")

    try:
        content = await file.read()
        text = content.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    attendee_list = [a.strip() for a in attendees.split(",") if a.strip()]

    try:
        from app.services.meet_ingestion import ingest_transcript

        turns = ingest_transcript(
            content=text,
            title=meeting_title,
            url="",
            attendees=attendee_list,
            file_type=file_type,
        )
        return {
            "status": "ingested",
            "meeting_title": meeting_title,
            "turns_processed": turns,
            "attendees": attendee_list,
        }
    except Exception as e:
        logger.error(f"Transcript upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
