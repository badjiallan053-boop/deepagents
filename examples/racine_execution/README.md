# RACINE Execution Agent Team

A runnable seven-specialist agent team for closing the first buyer-funded RACINE Injection / Continuity Signal Scan before material infrastructure or inventory spend.

## Agents

1. Market & Growth Intelligence
2. FRES Demand Miner
3. Partner Scout
4. Preorder & Offer Architect
5. Outreach & Revenue
6. Quality / Regulatory / Privacy Gatekeeper
7. Finance & Leverage Controller

The supervisor delegates focused work, reconciles evidence, requires compliance challenge and ends each mission with a 72-hour execution plan, owner, cost ceiling, proof gate and stop rule.

## Boundary

This project does not prescribe, dispense, import, relabel or market unapproved human-use peptide injections. It is a B2B research, operating-intelligence and commercial-validation system. Clinical, legal, pharmacy, quality, privacy, contract and payment decisions remain human-controlled.

## Setup

```bash
cd examples/racine_execution
uv sync
export OPENAI_API_KEY="..."
export TAVILY_API_KEY="..."
# Optional: defaults to openai:gpt-5.4
export RACINE_MODEL="openai:gpt-5.4"
```

## Run the default 72-hour mission

```bash
uv run python racine_team.py
```

## Run a focused mission

```bash
uv run python racine_team.py \
  "Find and score ten US fertility or specialty-pharmacy prospects, draft five evidence-led openers, challenge them for compliance, and rank the next actions under a 250 dollar spend ceiling."
```

## Suggested first missions

### Prospect cohort

```bash
uv run python racine_team.py \
  "Build a 10-account founding cohort across fertility clinics and specialty pharmacies. Require public triggers, buyer roles, recurring-problem hypotheses, sources, scores, personalised openers and next actions."
```

### Offer stress test

```bash
uv run python racine_team.py \
  "Stress-test the 7,500 dollar ten-day RACINE Signal Scan. Identify objections, scope-creep risks, missing acceptance criteria, safest deposit structure and a 30-day upsell."
```

### Friction corpus

```bash
uv run python racine_team.py \
  "Create a public-source-only FRES coding plan for IVF injection and fulfilment friction. Return taxonomy, search plan, evidence quality rules, privacy controls and the first 100-record sampling design."
```

## Human approval gates

The agents may research, structure, compare, draft and flag. They may not autonomously:

- send outreach;
- publish claims;
- execute contracts;
- initiate payments;
- represent a partner as confirmed;
- collect patient-identifiable information;
- make clinical, prescribing, dosing or pharmacy decisions.

## Commercial proof gate

Do not expand to consumer medicine access, paid creators, pharmacy integration, custom software or injectable inventory until:

1. one fixed-scope Signal Scan is signed;
2. the first 50% payment is collected;
3. the buyer confirms at least three actionable recurring failures;
4. two reversible interventions can be tested;
5. permitted de-identified aggregate rights are documented;
6. no severe compliance event has occurred.
