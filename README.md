# narD — evidence-first read-only observer

**Status: Phase 0 prototype, not production-ready.** Observe public permitted pages → retain source evidence → flag themes → find bounded cross-source candidates → human review → precommit falsifiable predictions. Observers never trade, send messages, submit forms, purchase or publish.

The system runs on Python, FastAPI, SQLAlchemy (SQLite for offline tests; PostgreSQL in Docker), a cheap deterministic keyword filter, source-family joins, and human-managed forecasts. There are no paid LLM calls.

## Run locally (offline, no scraping)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
python -m nard.cli demo
uvicorn nard.api:app --reload
```

The demo creates **synthetic** patent, grant and tender snippets mentioning battery recycling. It creates three join candidates plus a clearly labeled synthetic forecast, **not proof of an actual predictive edge**. Inspect endpoints at `http://127.0.0.1:8000/docs`.

## Production-like isolated stack

```bash
mkdir -p data && sudo chown 10001:10001 data
export NARD_DB_PASSWORD='generate-a-unique-secret'
export NARD_ADMIN_TOKEN='generate-a-different-unique-secret'
docker compose -f infra/docker-compose.yml up --build
```

All registry entries in [sources.json](sources.json) are disabled by default. **Before activating one**, verify that the exact source is public, the publisher's terms permit this automation, the site provides extractable text or a legitimate API, the source's robots policy allows it and the request budget is acceptable. Then explicitly set `enabled=true` and `terms_reviewed=true`. These are *candidate URLs*, not tested or contractually licensed live connectors.

The isolated observer can access only its private fetch gateway and database through internal Docker networks. Its gateway alone has WAN connectivity. The gateway accepts only registry IDs, uses HTTPS GET only, validates DNS against non-public addresses, pins DNS to connection IP with verified TLS identity, rejects redirects, enforces rate limits, MIME/size limits, and checks robots.txt conservatively. The hand-off API has no WAN network and is loopback-bound at `127.0.0.1:8000`. Prediction mutation endpoints require an admin bearer token.

```
Permitted official sources ← HTTPS GET gateway [WAN]
                                   ↑
                        internal observer network
                                   ↑
                          Observer worker ── PostgreSQL
                                               ↑
                                  internal API network
                                               ↑
                                 Human-only handoff API
```

A web GET is not literally passive ([RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html)): it creates server logs, can trigger badly designed endpoints, and may encounter tracking. Host-level outbound firewall rules and deployment-specific network audits remain necessary. The gateway itself has outbound WAN access, so **total zero-world-effect cannot be guaranteed**. Docker Compose isolation is a proposed boundary to test, not a formally verified capability security proof. No CAPTCHA circumvention is implemented.

## Data and semantics

- `Observation`: immutable-by-hash raw byte snapshot on disk, source URL, first observed time and metadata. Database owners can still edit rows: this is not a cryptographically immutable audit service.
- `Event`: deterministic theme mention with event/observation IDs. A theme match is not independently verified evidence.
- `Insight`: candidate pair with different source-family labels, same theme and at most a 90-day gap. Bound the join to 20 earlier matching events per new event. Provenance **must be reviewed**; different sites can syndicate the same source.
- `Prediction`: human-authored question, explicit resolution rule, evidence IDs, probability and deadline. Hides content/salt until resolution. A salted SHA-256 commitment detects tampering **only if independently timestamped**. On resolution, Brier = (probability − outcome)².

No automatic external insight dispatch, live trading, paid API calls or agent tool actions.

## Non-goals and next milestones

1. Source-by-source approvals, robots and page semantics review. Replace generic portal landing pages with stable permitted feeds/APIs.
2. Build durable scheduler, per-source connectors and operational telemetry.
3. Add patent/tender PDF extraction in a tightly sandboxed parser, plus canonical identifiers (application/publication number, tender ID, company CIN).
4. Replace keyword joins with entity + timeline joins and source lineage checks; measure precision, cost per true catch, false positives and lead time.
5. Build point-in-time backtest and independently timestamp commitments. Never label backfilled discoveries as live forecasts.
6. Evaluate retrieval, then add budgeted small-model triage and frontier-model analysis only after baselines and monitoring.
7. Harden database access with distinct read/write roles and migrations, egress firewall, gateway rate limiting across workers, and audited deployment controls.

See [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) on robots rules and [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) on untrusted content/prompt injection.

## Layout

```text
nard/
  config.py      approved source registry
  security.py    HTTPS GET transport / DNS, TLS / robots
  gateway.py     fetch gateway
  worker.py      observer loop
  engine.py      evidence extraction and bounded joins
  store.py       relational ledger and blobs
  forecast.py    commit-reveal and Brier scoring
  api.py         human hand-off
  cli.py         offline demo and one-shot runner
infra/docker-compose.yml
tests/
sources.json
```

### License

See [LICENSE](LICENSE). This prototype does **not** convey rights to scrape, redistribute or commercially exploit upstream data.
