# SURVIVAL ALPHA — MASTER PLAYBOOK
## From Zero to a Systematic Memecoin Trading Firm

**Status:** Research / paper-trading only  
**Primary region:** Singapore  
**Failover region:** Tokyo  
**Scope:** Proprietary research and proprietary-capital experimentation only  
**Live signing:** Not present in the research process  
**Core principle:** Probabilistic research may propose; deterministic systems measure, risk-check, and execute.

---

# 0. Mandate

Survival Alpha is not a "memecoin bot."

It is a systematic trading research firm whose first market is Solana memecoins.

The firm exists to answer four questions:

1. Does a signal contain information?
2. Is the information still valuable when we observe it?
3. Can that value be captured after fees, latency, liquidity, and landing risk?
4. Can the edge survive portfolio-level capital allocation without unacceptable drawdown?

The firm should prefer **no trade** to a trade without measured positive expectancy.

No source is trusted because it is popular, profitable historically, or persuasive.

Every source, strategy, data feed, execution path, and holding period must earn promotion through forward evidence.

---

# 1. Non-Negotiable Governance

## 1.1 Separation of duties

The same component must not be allowed to:

- discover a signal;
- change its own thresholds;
- allocate capital;
- override portfolio risk;
- and approve execution.

Roles are intentionally separated.

### Research layer

- Telegram Scout
- X/Reddit Narrative Scout
- Wallet Intelligence Scout
- Pump Event Scout
- Migration Scout
- Organic Flow Scout
- Cross-Venue Arbitrage Research
- Market-Making Research

### Decision layer

- Microstructure Agent
- Strategy Tournament
- Adverse Selection Agent
- Execution Alpha Model
- Reject Engine

### Firm layer

- Meta Allocator
- Portfolio Manager
- Firm Risk
- Markout Agent
- Post-Trade Attribution

### Supervisory layer

- ChatGPT Work / CIO
- GitHub / CI
- Incident review
- Research notebook / strategy registry

## 1.2 What ChatGPT Work may do

Work may:

- research X, Reddit, Telegram, GitHub, papers, and official documentation;
- inspect logs and dashboards;
- investigate wallet clusters;
- compare strategy and source scorecards;
- propose experiments;
- update research code/configuration through reviewed commits;
- promote or demote research hypotheses according to explicit evidence rules;
- create daily and weekly research reports.

Work must not sit in the sub-second hot path.

## 1.3 What the hot path may do

The hot path may:

- ingest deterministic market data;
- decode transactions;
- compute integer/float features;
- evaluate hard-coded strategy predicates or pre-approved statistical models;
- apply portfolio risk;
- construct approved paper or later live intents;
- submit through approved transports;
- record exact timestamps and outcomes.

No LLM call belongs between event reception and transaction submission.

---

# 2. Legal / Operational Boundary

Until specialist counsel says otherwise, operate this project as a **closed proprietary research/trading operation**:

- no customers;
- no client funds;
- no managed accounts;
- no public brokerage/execution service;
- no promises of returns;
- no public "dealer" offering.

The firm should obtain jurisdiction-specific advice before changing this scope.

Maintain:

- entity records;
- API/provider contracts;
- data-use terms;
- accounting records;
- wallet ownership records;
- strategy version history;
- incident history;
- change approvals.

---

# 3. Secrets and Security Architecture

## 3.1 Never expose secrets to the LLM

Never paste into chat:

- private keys;
- seed phrases;
- Helius keys;
- Jupiter keys;
- Telegram session strings;
- deployment tokens;
- Render credentials;
- exchange credentials.

## 3.2 Research process has no signing key

The research service should contain no:

- PRIVATE_KEY;
- SECRET_KEY;
- Keypair;
- sendTransaction;
- /swap/v2/execute live pathway.

CI should fail if these appear in the research branch.

## 3.3 Future live signing service

If Stage 1 is eventually earned, create a **separate signer/executor service**.

The signer should:

- run outside Work/LLM;
- use an isolated hot wallet;
- enforce per-transaction notional caps;
- enforce daily loss caps;
- enforce destination/program allowlists;
- accept only signed research intents matching a strict schema;
- reject expired intents;
- reject unknown program IDs;
- reject excessive slippage;
- record every request;
- expose a kill switch.

Research and execution remain separate repositories/processes.

---

