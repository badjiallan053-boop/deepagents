"""Control-bottleneck analysis: who decides the outcome, and what it costs to get a seat at that table.
Facts are token-matched against cached primary texts (CB-* verification rows). Every judgement or
assumption is labelled. Companies only; the EchoStar controlling shareholder is referred to by role."""
import os, re, sys, csv, json, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
CACHE = os.environ.get("HUGHES_CACHE", "/tmp")
DATA = "/workspace/triage_os_data"
HERE = os.path.dirname(os.path.abspath(__file__))
CL = "https://storage.courtlistener.com/recap/gov.uscourts.txsb.498986/gov.uscourts.txsb.498986.{}.0.pdf"
U = dict(
 D320=CL.format(320), D339=CL.format(339), D369=CL.format(369), D561=CL.format(561),
 Q2="https://www.sec.gov/Archives/edgar/data/1415404/000110465926089370/sats-20260630x10q.htm",
 S1126="https://www.law.cornell.edu/uscode/text/11/1126", S1129="https://www.law.cornell.edu/uscode/text/11/1129",
 S1121="https://www.law.cornell.edu/uscode/text/11/1121", S510="https://www.law.cornell.edu/uscode/text/11/510",
 S363="https://www.law.cornell.edu/uscode/text/11/363", R2019="https://www.law.cornell.edu/rules/frbp/rule_2019",
 EX991="https://www.sec.gov/Archives/edgar/data/1687202/000188852426017398/jpc16c04_ex991-202609.htm",
 C4="https://www.sec.gov/Archives/edgar/data/1013611/000153949716004038/n770_424b2-x10.htm",
 BAYWA="https://www.baywa.com/binaries/pdf/content/documents/baywacms-en/downloadcenter/other-ir/kronos-publication-of-the-results-of-the-vote-without-meeting/kronos-publication-of-the-results-of-the-vote-without-meeting/baywacms%3Adownloadpdf/Kronos+EKS+AG+%26+Co.+KG+-+Vote+without+Meeting+-+Publication+of+Results+-+261016.pdf",
 BRAN="https://branicks.com/wp-content/uploads/2026/10/Update-on-Implementation-Conditions-EN-15-Oct-2026.pdf",
 DBSD="https://law.justia.com/cases/federal/appellate-courts/ca2/4104292/634-f3d-79.html",
 LSQ="https://www.nysb.uscourts.gov/sites/default/files/opinions/241628_165_opinion.pdf",
 SERTA="https://www.ca5.uscourts.gov/opinions/pub/23/23-20181-CV0.pdf",
 MITEL="https://law.justia.com/cases/new-york/appellate-division-first-department/2024/index-no-651327-23-appeal-no-2918-case-no-2024-00169.html",
 INCORA="https://caselaw.findlaw.com/court/us-ban-crt-s-d-tex-hou-div/116894389.html",
 DBS="https://www.sec.gov/Archives/edgar/data/1415404/000141540426000048/sats-20261001x8k.htm",
 LOPX="https://loparex.com/loparex-announces-comprehensive-recapitalization-and-strategic-capital-support-to-advance-next-stage-of-growth/",
 SCHVG5="https://www.gesetze-im-internet.de/schvg/__5.html", SCHVG15="https://www.gesetze-im-internet.de/schvg/__15.html",
)
FILES = dict(D320="bfda20.txt", D339="h339.txt", D369="h369.txt", D561="h561.txt", Q2="sats_q2.txt", S1129="law_1129.txt",
             S1121="law_1121.txt", S510="law_510.txt", S363="law_363.txt", R2019="law_rule_2019.txt", EX991="ex991.txt", C4="c4.txt",
             BAYWA="baywa.txt", BRAN="bran.txt")
