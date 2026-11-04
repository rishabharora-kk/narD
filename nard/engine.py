"""Cheap deterministic triage and bounded candidate joins; never claim causality."""
import hashlib
import re
from datetime import timedelta
from bs4 import BeautifulSoup
from sqlalchemy import select
from nard.store import Observation,Event,Insight,put_blob,utcnow

class IngestResult:
    def __init__(self,observation_id,events,joins,duplicate):
        self.observation_id,self.events,self.joins,self.duplicate=observation_id,events,joins,duplicate

def uid(value): return hashlib.sha256(value.encode("utf-8")).hexdigest()

def textify(body,content_type):
    decoded=body.decode("utf-8",errors="replace")
    if content_type=="text/html":
        soup=BeautifulSoup(decoded,"html.parser")
        for tag in soup(["script","style","noscript","svg","footer","nav"]): tag.decompose()
        title=soup.title.get_text(" ",strip=True) if soup.title else ""
        content=soup.get_text(" ",strip=True)
    else: title,content="",decoded
    return title[:500],re.sub(r"\s+"," ",content).strip()[:100_000]

def themes_in(text,themes):
    return sorted({t.casefold() for t in themes if re.search(r"(?<!\w)"+re.escape(t.casefold())+r"(?!\w)",text.casefold())})

def ingest(session,source,body,content_type,*,blob_root=None,at=None):
    if content_type not in ("text/html","text/plain","application/xml","text/xml","application/rss+xml","application/atom+xml","application/json"):
        raise ValueError("Unsupported evidence format")
    at=at or utcnow()
    sha=hashlib.sha256(body).hexdigest()
    oid=uid(source.id+":"+sha)
    if session.get(Observation,oid): return IngestResult(oid,0,0,True)
    title,content=textify(body,content_type)
    path=put_blob(body,sha,blob_root)
    session.add(Observation(id=oid,source_id=source.id,source_family=source.family,
        source_url=source.url,fetched_at=at,first_seen_at=at,content_hash=sha,
        raw_path=path,content_type=content_type,title=title,text_excerpt=content[:3000]))
    session.flush()
    count=joined=0
    for theme in themes_in(content,source.themes):
        eid=uid(oid+":"+theme)
        session.add(Event(id=eid,observation_id=oid,source_id=source.id,
            source_family=source.family,theme=theme,detected_at=at,excerpt=content[:1000]))
        count+=1
        previous=session.scalars(select(Event).where(Event.theme==theme,
            Event.source_family!=source.family,
            Event.detected_at>=at-timedelta(days=90),
            Event.detected_at<=at).order_by(Event.detected_at.desc()).limit(20)).all()
        for old in previous:
            pair=sorted([eid,old.id])
            iid=uid("|".join([theme]+pair))
            if not session.get(Insight,iid):
                session.add(Insight(id=iid,theme=theme,evidence_event_ids=pair,
                    source_families=sorted([source.family,old.source_family]),
                    created_at=at,score=0.5,status="candidate"))
                joined+=1
    session.commit()
    return IngestResult(oid,count,joined,False)
