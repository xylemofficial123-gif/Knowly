from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
import logging
import io
from typing import Optional, List
from urllib.parse import quote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingestion"])
from app.core.auth import get_current_user_email
from app.core.database import SessionLocal
from app.core.acl import user_can_see_chunk
from app.core.config import settings
from app.models import Document


class TriggerRequest(BaseModel):
    source: str = "all"
    team_id: str = ""
    folder_ids: Optional[List[str]] = None


@router.post("/trigger")
def trigger_ingestion(req: TriggerRequest):
    from app.services.settings_service import is_source_enabled
    results = {}

    try:
        if req.source in ("slack", "all"):
            if not is_source_enabled("slack"):
                results["slack"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.slack_ingestion import backfill_all_channels
                try:
                    count = backfill_all_channels()
                    results["slack"] = {"status": "ok", "messages_ingested": count}
                except Exception as e:
                    results["slack"] = {"status": "error", "detail": str(e)}

        if req.source in ("clickup", "all"):
            if not is_source_enabled("clickup"):
                results["clickup"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.clickup_ingestion import ingest_all_clickup
                try:
                    count = ingest_all_clickup(req.team_id or None)
                    results["clickup"] = {"status": "ok", "tasks_ingested": count}
                except Exception as e:
                    results["clickup"] = {"status": "error", "detail": str(e)}

        if req.source in ("meet", "all"):
            if not is_source_enabled("meet"):
                results["meet"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.meet_ingestion import ingest_drive_transcripts
                from app.models import OAuthConnection
                from app.core.database import SessionLocal
                try:
                    db = SessionLocal()
                    try:
                        conns = db.query(OAuthConnection).filter(OAuthConnection.id.like("google:%")).all()
                        user_emails = [c.id[len("google:"):] for c in conns] or [None]
                    finally:
                        db.close()
                    total = sum(ingest_drive_transcripts(user_email=ue) for ue in user_emails)
                    results["meet"] = {"status": "ok", "transcripts_ingested": total}
                except Exception as e:
                    results["meet"] = {"status": "error", "detail": str(e)}

        if req.source in ("drive", "all"):
            if not is_source_enabled("drive"):
                results["drive"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.drive_ingestion import ingest_all_drive
                from app.models import GlobalSettings, OAuthConnection
                from app.core.database import SessionLocal
                try:
                    db = SessionLocal()
                    try:
                        folder_ids = req.folder_ids
                        if not folder_ids:
                            gs = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
                            if gs and gs.google_drive_folder_ids:
                                folder_ids = gs.google_drive_folder_ids
                        conns = db.query(OAuthConnection).filter(OAuthConnection.id.like("google:%")).all()
                        user_emails = [c.id[len("google:"):] for c in conns] or [None]
                    finally:
                        db.close()
                    total = sum(ingest_all_drive(folder_ids=folder_ids if folder_ids else None, user_email=ue) for ue in user_emails)
                    results["drive"] = {"status": "ok", "files_ingested": total}
                except Exception as e:
                    results["drive"] = {"status": "error", "detail": str(e)}

        if req.source in ("calendar", "all"):
            if not is_source_enabled("calendar"):
                results["calendar"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.calendar_sync import sync_calendar
                from app.models import OAuthConnection
                from app.core.database import SessionLocal
                try:
                    db = SessionLocal()
                    try:
                        conns = db.query(OAuthConnection).filter(OAuthConnection.id.like("google:%")).all()
                        user_emails = [c.id[len("google:"):] for c in conns] or [None]
                    finally:
                        db.close()
                    total = sum(sync_calendar(user_email=ue) for ue in user_emails)
                    results["calendar"] = {"status": "ok", "events_synced": total}
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
def list_folders(user_email: str = ""):
    """List available Google Drive folders for the requesting user."""
    from app.services.drive_ingestion import list_drive_folders

    try:
        folders = list_drive_folders(user_email=user_email or None)
        return {"status": "ok", "folders": folders}
    except Exception as e:
        logger.error(f"Failed to list Drive folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_email: str = Form(""),            # deprecated: identity comes from auth token
    scope: str = Form("private"),          # public | group | private
    group_id: str = Form(""),              # required when scope=group
    title: str = Form(""),
    shared_with: str = Form(""),           # comma-separated emails for private shares
    actor_email: str = Depends(get_current_user_email),
):
    """
    Upload a document with explicit scope.

    - scope=public   → visible to everyone (admin only)
    - scope=group    → visible to all members of group_id
    - scope=private  → visible only to the uploader (+ any shared_with emails)
    """
    from sqlalchemy import func
    from app.core.acl import build_acl, get_user_role
    from app.core.database import SessionLocal
    from app.models import GroupMembership
    from app.services.chunker import chunk_and_store
    actor_email = (actor_email or "").strip().lower()

    # Validate scope
    if scope not in ("public", "group", "private"):
        raise HTTPException(status_code=400, detail="scope must be public, group, or private")

    # Only admins can set public scope
    role = get_user_role(actor_email)
    if scope == "public" and role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can upload public documents")

    # Group scope validation
    if scope == "group":
        if not group_id:
            raise HTTPException(status_code=400, detail="group_id is required for group scope")
        # admin can upload to any group. group_admin can upload only for groups they manage.
        if role not in ("admin", "group_admin"):
            raise HTTPException(status_code=403, detail="Only admins or group admins can upload group documents")
        if role == "group_admin":
            db = SessionLocal()
            try:
                membership = (
                    db.query(GroupMembership)
                    .filter(
                        GroupMembership.group_id == group_id,
                        func.lower(GroupMembership.user_email) == actor_email,
                    )
                    .first()
                )
                if not membership or (membership.role or "").strip().lower() != "group_admin":
                    raise HTTPException(status_code=403, detail="You can only upload to groups where you are group_admin")
            finally:
                db.close()

    extra_emails = [e.strip() for e in shared_with.split(",") if e.strip()] if shared_with else None
    acl = build_acl(scope, actor_email, group_id=group_id or None, extra_emails=extra_emails)

    # Read file content
    content_bytes = await file.read()
    filename = title or file.filename or "uploaded_document"
    content_type = file.content_type or ""

    # Decode text
    try:
        if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            # Basic PDF text extraction
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content_bytes))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                text = content_bytes.decode("utf-8", errors="ignore")
        else:
            text = content_bytes.decode("utf-8", errors="ignore")
    except Exception:
        text = content_bytes.decode("latin-1", errors="ignore")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file")

    source_id = f"upload:{actor_email}:{filename}"
    source_url = f"{settings.BACKEND_URL}/api/ingest/uploaded/{quote(source_id, safe='')}"

    chunk_and_store(
        source="upload",
        source_id=source_id,
        text=text,
        url=source_url,
        acl=acl,
        title=filename,
        extra_metadata={
            "uploaded_by": user_email,
            "requested_user_email": user_email.strip().lower() if user_email else "",
            "scope": scope,
            "group_id": group_id or None,
            "filename": filename,
        },
        chunk_type="full_text",
    )

    logger.info(f"Uploaded '{filename}' by {actor_email} with scope={scope}, acl={acl}")
    return {
        "status": "ok",
        "filename": filename,
        "scope": scope,
        "acl": acl,
        "uploader": actor_email,
        "source_url": source_url,
    }


@router.get("/uploaded/{source_id:path}")
def get_uploaded_document(source_id: str, actor_email: str = Depends(get_current_user_email)):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.source_id == source_id, Document.source == "upload").first()
        if not doc:
            raise HTTPException(status_code=404, detail="Uploaded document not found")
        if not user_can_see_chunk(actor_email, list(doc.acl or [])):
            raise HTTPException(status_code=403, detail="You do not have access to this document")
        return {
            "title": doc.title or "Uploaded Document",
            "source_id": doc.source_id,
            "source": doc.source,
            "acl": doc.acl or [],
            "created_at": doc.created_at.isoformat() if doc.created_at else "",
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
            "content": doc.content or "",
        }
    finally:
        db.close()