FACTS = [
 ("CB01", "Noteholder Group holds >61.6% of 5.25% Secured Notes and >84.37% of 6.625% Senior Notes", "D320", "more than 61.6% of the outstanding principal of the $750 million 5.25% Senior Secured Notes and more than 84.37%", "fact"),
 ("CB02", "Excluding EchoStar's $123m insider position the Group holds 73.71% of the Secured Notes", "D320", "73.71% if EchoStar’s $123 million insider position is excluded", "fact"),
 ("CB03", "Third-party Secured Notes carrying $627.3m, fair value $536.8m (30 Jun 2026)", "Q2", "627,283 ​ ​ 536,766", "fact"),
 ("CB04", "6.625% Senior Notes $750.0m, fair value $435.0m (30 Jun 2026)", "Q2", "750,000 ​ ​ 435,000", "fact"),
 ("CB05", "Cash collateral: 'Required Prepetition Secured Parties' = majority in principal of Senior Secured Notes (EchoStar XXIV included but without vote) control waivers and remedies", "D561", "The holders of a majority in aggregate principal amount of the Senior Secured Notes outstanding at such time, together with EchoStar XXIV", "fact"),
 ("CB06", "Amended Third Interim cash collateral order runs through 23 Oct 2026; final hearing set 20 Oct 2026", "D561", "through and including October 23, 2026", "fact"),
 ("CB07", "Order recital (16 Oct 2026): no trustee or examiner has been appointed", "D561", "No trustee or examiner has been appointed", "fact"),
 ("CB08", "Examiner scope (16 Sep 2026): J3 lease, $529m + $500m 2024 dividends, ~$196m tax payments, SpaceX transaction, EchoStar's $123m note purchase and the $50m/$1m 2026 financings", "D339", "EchoStar’s 2025 purchase of $123 million in Secured Notes", "fact"),
 ("CB09", "The $50m EchoStar XXIV financing was added as an additional secured obligation under the security agreement for the Secured Notes", "D339", "added as an additional secured obligation under the security agreement for the Secured Notes", "fact"),
 ("CB10", "Examiner to report on equitable subordination and fiduciary-duty claims against EchoStar as controlling shareholder", "D339", "claims for breach of fiduciary duty against EchoStar Corporation as controlling shareholder", "fact"),
 ("CB11", "Stipulated stay (20 Sep 2026) of exclusivity litigation, investigations and any settlement of estate claims against EchoStar unless via mediation", "D369", "Any proposal to settle, compromise, or abandon any claims held by the Debtors’ estates against EchoStar", "fact"),
 ("CB12", "New non-ordinary-course EchoStar/Debtor transactions need prior written approval of the Committee and the Noteholder Group", "D369", "approved, in writing and in advance, by the Creditors’ Committee and the Noteholder Group", "fact"),
 ("CB13", "Group membership is listed on Exhibit A of the Rule 2019 Verified Statement, ECF No. 154", "D369", "Verified Statement of Noteholders Pursuant to Bankruptcy Rule 2019 [ECF No.154]", "fact"),
 ("CB14", "§1129(a)(10): an impaired accepting class is counted without insider acceptances", "S1129", "determined without including any acceptance of the plan by any insider", "law"),
 ("CB15", "§510(c): court may equitably subordinate all or part of an allowed claim", "S510", "under principles of equitable subordination, subordinate for purposes of distribution all or part of an allowed claim", "law"),
 ("CB16", "§363(k): a secured creditor may credit bid at a sale of its collateral unless the court for cause orders otherwise", "S363", "unless the court for cause orders otherwise the holder of such claim may bid at such sale", "law"),
 ("CB17", "Rule 2019 'disclosable economic interest' includes derivatives and any economic interest affected by a claim's value", "R2019", "\"disclosable economic interest\" means any claim, interest, pledge, lien, option, participation, derivative instrument", "law"),
 ("CB18", "§1121(d): court may reduce or increase exclusivity for cause; 18-month outer limit", "S1121", "may not be extended beyond a date that is 18", "law"),
 ("CB19", "Fresno Fashion Fair: $60m note in JPMDB 2016-C4, 3.587%, maturity 1 Nov 2026", "EX991", "RT Fresno CA Actual/360 3.587%", "fact"),
 ("CB20", "Fresno: special servicer finalising a Pre-Negotiation Letter with the borrower and sponsor Macerich", "EX991", "finalizing a Pre-Negotiation Letter Agreement with the Borrower's representative and the Loan's sponsor, Macerich", "fact"),
 ("CB21", "JPMDB 2016-C4 Directing Certificateholder (Sep 2026 10-D): Cytium Investment Management", "EX991", "Directing Certificateholder Cytium Investment Management", "fact"),
 ("CB22", "At issuance BlackRock Realty Advisors (agent for a managed account) bought Classes E, F and NR and appointed the special servicer", "C4", "will purchase the Class E, Class F and Class NR certificates", "fact"),
 ("CB23", "Kronos EKS (BayWa) hybrid: vote without meeting 12–14 Oct 2026 was quorate but no resolution adopted", "BAYWA", "quorate pursuant to Section 18 para. 1 SchVG in conjunction with Section 15 para. 3 sentence 1 SchVG", "fact"),
 ("CB24", "Branicks: shareholders' EGM (9 Oct) did not approve agenda item 4 consultancy agreements", "BRAN", "was not adopted. Implementation Condition 2", "fact"),
 ("CB25", "Branicks: holders of >50% of outstanding principal can instruct MR Treuhand to waive Implementation Conditions (other than 6 and 7)", "BRAN", "more than 50% of the aggregate principal amount of the outstanding Notes", "fact"),
]