# 4. Repository / Environment Layout

Suggested structure:

    survival-alpha/
      app.py
      realtime_engine.py
      pump_quote_service.mjs
      telegram_parser.py
      telegram_signal_agent.py
      social_signal.py
      elite_signals.py
      strategy_tournament.py
      channel_evaluator.py
      capital_allocator.py
      firm_risk.py
      firm_book.py
      agent_team.py
      tests/
      MASTER_PLAYBOOK.md
      WORK_CIO_PLAYBOOK.md
      AGENT_TEAM.md
      SOCIAL_SIGNAL_SPEC.md

Future HFT repository:

    survival-alpha-hft/
      crates/
        ingest/
        decode/
        state/
        features/
        strategies/
        risk/
        transaction_factory/
        submit/
        telemetry/
      configs/
      benches/
      replay/

Do not combine research Python and future key-holding Rust execution in one trust boundary.

---

# 5. Data Plant: The Most Important Asset

The trading firm's moat should become its **timestamped event tape**.

For every event record:

- upstream event timestamp;
- slot;
- transaction index where available;
- local receive timestamp;
- decode-complete timestamp;
- feature-ready timestamp;
- decision timestamp;
- quote-request timestamp;
- quote-response timestamp;
- transaction-built timestamp;
- signed timestamp;
- send timestamp by route;
- route acknowledgment;
- preconfirmation timestamp if available;
- landed slot;
- landed transaction index;
- confirmed timestamp;
- finalized timestamp.

Use a monotonic high-resolution clock in the hot path.

Never overwrite raw source records.

Derived datasets must always be reproducible from raw data + code version.

Store:

- provider;
- subscription/filter;
- schema version;
- git commit;
- strategy version;
- configuration hash.

The question for every dataset is:

> Does conditioning on this data improve a forward executable strategy versus not conditioning on it?

---

# 6. Data Feed Ladder

## Tier A — Current low-cost research

Use:

- Helius Developer;
- transactionSubscribe / LaserStream WSS;
- Helius Preprocessed Transactions;
- Jupiter Developer;
- Pump deterministic bonding-curve state;
- Telegram Bot API / optional Telethon research account;
- X/Reddit research via official/approved access;
- PumpPortal only where terms/costs make sense.

The goal is not minimum latency.

The goal is to establish whether an information edge exists.

## Tier B — Emerging low-latency desk

Only after measured alpha:

- Helius Business gRPC if justified;
- stronger Singapore compute;
- multiple landing providers;
- Jito Singapore;
- Tokyo failover;
- more complete telemetry.

## Tier C — HFT trial

Only after the Value-of-Latency study shows economic benefit:

- Helius Professional preconfirmations;
- BAM preconfSubscribe;
- preprocessed transactions as fallback;
- raw/deshredded streams for benchmarking;
- route racing;
- Rust hot path.

Preconfirmations must be treated as an early signal, not final truth.

Always reconcile with later processed/confirmed state.

## Tier D — Institutional latency stack

Only after capacity justifies cost:

- raw shred delivery;
- colocated infrastructure;
- dedicated nodes;
- multi-region redundancy;
- direct/optimized TPU paths;
- custom provider agreements.

Infrastructure spend must have measured incremental expected P&L greater than cost.

---

# 7. Market Regimes

Never treat "Pump.fun" as one market.

Split all research into at least:

1. **Bonding curve**
2. **Near-graduation**
3. **Migration event**
4. **Fresh PumpSwap**
5. **Mature post-graduation**
6. **Cross-venue**
7. **High-volatility market-wide regime**
8. **Low-liquidity / degraded execution regime**

A strategy promoted in one regime receives zero credit in another until tested.

---

# 8. Quote Engines

## 8.1 Bonding-curve book

Use live Pump reserves and official/protocol-compatible curve math.

Measure:

- tokens out;
- buy impact;
- immediate hypothetical sell-back;
- total round-trip friction;
- graduation progress;
- SOL remaining to graduation;
- current reserves;
- notional sensitivity.

Because the bonding curve charges a large platform fee on each trade, tiny scalps can be uneconomic before network/tip/slippage.

Test multiple hypothetical notionals.

## 8.2 Graduated book

Use Jupiter quote/order infrastructure.

For every candidate:

