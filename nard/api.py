"""Isolated human hand-off API: evidence and falsifiable forecast records only."""
import hmac
import os
from functools import lru_cache
from datetime import datetime
from fastapi import Depends,FastAPI,Header,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from nard.forecast import create_prediction,payload,resolve_prediction,verify
from nard.store import Event,Insight,Prediction,make_session_factory

app=FastAPI(title="narD evidence & forecasts",version="0.1.0")

@lru_cache(maxsize=1)
def factory(): return make_session_factory()

def require_admin(authorization:str|None=Header(default=None)):
    expected=os.getenv("NARD_ADMIN_TOKEN")
    if not expected or not authorization or not hmac.compare_digest(authorization,"Bearer "+expected):
        raise HTTPException(401,"Admin token required for state changes")

class ForecastIn(BaseModel):
    question:str=Field(min_length=10)
    resolution_rule:str=Field(min_length=10)
    probability:float=Field(ge=0,le=1)
    deadline:datetime
    evidence_event_ids:list[str]=Field(min_length=1)

class OutcomeIn(BaseModel):
    outcome:int=Field(ge=0,le=1)

@app.get("/health")
def health(): return {"status":"ok","plane":"handoff-only"}

@app.get("/events")
def events(limit:int=50):
    with factory()() as session:
        rows=session.scalars(select(Event).order_by(Event.detected_at.desc()).limit(min(max(limit,1),200))).all()
        return [{"id":e.id,"theme":e.theme,"source_id":e.source_id,"family":e.source_family,
            "detected_at":e.detected_at,"excerpt":e.excerpt[:300]} for e in rows]

@app.get("/insights")
def insights(limit:int=50):
    with factory()() as session:
        rows=session.scalars(select(Insight).order_by(Insight.created_at.desc()).limit(min(max(limit,1),200))).all()
        return [{"id":i.id,"theme":i.theme,"evidence_event_ids":i.evidence_event_ids,
            "source_families":i.source_families,"created_at":i.created_at,
            "score":i.score,"status":i.status} for i in rows]

def prediction_public(p):
    record={"id":p.id,"commitment":p.commitment,"created_at":p.created_at,
        "deadline":p.deadline,"resolved":p.resolved_at is not None}
    if p.resolved_at is not None:
        record.update({"payload":payload(p),"salt":p.salt,"outcome":p.outcome,
            "brier":p.brier,"verified":verify(p),"resolved_at":p.resolved_at})
    return record

@app.get("/predictions")
def predictions():
    with factory()() as session:
        rows=session.scalars(select(Prediction).order_by(Prediction.created_at.desc()).limit(200)).all()
        return [prediction_public(p) for p in rows]

@app.post("/predictions",dependencies=[Depends(require_admin)])
def add_prediction(body:ForecastIn):
    with factory()() as session:
        known={e.id for e in session.scalars(select(Event).where(Event.id.in_(body.evidence_event_ids)))}
        if len(known)!=len(set(body.evidence_event_ids)):
            raise HTTPException(422,"All evidence ids must refer to stored events")
        try: p=create_prediction(session,**body.model_dump())
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        return prediction_public(p)

@app.post("/predictions/{prediction_id}/resolve",dependencies=[Depends(require_admin)])
def resolve(prediction_id:str,body:OutcomeIn):
    with factory()() as session:
        p=session.get(Prediction,prediction_id)
        if p is None: raise HTTPException(404,"Unknown prediction")
        try: resolve_prediction(session,p,body.outcome)
        except ValueError as exc: raise HTTPException(409,str(exc)) from exc
        return prediction_public(p)


class ReviewIn(BaseModel):
    verdict: str = Field(pattern="^(accepted|rejected|needs_evidence)$")
    rationale: str = Field(min_length=15, max_length=2000)
    reviewer: str = Field(min_length=3, max_length=100)


@app.get("/reviews")
def reviews(limit: int = 50):
    """Review history is delivered only; observer processes cannot post decisions."""
    with factory()() as session:
        rows = session.scalars(select(ReviewDecision).order_by(
            ReviewDecision.decided_at.desc()).limit(min(max(limit, 1), 200))).all()
        return [
            {"id": r.id, "insight_id": r.insight_id, "verdict": r.verdict,
             "rationale": r.rationale, "reviewer": r.reviewer, "decided_at": r.decided_at}
            for r in rows
        ]


@app.post("/insights/{insight_id}/reviews", dependencies=[Depends(require_admin)])
def review_insight(insight_id: str, body: ReviewIn):
    """Human-only handoff; no external alerts, messages, trades or automated actions."""
    from uuid import uuid4

    with factory()() as session:
        candidate = session.get(Insight, insight_id)
        if candidate is None:
            raise HTTPException(404, "Unknown insight")
        row = ReviewDecision(
            id=str(uuid4()), insight_id=insight_id, verdict=body.verdict,
            rationale=body.rationale, reviewer=body.reviewer
        )
        session.add(row)
        session.commit()
        return {"review_id": row.id, "insight_id": insight_id, "verdict": body.verdict}