def flat(fn):
    p = os.path.join(CACHE, fn)
    return re.sub(r"\s+", " ", open(p, errors="ignore").read()) if os.path.exists(p) else None

def verify():
    out = {}
    for fid, claim, doc, tok, kind in FACTS:
        t = flat(FILES[doc]); ok = t is not None and re.sub(r"\s+", " ", tok) in t
        out[fid] = dict(claim=claim, url=U[doc], ok=ok, kind=kind, status="VERIFIED" if ok else "UNVERIFIABLE",
                        method=f"token match in primary text fetched 22 Oct 2026: '{tok[:70]}'")
    return out

def store(res):
    con = sqlite3.connect(DB)
    con.execute("create table if not exists verification(claim_id, artifact, claim, status, primary_url, checked, method, fix)")
    con.execute("delete from verification where claim_id like 'CB%'")
    for k, r in res.items():
        con.execute("insert into verification values(?,?,?,?,?,?,?,?)", (k, "research/control_bottleneck", r["claim"], r["status"], r["url"], "2026-10-22", r["method"], "Statute text" if r["kind"] == "law" else ""))
    con.commit(); con.close()

# ---------------- §1126(c) voting math ----------------
def block_threshold(voting_amount):
    """Smallest holding that defeats the two-thirds-in-amount test: strictly more than one third of the amount voted."""
    return voting_amount / 3.0

def can_carry(holding, voting_amount):
    return holding >= voting_amount * 2.0 / 3.0

def class_math(name, voting_amount, group_min, price, insider=0.0):
    """Returns blocking threshold, cost at price (cents), float outside the Group and insider, and who blocks."""
    thr = block_threshold(voting_amount)
    outside = max(0.0, voting_amount - group_min - insider)
    return dict(cls=name, voting=voting_amount, block=thr, cost=thr * price / 100 if price else None, group=group_min,
                group_blocks=group_min > thr, group_carries=can_carry(group_min, voting_amount), outside=outside,
                outside_can_block=outside > thr, insider=insider, insider_blocks=insider > thr)

SEC_TOT, SEC_ECHO, SEC_3P, UNS = 750.0, 122.7, 627.3, 750.0
P_SEC, P_UNS = 536.766 / 627.283 * 100, 435.0 / 750 * 100
G_SEC = 0.616 * SEC_TOT; G_UNS = 0.8437 * UNS

def hughes_classes():
    return [
        class_math("Secured Notes, all holders vote (EchoStar not designated)", SEC_TOT, G_SEC, P_SEC, insider=SEC_ECHO),
        class_math("Secured Notes, EchoStar votes designated/separately classed", SEC_3P, G_SEC, P_SEC),
        class_math("6.625% Senior Notes (unsecured)", UNS, G_UNS, P_UNS),
        dict(cls="EchoStar intercompany (J3 $50m secured + $1m unsecured)", voting=51.0, block=17.0, cost=None, group=0.0, group_blocks=False,
             group_carries=False, outside=0.0, outside_can_block=False, insider=51.0, insider_blocks=True),
    ]

def load_holders():
    p = os.path.join(DATA, "cmbs_control", "directing_holders.csv")
    if not os.path.exists(p): return []
    return list(csv.DictReader(open(p)))

def m(x): return f"${x:,.1f}m"

