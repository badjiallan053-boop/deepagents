"""Writes the Alpha Committee section (markdown + app JSON) from committee.py outputs."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import committee as C
D = "/workspace/triage_os_data/committee"; R = os.path.dirname(os.path.abspath(__file__))
LIC = [  # fetched 23 Oct 2026; quote = exact text from the primary source
 ("Singapore (MAS)", "https://sso.agc.gov.sg/Act/SFA2001?ProvIds=Sc2-", "PRIMARY (statute)", "“fund management” means managing the property of, or operating, a collective investment scheme, or undertaking on behalf of a customer ... the management of a portfolio of capital markets products",
  "An SMA or fund run from Singapore = regulated activity 'fund management' → capital markets services licence (or registered/licensed fund manager regime). Paid recommendations to Singapore clients may also be a financial advisory service under the Financial Advisers Act — FAA text not retrieved today (sso.agc.gov.sg timed out; mas.gov.sg licensing page in maintenance), so treat as OPEN."),
 ("United Kingdom (FCA)", "https://www.legislation.gov.uk/ukpga/2000/8/section/19", "PRIMARY (statute)", "No person may carry on a regulated activity in the United Kingdom, or purport to do so, unless he is— (a) an authorised person; or (b) an exempt person.",
  "Managing an SMA/fund needs Part 4A permission. A non-personalised periodical/data service can fall in the RAO art. 54 exclusion (below) only if its principal purpose is not advice or leading persons to buy/sell; personal recommendations are carved out (art. 54(2A))."),
 ("United Kingdom (FCA)", "https://www.legislation.gov.uk/uksi/2001/544/article/54", "PRIMARY (statute)", "Paragraphs (1) and (2) do not apply to advice which is a personal recommendation falling within article 53(1A).", "Signal subscriptions must stay non-personalised; FCA can certify a publication under art. 54(3)."),
 ("United States (SEC)", "https://www.law.cornell.edu/uscode/text/15/80b-2", "SECONDARY copy of statute (LII)", "publisher of any bona fide newspaper, news magazine or business or financial publication of general and regular circulation",
  "Advisers Act §202(a)(11)(D) publisher exclusion covers impersonal, regularly published research; an SMA or tailored advice requires SEC or state investment-adviser registration."),
 ("United States (CFTC)", "https://www.law.cornell.edu/cfr/text/17/4.14", "SECONDARY copy of regulation (LII)", "Providing commodity trading advice based on, or tailored to, the commodity interest or cash market positions or other circumstances or characteristics of particular clients",
  "17 CFR 4.14(a)(9): CTA registration exemption only if advice is not tailored and no client accounts are directed. Futures-based model portfolios or managed futures accounts → CTA/CPO registration with the CFTC/NFA."),
]
def main():
    bt = json.load(open(f"{D}/backtest.json")); ok, n = C.verify()
    rec = [json.loads(l) for l in open(C.LEDGER)]
    sample = json.load(open(f"{D}/sample_debate.json"))
    def row(name, s): return f"| {name} | {s.get('cagr')}% | {s.get('vol')}% | {s.get('sharpe')} | {s.get('maxdd')}% |"
    L = ["", "## TRIAGE Alpha Committee (adapted from AlphaAgents, arXiv:2508.11152)", "",
         "Source paper: Zhao, Lyu, Jones, Garber, Pasquali, Mehta (BlackRock), *AlphaAgents: Large Language Model based Multi-Agents for Equity Portfolio Constructions*, arXiv:2508.11152v1, https://arxiv.org/html/2508.11152v1 (read in full 23 Oct 2026).", "",
         "**What we kept from the paper:** role agents with data access restricted to their role (paper Table 1); the paper's coordinator prompt for debate (\"every agent ... has a chance to speak at least twice. Each agent can not decide for the whole group ... You must invoke all agents before deciding to Terminate\"); round-robin debate to consensus; explicit risk-neutral vs risk-averse profiles (§2.3); equal-weight portfolios from agent picks compared with single-agent portfolios and the benchmark using return and Sharpe (§3.2, §4.3); full debate logs kept for review.", "",
         "**Role mapping:** paper Fundamental → *Forced Seller* (who must sell, from credit-spread shocks) and *LME* (CFTC managed-money positioning); paper Sentiment → *Signal/Radar* (trend/flow) and *Contrarian* (crowding); paper Valuation → *Valuation* (annualised return and volatility tools, exactly the paper's §2.2.3 formulas); added Macro (Dalio regime), which the paper names as future work.", "",
         "**What we changed, and why (honest):** the agents are deterministic tool-based rules, not LLM calls. An LLM committee backtested on 2012–2026 would already 'know' those years from training data, so its backtest would be contaminated. The paper's prompts and our role prompts are stored in `committee.py` (PROMPTS) for a later LLM backend that runs only forward (live, paper-only). Debate rule: an agent whose conviction is below the mean conviction of disagreeing peers withdraws; nobody adopts a view without evidence; unresolved → majority, and the risk-averse profile takes no position on any dissent.", "",
         f"### Backtest — monthly, 22 cross-asset instruments, {bt['risk_neutral']['start']} → {bt['risk_neutral']['end']}, long-only equal-weight, cash when no BUY", ""]
    for prof in ("risk_neutral", "risk_averse"):
        for w, lab in (("full", "full period"), ("oos_2021", "2021 onward (rules fixed before; treat as out-of-sample)")):
            L += [f"**{prof.replace('_', '-')}, {lab}**", "", "| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |", "|---|---|---|---|---|"]
            s = bt[prof][w]; L += [row("Committee (debate)", s["committee"]), row("Equal-weight benchmark", s["equal_weight"])] + [row(f"Single agent: {k}", s[k]) for k in C.ROLES] + [""]
        L += [f"Committee BUY calls: {bt[prof]['committee_calls']}; share that beat the equal-weight month: {bt[prof]['committee_beat_ew_pct']}%.", ""]
    rn, ra = bt["risk_neutral"], bt["risk_averse"]
    L += ["**Honest result:** over the full period the risk-neutral committee edges the equal-weight benchmark (Sharpe "
          f"{rn['full']['committee']['sharpe']} vs {rn['full']['equal_weight']['sharpe']}, max drawdown {rn['full']['committee']['maxdd']}% vs {rn['full']['equal_weight']['maxdd']}%) and beats every single agent on Sharpe. "
          f"From 2021 it **underperforms** the benchmark (Sharpe {rn['oos_2021']['committee']['sharpe']} vs {rn['oos_2021']['equal_weight']['sharpe']}), and the single Valuation agent is better than the committee (Sharpe {rn['oos_2021']['valuation']['sharpe']}; risk-averse {ra['oos_2021']['valuation']['sharpe']}). "
          f"Only {rn['committee_beat_ew_pct']}% of committee picks beat the equal-weight month. The paper's headline (multi-agent beats single agents and benchmark) is **not reproduced out-of-sample** here; debate mainly cuts drawdown versus single agents. Contrarian and LME agents lose money alone. This is why the product proof is the forward, hash-chained record, not this backtest.", "",
          "### PAPER-ONLY live track record (hash-chained)", "",
          f"Ledger `track_record.jsonl`: {n} calls, chain verified = {ok}. Each record holds entry (last public close), thesis (each agent's view), catalyst, exit rule, benchmark, previous hash and SHA-256 hash, logged in SGT. No trades placed; not advice to anyone.", "",
          "| # | Kind | Instrument | Call | Entry | Entry date | Exit rule |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rec, 1):
        L.append(f"| {i} | {r['kind']} | {r['instrument'][:48]} | {r['call']} | {r['entry']:.4g} | {r['entry_date']} | {r['exit_rule'][:46]} |")
    L += ["", f"First hash {rec[0]['hash'][:16]}… → last hash {rec[-1]['hash'][:16]}…. To make the record externally verifiable, publish each day's last hash somewhere timestamped (e.g. a public git commit or an OpenTimestamps proof) — a user action, not done.", "",
          "### Monetisation (JUDGEMENT) — the track record is the product proof", "",
          "1. **Signal subscription** (impersonal, same feed to all subscribers; no personalised recommendations): radar + committee calls + mining layer. Fits the publisher-style exclusions below only if it stays impersonal and regularly published.",
          "2. **Model-portfolio licence** to managers/platforms who run the money themselves (B2B data/IP licence). Still check per jurisdiction whether the licensee relationship counts as advice.",
          "3. **Later: SMA or fund** — needs a licence in each place the money is managed or marketed. The user must handle this with counsel; nothing here is legal advice.", "",
          "| Jurisdiction | Source (fetched 23 Oct 2026) | Grade | Exact quote | What it means for TRIAGE |", "|---|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in LIC]
    L += ["", "Gates before any money: (a) 12+ months of forward paper calls with the chain anchored publicly; (b) hit rate and excess return reported net of costs vs the stated benchmark; (c) a licensing opinion for each target jurisdiction."]
    open(f"{R}/committee.md", "w").write("\n".join(L))
    app = dict(paper="https://arxiv.org/html/2508.11152v1", backtest=bt, ledger=rec, chain_ok=ok, n=n, licensing=[dict(jur=a, url=b, grade=c, quote=d, meaning=e) for a, b, c, d, e in LIC],
               sample_debate=sample, roles=C.ROLES)
    json.dump(app, open("/workspace/triage_os_data/committee.json", "w"), indent=1, ensure_ascii=False)
if __name__ == "__main__": main()
