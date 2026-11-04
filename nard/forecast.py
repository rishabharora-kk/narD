"""Salted prediction commitments; external timestamps required for public proof."""
import hashlib
import hmac
import json
import secrets
from datetime import timezone
from uuid import uuid4
from nard.store import Prediction,utcnow

def iso(dt):
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def payload(row):
    return {"id":row.id,"question":row.question,"resolution_rule":row.resolution_rule,
        "probability":row.probability,"evidence_event_ids":sorted(row.evidence_event_ids),
        "created_at":iso(row.created_at),"deadline":iso(row.deadline)}

def canonical_bytes(data):
    return json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def compute_commitment(data,salt):
    return hashlib.sha256(bytes.fromhex(salt)+canonical_bytes(data)).hexdigest()

def create_prediction(session,*,question,resolution_rule,probability,deadline,evidence_event_ids,at=None):
    at=at or utcnow()
    if not 0<=probability<=1 or not question.strip() or not resolution_rule.strip():
        raise ValueError("Nonempty question/rule and probability in [0,1] required")
    if not at.tzinfo or not deadline.tzinfo or deadline<=at:
        raise ValueError("Timezone-aware future deadline required")
    row=Prediction(id=str(uuid4()),question=question,resolution_rule=resolution_rule,
        probability=probability,deadline=deadline,evidence_event_ids=sorted(set(evidence_event_ids)),
        created_at=at,salt=secrets.token_hex(32),commitment="")
    row.commitment=compute_commitment(payload(row),row.salt)
    session.add(row)
    session.commit()
    return row

def resolve_prediction(session,row,outcome,*,at=None):
    if outcome not in (0,1): raise ValueError("Binary outcome required")
    if row.resolved_at is not None: raise ValueError("Already resolved")
    row.outcome=outcome
    row.resolved_at=at or utcnow()
    row.brier=(row.probability-outcome)**2
    session.commit()
    return row

def verify(row): return hmac.compare_digest(compute_commitment(payload(row),row.salt),row.commitment)
