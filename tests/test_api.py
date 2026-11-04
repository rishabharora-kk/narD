from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,pool
from sqlalchemy.orm import sessionmaker
from nard import api
from nard.config import Source
from nard.engine import ingest
from nard.store import Base,utcnow

def test_api_admin_required_and_prediction_commitment(tmp_path,monkeypatch):
    engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},
        poolclass=pool.StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(api,"factory",lambda:factory)
    monkeypatch.setenv("NARD_ADMIN_TOKEN","test-only-token")
    with factory() as session:
        ingest(session,Source(id="patent_x",family="patent",url="https://example.org/a",themes=["drone"]),
            b"Drone technology","text/plain",blob_root=tmp_path)
    client=TestClient(api.app)
    events=client.get("/events").json()
    assert len(events)==1
    body={"question":"Will procurement emerge for this drone technology?",
        "resolution_rule":"Yes iff official drone procurement tender appears",
        "probability":0.4,"deadline":(utcnow()+timedelta(days=30)).isoformat(),
        "evidence_event_ids":[events[0]["id"]]}
    assert client.post("/predictions",json=body).status_code==401
    created=client.post("/predictions",headers={"Authorization":"Bearer test-only-token"},json=body)
    assert created.status_code==200
    prediction=created.json()
    assert "salt" not in prediction and "payload" not in prediction
    response=client.post(f"/predictions/{prediction['id']}/resolve",json={"outcome":1},
        headers={"Authorization":"Bearer test-only-token"})
    assert response.status_code==200
    assert response.json()["verified"] is True
