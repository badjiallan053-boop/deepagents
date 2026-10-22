"""Flagship: 'TRIAGE OS - Credit & Forced-Seller Intelligence'. Merges World v2 (restructuring calendar, control
maps, prices/gaps), forced-seller layers (BDC queues, China NPL, HK banks, UK DB pensions, EU CLOs, J-REITs, short
crowding), the cross-asset radar as context only (no alpha claim), positioning, pricing, design partners, 90-day plan
and an honest credibility section. Facts are pulled from the verified JSON/markdown built in earlier passes."""
import json, os, re, sys, datetime
R = os.path.dirname(os.path.abspath(__file__)); H = os.path.dirname(R); D = "/workspace/triage_os_data"
sys.path.insert(0, H)
def sec(md, title_start):
    """Return the body of the '## ' section whose heading starts with title_start (without the heading)."""
    t = open(f"{R}/{md}").read(); parts = re.split(r"(?m)^## ", t)
    for p in parts:
        if p.startswith(title_start): return p.split("\n", 1)[1].strip()
    return f"_(section '{title_start}' not found in {md})_"
def main():
    W = json.load(open(f"{D}/world.json")); S = json.load(open(f"{D}/signals.json"))["signals"]; SC = json.load(open(f"{D}/shorts_crowding.json"))
    PIT = json.load(open(f"{D}/pit.json")) if os.path.exists(f"{D}/pit.json") else {}
    V4 = json.load(open(f"{D}/xasset/v4/log.json")) if os.path.exists(f"{D}/xasset/v4/log.json") else {}
    import committee as C; ok, n = C.verify()
    kept = [s for s in S if s["status"] == "KEPT"]; killed = [s for s in S if s["status"] == "KILLED"]
    L = ["# TRIAGE OS - Credit & Forced-Seller Intelligence", "",
         "_As of 23 Oct 2026 (SGT). Public data only; every situation fact was re-fetched on 23 Oct with URL, fetch time and exact quote (appendix of the World v2 file). JUDGEMENT marks our reads. Not investment advice; nothing here was sent to anyone._", "",
         "## 1. What TRIAGE is (positioning)", "",
         "**TRIAGE tells credit and special-situations desks who is forced to sell, who decides the outcome, and when, across 12 markets outside the US plus the US private-credit complex.** Three products, one dataset:", "",
         "1. **Worldwide restructuring calendar**: 25 live non-US situations with the next court/vote/consent date, the voting threshold that decides it, and a public price where one exists (with the recovery-vs-price gap only when both are sourced).",
         "2. **Control maps**: who holds the blocking or directing position (Class A/super-senior ≥66.66% at Thames, 25% hybrid blocker at BayWa/Kronos EKS, backstop group 93.4% at Bigben, CMBS directing holders).",
         "3. **Forced-seller layer (weekly)**: holders who *must* sell or buy regardless of price: non-traded BDC redemption queues and mark cliffs, China bank NPL transfers, Hong Kong classified loans, UK DB pension illiquid sales, 2021–22 vintage European CLOs, J-REIT leverage, crowded disclosed short positions (forced buy-in risk) and estate distributions.", "",
         "**What it is not:** the cross-asset radar is context (macro regime, forced-flow backdrop). After honest testing it is **not** an alpha product (section 7).", "",
         "## 2. The restructuring calendar (25 live non-US situations)", "", sec("triage_world.md", "3. The 25"), "",
         "## 3. Prices and recovery gaps", "", sec("triage_world.md", "5. Prices"), "",
         "## 4. Control maps", "", sec("triage_world.md", "6. Control maps"), "",
         "## 5. Forced sellers: the weekly layer", "",
         "### 5a. US private credit: non-traded BDC queues and mark cliffs", "", sec("systemic_radar.md", "3. Thesis 1")[:6000], "",
         "### 5b. China NPL, HK banks, UK DB pensions, EU CLOs, J-REITs", "", sec("triage_world.md", "4. Weekly layer"), "",
         "### 5c. Crowded short positions (forced buy-in watch): France AMF and Netherlands AFM registers", "",
         f"Public registers of net short positions ≥0.5% of share capital: {SC['positions']:,} position records across {SC['n_issuers']} issuers (AMF since Nov 2012; AFM history). Aggregate disclosed short per issuer at 30 Sep 2026:", "",
         "| Issuer | Country | Disclosed net short (% of capital) |", "|---|---|---|"] + [f"| {x['name']} | {x['country']} | {x['short_pct']}% |" for x in SC["live_crowded"][:12]] + ["",
         f"**Backtest (honest):** issuers whose disclosed short first crosses 5%: OOS 2019+ n={SC['stats']['OOS_x60']['n']}, {SC['stats']['OOS_x60']['pct_up']}% beat the country ETF at 60 days, mean {SC['stats']['OOS_x60']['mean']}% (t={SC['stats']['OOS_x60']['t']}); in-sample n={SC['stats']['IS_x60']['n']}, mean {SC['stats']['IS_x60']['mean']}%. There is no squeeze edge and no reliable short-side edge either, so we use crowding as a *risk flag* for desks (buy-in and recall exposure), not as a trade signal. {len(SC['unresolved'])} issuers could not be priced (many delisted). That is a survivorship gap, stated.", "",
         "### 5d. Estate distributions", "", "Crypto estate and government-wallet distributions (e.g. bankruptcy-estate repayments) are in scope for the Crypto Flows desk. **No estate facts are claimed in this edition**: none were re-verified from court or trustee primary sources today. Listed as a gap.", "",
         "## 6. Macro and forced-flow context (radar, not alpha)", "",
         "Regime (Dalio-style, sources in the radar file): US 10y real yield 2.77% (99th percentile, 20y), HY OAS 3.27% (+0.30pp y/y), 10y–2y +0.32pp, USD reserve share 56.7% (IMF COFER 2026-Q2, −2.2pp in two years), commodities cheap vs equities (13th percentile). Use: it tells a credit desk whether forced selling is likely to be absorbed (easy liquidity) or to cascade (restrictive real rates + widening spreads).", "",
         "## 7. Credibility: what we tested, what we killed, what we can prove", "",
         f"- **Signal library:** {len(S)} cross-asset signals tested with publication lags, costs and a fixed out-of-sample rule. **{len(kept)} kept ({', '.join(s['id'] for s in kept) or 'none'}), {len(killed)} killed**, the rest fragile or untested. Short-crowding (5c) and district staking surges were also killed. Every kill is published in the Radar file.",
         f"- **Point-in-time rebuild:** {PIT.get('summary', 'ALFRED vintages pending')}",
         "- **Committee (multi-agent debate, adapted from AlphaAgents arXiv:2508.11152):** after costs it does **not** beat an equal-weight benchmark out of sample. We say so.",
         f"- **Verified forward ledger:** {n} paper-only calls in a SHA-256 hash chain (verified = {ok}), anchored daily at 23:30 SGT with OpenTimestamps in Bitcoin; anyone can check it with `verify_ledger.py` (ledger_proofs/README.md). This is the credibility asset: a dated record that cannot be back-filled.",
         "- **Quant Validation agent has veto:** nothing is shown as recommendation-grade unless KEPT, ≥8 OOS events, stated OOS window and point-in-time data.", "",
         "## 8. Pricing (JUDGEMENT, anchored on a verified comparable)", "",
         f"Anchor: Debtwire subscription £39.6k/yr (verified in World v2). TRIAGE prices under it for breadth, over it for control maps.", "",
         "| Tier | Who | What | Price (JUDGEMENT) |", "|---|---|---|---|",
         "| Watchlist | Credit PMs, family offices | Weekly calendar + forced-seller note (PDF/email), app read-only | £12k/yr |",
         "| Desk | Special-sits / distressed teams (≤10 seats) | Full app: control maps, prices/gaps, alerts on dates and thresholds, sourcing log, analyst Q&A | £36k/yr |",
         "| Data licence | Funds, banks, data platforms | API/flat files: calendar, control holders, forced-seller series, ledger | £75k–£120k/yr |",
         "| Pilot | Design partners | 60-day Desk access, weekly call, feedback rights | £5k (credited to year 1) |", "",
         f"Revenue scenarios from World v2 (year 1, JUDGEMENT): bear £{W['scenarios'][0]['arr']}k, base £{W['scenarios'][1]['arr']}k, bull £{W['scenarios'][2]['arr']}k ARR.", "",
         "## 9. First 10 design-partner targets by region (firms only; nothing sent)", "",
         "| # | Region | Firm | Why them (situation in the calendar) |", "|---|---|---|---|"]
    picks = [("UK", "Attestor"), ("UK", "Arini"), ("UK", "Davidson Kempner (London)"), ("UK/DE", "Strategic Value Partners Europe"), ("Nordics", "Cheyne Capital"),
             ("France", "Tikehau Capital"), ("Spain", "Värde Partners Europe"), ("Italy", "Hayfin"), ("Hong Kong/China", "ADV Partners"), ("Pan-Europe", "Ares Europe")]
    B = {b["firm"]: b for b in W["buyers"]}
    for i, (reg, f) in enumerate(picks, 1):
        b = B.get(f, {}); L.append(f"| {i} | {reg} | {f} ({b.get('base','')}) | {b.get('situation','')} |")
    L += ["", "Japan (Kizuna, J-REIT) and Singapore (mm2 Asia) have no named partner yet: a gap to fill from the Japan/SG desk.", "",
          "## 10. 90-day plan to paid pilots", "",
          "| Days | Milestone | Exit test |", "|---|---|---|",
          "| 0–15 | Freeze the Desk product on the 25 situations + weekly forced-seller note; Quant Validation sign-off; ledger running daily | Two consecutive weekly notes published internally with zero unsourced facts |",
          "| 15–30 | User sends intros/outreach to the 10 targets (you send; TRIAGE drafts only) | 5 first calls booked |",
          "| 30–60 | 3–5 design partners on the £5k pilot; each picks 3 situations they care about; we add their markets | ≥3 pilots signed; ≥1 situation where TRIAGE flagged a date/threshold before the partner's existing provider |",
          "| 60–90 | Convert to Desk (£36k) or Data licence; collect written feedback/LOIs | 2–3 paid pilots → £150k ARR in signed LOIs (the fundraising milestone from World v2) |", "",
          "## 11. Data added this pass and gaps", "", "| Dataset | Rows | Source | Note |", "|---|---|---|---|"]
    for k, v in sorted(V4.items()): L.append(f"| {k} | {v['rows']:,} | {v['src'][:80]} | {v.get('note','')} |")
    L += ["", "Gaps: FCA (UK) short-position file returns 403 to the box; BaFin/Bundesanzeiger (DE) needs JavaScript; CNMV (ES) and Consob (IT) pages need interactive search (not scraped). CME depository reports return 403; LME stocks are paid. EDINET API needs a free key (account); TDnet has no free bulk feed. Estate distributions are not verified. Comtrade preview is capped at 500 rows per call. Survivorship gap in short-crowding prices.", "",
          "## 12. Team", "", "Desk agents now in team.py: Quant Validation (veto), Commodities & Shipping, Crypto Flows, Macro Regime, Mining Geologist, Ledger & Compliance (veto on anything that reads as personal advice)."]
    m = "\n".join(L); open(f"{R}/flagship.md", "w").write(m)
    from design import report_from_markdown
    report_from_markdown(m, "TRIAGE OS - Credit & Forced-Seller Intelligence", "Flagship · 23 Oct 2026", "Who is forced to sell, who decides, and when, across 12 markets and US private credit",
        [("Core", "Restructuring calendar · control maps · forced sellers"), ("Proof", f"{n}-call hash-chained ledger, OpenTimestamps"), ("Rules", "public data · firms only · nothing sent")],
        f"{R}/TRIAGE_OS_Credit_Forced_Seller_Intelligence.html", f"{R}/TRIAGE_OS_Credit_Forced_Seller_Intelligence.pdf")
    json.dump(dict(asof="2026-10-23", positioning="Who is forced to sell, who decides, and when.", tiers=[("Watchlist", "£12k/yr"), ("Desk", "£36k/yr"), ("Data licence", "£75k–£120k/yr"), ("Pilot", "£5k / 60 days")],
                   partners=[dict(region=r, firm=f, situation=B.get(f, {}).get("situation", "")) for r, f in picks], crowded=SC["live_crowded"][:12], short_bt=SC["stats"],
                   ledger=dict(n=n, ok=ok), kept=[s["id"] for s in kept], killed=[s["id"] for s in killed], pit=PIT, datasets=V4,
                   situations=[dict(entity=s["entity"], country=s["country"], date=s["date"], basis=s["basis"], price=s["price"], gap=s["gap"]) for s in W["situations"]]),
              open(f"{D}/flagship.json", "w"), indent=1, ensure_ascii=False, default=str)
if __name__ == "__main__": main()