- executable buy quote at decision time;
- immediate hypothetical sell-back;
- 100 ms;
- 250 ms;
- 500 ms;
- 1 s;
- 2 s;
- 5 s where appropriate.

Record:

- out amount;
- price impact;
- router;
- API RTT;
- fee fields;
- route changes;
- quote failures.

The system must learn an **alpha-decay curve**, not a single return.

---

# 9. Signal Desks

## 9.1 Telegram Desk

Two ingestion modes:

- Bot API for accessible groups/channels;
- Telethon/MTProto research account where bot access is not possible and use is permitted.

Parser extracts:

- channel;
- message ID;
- publication time;
- observation time;
- mint;
- call type;
- confidence;
- normalized fingerprint;
- source URL.

Rules:

- first actionable call per channel/mint is the unit of analysis;
- repeated "2x / 5x / hold / buy more" messages do not create new winning samples;
- copied/duplicate calls are clustered;
- channel performance is measured from **our executable price after receiving the message**.

Channel scorecard:

- N;
- mean;
- median;
- profit factor;
- positive rate;
- large-loss rate;
- bootstrap lower confidence bound;
- sellability failure;
- best markout horizon.

Telegram channels require their own promotion independently from the strategy.

## 9.2 Wallet Intelligence Desk

Never use leaderboard ROI as the signal.

For each wallet measure:

- historical realized P&L;
- copyable P&L after our delay;
- 100ms/250ms/500ms/1s/2s decay;
- holding period distribution;
- token-age preference;
- venue preference;
- position sizing;
- exit behavior;
- tail dependence;
- profit concentration;
- creator/funder relationships.

Collapse correlated addresses into clusters using:

- common funding;
- common upstream funders;
- token-overlap graph;
- repeated same-slot timing;
- similar notional signatures;
- holding-period fingerprints;
- repeated creator interaction.

Ten addresses from one cluster = one signal.

## 9.3 Social / Narrative Desk

X and Reddit are **candidate-generation and manipulation-detection** inputs.

Features:

- first-observed time;
- first-published time;
- unique authors;
- duplicate-text ratio;
- new-account concentration;
- cross-platform confirmation;
- contract-address consistency;
- mention acceleration;
- promoter historical score;
- social-vs-on-chain divergence.

Social can nominate a candidate.

Social cannot authorize capital alone.

## 9.4 Organic Flow Desk

Leverage Jupiter organic metrics as an independent signal.

Use:

- organic score;
- organic-score acceleration;
- buyer acceleration;
- cross-source confirmation;
- route/liquidity health.

Do not equate high organic activity with positive future return.

Forward-test it.

## 9.5 Pump / Migration Desk

Watch:

- new token;
- graduation progress;
- migration;
- first post-migration pools;
- liquidity growth;
- independent buyers;
- sell emergence;
- fee competition;
- authority state;
- holder concentration.

Avoid assuming launch sniping is the best opportunity.

Migration and early post-migration can be separate strategies.

## 9.6 Cross-Venue Arbitrage Desk

Build a state graph with nodes such as:

- Pump curve;
- PumpSwap;
- Raydium;
- Meteora;
- Jupiter routes;
- SOL pair;
- USDC pair where applicable.

Edges are executable conversion rates after:

- LP fees;
- protocol fees;
- priority fees;
- tips;
- price impact.

Only count an arbitrage when the executable cycle remains positive after all costs.

## 9.7 Market-Making Research Desk

Later phase only.

Research:

- fair value from cross-venue graph;
- two-sided quoting;
- inventory skew;
- toxic-flow withdrawal;
- quote refresh frequency;
- adverse selection;
- venue-specific fee structure.

Do not deploy before directional/arb infrastructure and risk accounting are robust.

---

# 10. Microstructure Features

For each candidate capture:

- buy count;
- sell count;
- unique buyers;
- unique sellers;
- buy/sell ratio;
- flow imbalance;
- same-slot buy concentration;
- largest buyer share;
- holder concentration;
- mint authority;
- freeze authority;
- transaction fee intensity;
- failed transaction density;
- route availability;
- liquidity depth;
- round-trip sellability;
- migration status;
- organic activity;
- source count;
- independent wallet count.

Avoid one giant opaque score.

Store components independently so failure can be attributed.

---

# 11. Adverse Selection / Toxicity

Build a Source Toxicity Score for:

