from datetime import timedelta
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from nard.config import Source
from nard.engine import ingest
from nard.forecast import create_prediction,resolve_prediction,verify
from nard.store import Base,Event,Insight,Observation,utcnow

def test_ingest_is_idempotent_and_joins_distinct_families(tmp_path):
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    a=Source(id="patent_a",family="patent",url="https://example.org/a",themes=["battery"])
    b=Source(id="grant_b",family="grant",url="https://example.org/b",themes=["battery"])
    c=Source(id="patent_c",family="patent",url="https://example.org/c",themes=["battery"])
    at=utcnow()
    with Session(engine) as session:
        first=ingest(session,a,b"<html><title>A</title><script>battery</script>Battery invention</html>",
            "text/html",blob_root=tmp_path,at=at)
        same=ingest(session,a,b"<html><title>A</title><script>battery</script>Battery invention</html>",
            "text/html",blob_root=tmp_path,at=at)
        third=ingest(session,c,b"<html>Battery novel invention</html>","text/html",blob_root=tmp_path,at=at)
        second=ingest(session,b,b"<html><h1>Battery pilot funding</h1></html>","text/html",blob_root=tmp_path,at=at)
        assert first.events==1 and first.joins==0
        assert same.duplicate and same.events==0
        assert third.events==1 and third.joins==0
        assert second.events==1 and second.joins==2
        assert len(session.scalars(select(Observation)).all())==3
        assert len(session.scalars(select(Insight)).all())==2
        event_ids=[e.id for e in session.scalars(select(Event)).all()]
        p=create_prediction(session,question="Will an independent source report battery funding?",
            resolution_rule="Resolve yes if an official procurement notice appears by deadline",
            probability=0.35,evidence_event_ids=event_ids,
            deadline=at+timedelta(days=30),at=at)
        assert verify(p)
        commitment=p.commitment
        resolve_prediction(session,p,1,at=at+timedelta(days=2))
        assert p.brier==(0.35-1)**2 and verify(p) and p.commitment==commitment

def test_old_events_cannot_be_joined(tmp_path):
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    a=Source(id="patent_x",family="patent",url="https://example.org/a",themes=["drone"])
    b=Source(id="grant_x",family="grant",url="https://example.org/b",themes=["drone"])
    at=utcnow()
    with Session(engine) as session:
        ingest(session,a,b"Drone systems","text/plain",blob_root=tmp_path,at=at-timedelta(days=100))
        result=ingest(session,b,b"Drone research","text/plain",blob_root=tmp_path,at=at)
        assert result.joins==0
