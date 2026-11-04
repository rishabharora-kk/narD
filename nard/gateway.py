"""Private read-only fetch gateway, accessible only from isolated observer network."""
import threading
import time
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from nard.config import approved, load_registry
from nard.security import FetchDenied, pinned_get, robots_allowed

app=FastAPI(title="narD private fetch gateway",docs_url=None,redoc_url=None,openapi_url=None)
_lock=threading.Lock()
_last_attempt={}

@app.get("/health")
def health(): return {"status":"ok","plane":"fetch-only"}

@app.get("/v1/fetch/{source_id}")
def fetch_source(source_id:str):
    try: source=load_registry().get(source_id)
    except (KeyError,ValueError,OSError) as exc: raise HTTPException(404,"Unknown source") from exc
    if not approved(source): raise HTTPException(403,"Source lacks explicit access-policy approval")
    host=urlsplit(source.url).hostname
    now=time.monotonic()
    with _lock:
        if now-_last_attempt.get(host,-1e12)<source.poll_seconds:
            raise HTTPException(429,"Per-host fetch cooldown")
        _last_attempt[host]=now
    if not robots_allowed(source.url,host):
        raise HTTPException(403,"Disallowed by robots or unable to verify robots")
    try: result=pinned_get(source.url,host)
    except (FetchDenied,OSError,TimeoutError,ValueError) as exc:
        raise HTTPException(502,"Fetch unavailable; check gateway logs") from exc
    return Response(content=result.body,media_type=result.content_type,
        headers={"X-narD-Source-Id":source.id,"Cache-Control":"no-store"})
