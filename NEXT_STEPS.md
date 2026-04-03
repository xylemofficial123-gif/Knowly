# Next Steps — Xylem Intelligence

## 1. Per-User Google OAuth ✅ DONE (2026-04-03)

Replace the single shared `google_token.json` with per-user OAuth connections,
same pattern as ClickUp OAuth already built.

### Backend
- Add `GET /api/oauth/google/authorize` — returns Google OAuth URL
  - Scopes needed: `drive.readonly`, `calendar.readonly`, `https://www.googleapis.com/auth/drive.metadata.readonly`
  - State token stored in Redis for CSRF
- Add `GET /api/oauth/google/callback` — exchanges code, saves to `OAuthConnection` table
  - Provider id: `"google:<user_email>"` or just `"google"` for single-user
  - Store: access_token, refresh_token (Google gives refresh tokens), connected_email
- Add `GET /api/oauth/google/status` — returns connected email + status
- Add `DELETE /api/oauth/google/disconnect` — removes token from DB
- Update `backend/app/services/drive_ingestion.py` — read token from `OAuthConnection` via `token_store.get_connection("google")` instead of `google_token.json`
- Update `backend/app/services/meet_ingestion.py` — same
- Update `backend/app/services/calendar_sync.py` — same
- Update `backend/app/core/config.py` — keep GOOGLE_CLIENT_ID/SECRET (same app), remove reliance on GOOGLE_TOKEN_JSON env var
- Key difference from ClickUp: Google gives a refresh_token — must handle token refresh automatically

### Frontend
- Add Google card to Connections tab (`frontend/app/ingest/page.tsx`) alongside ClickUp card
- Shows connected email, connected date, disconnect button
- "Connect Google" button → calls authorize endpoint → redirects to Google

### Notes
- `google_token.json` file becomes obsolete — token lives in DB
- `GOOGLE_TOKEN_JSON` Railway env var can be removed after migration
- Redirect URI: `https://backend-api-production-148e.up.railway.app/api/oauth/google/callback`
- Frontend URL: `https://xylem-memory.vercel.app`
- Google OAuth requires `access_type=offline` and `prompt=consent` to get refresh_token

---

## 2. Git Cleanup (quick — do before or after Google OAuth)

- Delete stale local branch: `git branch -d feature/ingestion-toggles`
- Delete stale remote branch: `git push origin --delete feature/ingestion-toggles`
- Delete stale remote branch: `git push origin --delete ui/frontend-redesign`
- Add `frontend/tsconfig.tsbuildinfo` to `.gitignore`

---

## 3. Identity Mapping / Email Alias System (after Google OAuth)

When a user's Xylem login email differs from their ClickUp/Slack/Google email,
they get blocked by ACL. Need a `UserIdentity` table mapping primary email → aliases.

- `UserIdentity` model: `primary_email`, `provider` (clickup/slack/google), `external_email`
- Update `user_can_see_chunk()` in `acl.py` to fetch all aliases before checking ACL
- Admin UI: simple form to link "my ClickUp email is X"

---

## 2. Register Google OAuth Redirect URI in Google Cloud Console (NEXT — do this now)

Before the Google OAuth flow can work, you must add the callback URL to your Google Cloud project:

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Click on your OAuth 2.0 Client ID (the one with `GOOGLE_CLIENT_ID`)
3. Under "Authorized redirect URIs", add:
   `https://backend-api-production-148e.up.railway.app/api/oauth/google/callback`
4. Save
5. Go to "OAuth consent screen" → Scopes → add:
   - `https://www.googleapis.com/auth/drive.readonly`
   - `https://www.googleapis.com/auth/calendar.readonly`
   - `openid`, `email`
6. Test: Click "Connect Google" on the Connections tab → log in with excylem@gmail.com

---

## 4. Re-authenticate Google Drive with excylem@gmail.com (for testing)

Until Google OAuth is built, do this manually:
1. `rm backend/google_token.json`
2. Run drive service to trigger OAuth browser flow → log in with `excylem@gmail.com`
3. Copy new `google_token.json` contents → update `GOOGLE_TOKEN_JSON` on Railway
4. Re-run Drive backfill

---

## Context

- Backend URL: `https://backend-api-production-148e.up.railway.app`
- Frontend URL: `https://xylem-memory.vercel.app`
- ClickUp OAuth: already built in `backend/app/api/oauth.py` — use as template for Google
- `OAuthConnection` model: already exists in `backend/app/models/__init__.py`
- `token_store.py`: already exists in `backend/app/core/token_store.py`
- Google Client ID/Secret: already in Railway env as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
- Current Google token: `google_token.json` locally + `GOOGLE_TOKEN_JSON` on Railway (sachin.kurup@seedlinglabs.com)
- Testing account: `excylem@gmail.com`
- Production account: `sachin.kurup@seedlinglabs.com`
