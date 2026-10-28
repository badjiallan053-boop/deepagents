"""Builds the signal-library / committee-v2 / proofs / gap-audit / agents section of TRIAGE Cross-Asset Radar."""
import json, os, glob, subprocess
D = "/workspace/triage_os_data"; R = os.path.dirname(os.path.abspath(__file__)); H = os.path.dirname(R)
S = json.load(open(f"{D}/signals.json"))["signals"]; V2 = json.load(open(f"{D}/committee_v2.json"))
LOG = {}
for p in glob.glob(f"{D}/xasset/v3/log.json"): LOG.update(json.load(open(p)))
GAPS = [  # (what, why a buyer cares, free source?, status)
 ("Point-in-time database (as-first-published values, vintages)", "Revised macro/positioning data inflate backtests", "ALFRED vintages (FRED) free", "MISSING — biggest methodological gap"),
 ("Survivorship-bias control", "Index/ETF lists today exclude dead names", "Wikipedia S&P changes, delisted prices (paid)", "MISSING — S&P inclusion signal not built for this reason"),
 ("Transaction costs and capacity", "A signal that can't be traded at size is worthless", "Spreads from exchange data (paid); bp assumptions", "PARTIAL — flat bp costs + short borrow; no capacity model"),
 ("Multiple-testing control", "23 signals tested → some pass by luck", "Deflated Sharpe / Bonferroni", "PARTIAL — t-stats shown; no deflation"),
 ("AIS ship tracking / port congestion", "Physical flows lead prices for oil, LNG, grains, metals", "AISHub (exchange), NOAA MarineCadastre (US, lagged), UN Global Platform", "MISSING"),
 ("Sentinel-1 SAR (oil tank floating roofs, stockpiles)", "Storage without clouds", "Copernicus/Earth Search sentinel-1-grd", "MISSING"),
 ("Customs data (China GACC, Comtrade monthly)", "Export-control effects show up in tonnages", "UN Comtrade (free tier, key), GACC site", "MISSING"),
 ("LME/SHFE/CME warehouse stocks & cancelled warrants", "Squeeze precursors in metals", "LME (paid/delayed), SHFE weekly PDFs (free), CME depository reports (free xls)", "MISSING — CME xls is the top free next step"),
 ("JODI oil, USDA WASDE", "Global balances", "JODI csv (free), USDA WASDE xml (free)", "MISSING"),
 ("TIC foreign holdings, ECB SDW, BoJ", "Who must sell Treasuries/JGBs", "treasury.gov TIC (free), ECB data portal API (free), BoJ time-series (free)", "PARTIAL — OECD 10y yields via FRED only"),
 ("Sovereign CDS", "Default-risk pricing", "Paid (Markit)", "MISSING (paid)"),
 ("ESMA/FCA net short positions, Japan TDnet, HKEX DI, EDINET large holdings", "Forced covering / stake-building", "FCA daily xlsx (free), HKEX DI (free), EDINET API (free key)", "MISSING — FCA short-position xlsx is the top free next step"),
 ("Crypto: ETF flows, token unlocks, estate (Mt Gox/FTX) & government wallets", "Mechanical supply", "Issuer sites (free), on-chain explorers", "MISSING (funding/OI/stablecoins only)"),
 ("Power & grid (ENTSO-E, EIA-930)", "Industrial activity, data-centre load", "ENTSO-E (free key), EIA-930 (free)", "MISSING"),
 ("Patents, job postings, app data", "Alt-data growth signals", "USPTO/EPO bulk (free), job boards (ToS), app data (paid)", "MISSING"),
 ("ECB bank stress / EBA transparency", "Bank forced sellers", "EBA transparency exercise CSVs (free)", "MISSING"),
 ("Night lights (VIIRS Black Marble)", "Operating activity", "NASA LAADS (Earthdata login)", "MISSING — needs Earthdata account (user)"),
 ("Geology (MRDS/USMIN), GA, provincial registries", "Deposit join for staking signal", "USGS (403 to box), GA (403)", "BLOCKED from box — try from user's machine"),
]
AGENTS = [
 ("Quant Validation", "Owns backtest hygiene for every signal and committee: point-in-time data (ALFRED vintages), publication lags, survivorship, multiple-testing (deflated Sharpe), cost and capacity models, and the kill rule. Nothing reaches the PDF or the ledger without its sign-off; it may only veto, never add signals. This is the agent a Citadel or Elliott diligence team would ask to meet first."),
 ("Commodities & Shipping desk", "Ingests physical-flow data — EIA/JODI/WASDE balances, CME/SHFE warehouse stocks and cancelled warrants, AIS/port congestion, Sentinel-1 storage — and maintains the commodity signals (S1–S4, S16). Output: weekly balance tables and squeeze watchlist for trading houses."),
 ("Crypto Flows desk", "Tracks mechanical crypto supply/demand: stablecoin mint/burn, perp funding and OI, ETF creations/redemptions, token unlock calendars, estate and government wallet movements. Maintains S10–S13 and owns the on-chain source list and its address labels."),
 ("Macro Regime agent", "Maintains the Dalio-style regime dashboard (real rates, credit, curve, debasement, COFER, central-bank gold, liquidity) with point-in-time vintages, and supplies the regime vote in the committee. Publishes a one-page regime note weekly."),
 ("Mining Geologist", "Joins deposits (MRDS/USMIN, GA, provincial databases, historical reports) to tenure (BLM MLRS, state/provincial registries) and owners (SEDAR+/ASX). Maintains the staking signals (S17, S20) and the satellite site list; flags controlled-mineral deposits on lapsed ground."),
 ("Ledger & Compliance clerk", "Runs the daily OpenTimestamps anchor, checks the chain, keeps every published call impersonal (no personalised advice), and keeps the licensing memo current. Escalates anything that looks like advice to a person."),
]
def tbl(s, k):
    x = s[k]
    return "—" if not x.get("n") else f"{x['n']} / {x.get('precision')}% / {x.get('mean_excess'):+.2f}% / t={x.get('t_stat')}"
