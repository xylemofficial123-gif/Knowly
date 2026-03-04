from sqlalchemy import Column, String, Text, DateTime, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid, datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False)   # 'slack','notion','drive','zoom'
    source_id = Column(String, unique=True)   # original ID in source system
    title = Column(String)
    content = Column(Text)
    url = Column(String)
    acl = Column(JSON, default=list)           # list of user/group IDs allowed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    freshness_score = Column(Float, default=1.0)

class Chunk(Base):
    __tablename__ = 'chunks'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'))
    text = Column(Text)
    chunk_index = Column(String)
    embedding_id = Column(String)              # ID in Qdrant
    acl = Column(JSON, default=list)
    source_url = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DecisionRecord(Base):
    __tablename__ = 'decision_records'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision = Column(Text)
    rationale = Column(Text)
    options_considered = Column(JSON, default=list)
    status = Column(String, default='active')  # active, reversed, superseded
    source_chunk_ids = Column(JSON, default=list)
    participants = Column(JSON, default=list)
    decided_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)