- Telegram channel;
- X account;
- wallet;
- wallet cluster;
- token creator;
- Pump deployer;
- launch/migration event type.

Measure post-observation trajectory:

- +100ms;
- +250ms;
- +500ms;
- +1s;
- +2s;
- +5s;
- +30s;
- +2m;
- +5m;
- +15m.

A source with excellent historical P&L but negative post-observation markouts is toxic to a copier.

The correct question is:

> What happens after this source becomes observable to us?

---

# 12. Execution Alpha Model

Price direction and execution quality are separate predictions.

Build:

    P(positive_markout | signal)
    P(land | route, fee, leader, contention)
    P(sellability_failure | token state)
    E(markout | delay, notional)
    E(cost | route, fee, tip, size)

Then estimate:

    EV =
      P(land) * expected_markout
      - execution_cost
      - adverse_selection_penalty
      - tail_loss_penalty

Reject positive-price signals when landing/cost quality destroys expectancy.

---

# 13. Leader-Conditioned Execution Research

Future HFT telemetry should include:

- current slot;
- scheduled leader;
- region;
- validator client where knowable;
- BAM/preconf coverage;
- route RTT;
- account contention;
- priority-fee environment;
- Jito auction conditions;
- sender route;
- landing slot;
- transaction index.

Research whether execution quality differs by:

- leader cohort;
- provider;
- region;
- time of day;
- congestion state;
- program/account set.

Do not assume one route is globally best.

---

# 14. Strategy Tournament

Maintain independent hypotheses.

Current examples:

- TRENCHER_ORGANIC
- INDEPENDENT_WALLET_CONSENSUS
- POST_MIGRATION_SURVIVOR
- ORGANIC_MIND_SHARE

Add only explicit hypotheses.

Every strategy must have:

- version;
- feature definition;
- threshold definition;
- intended regime;
- expected holding horizon;
- risk assumptions;
- start date;
- evidence scorecard.

Do not modify thresholds retrospectively without creating a new version.

---

# 15. Research Book

The Research Book exists to answer:

> Is there information?

It should:

- use fixed/notional-normalized paper sizing;
- include every accepted hypothesis;
- track rejected candidates;
- calculate counterfactual outcomes;
- capture all quote failures;
- capture unsellable states;
- track multiple horizons.

The Research Book does **not** optimize capital allocation.

---

# 16. Counterfactual Book

Every rejected candidate must also be marked.

Compare:

- accepted mean/median;
- rejected mean/median;
- large-loss rate;
- sellability failures;
- distribution tails.

A filter is valuable only if accepted outcomes improve relative to what it rejected.

Do not judge a filter by how "sensible" it sounds.

---

# 17. Markout Grid / Alpha Half-Life

Default research horizons:

- 100 ms where feed permits;
- 250 ms;
- 500 ms;
- 1 s;
- 2 s;
- 5 s;
- 30 s;
- 2 min;
- 5 min;
- 15 min.

For each strategy/source estimate:

    alpha(t)

Then calculate:

    ValueOfLatency(dt) = EV(t - dt) - EV(t)

This is the economic justification for buying faster infrastructure.

If a source retains alpha for minutes, shreds/preconfs may not be worth the expense.

---

# 18. Promotion / Demotion

## Promotion baseline

A strategy/source bucket should ordinarily require:

- at least 30 forward observations before "promoted research";
- profit factor > 1.30;
- positive 95% bootstrap lower bound;
- accepted set better than rejected set;
- no single token/wallet/day dominating performance;
- tail losses within limit;
- executable quote availability;
- no causal-ordering/data-integrity issue.

For the Stage-1 live gate, require much more evidence than 30 observations.

## Demotion

Demote or rework when:

- PF <= 1.0 over a meaningful forward window;
- lower confidence bound turns negative;
- tail loss rate exceeds limit;
- execution cost consumes edge;
- source behavior changes;
- performance concentrates in one outlier;
- data provenance breaks;
- market regime changes materially.

Killed strategies stay in shadow mode so recovery can be measured.

---

# 19. Simulated Firm Book

The Firm Book asks:

> Would we allocate scarce capital to this already-proven edge?

It is separate from the Research Book.

Capital eligibility requires:

1. strategy currently passes;
2. same strategy was previously promoted;
3. source/channel was previously promoted when relevant;
4. risk governor approves.

