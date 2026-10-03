# SURVIVAL ALPHA — MULTI-ASSET FIRM

## Objective

Scan broadly across liquid markets, but trade only where forward, executable, risk-adjusted expectancy is positive.

The firm is not organized by "one AI that trades everything." It is organized like a systematic prop shop:

1. **Data plant** gathers primary market, macro, corporate, news, alternative, and social events.
2. **Specialist research desks** convert those events into testable hypotheses.
3. **Independent strategy engines** backtest and forward-test each hypothesis in the market where it belongs.
4. **Execution engines** are venue/asset specific.
5. **Central risk and portfolio construction** allocate capital only to promoted, sufficiently independent alpha sleeves.
6. **Grok/LLMs** are slow-thinking researchers and supervisors, never hot-path executors.

## Signal hierarchy: signal over noise

Rank information by causal proximity and reliability.

### Tier 0 — executable market state

Highest priority:
- order books, trades, spreads, depth, queue state;
- futures basis and funding;
- options surfaces and realized volatility;
- DEX pools and on-chain state;
- liquidations / open interest;
- borrow, financing and inventory costs.

### Tier 1 — primary-source events

Prefer:
- SEC filings and company IR;
- earnings releases and transcripts;
- central-bank releases;
- official macro releases;
- government/regulator data;
- exchange notices;
- corporate actions.

### Tier 2 — derived institutional information

Examples:
- analyst revisions;
- estimate dispersion;
- positioning;
- ETF / fund flows;
- CFTC positioning;
- short interest;
- supply-chain/shipping information;
- stablecoin flows and bridge flows.

### Tier 3 — news

Use publication and observation timestamps.
Measure novelty, source reliability, affected instruments, and post-event markouts.

### Tier 4 — social attention

X, Reddit, Telegram, Discord and influencers are candidate-generation/manipulation signals.

A social source earns capital only if its post-observation executable markouts prove value.

## Desks

### 1. Global Macro Desk

Universe:
- rates;
- FX;
- equity index futures;
- gold / oil / major commodities;
- liquid bond / commodity ETFs.

Signals:
- macro surprise versus consensus;
- revisions;
- yield-curve changes;
- central-bank language;
- inflation/growth regime;
- CFTC positioning;
- cross-asset risk-on/risk-off;
- real-rate and dollar relationships.

Research horizon:
minutes to months.

### 2. Equity Event Desk

Universe:
- liquid US equities first;
- ETFs;
- later international equities.

Signals:
- earnings surprise;
- guidance revisions;
- SEC 8-K/10-Q/10-K;
- M&A;
- buybacks;
- capital raises;
- insider transactions;
- product/regulatory catalysts;
- estimate revisions.

Primary-source-first rule:
filing/IR > reputable wire/news > social interpretation.

### 3. Options / Volatility Desk

Universe:
- SPY/QQQ/IWM;
- liquid index options;
- highly liquid single-stock options.

Signals:
- implied versus realized;
- term structure;
- skew;
- event volatility;
- dispersion;
- relative-value vol;
- post-event vol crush;
- unusual surface dislocations.

Avoid naive "unusual options activity = bullish" rules.

### 4. Stat-Arb / Cross-Sectional Desk

Universe:
- equities;
- ETFs;
- futures;
- crypto pairs.

Strategies:
- residual mean reversion;
- pairs;
- sector-neutral momentum;
- lead-lag;
- cross-sectional factor portfolios;
- ETF/component dislocations;
- relative value.

Requirements:
point-in-time universe, delisting/corporate-action handling, turnover costs and OOS validation.

### 5. Crypto CEX / Perpetual Desk

Universe:
- BTC/ETH/SOL first;
- liquid alts only when capacity supports them.

Signals:
- funding;
- basis;
- OI changes;
- liquidation cascades;
- spot/perp divergence;
- cross-exchange spreads;
- stablecoin and ETF flows;
- order-book imbalance;
- market-making opportunities.

Execution foundation:
Hummingbot-style connectors/controllers/executors.

### 6. On-chain / DEX Desk

Keep our existing Solana/Pump work:
- bonding curve;
- migration;
- post-migration;
- wallet clusters;
- DEX arbitrage;
- execution alpha;
- sellability;
- latency decay.

Other chains only after the Solana book proves process quality.

### 7. Cross-Venue Arbitrage Desk

Search deterministic conversion graphs across:
- spot venues;
- futures;
- perpetuals;
- ETFs/futures;
- DEX/CEX;
- stablecoins.

Count profit only after:
fees + impact + borrow + funding + transfer/settlement + fill risk.

### 8. Market-Making Research Desk

Focus first on very liquid venues.

Measure:
- spread capture;
- adverse selection;
- queue position;
- inventory risk;
- hedge cost;
- fill probability;
- rebates;
- toxic flow.

No deployment based on candle backtests.

### 9. News / Event Desk

Mission:
create a timestamped event graph, not sentiment scores.

For every event:
- primary source;
- published_at;
- observed_at;
- entities;
- affected instruments;
- novelty;
- expected horizon;
- confidence;
- prior similar events;
- markouts.

### 10. Social / Attention Desk

Sources:
- X;
- Reddit;
- Telegram;
- Discord where permitted.

Features:
- first-mover time;
- author independence;
- duplicate/campaign clustering;
- promoter history;
- attention acceleration;
- price move before/after attention;
- narrative diffusion across platforms.

## Open-source architecture to leverage

### LEAN

Use for multi-asset research/backtest/live parity across equities, options, futures, forex and crypto.

