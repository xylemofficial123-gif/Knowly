import logging
import time
from typing import Optional, Dict

import requests
from fastapi import Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.core.database import get_db
from app.models import User

logger = logging.getLogger(__name__)
_jwks_clients: Dict[str, tuple[PyJWKClient, float]] = {}
_JWKS_CLIENT_TTL_SEC = 3600


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    return parts[1].strip()


def _clerk_headers() -> dict:
    if not settings.CLERK_SECRET_KEY:
        raise HTTPException(status_code=500, detail="CLERK_SECRET_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    now = time.time()
    cached = _jwks_clients.get(jwks_url)
    if cached and (now - cached[1]) < _JWKS_CLIENT_TTL_SEC:
        return cached[0]
    client = PyJWKClient(jwks_url)
    _jwks_clients[jwks_url] = (client, now)
    return client


def _verify_clerk_token(token: str) -> dict:
    # Path 1: JWT verification via Clerk JWKS (preferred)
    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer = (unverified_claims or {}).get("iss", "").rstrip("/")
        if not issuer:
            raise ValueError("Token missing issuer claim")
        jwks_url = f"{issuer}/.well-known/jwks.json"
        signing_key = _get_jwks_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        if not isinstance(claims, dict) or not claims.get("sub"):
            raise HTTPException(status_code=401, detail="Invalid Clerk token claims")
        return claims
    except Exception as e:
        logger.warning(f"Clerk JWT verification failed, trying API fallback: {e}")

    # Path 2: Clerk token verification API fallback (supports non-JWT token formats)
    verify_paths = ("/v2/token/verify", "/v1/tokens/verify")
    for path in verify_paths:
        try:
            resp = requests.post(
                f"{settings.CLERK_API_BASE}{path}",
                headers=_clerk_headers(),
                json={"token": token},
                timeout=10,
            )
            if resp.status_code >= 400:
                continue
            data = resp.json() if resp.content else {}
            claims = data.get("claims") or data.get("payload") or data
            if isinstance(claims, dict) and claims.get("sub"):
                return claims
        except Exception as e:
            logger.warning(f"Clerk API token verification failed at {path}: {e}")
            continue

    raise HTTPException(status_code=401, detail="Invalid or unverifiable Clerk token")


def _get_clerk_user_email(user_id: str) -> str:
    try:
        resp = requests.get(
            f"{settings.CLERK_API_BASE}/v1/users/{user_id}",
            headers=_clerk_headers(),
            timeout=10,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=401, detail="Unable to fetch Clerk user profile")
        data = resp.json()
        primary_id = data.get("primary_email_address_id", "")
        email_addresses = data.get("email_addresses") or []
        for entry in email_addresses:
            if entry.get("id") == primary_id and entry.get("email_address"):
                return entry["email_address"].strip().lower()
        for entry in email_addresses:
            if entry.get("email_address"):
                return entry["email_address"].strip().lower()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to fetch Clerk user email for {user_id}: {e}")
    raise HTTPException(status_code=401, detail="Unable to resolve user email from Clerk token")


def get_current_user_email(authorization: Optional[str] = Header(default=None)) -> str:
    token = _extract_bearer_token(authorization)
    claims = _verify_clerk_token(token)
    user_id = claims.get("sub", "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid Clerk token claims")
    return _get_clerk_user_email(user_id)


def require_admin(
    current_email: str = Depends(get_current_user_email),
    db: Session = Depends(get_db),
) -> str:
    user = db.query(User).filter(func.lower(User.email) == current_email).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_email
