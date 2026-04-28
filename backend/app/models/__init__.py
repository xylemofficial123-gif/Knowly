from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False)
    source_id = Column(String, unique=True)
    title = Column(String)
    content = Column(Text)
    url = Column(String)
    acl = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    freshness_score = Column(Float, default=1.0)
    # Version awareness: draft | in_review | finalized | unknown
    doc_status = Column(String, default="unknown")


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    text = Column(Text)
    chunk_index = Column(String)
    embedding_id = Column(String)
    acl = Column(JSON, default=list)
    source_url = Column(String)
    slack_user_id = Column(String)
    # context optimization: summary, decision, action_item, full_text
    chunk_type = Column(String, default="full_text")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class DecisionRecord(Base):
    __tablename__ = "decision_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision = Column(Text)
    rationale = Column(Text)
    options_considered = Column(JSON, default=list)
    status = Column(String, default="active")  # active, superseded
    source_chunk_ids = Column(JSON, default=list)
    participants = Column(JSON, default=list)  # emails (preferred) — legacy rows may hold Slack user IDs
    # ACL list using the same format as Document/Chunk (public | group:<id> | user:<email> | <email>).
    # Empty list means public for backward-compat with rows written before this column existed.
    acl = Column(JSON, default=list)
    decided_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    # Decision reversal tracking
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("decision_records.id"), nullable=True)
    superseded_at = Column(DateTime, nullable=True)
    reversal_reason = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_email = Column(String)
    query = Column(Text)
    chunks_returned = Column(String)
    result_count = Column(String)
    agent = Column(String)
    query_type = Column(String)
    confidence = Column(Float)
    response_time_ms = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class AnswerFeedback(Base):
    __tablename__ = "answer_feedback"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_log_id = Column(UUID(as_uuid=True), ForeignKey("audit_log.id"), nullable=True)
    session_id = Column(String)
    user_email = Column(String)
    query = Column(Text)
    rating = Column(String)  # "helpful" or "not_helpful"
    comment = Column(Text, nullable=True)
    agent = Column(String)
    query_type = Column(String)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class GlobalSettings(Base):
    __tablename__ = "global_settings"
    id = Column(String, primary_key=True, default="default")
    # List of enabled sources, e.g., ["drive", "calendar", "slack", "meet", "clickup"]
    enabled_sources = Column(JSON, default=list)
    # Target Google Drive folder IDs
    google_drive_folder_ids = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ── Three-Tier Access Control Models ──────────────────────────────────────────

class User(Base):
    """Registered user with a role in the three-tier system."""
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    # admin | group_admin | member
    role = Column(String, default="member", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Group(Base):
    """A team or department group whose members share documents."""
    __tablename__ = "groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class GroupMembership(Base):
    """Maps a user to a group with an optional group-admin role."""
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("user_email", "group_id", name="uq_group_member"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_email = Column(String, nullable=False, index=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    # group_admin | member
    role = Column(String, default="member", nullable=False)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)


class OAuthConnection(Base):
    """Stores OAuth tokens for third-party integrations (ClickUp, Slack, Google, etc.)."""
    __tablename__ = "oauth_connections"
    id             = Column(String, primary_key=True)   # "clickup" | "slack" | "google"
    access_token   = Column(Text, nullable=False)
    refresh_token  = Column(Text, nullable=True)        # Google (and future providers) refresh token
    token_type     = Column(String, default="bearer")
    scope          = Column(Text, nullable=True)
    team_id        = Column(String, nullable=True)       # ClickUp workspace/team ID
    workspace_name = Column(String, nullable=True)
    bot_user_id    = Column(String, nullable=True)       # Slack bot user ID
    workspace_id   = Column(String, nullable=True)       # Slack workspace ID
    connected_email = Column(String, nullable=True)      # Google account email
    connected_by   = Column(String, nullable=True)
    connected_at   = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ExclusionRule(Base):
    """No-index zones: mark specific sources/channels/folders as excluded from ingestion."""
    __tablename__ = "exclusion_rules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # drive | slack | clickup
    source_type = Column(String, nullable=False)
    # Channel ID, folder ID, space ID, etc.
    identifier = Column(String, nullable=False)
    # Human-readable name (e.g., "#hr-private", "Salary Docs")
    name = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (UniqueConstraint("source_type", "identifier", name="uq_exclusion_rule"),)


class GuardianAlert(Base):
    """Log of every Guardian Agent check that produced a match."""
    __tablename__ = "guardian_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Where the trigger came from: slack | clickup | drive | manual
    trigger_source = Column(String, nullable=False)
    # Unique ID of the triggering content, e.g. "slack:C123:1234567890.123"
    source_id = Column(String, nullable=True, index=True)
    source_url = Column(String, nullable=True)
    user_email = Column(String, nullable=False, index=True)
    # First 500 chars of the text that triggered the check
    text_snippet = Column(Text, nullable=True)
    match_count = Column(String, default="0")
    highest_score = Column(Float, default=0.0)
    # pending | sent | failed | suppressed (below threshold / too short)
    alert_status = Column(String, default="pending")
    matches_json = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
