from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nard import api
from nard.config import Source
from nard.engine import ingest
from nard.store import Base, Insight


def test_review_queue_is_admin_only_and_append_only(tmp_path, monkeypatch):
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api, "factory", lambda: factory)
    monkeypatch.setenv("NARD_ADMIN_TOKEN", "review-test-token")
    with factory() as session:
        ingest(session, Source(id="patent_sample", family="patent", url="https://example.org/a",
            themes=["drone"]), b"Drone research", "text/plain", blob_root=tmp_path)
        ingest(session, Source(id="grant_sample", family="grant", url="https://example.org/b",
            themes=["drone"]), b"Drone funding", "text/plain", blob_root=tmp_path)
        insight = session.query(Insight).first()
        assert insight is not None
        insight_id = insight.id
    client = TestClient(api.app)
    path = f"/insights/{insight_id}/reviews"
    payload = {"verdict": "needs_evidence", "rationale": "Only thematic overlap; no identifiers",
               "reviewer": "human-reviewer"}
    assert client.post(path, json=payload).status_code == 401
    assert client.post(path, json=payload, headers={
        "Authorization": "Bearer review-test-token"}).status_code == 200
    response = client.get("/reviews")
    assert response.status_code == 200
    assert response.json()[0]["rationale"] == payload["rationale"]
    payload["verdict"] = "rejected"
    assert client.post(path, json=payload, headers={
        "Authorization": "Bearer review-test-token"}).status_code == 200
    assert len(client.get("/reviews").json()) == 2
    assert client.post("/insights/unknown/reviews", json=payload, headers={
        "Authorization": "Bearer review-test-token"}).status_code == 404
