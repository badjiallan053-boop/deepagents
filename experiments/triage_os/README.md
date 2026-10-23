# TRIAGE OS — special situations intelligence desk (MVP)

This is an isolated prototype under `experiments/triage_os/`. It does **not** change the upstream DeepAgents runtime.

## Run locally
```bash
python experiments/triage_os/desk.py init
python experiments/triage_os/desk.py ingest-sec --cik 0001326801 --user-agent "TRIAGE Research contact@example.com"
COURTLISTENER_TOKEN=... python experiments/triage_os/desk.py ingest-court --query 'sale procedures'
python experiments/triage_os/desk.py rank
python -m unittest discover -s experiments/triage_os -p 'test_*.py'
```

The SEC company-submissions endpoint monitors **one specified public company**; it is not a global bankruptcy scanner. The CourtListener search endpoint requires a valid API token and its query/search-type parameters may evolve. Review source API documentation before production use. No scraped credentials, no paid PACER access and no claim that a record represents an available deal.

## Agent responsibilities
1. **Source scout:** official public filings and provenance (automated).
2. **Entity resolution:** match debtor, sponsor, lender, property and aliases (planned).
3. **Credit analyst:** claims, liens, waterfall, maturity and fulcrum (planned).
4. **Property diligence:** title, environmental, taxes, leases and capex (planned).
5. **Valuation:** scenario ranges and missing-data abstention (planned).
6. **Red team:** independent contradictory evidence and hard stops (planned).
7. **Investment committee:** no BUY signal without verified documents and human approval (planned).
8. **Buyer mandate desk:** permissioned buyer preferences and conflict checks (planned).

## Controls
- Original source URLs and retrieved timestamps are mandatory.
- Scores are triage priorities, **not expected returns**.
- No autonomous outreach, bidding, contracts, wire transfers, brokerage or investment recommendations.
- Human review required for legal conclusions, counterparties and transaction execution.
- Skill files from skills.sh are untrusted inputs: pin commit, inspect content, sandbox, disallow secrets/network by default.
- The SQLite database is local and contains no credentials. Do not commit it.

## Next milestone
Add state-specific property/foreclosure connectors, filing-document parser with citation offsets, entity graph, buyer mandates, review dashboard and scheduled ingestion with monitoring. Verify data licenses, API quotas and US regulatory scope before commercial deployment.

## Connector notes (verified live 2026-10-22)

- CourtListener: uses REST **v4** search (`type=r`, `order_by=dateFiled desc`, optional `filed_after`), follows the `next` cursor up to `--max-pages`. Anonymous search works; `COURTLISTENER_TOKEN` is optional (higher limits). Results are keyed on `docket_id` / `docket_absolute_url`; scoring uses case name, `chapter` and `recap_documents` descriptions.
- SEC: submissions API (`--history` also pages `filings.files`) and EDGAR full-text search (`ingest-sec-fulltext`, filtered by 8-K items such as 1.03, 2.04, 2.06, 3.01). 8-K item codes add to the priority score. Requests are throttled below 10 req/s and retried with backoff on 429/5xx.
- `export --out signals.csv` writes the top ranked signals. All signals remain `unverified`.
- Tests are offline and use recorded fixtures in `fixtures/`.

## Agent team (`team.py`)

Native reimplementation of the patterns in the team research note (no third-party skill code, no hooks, no outreach):
- Append-only SQLite bus (`bus` table, UPDATE/DELETE blocked by triggers). Types: HANDOFF, REQUEST, CHALLENGE, ABSTAIN, VERIFY, DECISION. Every message: summary ≤200 tokens, claims with source_url/doc_page/as_of/confidence, mandatory `unknowns`/`skipped`/`risks`. Claims without source_url + as_of are downgraded to `unknown`.
- `cases/<id>/case.json`, written only by `desk_lead` under an O_EXCL lock. Deadline clock fields and a standard `REJECTION_REASONS` taxonomy (kills are stored as negative outcome labels).
- Gates: G1 provenance → G2 entity → G3 Verifier (veto) → G4 Valuation (ABSTAIN when title/debt/occupancy/legal status are unknown) → G5 Contrarian (veto, max 2 revise loops, then escalate) → G6 Buyer match → G7 IC pack → **AWAITING_HUMAN**.
- Only a `human_ic` DECISION can unlock `external_action()`, and only for the actions it names. Even then the function performs nothing; it just grants permission.
- Roles are deterministic stubs; pass `llm=callable(role, case, inbox)` to `DeskLead` to plug in a model.
- Demo: `python demo_case.py --signals-db triage.db --workdir ./desk_run`.

## Daily hunt, entity dedupe, item confirmation

- `python desk.py daily-hunt --days 2 --out /workspace/triage_os_data/` runs SEC full-text (items 1.03/2.04/2.06/3.01) and CourtListener queries over the last N days, then writes `signals_top.csv` (deduped by entity) and `signals_new.csv` (only entities never seen in that DB before). Each query fails on its own and stored rows are kept. Set `COURTLISTENER_TOKEN` (optional) and `SEC_USER_AGENT`.
- Entities are keyed by CIK when known, else by normalized name. A name-only entity merges into a matching CIK entity. Ranked/exported rows carry `signal_count`, `sources`, `signal_types` and `all_urls`.
- SEC full-text hits are kept only if the filing's `items` in the submissions JSON contain a wanted item, so text-only mentions are dropped.
- The Verifier and IC Secretary read every message in the case.

## Terminal UI, research note and landing page (design pass, 22 Oct 2026)
- `web/`: React + Vite + Tailwind with shadcn-style components (Radix Dialog, cmdk, Cytoscape). It has a dark terminal theme, sortable and filterable tables, mark sparklines, a cap-structure waterfall, case timelines, verification badges, a source drawer and a Ctrl-K palette.
  Build with `cd web && npm ci && npm run build`. Then `python3 app/server.py` serves `web/dist` and the read-only API at http://127.0.0.1:8765.
- `design.py`: the shared print design system (CSS and SVG charts) used by the note, the master report and the landing page.
- `research/hughes_note.py` builds `research/Hughes_Satellite_Note.pdf`. Its claims HN01–HN32 are token-checked against primary docs and written to the `verification` table.
- `landing.py` builds `landing/index.html`, which is served at `/landing.html`.
- Screenshots at 1440x900 are in `app/screenshots/v2/`.
