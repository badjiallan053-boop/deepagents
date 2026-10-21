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