def main():
    L = ["## Signal library: 23 cross-asset signals, backtested, kill rule applied", "",
         "Method: event = first trigger after a cooldown of h days; entry at the first close after publication; the excess move is drift-adjusted and signed; precision = share of events with positive excess; costs are deducted per event. **KEPT** = OOS mean > 0 and OOS precision ≥ 52%, and in-sample agrees. **FRAGILE** = OOS passes but in-sample disagrees. **UNTESTED** = fewer than 8 OOS events. **KILLED** = fails OOS. Rules were set before the OOS numbers were read; nothing was re-tuned after (S3 lost KEPT when a data error was fixed: the 20 Apr 2020 negative WTI print had produced a +154% 'event').", "",
         "| ID | Class | Signal (trigger → trade) | h | IS n / prec / mean / t | OOS n / prec / mean / t | Verdict | Live now |", "|---|---|---|---|---|---|---|---|"]
    for s in S:
        L.append(f"| {s['id']} | {s['cls']} | {s['trigger'][:90]} | {s['h']}d | {tbl(s,'in_sample')} | {tbl(s,'oos')} (OOS from {s['oos_start'][:10]}) | **{s['status']}** | {'FIRED' if s['live']['fired'] else '—'}: {s['live']['detail'][:70]} |")
    k = [s for s in S if s["status"] == "KEPT"]; f = [s for s in S if s["status"].startswith("FRAGILE")]; u = [s for s in S if s["status"].startswith("UNTESTED")]; x = [s for s in S if s["status"] == "KILLED"]
    L += ["", f"**Score:** {len(k)} kept ({', '.join(s['id'] for s in k)}), {len(f)} fragile ({', '.join(s['id'] for s in f)}), {len(u)} untested ({', '.join(s['id'] for s in u)}), {len(x)} killed ({', '.join(s['id'] for s in x)}).", "",
          "**Honest read:** only S21 (Fed net liquidity, WALCL − RRP) survives, and its OOS is dominated by the 2020–21 QE window. Its events from 2022 onward lose money, so treat it as regime-conditional. Killed: COT crowded-long fade, EIA crude surprise, NG storage, copper/gold → yields, stablecoin impulse, negative funding, JGB jump, real-rate → gold, and both staking signals (S17 district surges −11% vs GDXJ at 60d across 19 events; S20 national surges). Most mechanisms in the library are well known and already priced. The edge has to come from data others do not have (gap audit below), not from re-testing public series.", "",
          "### Staking-surge backtest (S17): dated claims from the BLM MLRS hub 'Created' field", "",
          "BLM's public MLRS layers carry no location date, but the national hub FeatureServers do carry a record `Created` date. For MLRS-native serials (no legacy LR2000 number) this is the date the claim was filed into MLRS, so it is usable from 2021 onward. Legacy records were migrated in bulk and are excluded. LR2000 case recordation dates sit behind the interactive reports.blm.gov forms and were not scraped.", "",
          "| District | Ticker | Month after surge | New claims | Excess vs GDXJ +20d | +60d |", "|---|---|---|---|---|---|"]
    st17 = next(s for s in S if s["id"] == "S17")
    for r in st17.get("staking_events", []): L.append(f"| {r['site']} | {r['ticker']} | {r['month']} | {r['claims']} | {r.get('x20','n/a')}% | {r.get('x60','n/a')}% |")
    L += ["", "Result: KILLED. The surges come *after* the nearby developer has already re-rated (staking follows price), so buying the developer after the surge loses. The inverse (fade) is not tested here, because testing it after seeing this result would be data-snooping.", "",
          "### Top 10 live signals (ranked: verdict tier, then distance to trigger)", "",
          "No KEPT or candidate signal is firing today (23 Oct 2026). Ranking by how close each credible signal is to firing:", "",
          "| Rank | Signal | Verdict | Now | Trigger | Distance |", "|---|---|---|---|---|---|",
          "| 1 | S21 Fed net liquidity → SPY | KEPT (regime-conditional) | +$13bn / 13w | +$200bn | far |",
          "| 2 | S6 HYG vs IEF credit flush → buy HYG | UNTESTED (IS 59%/+1.5%, OOS 7 events 71%/+1.0%) | −2.0% / 22d | −4% | halfway |",
          "| 3 | S8 Dollar squeeze → short EEM | FRAGILE | DXY +0.1% / 3m | +5% | far |",
          "| 4 | S7 VIX>30 → long SPY | FRAGILE | VIX 16.7 | 30 | far |",
          "| 5 | S5 Weak long-end UST auction → short TLT | FRAGILE | last z +0.08 (8 Oct) | z < −1.5 | next 10y/30y auction |",
          "| 6 | S2 COT crowded short → long | FRAGILE | none ≤5th pctile | ≤5% | — |",
          "| 7 | S13 BTC OI +20%/7d → short | UNTESTED | +4.6% | +20% | far |",
          "| 8 | S15 BTP–Bund +40bp m/m → short EWI | UNTESTED | 0.80pp (Aug) | +0.40 m/m | far |",
          "| 9 | S23 STLFSI4 > 1 → long SPY 60d | UNTESTED | −0.63 | +1.0 | far |",
          "| 10 | S16 MOFCOM control → long REMX 5d | UNTESTED (3 OOS) | no new notice found | announcement | event-driven |", "",
          "Fired but KILLED (shown, not traded): S1 soybeans MM 97th pctile; S18 JGB +38bp/3m; S20 national claims (October lower than average).", "",
          "## Alpha Committee v2: signals only, costs included", "",
          "Tier A = KEPT signals only (S21). Tier B adds candidates whose IS and OOS means are both positive (S6, S8, S13, S15, S16, S23). **Tier B was chosen after seeing OOS, so its OOS number is biased upward. Treat it as an upper bound.** Daily book: equal weight across open trades, cash otherwise. Costs: 10 bp round trip (20 bp crypto), 5 bp/month short borrow. Agents abstain when they disagree on the same asset (paper's consensus rule). The risk-averse profile halves gross exposure.", "",
          "| Book (OOS 2019-01 → 2026-10) | CAGR | Vol | Sharpe | Max DD | Trades | 2022+ Sharpe |", "|---|---|---|---|---|---|---|"]
    for lab in ("v2_tierA_kept_only", "v2_tierA+B_candidates"):
        for prof in ("risk_neutral", "risk_averse"):
            a = V2[f"{lab}|{prof}"]; b = V2[f"{lab}|{prof}|2022+"]
            L.append(f"| {lab} · {prof} | {a['cagr']}% | {a['vol']}% | {a['sharpe']} | {a['maxdd']}% | {a['trades']} | {b['sharpe']} |")
    e = V2["equal_weight_universe|daily"]; e2 = V2["equal_weight_universe|2022+"]; v1 = V2["v1_rule_committee_net|monthly"]
    L += [f"| Equal-weight 22-asset benchmark | {e['cagr']}% | {e['vol']}% | {e['sharpe']} | {e['maxdd']}% | — | {e2['sharpe']} |",
          f"| Committee v1 (rule agents, monthly) net of costs | {v1['cagr']}% | {v1['vol']}% | {v1['sharpe']} | {v1['maxdd']}% | — | — |", "",
          "**Honest result:** after costs, no committee beats the equal-weight benchmark on Sharpe over 2019–2026. The tier-A book (S21 only) loses money from 2022. The biased tier-B book roughly matches the benchmark from 2022 with half the drawdown. The product claim therefore cannot be 'we have alpha' yet. It can be: (1) a verified, timestamped forward record; (2) forced-flow and credit-situation intelligence buyers can't easily assemble; (3) honest kill-lists that save a desk research time.", "",
          "## Public ledger proofs (OpenTimestamps)", "",
          f"Ledger: 39 paper calls (32 v1 + 7 v2 FLAT records), SHA-256 chain verified. Anchored 23 Oct 2026 with the OpenTimestamps reference client: only the digest of `ledger_proofs/2026-10-23.anchor.txt` (which contains the last hash) went to 4 public calendars. Status at build time: **pending Bitcoin confirmation** (normal; upgrade after a few hours). Outsider steps: `ledger_proofs/README.md` and `verify_ledger.py`. Daily anchoring is a manual or scheduled command (`anchor_ledger.py`). No scheduler has been set up yet.", "",
          "## Data added this pass", "", "| Dataset | Rows | Source | Fetched |", "|---|---|---|---|"]
    for k_, v in sorted(LOG.items()): L.append(f"| {k_} | {v['rows']:,} | {v['src'][:70]} | {v['fetched'][:16]} |")
    L += ["| FRED IT/DE/FR/GB 10y, WALCL, RRP, STLFSI4, DEXJPUS | 13,985 max | fred.stlouisfed.org/graph/fredgraph.csv | 2026-10-23 |",
          "", "NASA FIRMS: the MAP_KEY is issued only through an email form on firms.modaps.eosdis.nasa.gov/api/map_key/ (submitting it is an outbound action that needs your email; not done). The **no-key public 7-day VIIRS NOAA-20 global CSV** was ingested instead (478,400 detections): Kolwezi (DRC) 12, Bayan Obo 2, Mountain Pass 1, Norilsk 1 detection within ±0.15° this week. VIIRS night lights (Black Marble) need an Earthdata login (yours).", "",
          "## Gap audit: what a sceptical buyer (Citadel, Elliott, a sovereign fund, a trading house) would say is missing", "",
          "| Gap | Why it matters | Free source? | Status |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in GAPS]
    L += ["", "Top 5 free ingests done now: EIA weekly crude, EIA weekly gas storage, Treasury auction results (1,863), BLM MLRS dated claims (hub `Created`), NASA FIRMS VIIRS 7-day. Also: FRED sovereign/liquidity/stress series and 14 extra price series.",
          "Next free ingests by value: ALFRED point-in-time vintages, CME depository stocks, FCA short positions, EIA-930 grid, UN Comtrade (free key).", "",
          "## Recommended new agents (charters only; not created)", ""]
    L += [f"- **{a}.** {b}" for a, b in AGENTS]
    open(f"{R}/signals_v3.md", "w").write("\n".join(L))
    json.dump(dict(signals=S, v2=V2, gaps=[dict(gap=a, why=b, source=c, status=d) for a, b, c, d in GAPS], agents=[dict(name=a, charter=b) for a, b in AGENTS], datasets=LOG),
              open(f"{D}/signals_app.json", "w"), indent=1, default=str)
if __name__ == "__main__": main()
