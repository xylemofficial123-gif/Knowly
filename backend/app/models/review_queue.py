from sqlalchemy import Column, String, Text, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from app.models import Base
import uuid
import datetime


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_text = Column(Text)
    proposed_decision = Column(Text)
    proposed_rationale = Column(Text)
    confidence = Column(Float)
    decision_type = Column(String)
    trigger_phrase = Column(String)
    source_chunk_id = Column(String)
    source_url = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
