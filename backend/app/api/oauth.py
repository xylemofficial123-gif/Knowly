"""
OAuth 2.0 endpoints for ClickUp and Google integration.

ClickUp flow:
  1. Frontend calls GET /api/oauth/clickup/authorize
     → returns {"url": "https://app.clickup.com/api?client_id=...&redirect_uri=...&state=..."}
  2. Frontend sets window.location.href to that URL
  3. User approves in ClickUp
  4. ClickUp redirects browser to GET /api/oauth/clickup/callback?code=...&state=...
  5. Backend exchanges code → access_token, fetches workspace, saves to DB
  6. Backend redirects browser to frontend /ingest?clickup=connected

Google flow:
  1. Frontend calls GET /api/oauth/google/authorize
     → returns {"url": "https://accounts.google.com/o/oauth2/v2/auth?..."}
  2. Frontend sets window.location.href to that URL
  3. User approves in Google
  4. Google redirects browser to GET /api/oauth/google/callback?code=...&state=...
  5. Backend exchanges code → access_token + refresh_token, fetches email, saves to DB
  6. Backend redirects browser to frontend /ingest?google=connected
"""
import logging
import secrets
import requests as http

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.token_store import get_connection, save_connection, delete_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oauth", tags=["oauth"])

CLICKUP_AUTH_URL  = "https://app.clickup.com/api"
CLICKUP_TOKEN_URL = "https://api.clickup.com/api/v2/oauth/token"
CLICKUP_TEAM_URL  = "https://api.clickup.com/api/v2/team"

GOOGLE_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL   = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "openid",
    "email",
]

# Redis client for CSRF state tokens (10-min TTL)
def _redis():
    import redis
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


# ── ClickUp ───────────────────────────────────────────────────────────────────

@router.get("/clickup/authorize")
def clickup_authorize():
    """Return the ClickUp OAuth URL for the frontend to redirect to."""
    if not settings.CLICKUP_CLIENT_ID:
        raise HTTPException(status_code=501, detail="CLICKUP_CLIENT_ID not configured")

    state = secrets.token_urlsafe(32)
    try:
        _redis().setex(f"oauth:state:{state}", 600, "clickup")
    except Exception as e:
        logger.warning(f"Redis unavailable for OAuth state — proceeding without CSRF: {e}")

    redirect_uri = f"{settings.BACKEND_URL}/api/oauth/clickup/callback"
    url = f"{CLICKUP_AUTH_URL}?client_id={settings.CLICKUP_CLIENT_ID}&redirect_uri={redirect_uri}&state={state}"
    return {"url": url}


