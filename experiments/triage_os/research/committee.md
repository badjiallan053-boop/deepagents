
## TRIAGE Alpha Committee (adapted from AlphaAgents, arXiv:2508.11152)

Source paper: Zhao, Lyu, Jones, Garber, Pasquali, Mehta (BlackRock), *AlphaAgents: Large Language Model based Multi-Agents for Equity Portfolio Constructions*, arXiv:2508.11152v1, https://arxiv.org/html/2508.11152v1 (read in full 23 Oct 2026).

**What we kept from the paper:** role agents with data access restricted to their role (paper Table 1); the paper's coordinator prompt for debate ("every agent ... has a chance to speak at least twice. Each agent can not decide for the whole group ... You must invoke all agents before deciding to Terminate"); round-robin debate to consensus; explicit risk-neutral vs risk-averse profiles (§2.3); equal-weight portfolios from agent picks compared with single-agent portfolios and the benchmark using return and Sharpe (§3.2, §4.3); full debate logs kept for review.

**Role mapping:** paper Fundamental → *Forced Seller* (who must sell, from credit-spread shocks) and *LME* (CFTC managed-money positioning); paper Sentiment → *Signal/Radar* (trend/flow) and *Contrarian* (crowding); paper Valuation → *Valuation* (annualised return and volatility tools, exactly the paper's §2.2.3 formulas); added Macro (Dalio regime), which the paper names as future work.

**What we changed, and why (honest):** the agents are deterministic tool-based rules, not LLM calls. An LLM committee backtested on 2012–2026 would already 'know' those years from training data, so its backtest would be contaminated. The paper's prompts and our role prompts are stored in `committee.py` (PROMPTS) for a later LLM backend that runs only forward (live, paper-only). Debate rule: an agent whose conviction is below the mean conviction of disagreeing peers withdraws; nobody adopts a view without evidence; unresolved → majority, and the risk-averse profile takes no position on any dissent.

### Backtest — monthly, 22 cross-asset instruments, 2012-02-29 → 2026-09-30, long-only equal-weight, cash when no BUY

**risk-neutral, full period**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 9.0% | 13.1% | 0.69 | -28.5% |
| Equal-weight benchmark | 8.5% | 13.2% | 0.65 | -29.1% |
| Single agent: signal | 10.4% | 19.6% | 0.53 | -44.5% |
| Single agent: valuation | 8.6% | 16.2% | 0.53 | -41.8% |
| Single agent: contrarian | -2.3% | 11.7% | -0.19 | -46.5% |
| Single agent: forced_seller | 0.1% | 0.4% | 0.26 | 0% |
| Single agent: lme | -4.1% | 17.9% | -0.23 | -63.4% |
| Single agent: macro | 1.0% | 2.5% | 0.39 | -1.6% |

**risk-neutral, 2021 onward (rules fixed before; treat as out-of-sample)**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 10.2% | 14.9% | 0.68 | -28.5% |
| Equal-weight benchmark | 11.9% | 13.3% | 0.89 | -18.3% |
| Single agent: signal | 5.7% | 18.9% | 0.3 | -44.5% |
| Single agent: valuation | 12.6% | 17.3% | 0.73 | -31.6% |
| Single agent: contrarian | 2.6% | 10.2% | 0.26 | -10.5% |
| Single agent: forced_seller | 0.3% | 0.7% | 0.42 | 0% |
| Single agent: lme | -1.0% | 14.2% | -0.07 | -23.1% |
| Single agent: macro | 2.5% | 4.0% | 0.63 | -1.6% |

Committee BUY calls: 1988; share that beat the equal-weight month: 47%.

**risk-averse, full period**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 7.4% | 14.0% | 0.53 | -38.5% |
| Equal-weight benchmark | 8.5% | 13.2% | 0.65 | -29.1% |
| Single agent: signal | 10.4% | 19.6% | 0.53 | -44.5% |
| Single agent: valuation | 6.3% | 10.0% | 0.63 | -27.6% |
| Single agent: contrarian | -2.3% | 11.7% | -0.19 | -46.5% |
| Single agent: forced_seller | 0.1% | 0.4% | 0.26 | 0% |
| Single agent: lme | -4.1% | 17.9% | -0.23 | -63.4% |
| Single agent: macro | 1.0% | 2.5% | 0.39 | -1.6% |

**risk-averse, 2021 onward (rules fixed before; treat as out-of-sample)**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 10.1% | 13.3% | 0.76 | -21.5% |
| Equal-weight benchmark | 11.9% | 13.3% | 0.89 | -18.3% |
| Single agent: signal | 5.7% | 18.9% | 0.3 | -44.5% |
| Single agent: valuation | 13.0% | 9.5% | 1.38 | -11.0% |
| Single agent: contrarian | 2.6% | 10.2% | 0.26 | -10.5% |
| Single agent: forced_seller | 0.3% | 0.7% | 0.42 | 0% |
| Single agent: lme | -1.0% | 14.2% | -0.07 | -23.1% |
| Single agent: macro | 2.5% | 4.0% | 0.63 | -1.6% |

Committee BUY calls: 1753; share that beat the equal-weight month: 47%.

**Honest result:** over the full period the risk-neutral committee edges the equal-weight benchmark (Sharpe 0.69 vs 0.65, max drawdown -28.5% vs -29.1%) and beats every single agent on Sharpe. From 2021 it **underperforms** the benchmark (Sharpe 0.68 vs 0.89), and the single Valuation agent is better than the committee (Sharpe 0.73; risk-averse 1.38). Only 47% of committee picks beat the equal-weight month. The paper's headline (multi-agent beats single agents and benchmark) is **not reproduced out-of-sample** here; debate mainly cuts drawdown versus single agents. Contrarian and LME agents lose money alone. This is why the product proof is the forward, hash-chained record, not this backtest.

### PAPER-ONLY live track record (hash-chained)

Ledger `track_record.jsonl`: 32 calls, chain verified = True. Each record holds entry (last public close), thesis (each agent's view), catalyst, exit rule, benchmark, previous hash and SHA-256 hash, logged in SGT. No trades placed; not advice to anyone.

| # | Kind | Instrument | Call | Entry | Entry date | Exit rule |
|---|---|---|---|---|---|---|
| 1 | cross-asset | SPY | BUY | 763.7 | 2026-10-22 | close at the next month-end committee or if th |
| 2 | cross-asset | EEM | SELL | 61.74 | 2026-10-22 | close at the next month-end committee or if th |
| 3 | cross-asset | I_HSI | SELL | 2.365e+04 | 2026-10-21 | close at the next month-end committee or if th |
| 4 | cross-asset | I_N225 | BUY | 6.462e+04 | 2026-10-21 | close at the next month-end committee or if th |
| 5 | cross-asset | I_STOXX50E | SELL | 6087 | 2026-10-22 | close at the next month-end committee or if th |
| 6 | cross-asset | COPX | SELL | 73.34 | 2026-10-22 | close at the next month-end committee or if th |
| 7 | cross-asset | SIL | SELL | 76.16 | 2026-10-22 | close at the next month-end committee or if th |
| 8 | cross-asset | URA | SELL | 34.15 | 2026-10-22 | close at the next month-end committee or if th |
| 9 | cross-asset | REMX | SELL | 51.63 | 2026-10-22 | close at the next month-end committee or if th |
| 10 | cross-asset | HYG | SELL | 77.1 | 2026-10-22 | close at the next month-end committee or if th |
| 11 | cross-asset | JNK | SELL | 92.56 | 2026-10-22 | close at the next month-end committee or if th |
| 12 | cross-asset | TLT | BUY | 81.64 | 2026-10-22 | close at the next month-end committee or if th |
| 13 | cross-asset | IEF | BUY | 91.24 | 2026-10-22 | close at the next month-end committee or if th |
| 14 | cross-asset | GLD | BUY | 370.5 | 2026-10-22 | close at the next month-end committee or if th |
| 15 | cross-asset | BTC-USD | SELL | 8.122e+04 | 2026-10-22 | close at the next month-end committee or if th |
| 16 | cross-asset | CL_F | BUY | 99.36 | 2026-10-22 | close at the next month-end committee or if th |
| 17 | cross-asset | HG_F | BUY | 6.418 | 2026-10-22 | close at the next month-end committee or if th |
| 18 | cross-asset | SI_F | BUY | 55.01 | 2026-10-22 | close at the next month-end committee or if th |
| 19 | cross-asset | NG_F | SELL | 2.819 | 2026-10-22 | close at the next month-end committee or if th |
| 20 | cross-asset | ZS_F | SELL | 1254 | 2026-10-22 | close at the next month-end committee or if th |
| 21 | cross-asset | ZW_F | BUY | 625.5 | 2026-10-22 | close at the next month-end committee or if th |
| 22 | credit-situation | Bigben Interactive — BIG.PA shares | WATCH | 0.069 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 23 | credit-situation | Nacon (56.72% owned by Bigben) — NACON.PA shares | WATCH | 0.053 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 24 | credit-situation | Agile Group — 6.875% senior perpetual (XS1785422 | AVOID (price > recovery) | 0.375 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 25 | credit-situation | BayWa / Kronos EKS €100m hybrid (DE000A351PD9) — | WATCH | 6 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 26 | credit-situation | Booster Precision Components (€60m bond NO001271 | WATCH | 39 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 27 | credit-situation | Zhenro Properties — 6158.HK shares | WATCH | 0.017 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 28 | credit-situation | KWG Group — 1813.HK shares | WATCH | 0.088 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 29 | credit-situation | Redco Properties — 1622.HK shares | WATCH | 0.141 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 30 | credit-situation | VPower Group — 1608.HK shares | WATCH | 0.031 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 31 | credit-situation | Branicks Group (€400m bond) — BRNK.DE shares | WATCH | 0.41 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 32 | credit-situation | China Aoyuan (secured assets) — 3883.HK shares | WATCH | 0.031 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |

First hash 891dbead90cbf53a… → last hash ce04c096409fd7d7…. To make the record externally verifiable, publish each day's last hash somewhere timestamped (e.g. a public git commit or an OpenTimestamps proof) — a user action, not done.

### Monetisation (JUDGEMENT) — the track record is the product proof

1. **Signal subscription** (impersonal, same feed to all subscribers; no personalised recommendations): radar + committee calls + mining layer. Fits the publisher-style exclusions below only if it stays impersonal and regularly published.
2. **Model-portfolio licence** to managers/platforms who run the money themselves (B2B data/IP licence). Still check per jurisdiction whether the licensee relationship counts as advice.
3. **Later: SMA or fund** — needs a licence in each place the money is managed or marketed. The user must handle this with counsel; nothing here is legal advice.

| Jurisdiction | Source (fetched 23 Oct 2026) | Grade | Exact quote | What it means for TRIAGE |
|---|---|---|---|---|
| Singapore (MAS) | https://sso.agc.gov.sg/Act/SFA2001?ProvIds=Sc2- | PRIMARY (statute) | “fund management” means managing the property of, or operating, a collective investment scheme, or undertaking on behalf of a customer ... the management of a portfolio of capital markets products | An SMA or fund run from Singapore = regulated activity 'fund management' → capital markets services licence (or registered/licensed fund manager regime). Paid recommendations to Singapore clients may also be a financial advisory service under the Financial Advisers Act — FAA text not retrieved today (sso.agc.gov.sg timed out; mas.gov.sg licensing page in maintenance), so treat as OPEN. |
| United Kingdom (FCA) | https://www.legislation.gov.uk/ukpga/2000/8/section/19 | PRIMARY (statute) | No person may carry on a regulated activity in the United Kingdom, or purport to do so, unless he is— (a) an authorised person; or (b) an exempt person. | Managing an SMA/fund needs Part 4A permission. A non-personalised periodical/data service can fall in the RAO art. 54 exclusion (below) only if its principal purpose is not advice or leading persons to buy/sell; personal recommendations are carved out (art. 54(2A)). |
| United Kingdom (FCA) | https://www.legislation.gov.uk/uksi/2001/544/article/54 | PRIMARY (statute) | Paragraphs (1) and (2) do not apply to advice which is a personal recommendation falling within article 53(1A). | Signal subscriptions must stay non-personalised; FCA can certify a publication under art. 54(3). |
| United States (SEC) | https://www.law.cornell.edu/uscode/text/15/80b-2 | SECONDARY copy of statute (LII) | publisher of any bona fide newspaper, news magazine or business or financial publication of general and regular circulation | Advisers Act §202(a)(11)(D) publisher exclusion covers impersonal, regularly published research; an SMA or tailored advice requires SEC or state investment-adviser registration. |
| United States (CFTC) | https://www.law.cornell.edu/cfr/text/17/4.14 | SECONDARY copy of regulation (LII) | Providing commodity trading advice based on, or tailored to, the commodity interest or cash market positions or other circumstances or characteristics of particular clients | 17 CFR 4.14(a)(9): CTA registration exemption only if advice is not tailored and no client accounts are directed. Futures-based model portfolios or managed futures accounts → CTA/CPO registration with the CFTC/NFA. |

Gates before any money: (a) 12+ months of forward paper calls with the chain anchored publicly; (b) hit rate and excess return reported net of costs vs the stated benchmark; (c) a licensing opinion for each target jurisdiction.