def build_md(res):
    f = lambda k: f"[{k}]"
    C = hughes_classes(); H = load_holders(); found = [h for h in H if h["directing_holder"]]
    L = []
    L.append(f"""# Control bottleneck

## 1. The answer in one page

**Hughes (26-90739) has one chokepoint, and it is already owned.** The Noteholder Group's disclosed positions (more than 61.6% of the secured notes, more than 84.37% of the unsecured notes) give it, simultaneously:

- the **blocking and carrying vote in both note classes** under §1126(c){f('CB01')}{f('CB02')};
- the **cash-collateral trigger**: the "Required Prepetition Secured Parties" are the majority of secured notes, and EchoStar XXIV is named without a vote{f('CB05')}. The order runs only through **23 Oct 2026**{f('CB06')}, so the Group re-prices the Debtors' liquidity every few weeks;
- a **veto on any new EchoStar/Debtor transaction** and on settling estate claims outside mediation, under the 20 Sep stipulated order{f('CB11')}{f('CB12')}.

The float the Group does not own is too small to block either class. Non-Group third parties hold at most **{m(SEC_3P-G_SEC)} of the secured notes** and **{m(UNS-G_UNS)} of the unsecured notes**. Blocking needs more than {m(SEC_3P/3)} and {m(UNS/3)} respectively. **An outsider cannot buy a blocking position in the market. It can only buy one from Group members, or join the Group.**

The counter-chokepoint belongs to **EchoStar (the parent)**. It owns the J3 satellite through non-debtor EchoStar XXIV, holds $172.7m of secured claims, and controls the Debtors' board until exclusivity ends. Its claims are the target of the examiner's equitable-subordination brief{f('CB08')}{f('CB10')}. As of 16 Oct, though, the order recites that **no examiner had yet been appointed**{f('CB07')}. The three dates that decide control are **23 Oct** (cash collateral), **1 Dec** (exclusivity hearing) and the **lien-challenge deadline**.

**What a billionaire would do (judgement):** not fight the Group. Instead, (1) buy into it through a member's position, or (2) take the one seat it does not hold: **litigation-trust funder** or **bidder for the post-exit equity / sale process**. In the side situations the same logic gives:
- **Fresno**: about $11.2m of CMBS class F controls the directing seat on a $325m loan.
- **Branicks**: more than 50% of a €400m bond can waive the broken shareholder condition.
- **BayWa**: more than 25% of the votes cast blocks the hybrid.
- **Loparex**: the lenders who led the out-of-court recapitalisation already own the outcome.

## 2. Hughes: voting math, class by class

The rule is §1126(c): a class accepts if creditors holding **at least two-thirds in amount and more than half in number of the claims that actually vote** accept. Votes designated under §1126(e) are excluded (https://www.law.cornell.edu/uscode/text/11/1126). A plan also needs one impaired accepting class, **counted without insider votes**{f('CB14')}.

Prices are the issuer's reported fair values at 30 Jun 2026: **{P_SEC:.1f}** secured, **{P_UNS:.1f}** unsecured{f('CB03')}{f('CB04')}. These are Level-2 estimates, not trades. Group holdings are the disclosed minimums.

| Class | Amount voting ($m, assumes 100% turnout) | Block threshold (>1/3) | Cost of block at FV | Group holding (min) | Group blocks? | Group carries alone? | Max float outside Group/insider | Outside float can block? | Likely blocker |
|---|---|---|---|---|---|---|---|---|---|""")
    for c in C:
        cost = m(c["cost"]) if c["cost"] else "n/a (single insider holder)"
        who = "Noteholder Group" if c["group_blocks"] else ("EchoStar (insider)" if c["insider_blocks"] else "nobody alone")
        L.append(f"| {c['cls']} | {c['voting']:,.1f} | {m(c['block'])} | {cost} | {m(c['group'])} | {'yes' if c['group_blocks'] else 'no'} | {'yes' if c['group_carries'] else 'no'} | {m(c['outside'])} | {'yes' if c['outside_can_block'] else 'no'} | {who} |")
    L.append(f"""| Trade / general unsecured | not disclosed in documents retrieved | – | – | – | – | – | – | – | Gap: schedules not retrieved. The Group term sheet keeps trade claims unimpaired up to a cap, and an unimpaired class is deemed to accept (§1126(f)), so it **does not vote** |

**How to read it.**
- **Secured class.** EchoStar's $122.7m is {SEC_ECHO/SEC_TOT*100:.1f}% of the class and cannot block alone in amount. If EchoStar is designated, as DISH was in DBSD (below), the class shrinks to $627.3m. The Group then holds 73.71% and carries the class by itself{f('CB02')}. **But if EchoStar is *not* designated, the Group (≥$462.0m) falls short of the $500m needed to carry the full class alone. EchoStar ($122.7m) plus at least about $127.3m of the ≤$165.3m non-Group float (more than $250m in total) could block. That makes designation of EchoStar's vote the real swing in the secured class, and makes the remaining non-Group secured holders the kingmakers (judgement).**
- **Numerosity is the only soft spot.** "More than half in number" counts holders, not dollars. The member count on Exhibit A of ECF 154 was **not retrievable** (not on RECAP; the Epiq site needs JavaScript){f('CB13')}. A plan sponsor facing a Group of fewer than about 10 funds could in theory be out-voted by number if many small holders voted against it. Judgement: this is unlikely for institutional 144A notes, where holders vote through DTC participants and turnout among small holders is low.
- **Turnout lowers every threshold.** If only 70% of the secured class votes, blocking needs just {m(SEC_TOT*0.7/3)}. The Group's position only gets more dominant.
- **EchoStar intercompany class.** EchoStar can make this class reject (cost: nothing, it owns the claim). But its acceptance cannot satisfy §1129(a)(10){f('CB14')}, and a rejecting class can be crammed down if the plan is fair and equitable. Its real leverage is economic, not legal: **J3**. The satellite sits outside the estate. The Group plan rejects the lease unless EchoStar XXIV modifies it, so Hughes needs replacement capacity or a renegotiated lease.

## 3. Paths to control (likelihoods are judgement, not forecasts)

| Path | Who benefits | Likelihood (judgement) | Cost | Timeline | Precedent / authority |
|---|---|---|---|---|---|
| Exclusivity terminated at the 1 Dec hearing | Noteholder Group | 45–60% | Legal fees only; the Group already filed a term sheet (Dkt 320) | Ruling at or after 1 Dec 2026 | §1121(d) "for cause"{f('CB18')}; the stay of exclusivity litigation was negotiated, not imposed{f('CB11')} |
| Competing Group plan confirmed (debt-for-equity + litigation trust) | Group | 35–50% conditional on termination | Bridge DIP + exit ABL (sizes not disclosed) | Group milestones: file in 20 days, disclosure statement in 40 days, confirmation 30 days after that, so about Q1–Q2 2027 | Group controls both note classes (section 2); cramdown of EchoStar classes |
| Credit bid of secured collateral | Secured holders (Group-directed) | 15–25% | Up to ~$800m of All-Asset Secured Claims can be bid; cash only for senior costs | 3–6 months + FCC | §363(k){f('CB16')}. The $50m J3 advance shares the collateral{f('CB09')}, so who credit-bids first is itself a fight |
| Buying EchoStar's intercompany claims | Third party | <10% | ~$172.7m face; price unknowable | – | DBSD: buying debt for strategic control risks designation |
| Equitable subordination / recharacterization of the $172.7m | Third-party secured, then unsecured | 30–50% (any portion subordinated) | Litigation cost; examiner budget | Examiner interim reports every 45 days once appointed | §510(c){f('CB15')}; examiner scope{f('CB10')}; LightSquared (affiliate claim subordinated **to the extent of harm**, not disallowed) |
| Examiner findings move the negotiation | Committee + Group | High influence, low direct control | Estate-funded | Examiner not yet appointed as of 16 Oct{f('CB07')} | Order defining scope, Dkt 339 |
| DIP roll-up | DIP lender (a Group member) | 30–45% if exclusivity ends | DIP size undisclosed; illustrative $100–200m | With plan filing | Serta (5th Cir. 2024): a non-pro-rata uptier was not an "open market purchase", and the indemnity was struck. Incora/Wesco: liens restored where the 2/3 vote was lacking. Mitel: an NY uptier was upheld. **Any in-court roll-up is court-supervised, so these cases set the fairness bar, not the mechanics** |
| 363 sale of spectrum / satellite assets | Highest bidder, often the secured credit bid | 20–35% | Market price (illustrative EV $350–900m, Hughes note A2) | 6–12 months; FCC licence transfer approval needed | Group plan builds in a one-year post-effective sale process (Dkt 320). DISH DBS (sister subsidiary) emerged on 1 Oct 2026 via its own Chapter 11 |

**Precedents (primary).**
- **DBSD** (2d Cir. 2011): DISH's vote was designated after it bought the first-lien class to obtain strategic assets. {U['DBSD']}
- **LightSquared** (Bankr. S.D.N.Y., 10 Jun 2014): SPSO, the controlling shareholder's vehicle, bought about $844m of debt. The claim was not disallowed, but was subordinated to the extent of injury. {U['LSQ']}
- **Serta** (5th Cir., 31 Dec 2024). {U['SERTA']}
- **Mitel** (App. Div. 1st Dept, 31 Dec 2024). {U['MITEL']}
- **Incora/Wesco** (S.D. Tex.). {U['INCORA']}
- **DISH DBS emergence** (8-K, 1 Oct 2026). {U['DBS']}

The DBSD and LightSquared lessons point both ways in this case. EchoStar's group has itself been on the buying side of these tactics. That raises the probability (judgement) that its own $122.7m note purchase is designated or subordinated.

## 4. Five billionaire playbooks

Every number in this section is an **assumption** unless it carries a CB reference. Returns are gross, before fees and financing, and illustrative.""")
    PB = [
     ("(a) Blocking position in the secured notes", f"Needs >{m(SEC_3P/3)} face (EchoStar designated) ≈ **{m(SEC_3P/3*P_SEC/100)}** at {P_SEC:.1f}. The available non-Group float is at most {m(SEC_3P-G_SEC)}, so the block **must include bonds bought from Group members**",
      "Buy at 85.6. Low 41 / base 84 / high 100 cents (Hughes note model) gives **−52% / −2% / +17%**. The block itself pays only if it extracts consideration, and that is exactly what §1126(e) punishes",
      "Bad-faith designation (DBSD). Rule 2019 disclosure if acting as a group{f('CB17')}. MNPI if the bonds are bought from restricted Group members (cleansing needed)"),
     ("(b) Fund the litigation trust", "**$25–50m** commitment (assumption) for 20–35% of net proceeds (assumption, market-typical)",
      "Claims in examiner scope: $1.029bn dividends + ~$196m tax payments, **alleged**{f('CB08')}. Net trust proceeds low 0 / base 150 / high 400 ($m, Hughes note A3) → funder at 30% earns **0 / $45m / $120m** on $35m, i.e. **−100% / 1.3x / 3.4x** over 2–4 years",
      "Funding terms need court and plan approval. Settlement of EchoStar claims outside mediation is frozen{f('CB11')}. LightSquared shows partial, not total, subordination"),
     ("(c) Bridge DIP", "**$100–200m** (assumption; Group alleges ~$91m of deferred J3 payments and fees and no unencumbered cash, Dkt 534)",
      "Coupon 12–15% + 2–4% fees (assumption) → **14–19% annualised**, super-priority. Roll-up optionality only if the lender also holds secured notes",
      "Priming requires adequate protection or consent of the Required Prepetition Secured Parties, i.e. the Group{f('CB05')}. **A third-party DIP is not executable without the Group.** Serta/Incora fairness scrutiny of any roll-up"),
     ("(d) Buy trade / admin claims", "Trade pool size **unknown** (gap). Admin claims are mostly professionals' fees and EchoStar XXIV's deferred J3 rent, which is not tradable at scale",
      "If trade stays unimpaired up to the Group's cap: buy at 60–85 (assumption), receive par → **+18% to +67%**. Above the cap, recovery falls to the unsecured waterfall",
      "Near-zero control value: an unimpaired class does not vote. Bankruptcy Rule 3001(e) transfer notices; claim-objection risk travels with the claim"),
     ("(e) Bid for the assets", "Enterprise value **$350–900m** (Hughes note A2). A cash bid must beat a credit bid of up to ~$800m secured face{f('CB16')}",
      "Equity upside only if bought below base EV ($600m). Subscriber base −21.7% YoY (Hughes note), so the case is distressed-operating, not a spectrum arbitrage",
      "FCC licence-transfer approval. J3 is owned by **non-debtor** EchoStar XXIV, so a buyer must also deal with the parent. §363(k) credit-bid priority"),
    ]
    for t, cap, ret, risk in PB:
        L.append(f"\n### {t}\n\n| Capital needed | Return range | Risks and legal constraints |\n|---|---|---|\n| {cap} | {ret} | {risk} |")
    L.append(f"""
**Legal constraints common to all five.**
- **MNPI.** Group members sign NDAs and trade behind walls; an outsider buying from them must get them "cleansed". Trading on Debtor or EchoStar MNPI violates Rule 10b-5.
- **Rule 2019.** Anyone acting in concert must disclose every "disclosable economic interest", including derivatives{f('CB17')}.
- **§1126(e).** Votes bought to obtain a non-creditor advantage can be designated (DBSD).
- **Insider status.** Anyone affiliated with EchoStar cannot supply the impaired accepting class{f('CB14')}.

**Ranking (judgement).** Highest risk-adjusted control: **(b) the litigation trust**, because it is the one valuable seat the Group does not already own. Next is **(e)**, but only as a partner of the Group's sale process. **(c)** works only through a Group member. **(a)** is effectively unavailable. **(d)** is yield, not control.

## 5. Fresno Fashion Fair (CMBS): the B-piece holds the pen

- **The loan.** Fresno Fashion Fair is a $325m whole loan; the $60m A-1-A note sits in JPMDB 2016-C4 at 3.587% and matures 1 Nov 2026{f('CB19')}. It moved to special servicing on 29 Jul 2026 for imminent monetary default. Rialto, the special servicer, is finalising a Pre-Negotiation Letter with the sponsor, Macerich{f('CB20')}.
- **Who controls.**
  - The trust is the controlling noteholder for the whole loan.
  - The **Directing Certificateholder is Cytium Investment Management**{f('CB21')}. At issuance it was BlackRock Realty Advisors, which bought Classes E, F and NR and appointed the special servicer{f('CB22')}.
  - The controlling class is **F: $11.244m face, now receiving zero interest**.
- **The chokepoint math.** About **$11.2m of face directs workout, extension or foreclosure consent on a $325m loan: a 29x lever**. The holder can also replace the special servicer, subject to appraisal-reduction control-shift tests. Judgement: if appraisal reductions erase class F, control shifts up to class E ($22.5m), so a buyer must model the appraisal.
- **Billionaire move (assumption).** Buy class F + E (about $34m face) at deep discount from the current holder, then drive a negotiated extension with Macerich. The alternative is to buy the companion notes held in other trusts, which carry no control.

## 6. Loparex: control already exercised out of court

- **The lender's position.** OBDC holds second-lien positions of $112m and $21m, marked 61 → 5. Its first-lien pieces are small: $4.12m at 21.5 and $0.78m at 102.6 (30 Jun 2026).
- **The recap.** Loparex announced a recapitalisation on 8 Sep 2026, **led by Monarch Alternative Capital and Atlantic Park**, expected to close in Q4 2026. {U['LOPX']}
- **Second-lien and first-lien treatment.** Secondary press reports the second lien goes to zero and about half of the first lien converts to equity. **This is not confirmed by a primary source.**
- **No WHOA filing was found.** The chokepoint was the majority-lender consent under the first-lien credit agreement. It has been used, and the BDC 2L holders were not on the deciding side.
- **Lesson.** In private credit, control sits with whoever holds the required-lender percentage of the senior tranche, not with the largest BDC mark.

## 7. BayWa (Kronos EKS €100m hybrid): the 25% blocker

- **The rule.** Under §5(4) SchVG, material amendments need **75% of votes cast**. The first vote needs a quorum of 50% of outstanding notes (§15(3)); the second meeting needs 25%. {U['SCHVG5']} {U['SCHVG15']}
- **The October vote.** The 12–14 Oct vote was **quorate, yet neither the issuer's resolutions nor the countermotions passed**{f('CB23')}.
- **Minimum blocking stake.** At minimum participation (50 of €100m), more than **€12.5m** blocks. At full participation, more than €25m.
- **Second meeting.** At its 25% quorum, as little as **€6.25m** can block.
- **Judgement.** A €6–15m holder, buying hybrids at distressed prices, has a veto on a €100m write-down. That is the cheapest control seat in this set.

## 8. Branicks: the 50% waiver and the shareholder veto

- **What creditors approved.** Creditors approved the restructuring of the €400m 2.25% bond (M05: 99% of votes cast).
- **What shareholders blocked.** The 9 Oct EGM **did not approve** the consultancy agreements (agenda item 4), so Implementation Condition 2 failed{f('CB24')}.
- **The way around it.** Holders of **more than 50% of the outstanding principal (>€200m)** can instruct MR Treuhand to waive any condition except 6 and 7{f('CB25')}.
- **Where the chokepoint sits.** It is a **€200m+ coalition of noteholders**, not the shareholders.
- **Judgement.** The anchor holders who negotiated the deal (not named in the primary text) already sit close to that line. An outsider with 10–15% can bargain for consideration but cannot stop a waiver.

## 9. CMBS directing holders found in the filings

Source: the latest 10-D Exhibit 99.1 for each trust, parsed by cmbs_control.py. **{len(found)} of {len(H)} trusts named a directing holder or controlling class representative.** Computershare-format BMO and several other trusts print no name in the 10-D. Names are entities as printed; "Pacific Design Center" (Benchmark 2023-B38) looks like a loan label, not a holder, and is flagged.

| Trust | Label | Directing holder / CCR | Special servicer | Controlling class | Class balance ($m) | Source |
|---|---|---|---|---|---|---|""")
    for h in found:
        bal = f"{float(h['cc_balance'])/1e6:,.1f}" if h["cc_balance"] else "–"
        flag = " ⚑ suspect" if "Pacific Design" in h["directing_holder"] else ""
        L.append(f"| {h['trust']} | {h['label']} | {h['directing_holder']}{flag} | {h['special_servicer']} | {h['controlling_class']} | {bal} | {h['source_url']} |")
    L.append("\n## 10. Verification ledger\n\n| ID | Claim | Status | Source |\n|---|---|---|---|")
    for k, r in res.items():
        L.append(f"| {k} | {r['claim']} | {r['status']} | {r['url']} |")
    L.append("""
## 11. Gaps (stated, not papered over)

- **Rule 2019 Exhibit A (ECF 154).** Group membership and member count are not on RECAP, and the Epiq page is JavaScript-only. **Numerosity analysis is therefore incomplete.** Dkt 93 is the examiner motion, not a 2019 statement, and returns 404 on RECAP. No amended 2019 statement was found on RECAP.
- **Trade claims.** The size of the trade pool and the trade cap were not retrieved (schedules and SOFAs not on RECAP).
- **Final cash-collateral order (20 Oct hearing) and the lien-challenge deadline.** Neither date was confirmed from a primary source.
- **Prices.** Fair values are issuer Level-2 estimates at 30 Jun 2026, not trades. TRACE prints were not used.
- **Loparex.** Recap terms beyond the press release are secondary-source only.
- **Branicks anchor holders.** Not named in primary text.
- **BayWa.** Actual participation and the vote split were not published.
- **CMBS.** 52 of 102 trusts print no directing holder in the 10-D. PSA designation notices would be needed.
- **PACER** was declined by the user. No account was created, and paywalled dockets were not accessed.
""")
    return "\n".join(L)

