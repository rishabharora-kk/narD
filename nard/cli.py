"""Offline synthetic demo and one-shot observation cycle."""
import argparse
import json
from datetime import timedelta
from sqlalchemy import select
from nard.config import Source
from nard.engine import ingest
from nard.forecast import create_prediction
from nard.store import Event,Insight,make_session_factory,utcnow

def demo():
    factory=make_session_factory()
    examples=[
        ("sample_patent","patent",b"<html><title>Inventor</title><body>Battery recycling cathode recovery technology patent filed.</body></html>"),
        ("sample_grant","grant",b"<html><title>Funding</title><body>New battery recycling demonstration grants announced.</body></html>"),
        ("sample_tender","procurement",b"<html><title>Request</title><body>Public procurement tender for battery recycling equipment.</body></html>"),
    ]
    summaries=[]
    now=utcnow()
    with factory() as session:
        for sid,family,body in examples:
            src=Source(id=sid,family=family,url=f"https://example.org/{sid}",themes=["battery recycling"])
            result=ingest(session,src,body,"text/html",at=now)
            summaries.append({"source":sid,"events":result.events,"join_candidates":result.joins,
                "duplicate":result.duplicate})
        events=session.scalars(select(Event).where(Event.theme=="battery recycling")).all()
        commitment=None
        if events:
            pred=create_prediction(session,question="DEMO ONLY: Will a fourth family mention battery recycling?",
                resolution_rule="DEMO ONLY: fourth independent source family mentions phrase within 90 days",
                probability=0.5,deadline=now+timedelta(days=90),
                evidence_event_ids=[e.id for e in events],at=now)
            commitment=pred.commitment
        total=len(session.scalars(select(Insight)).all())
    print(json.dumps({"synthetic_demo":True,"sources":summaries,
        "total_join_candidates":total,"sample_prediction_commitment":commitment},indent=2))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["demo","once"])
    args=parser.parse_args()
    if args.command=="demo": demo()
    else:
        from nard.worker import run_once
        print(json.dumps(run_once(),indent=2))

if __name__=="__main__": main()