Do not rewrite a generic institutional engine when LEAN already solves data/event/order-model plumbing.

### Qlib + RD-Agent concepts

Use for:
- factor mining;
- model experiments;
- rolling models;
- ML research;
- auto-R&D.

Import methodology, not blind optimized factors.

### FinRobot concepts

Use its principle:
**models reason, software computes, agents orchestrate, systems verify.**

This is the Grok-team doctrine.

### Hummingbot

Use for:
- CEX/DEX connectors;
- market making;
- cross-exchange strategies;
- TWAP;
- arbitrage;
- crypto order lifecycle.

### Nautilus / Nautilus Agents concepts

Adopt the authority boundary:
agents make narrow semantic proposals;
the deterministic trading engine revalidates and owns production execution.

### Freqtrade / Jesse

Use primarily as strategy prototyping references and independent backtest comparators for crypto.

## Unified event schema

Every data adapter should normalize into a point-in-time event containing:

- event_id;
- published_at_utc;
- observed_at_utc;
- market_timestamp_utc;
- source;
- source_type;
- asset_class;
- instrument;
- venue;
- event_type;
- entity_ids;
- raw_reference;
- revision_id;
- novelty_score;
- source_reliability;
- latency_ms;
- tradability_score;
- liquidity/capacity;
- candidate_horizons;
- correlation_cluster;
- provenance_hash.

Never destroy the raw source.

## Alpha scorecard

Every strategy/source/regime/horizon must earn promotion on:

- N;
- mean return;
- median return;
- profit factor;
- bootstrap confidence interval;
- drawdown;
- tail loss;
- turnover;
- execution cost;
- capacity;
- correlation to existing sleeves;
- regime stability;
- accepted-minus-rejected edge.

Do not optimize win rate.

## Portfolio architecture

Think in alpha sleeves:

- Macro;
- Equity Events;
- Equity Factors/Stat Arb;
- Options Vol;
- Crypto Relative Value;
- On-chain;
- Arbitrage;
- Market Making;
- News/Event;
- Social/Attention.

Capital allocation should favor:
- positive forward evidence;
- low correlation to current sleeves;
- adequate liquidity;
- stable execution;
- capacity;
- bounded tail risk.

Risk may always veto.

## Grok operating model

Grok acts as a distributed research department.

### GROK CIO
Capital/research prioritization across desks.

### GLOBAL_MACRO
Macro releases, central banks, rates/FX/commodities.

### EQUITY_EVENT
Filings, earnings, guidance, corporate actions.

### OPTIONS_VOL
Surface/volatility research.

### STAT_ARB
Cross-sectional and relative-value research.

### CRYPTO_RELATIVE_VALUE
Basis/funding/OI/liquidations/cross-exchange.

### WALLET_INTELLIGENCE
On-chain wallets and clusters.

### X_NARRATIVE_SCOUT
Narrow X research triggered by observed market hypotheses.

### NEWS_EVENT
Primary-source event interpretation.

### ALT_DATA
Incremental-value tests for new datasets.

### DATA_PROVENANCE
Point-in-time, leakage and source audit.

### EXECUTION_ANALYST / EXECUTION_ROUTER
Execution cost and routing research.

### PORTFOLIO_CONSTRUCTION
Cross-desk capital allocation.

### RISK_OFFICER
Independent veto/risk review.

### RED_TEAM
Attempts to disprove every promoted edge.

### INVESTMENT_COMMITTEE
Periodic multi-agent synthesis.

### CODE_REVIEW
Engineering reliability.

## Grok Bot deployment

Use persistent Grok Bots as named teammates.

Each bot gets:
- one mandate;
- one approved source list;
- one output schema;
- one cadence;
- one escalation path.

No bot gets:
- broker/exchange withdrawal permission;
- wallet seed/private key;
- authority to change risk limits;
- authority to enable a signer.

## Research cadence

### Continuous deterministic
- prices/order books;
- on-chain;
- funding/OI;
- executable quotes;
- risk;
- markouts.

### 5–15 minute agents
Only for event investigation, not blanket scanning.

### Daily
- strategy scorecards;
- news/event attribution;
- social source attribution;
- portfolio/risk review.

### Weekly
- investment committee;
- red team;
- dataset value review;
- infrastructure ROI;
- strategy kill list.

## Build order

### Phase 1 — Multi-asset research plant
1. Keep current Solana service.
2. Add a normalized multi-asset event store.
3. Add primary SEC EDGAR event ingestion.
4. Add macro calendar / FRED/CFTC research ingestion.
5. Add equity/ETF price data.
6. Add crypto CEX/perp feeds.
7. Store all point-in-time.

### Phase 2 — Backtest engines
1. LEAN for equities/options/futures/FX.
2. Hummingbot for crypto market making/arb.
3. Qlib for cross-sectional/ML research.
4. Survival Alpha for Solana/on-chain.

### Phase 3 — Grok team
Each agent consumes compact scorecards and selected raw evidence.

### Phase 4 — Shadow portfolio
No live money. All desks compete on forward executable outcomes.

### Phase 5 — Capital promotion
Only sleeves with strong forward evidence graduate.

## Doctrine

**Scan everything. Trade almost nothing.**

**Primary source before commentary.**

**Executable state before sentiment.**

**Specialist engines before universal agents.**

**Point-in-time data before clever models.**

**Independent alpha before more signals.**

**Central risk before desk conviction.**

**Grok proposes; software verifies; risk decides.**
