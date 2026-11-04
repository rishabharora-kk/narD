# narD engineering and research execution gates

This is an implementation and validation program, not a claim of completed field deployment.
The linked GitHub issues contain phase-specific acceptance criteria.

| Phase | Artifact | Release gate |
|---|---|---|
| 0 | audited fetch gateway, hashed source snapshots | deterministic test suite passes; no source enabled by default |
| 1 | cost-aware triage, durable poll scheduler, health and budgets | record outcomes for >= 1,000 source documents without unapproved egress |
| 2 | entity IDs, provenance graph, point-in-time replay | >= 100 human-labeled join candidates, PR-AUC/baseline comparison and false positives |
| 3 | separate human review handoff, feedback log | >= 3 external evaluators, explicit feedback and safe operator permissions |
| 4 | database least-privilege and host firewall | penetration and read-only invariants verified in deployment |
| 5 | offline bandit/VOI exploration | beat fixed-cadence policy on held-out point-in-time observations within budget |
| 6 | licensing, distribution and pricing | actual paid pilot or justified stop/pivot outcome |

## Nonnegotiable conditions
- No unknown URL, browser click, POST to remote sites, or login credentials for observers.
- No real public source enabled without verified legal/technical access approval.
- Only handoff/operator plane creates predictions or feedback and never acts externally.
- No LLM extraction passes into verified identities without provenance and validation.
- Backtesting uses the *latest* of publication time and earliest verified observation; no retroactive omniscience.
- Source family diversity is not independent confirmation by itself.
- Forecast hashes require an external time anchor to support public track-record claims.

## Phase 1-3 foundation added in this branch
`nard.identities` contains exact public identifiers rather than speculative name joining.
`nard.evaluation` provides time-gated replay and calibration/detection metrics.
`nard.curiosity` provides an offline, budgeted ranking primitive; it cannot issue requests.

These are isolated utilities, **not** a complete working live entity graph, backtest dataset,
quality-validated cross-domain system, or operator dashboard. Integration is a separate milestone.