@router.get("/clickup/callback")
def clickup_callback(code: str, state: str = ""):
    """ClickUp redirects here after user approves. Exchanges code for token."""
    # CSRF state check (best-effort — skip if Redis is down)
    try:
        stored = _redis().get(f"oauth:state:{state}")
        if stored is None:
            logger.warning("OAuth state token not found in Redis — may have expired")
        else:
            _redis().delete(f"oauth:state:{state}")
    except Exception:
        pass

    # Exchange code for access token
    redirect_uri = f"{settings.BACKEND_URL}/api/oauth/clickup/callback"
    try:
        resp = http.post(
            CLICKUP_TOKEN_URL,
            json={
                "client_id":     settings.CLICKUP_CLIENT_ID,
                "client_secret": settings.CLICKUP_CLIENT_SECRET,
                "code":          code,
            },
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as e:
        logger.error(f"ClickUp token exchange failed: {e}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?clickup=error")

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(f"No access_token in ClickUp response: {token_data}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?clickup=error")

    # Fetch workspace info
    team_id, workspace_name = "", ""
    try:
        teams_resp = http.get(
            CLICKUP_TEAM_URL,
            headers={"Authorization": access_token},
            timeout=10,
        )
        teams_resp.raise_for_status()
        teams = teams_resp.json().get("teams", [])
        if teams:
            team_id       = teams[0].get("id", "")
            workspace_name = teams[0].get("name", "")
    except Exception as e:
        logger.warning(f"Could not fetch ClickUp workspace info: {e}")

    save_connection(
        "clickup",
        access_token,
        token_type=token_data.get("token_type", "bearer"),
        team_id=team_id,
        workspace_name=workspace_name,
    )

    logger.info(f"ClickUp OAuth connected — workspace: {workspace_name} ({team_id})")
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?clickup=connected")


@router.get("/clickup/status")
def clickup_status():
    """Return the current ClickUp connection status."""
    conn = get_connection("clickup")
    if not conn:
        return {"connected": False}
    return {
        "connected":      True,
        "workspace_name": conn.workspace_name,
        "team_id":        conn.team_id,
        "connected_at":   conn.connected_at.isoformat() if conn.connected_at else None,
    }


@router.delete("/clickup/disconnect")
def clickup_disconnect():
    """Remove the ClickUp OAuth connection."""
    delete_connection("clickup")
    return {"status": "disconnected"}


@router.post("/clickup/register-webhook")
def clickup_register_webhook():
    """Register ClickUp webhook so real-time task events fire to this backend."""
    conn = get_connection("clickup")
    if not conn:
        raise HTTPException(status_code=400, detail="ClickUp not connected")
    if not conn.team_id:
        raise HTTPException(status_code=400, detail="No team_id found in connection")

    from app.services.clickup_ingestion import register_webhook
    endpoint = f"{settings.BACKEND_URL}/api/clickup/webhook"
    try:
        result = register_webhook(conn.team_id, endpoint)
        return {"status": "registered", "webhook_id": result.get("id"), "endpoint": endpoint}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook registration failed: {e}")


# ── Google ─────────────────────────────────────────────────────────────────────

@router.get("/google/authorize")
def google_authorize():
    """Return the Google OAuth URL for the frontend to redirect to."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="GOOGLE_CLIENT_ID not configured")

    state = secrets.token_urlsafe(32)
    try:
        _redis().setex(f"oauth:state:{state}", 600, "google")
    except Exception as e:
        logger.warning(f"Redis unavailable for OAuth state — proceeding without CSRF: {e}")

    import urllib.parse
    redirect_uri = f"{settings.BACKEND_URL}/api/oauth/google/callback"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return {"url": url}


@router.get("/google/callback")
def google_callback(code: str, state: str = "", error: str = ""):
    """Google redirects here after user approves. Exchanges code for tokens."""
    if error:
        logger.warning(f"Google OAuth error: {error}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?google=error")

    # CSRF state check (best-effort)
    try:
        stored = _redis().get(f"oauth:state:{state}")
        if stored is None:
            logger.warning("Google OAuth state token not found in Redis — may have expired")
        else:
            _redis().delete(f"oauth:state:{state}")
    except Exception:
        pass

    redirect_uri = f"{settings.BACKEND_URL}/api/oauth/google/callback"

    # Exchange code for tokens
    try:
        resp = http.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as e:
        logger.error(f"Google token exchange failed: {e}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?google=error")

    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token:
        logger.error(f"No access_token in Google response: {token_data}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?google=error")

    # Fetch connected Google account email
    connected_email = ""
    try:
        userinfo_resp = http.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        connected_email = userinfo_resp.json().get("email", "")
    except Exception as e:
        logger.warning(f"Could not fetch Google user info: {e}")

    save_connection(
        "google",
        access_token,
        refresh_token=refresh_token,
        token_type=token_data.get("token_type", "bearer"),
        scope=token_data.get("scope", ""),
        connected_email=connected_email,
    )

    logger.info(f"Google OAuth connected — account: {connected_email}")
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/ingest?google=connected")


@router.get("/google/status")
def google_status():
    """Return the current Google connection status."""
    conn = get_connection("google")
    if not conn:
        return {"connected": False}
    return {
        "connected":       True,
        "connected_email": conn.connected_email,
        "connected_at":    conn.connected_at.isoformat() if conn.connected_at else None,
    }


@router.delete("/google/disconnect")
def google_disconnect():
    """Remove the Google OAuth connection."""
    delete_connection("google")
    return {"status": "disconnected"}