def build():
    res = verify(); store(res)
    md = build_md(res)
    open(os.path.join(DATA, "control_bottleneck.md"), "w").write(md)
    C = hughes_classes(); H = load_holders()
    json.dump(dict(as_of="2026-10-22", classes=C, holders=H, prices=dict(secured=P_SEC, unsecured=P_UNS),
                   facts=[dict(id=k, **v) for k, v in res.items()],
                   situations=[
                     dict(name="Hughes 26-90739", chokepoint="Noteholder Group: >61.6% secured / >84.37% unsecured; Required Secured Parties for cash collateral", cost="Block unavailable in market (float < threshold)", date="1 Dec 2026 exclusivity hearing"),
                     dict(name="Fresno Fashion Fair (JPMDB 2016-C4)", chokepoint="Directing Certificateholder Cytium; controlling class F $11.244m", cost="~$11.2m face controls $325m loan", date="Maturity 1 Nov 2026"),
                     dict(name="Loparex", chokepoint="Required 1L lenders (Monarch, Atlantic Park led recap)", cost="Already exercised out of court", date="Close Q4 2026"),
                     dict(name="BayWa / Kronos hybrid", chokepoint=">25% of votes cast blocks (SchVG §5(4))", cost="€6.25–25m", date="Second meeting TBD"),
                     dict(name="Branicks €400m bond", chokepoint=">50% principal instructs MR Treuhand waiver", cost=">€200m coalition", date="Implementation by 31 Mar 2027"),
                   ]), open(os.path.join(DATA, "control.json"), "w"), indent=1, default=str)
    from design import report_from_markdown
    pdf = os.path.join(HERE, "Control_Bottleneck.pdf")
    pages = report_from_markdown(md, "Control bottleneck: who decides, and what a seat costs", "Special situations · control analysis · 22 Oct 2026",
        "Hughes 26-90739 voting math, paths to control and five capital playbooks; Fresno CMBS, Loparex, BayWa and Branicks chokepoints; CMBS directing holders.",
        [("As of", "22 Oct 2026"), ("Facts verified", f"{sum(r['ok'] for r in res.values())}/{len(res)}"), ("Directing holders", f"{len([h for h in H if h['directing_holder']])}/{len(H)}"), ("Next date", "1 Dec 2026")],
        os.path.join(HERE, "Control_Bottleneck.html"), pdf)
    return res, pages, pdf

if __name__ == "__main__":
    res, pages, pdf = build()
    print("verified", sum(r["ok"] for r in res.values()), "/", len(res), [k for k, r in res.items() if not r["ok"]], "pages", pages, pdf)
