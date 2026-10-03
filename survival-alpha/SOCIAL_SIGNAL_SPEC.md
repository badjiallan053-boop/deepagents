# Social Signal Spec — X + Reddit

## Principle

Social data is a **candidate generator and manipulation sensor**, never a trade-authority layer.

The service stores structured provenance and a normalized content fingerprint, not raw post text.
A social event can only produce `SAMPLE_QUOTES_ONLY`; it can never produce a buy/sell instruction.

## Why

Public evidence consistently shows three failure modes:

1. Social attention is frequently downstream of the price move.
2. Duplicate/copied promotion can create fake consensus.
3. High-PnL wallets and promoters may farm copy traders as exit liquidity.

So the first question is causal: **was the signal observable before the move and before our quote?**

## Current features

For each mint over the last 5 minutes:

- post count
- unique authors
- X/Reddit source diversity
- normalized duplicate-content ratio
- new-account share
- verified-author share
- contract-address-present share
- log-scaled engagement
- mention acceleration versus the previous 15 minutes

Outputs:

- `social_heat`
- `manipulation_risk`
- `social_candidate`

A candidate requires at least two recent posts from at least two authors, sufficient heat, and manipulation risk below the veto threshold.

## Causal ordering

The production paper tape must record these timestamps separately:

- social post published time
- social post observed time
- on-chain event time/slot
- our first Jupiter quote request time
- our first quote response time
- delayed quote times (500 / 1000 / 2000 ms)
- hypothetical sell-back quote time

A post that appears after the move is context, not alpha.

## The six irreversible gates

1. **Strategy spec** — frozen feature definitions and thresholds.
2. **Data provenance** — source IDs, timestamps, duplicate detection, no silent rewrites.
3. **Causal alignment** — signal must precede the action it is claimed to predict.
4. **Replay/backtest** — fees, drift, sellability, and cluster de-duplication included.
5. **Forward paper** — hundreds of forward observations, including rejected candidates.
6. **Risk/execution lock** — only a deterministic governor can ever arm execution later.

The current branch stops at Gate 5. There is no execution code.

## Next features to add after the forward tape exists

- cross-platform lead/lag score
- author historical hit-rate measured only on prior calls
- token co-mention graph
- repeated promoter / wallet-cluster overlap
- first-mover versus recycler classification
- social-to-organic-score divergence
- post-move FOMO detector
- round-trip sellability curve at multiple notionals

Do not add LLM sentiment as a primary signal until the causal and manipulation features have been evaluated out-of-sample.
