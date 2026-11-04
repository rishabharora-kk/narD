"""Observer plane: isolated from Internet, only reaches its gateway and database."""
import json
import logging
import os
import time
import httpx
from nard.config import approved,load_registry
from nard.engine import ingest
from nard.store import make_session_factory

log=logging.getLogger("nard.observer")

def run_once(session_factory=None,client=None):
    factory=session_factory or make_session_factory()
    gateway=os.getenv("NARD_GATEWAY_URL","http://gateway:8081").rstrip("/")
    if not (gateway.startswith("http://gateway:") or gateway.startswith("http://127.0.0.1:")):
        raise RuntimeError("Observer gateway must be isolated/local")
    owns_client=client is None
    client=client or httpx.Client(timeout=30,trust_env=False,follow_redirects=False)
    results=[]
    try:
        for source in load_registry().sources:
            if not approved(source): continue
            try:
                response=client.get(gateway+"/v1/fetch/"+source.id)
                response.raise_for_status()
                content_type=response.headers.get("content-type","").split(";",1)[0].lower()
                with factory() as session:
                    result=ingest(session,source,response.content,content_type)
                results.append({"source":source.id,"observation":result.observation_id,
                    "events":result.events,"join_candidates":result.joins,"duplicate":result.duplicate})
            except (httpx.HTTPError,ValueError) as exc:
                log.warning("Source %s skipped: %s",source.id,type(exc).__name__)
                results.append({"source":source.id,"error":type(exc).__name__})
    finally:
        if owns_client: client.close()
    return results

def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        log.info("Observation cycle: %s",json.dumps(run_once()))
        time.sleep(int(os.getenv("NARD_RUN_INTERVAL","3600")))

if __name__=="__main__": main()