Never allocate because "five agents agree" if they share the same underlying data/source.

---

# 20. Firm Risk Governor

Starting research limits:

- maximum open positions;
- maximum gross exposure;
- maximum position size;
- maximum source/channel exposure;
- duplicate-mint prohibition;
- daily realized loss limit;
- drawdown cap;
- unsellable-position circuit breaker.

Risk can only veto.

No strategy confidence score can override risk.

Keep kill switches outside strategy code.

---

# 21. Capital Allocation

Start with simple bounded allocations.

Avoid Kelly sizing until:

- sufficient samples;
- stable distribution;
- tail modeling;
- live fill data;
- regime segmentation.

Possible early allocation rule:

    base allocation
    x independent promoted confirmations
    x liquidity capacity adjustment
    x execution-quality adjustment
    x regime multiplier

Then hard-cap by firm risk.

Scale notional only after the quote-size curve remains profitable.

---

# 22. Capacity / Notional Testing

For every promoted strategy test quotes at multiple sizes.

Example:

- 0.01 SOL;
- 0.02 SOL;
- 0.05 SOL;
- 0.10 SOL;
- 0.25 SOL;
- larger only if liquidity permits.

Estimate:

    NetAlpha(q) =
      signal_return(q)
      - roundtrip_cost(q)
      - latency_decay(q)
      - landing_cost(q)
      - failed_exit_risk(q)

Capacity is the largest q for which conservative NetAlpha remains positive.

---

# 23. HFT Hot Path — Future Rust Service

Target modules:

    ingest.rs
    decoder.rs
    state.rs
    features.rs
    strategy.rs
    risk.rs
    transaction_factory.rs
    submit.rs
    telemetry.rs

Hot path:

    receive
    -> decode
    -> update state
    -> compute features
    -> deterministic strategy
    -> risk
    -> patch transaction
    -> sign
    -> submit

No HTTP price-query fan-out if state can be maintained locally.

No JSON if a binary hot-path feed is available.

No LLM.

---

# 24. Preconfirmations Desk

Only after cheaper feeds prove edge.

Helius/Jito BAM preconfirmations are an earlier signal than shreds, but:

- they are not final;
- coverage is partial;
- a preconfirmed transaction may fail to become canonical;
- they represent already-executed leader outcomes, not exploitable pending order flow.

Use them to update future state early.

Architecture:

    preconf
      -> decode transaction
      -> apply state delta to local projected state
      -> calculate reaction
      -> risk
      -> submit response
      -> reconcile later processed/confirmed result

Always maintain fallback to preprocessed/shred/processed feed when preconf coverage is absent.

---

# 25. Execution Route Race — Future Live Stage

Later, the same signed transaction can be sent through approved parallel transports.

Candidate routes:

- Jito Singapore;
- Helius Sender;
- Jupiter transaction submit;
- approved direct/TPU path where supported.

Record:

- route send time;
- acknowledgment;
- landing;
- cost/tip;
- leader;
- congestion;
- slot.

Build a route-selection/landing model rather than assuming one route always wins.

For Asia:

- Singapore primary;
- Tokyo failover.

---

# 26. Fee / Landing Model

Model fees locally to the account/program set.

Inputs may include:

- account contention;
- recent successful priority fees;
- failed transaction density;
- Jito tip environment;
- compute units;
- leader;
- time in slot;
- event type.

Output:

    minimum expected cost for target landing probability

Do not blindly maximize tips.

The objective is net EV, not raw landing rate.

---

# 27. Monitoring and Observability

Dashboards should include:

### Data health

- feed uptime;
- message rate;
- gaps;
- sequence errors;
- duplicate rate;
- clock skew.

### Signal health

- candidates/source;
- acceptance rate;
- source diversity;
- cluster diversity;
- manipulation-risk rate.

### Execution research

- quote RTT;
- round-trip friction;
- 100/250/500/1000/2000ms decay;
- route failures;
- sellability failures.

### Strategy

- PF;
- mean;
- median;
- bootstrap CI;
- large-loss rate;
- accepted-minus-rejected edge;
- best horizon;
- performance by regime.

### Firm

- simulated NAV;
- realized/unrealized PnL;
- gross exposure;
- source/channel exposure;
- drawdown;
- risk vetoes;
- capital by strategy.

---

# 28. Incident Response

