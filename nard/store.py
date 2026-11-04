"""Evidence-first relational ledger with content-addressed raw snapshots."""
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def utcnow(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass

class Observation(Base):
    __tablename__="observations"
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    source_id:Mapped[str]=mapped_column(String(100),index=True)
    source_family:Mapped[str]=mapped_column(String(100),index=True)
    source_url:Mapped[str]=mapped_column(Text)
    fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    first_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    content_hash:Mapped[str]=mapped_column(String(64))
    raw_path:Mapped[str]=mapped_column(Text)
    content_type:Mapped[str]=mapped_column(String(100))
    title:Mapped[str]=mapped_column(Text)
    text_excerpt:Mapped[str]=mapped_column(Text)
    __table_args__=(UniqueConstraint("source_id","content_hash"),)

class Event(Base):
    __tablename__="events"
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    observation_id:Mapped[str]=mapped_column(ForeignKey("observations.id"),index=True)
    source_id:Mapped[str]=mapped_column(String(100))
    source_family:Mapped[str]=mapped_column(String(100))
    theme:Mapped[str]=mapped_column(String(120),index=True)
    detected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    excerpt:Mapped[str]=mapped_column(Text)

class Insight(Base):
    __tablename__="insights"
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    theme:Mapped[str]=mapped_column(String(120),index=True)
    evidence_event_ids:Mapped[list[str]]=mapped_column(JSON)
    source_families:Mapped[list[str]]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    score:Mapped[float]=mapped_column(Float)
    status:Mapped[str]=mapped_column(String(30),default="candidate")

class Prediction(Base):
    __tablename__="predictions"
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    question:Mapped[str]=mapped_column(Text)
    resolution_rule:Mapped[str]=mapped_column(Text)
    probability:Mapped[float]=mapped_column(Float)
    evidence_event_ids:Mapped[list[str]]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    deadline:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    commitment:Mapped[str]=mapped_column(String(64),unique=True)
    salt:Mapped[str]=mapped_column(String(64))
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    outcome:Mapped[int|None]=mapped_column(Integer,nullable=True)
    brier:Mapped[float|None]=mapped_column(Float,nullable=True)

def make_session_factory(url=None):
    url=url or os.getenv("NARD_DATABASE_URL","sqlite:///./nard.db")
    engine=create_engine(url,connect_args={"check_same_thread":False} if url.startswith("sqlite") else {},pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine,expire_on_commit=False)

def put_blob(data,sha,root=None):
    root=Path(root or os.getenv("NARD_DATA_DIR","./data"))/"blobs"/sha[:2]
    root.mkdir(parents=True,exist_ok=True)
    path=root/sha
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=root,delete=False) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            tmp=Path(f.name)
        try:
            if not path.exists(): os.replace(tmp,path)
        finally: tmp.unlink(missing_ok=True)
    return str(path)
