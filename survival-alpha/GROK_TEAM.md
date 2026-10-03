# Survival Alpha — Grok Team

## Purpose

Grok is a slow-thinking research organization above the deterministic Survival Alpha engine.

It does **not**:
- hold keys;
- sign transactions;
- bypass risk;
- sit in the sub-second execution path.

It does:
- inspect the forward tape;
- challenge strategy evidence;
- research X/web only when justified;
- propose experiments;
- prepare investment-committee reviews;
- compare infrastructure spend with measured Value of Latency.

## Two operating modes

### Mode A — Grok Bot / SuperGrok manual CIO

Use the consumer Grok product as a human-supervised research console.

This mode needs no xAI API integration in Railway.

Feed Grok only sanitized outputs from:
- /team/strategy-scorecards
- /team/channel-scorecards
- /team/horizon-scorecards
- /realtime/evaluation
- /realtime/strategy-evaluation
- /firm/status
- /firm/markouts

Never give Grok:
- PAPER_ADMIN_TOKEN
- database credentials
- API keys
- Telegram session strings
- private keys

### Mode B — xAI API team

Railway can run the Grok team through xAI's Responses API.

Required secret:
- XAI_API_KEY

Safe defaults:
- GROK_ENABLED=false
- GROK_ALLOW_WEB_SEARCH=false
- GROK_ALLOW_X_SEARCH=false
- GROK_DAILY_BUDGET_USD=2.00

Models:
- routine: grok-4.3
- deep committee: grok-4.20-multi-agent-0309
- code review: grok-build-0.1

## Roles

### CIO
Reads only our forward evidence and decides what research deserves attention.

### EXECUTION_ANALYST
Studies round-trip friction, quote decay, sellability, market phase, and latency.

### STRATEGY_FORENSICS
Compares pass/fail outcomes, markout horizons, outliers, and regime dependence.

### TELEGRAM_FORENSICS
Evaluates channels from our delayed executable fills, never follower count or screenshots.

### WALLET_INTELLIGENCE
Tests whether wallet alpha survives our observation delay and whether wallets are independent.

### X_NARRATIVE_SCOUT
Optional paid X search. Used only for narrow hypotheses after our tape identifies something worth investigating.

### WEB_INFRA_SCOUT
Optional web search for current Solana/Jito/Helius/Jupiter infrastructure, pricing, releases, and engineering opportunities.

### RED_TEAM
Tries to falsify the entire system.

### INVESTMENT_COMMITTEE
Uses the multi-agent model for periodic deep review. It does not trade.

### CODE_REVIEW
Uses grok-build-0.1 for architecture/reliability review.

## Cost doctrine

The always-on trading plant should not call an LLM per market event.

Routine Grok reviews should use compact database summaries.

X search is opt-in because tool usage can dominate cost.

Suggested cadence:
- CIO: 2-4 times/day
- Execution analyst: after meaningful sample growth or incident
- Strategy forensics: daily
- Telegram forensics: daily if channel sample changed
- X narrative scout: only on hypothesis
- Web infra scout: weekly or when a provider issue appears
- Investment committee: daily or every other day
- Red team: weekly
- Code review: after substantive commits

## Budget controls

Every API response is persisted to grok_run with:
- role
- model
- tool selection
- context hash
- output
- citations
- exact API cost if returned by xAI

Before a call, the team checks the cumulative UTC-day spend.

When the daily budget is exhausted, further calls fail closed.

## API endpoints

All require X-Paper-Token admin authentication.

- GET /grok/status
- GET /grok/context/{role}
- POST /grok/run/{role}
- GET /grok/runs

Example request body:

    {
      "objective": "Explain why accepted candidates underperformed rejected candidates today.",
      "deep": false,
      "use_web": false,
      "use_x": false
    }

## Manual Grok Bot team prompts

### CIO
You are CIO of Survival Alpha. Use only the forward executable evidence I provide. Distinguish sample size, mean, median, profit factor, tail losses, accepted-vs-rejected edge, sellability, and latency decay. Output STATE, FAILURES, ACTIONS, PROMOTION, BUDGET. Do not recommend live trading or bypass risk.

### Red Team
Try to prove Survival Alpha has no edge. Search for look-ahead, survivorship bias, data leakage, correlated wallets, copied Telegram calls, quote-model optimism, regime dependence, outlier concentration, and execution assumptions. Give falsification tests, not opinions.

### X Narrative Scout
Use X only to answer this narrow hypothesis: [HYPOTHESIS]. Find first movers, duplicates, promoter overlap, timing relative to the price move, and counterexamples. Do not infer alpha from popularity. Return evidence that can be joined to our timestamped tape.

### Investment Committee
Act as an independent committee. Review all source/strategy/regime/horizon evidence. Agents should disagree where evidence is weak. Promote only where prior forward executable evidence supports it. Otherwise return COLLECT/REWORK/KILL.

## Governance

Grok outputs are proposals.

The deterministic strategy tournament and risk governor remain authoritative.

A Grok recommendation can create:
- a research hypothesis;
- a code-review task;
- a provider/infrastructure investigation;
- a promotion/demotion proposal.

It cannot:
- create a live trade;
- alter a signing key;
- override risk;
- increase capital limits;
- enable a signer.