Immediate freeze conditions:

- source schema silently changes;
- timestamps cannot be trusted;
- database writes stop;
- quote engine returns impossible values;
- Pump/Jupiter market phase misclassification;
- risk table unavailable;
- duplicate transaction behavior;
- clock synchronization failure;
- provider outage causing stale state;
- unexpected signer/live code appears in research service;
- position becomes unsellable beyond configured threshold.

Incident sequence:

1. stop allocation;
2. preserve logs/raw events;
3. label affected interval invalid;
4. identify root cause;
5. add regression test;
6. replay impacted period;
7. re-enable only after test passes.

Never "trade through" a data-integrity incident.

---

# 29. ChatGPT Work / CIO Operating Cadence

## Every 15 minutes

Check:

- service health;
- data feeds;
- database growth;
- quote failures;
- unexpected latency;
- risk status.

## Hourly

Review:

- channel scorecards;
- strategy scorecards;
- horizon scorecards;
- accepted vs rejected;
- large losses;
- execution degradation;
- new wallet clusters;
- narrative explanations.

Do not alter thresholds because of one hour.

## Daily

Produce:

- source attribution;
- strategy attribution;
- execution-cost attribution;
- market-regime attribution;
- simulated firm PnL;
- drawdown;
- risk veto summary;
- promoted/demoted strategies;
- open research questions;
- proposed code/config experiments.

Always report N next to performance metrics.

## Weekly

Review:

- data value;
- infrastructure spend;
- Value of Latency;
- source drift;
- capacity;
- risk limits;
- whether any desk should be killed.

---

# 30. Stage Gates

## Gate 0 — Code integrity

Required:

- CI green;
- no live signer;
- no private-key path;
- raw event persistence;
- deterministic quote pipeline;
- database persistence;
- risk tests.

## Gate 1 — Data validity

Required:

- timestamps validated;
- causal ordering validated;
- quote data realistic;
- Pump/Jupiter market-phase handling correct;
- rejected candidates marked;
- no look-ahead.

## Gate 2 — Research edge

Required:

- hundreds of forward candidates;
- multiple days/regimes;
- accepted > rejected;
- at least one source/strategy with PF > 1.3;
- positive confidence lower bound;
- edge not dominated by one outlier;
- sellability acceptable.

## Gate 3 — Simulated firm

Required:

- promoted strategies only;
- portfolio risk enforced;
- acceptable portfolio drawdown;
- source concentration controlled;
- simulated NAV positive after realistic costs.

## Gate 4 — Stage 1 live

Only consider a separate signer after:

- >= 300 forward candidates;
- multiple market regimes;
- one genuinely promoted strategy/source;
- forward PF > 1.30;
- positive 95% confidence lower bound;
- drawdown inside declared cap;
- accepted set materially beats rejected;
- quote/slippage model resembles actual opportunity;
- no unresolved security/data incident.

Start with tiny isolated capital.

## Gate 5 — Latency upgrade

Upgrade infrastructure only if:

    incremental expected P&L from faster feed
    >
    incremental infrastructure cost + operational risk

## Gate 6 — HFT

Call the desk HFT only when:

- measured alpha half-life justifies sub-second reaction;
- Rust hot path is benchmarked;
- execution route race is measurable;
- landing model is calibrated;
- nanosecond/monotonic telemetry exists;
- capital is still limited by risk/capacity, not by unmeasured assumptions.

---

# 31. Infrastructure Budget Ladder

## Research

- Jupiter Developer;
- Helius Developer;
- Singapore always-on compute;
- Postgres;
- Telegram bot/research account;
- monitoring.

## Emerging prop

Only when research edge is established:

- stronger Singapore host;
- Helius Business if gRPC throughput is economically justified;
- multiple submission endpoints;
- Tokyo failover;
- richer telemetry.

## HFT trial

Only if Value-of-Latency is positive:

- Helius Professional;
- preconfirmations trial;
- Sender Max / equivalent;
- Rust event engine;
- preprocessed/shred benchmark.

## Institutional

Only if live capacity supports it:

- raw shreds;
- dedicated node;
- colocation;
- multiple providers;
- network/clock engineering;
- dedicated observability.

---

# 32. First 30 Days

## Days 1–3 — Stabilize the research plant

- deploy Singapore service;
- deploy persistent Postgres;
- configure secrets outside chat;
- enable Helius/Jupiter;
- validate Pump quote sidecar;
- enable Telegram ingestion;
- seed a small wallet cohort;
- verify raw and derived timestamps;
- verify markout generation.

Success condition:

> reliable data, not profit.

## Days 4–7 — Build the baseline

Collect:

- Telegram calls;
- wallet signals;
- migrations;
- organic candidates;
- Pump curve candidates.

Do not tune aggressively.

Produce first:

- source scorecards;
- strategy scorecards;
- 30s/2m/5m/15m markouts;
- accepted vs rejected comparison.

## Days 8–14 — Kill weak ideas

Identify:

- sources with negative post-observation markouts;
- strategies whose edge disappears by our latency;
- regimes where costs dominate;
- filters that do not improve the rejected baseline.

Demote them.

Add only one major hypothesis per experiment.

## Days 15–21 — Capacity / execution research

For the best surviving strategies:

- test quote sizes;
- build alpha-decay curves;
- measure API/feed latency;
- estimate Value of Latency;
- compare market regimes.

Still no need for live money.

## Days 22–30 — Firm simulation

Run promoted strategies through:

- capital allocator;
- portfolio risk;
- simulated NAV;
- multiple holding horizons.

At day 30 ask:

1. Is there a real forward edge?
2. Which source?
3. Which regime?
4. Which holding period?
5. What notional capacity?
6. Is latency the bottleneck?
7. Is a Stage-1 live experiment justified?

If any answer is unclear, remain paper-only.

---

# 33. What Not To Do

Do not:

- buy because a wallet is on a leaderboard;
- buy because Telegram says "insider";
- use screenshots as performance evidence;
- optimize for win rate;
- assume paper fills equal executable fills;
- assume the fastest signal is the best signal;
- treat ten related wallets as ten votes;
- treat social volume as organic;
- tune on future information;
- fund a wallet before the paper book works;
- buy expensive shreds/nodes before Value-of-Latency is measured;
- let an LLM hold a private key;
- let strategy code override risk;
- scale because of a small winning streak.

---

# 34. North-Star Metrics

The firm should optimize for:

## Information quality

    AcceptedMinusRejectedEdge

## Execution quality

    RealizableAlpha = TheoreticalAlpha - Drift - Fees - Slippage - LandingCost

## Risk-adjusted portfolio performance

    NetPnL / Drawdown

## Data value

    performance improvement when conditioning on dataset

## Infrastructure ROI

    IncrementalPnL(faster_path) - IncrementalCost(faster_path)

## Capacity

    maximum notional with conservatively positive NetAlpha

The purpose of the firm is not to trade often.

It is to allocate capital only where **forward, executable, risk-adjusted expectancy is positive**.

---

# 35. Current Provider / Protocol Facts To Re-Verify Before Purchase

These values change. Always check current official documentation before upgrading.

At the time this playbook was written:

- Pump bonding-curve total trading fee is 1.25% per trade.
- Jupiter Developer is $25/month with 10 general API requests/sec.
- Helius Developer is $49/month and includes Preprocessed Transactions.
- Helius Business is $499/month and includes mainnet LaserStream gRPC.
- Helius Professional is $999/month and is the entry tier for Preconfirmations.
- Helius Preprocessed Transactions are available on paid plans and are earlier than processed commitment.
- BAM Preconfirmations sit upstream of shreds and have partial validator coverage.
- Jito Block Engine supports Singapore and Tokyo and runs parallel auctions at 50ms ticks.

Treat every price/feature above as a current snapshot, not a permanent constant.

---

# 36. Source of Truth

Official infrastructure/protocol documentation should outrank:

1. official docs;
2. official GitHub;
3. peer-reviewed / reproducible research;
4. credible engineering writeups;
5. community experiments;
6. X/YouTube claims;
7. screenshots.

YouTube/X/Reddit are excellent hypothesis generators.

They are not evidence until the hypothesis survives our forward tape.

---

# 37. Final Doctrine

**Research before speed.**

**Causality before correlation.**

**Executable prices before candles.**

**Source quality before follower count.**

**Reject-book performance before confidence.**

**Portfolio risk before strategy enthusiasm.**

**Measured Value of Latency before infrastructure spend.**

**Deterministic execution before agent autonomy.**

**Stay flat when the edge is not proven.**
