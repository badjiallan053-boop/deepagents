"""Edge Lab addendum: ledger entries for live BNF triggers (KEPT variants) and upcoming worldwide emergences (vetoed, calendar WATCH),
Comtrade China-export join for the export-control names, H.4.1 point-in-time status."""
import json, os, datetime, statistics as st, collections
import committee as K, bnf_cis as BC
DATA = "/workspace/triage_os_data"; TODAY = "2026-10-23"
def have(kind): return {(r.get("ticker"), r.get("asof")) for r in map(json.loads, open(K.LEDGER)) if r.get("kind") == kind}
def bnf_ledger():
    J = json.load(open(f"{DATA}/bnf_cis.json")); h = have("bnf_cis_watch"); out = []
    for x in J["live"]:
        ok = (x["kind"] == "BNF" and x["region"] in ("JP", "HK"))
        if not ok: continue
        x["variant"] = "JP kairi<=-25% 5d" if x["region"] == "JP" and x["kairi"] <= -25 else ("JP kairi<=-20% 5d" if x["region"] == "JP" else "HK kairi<=-20% 5d")
        x["exit"] = "close of the 5th trading day after entry (entry = close of 23 Oct 2026 local)"
        x["kill"] = "Kairi deepens below -40% before day 5, or a trading halt / going-concern / delisting notice"
        out.append(x)
        if (x["t"], TODAY) not in h:
            K.append(dict(kind="bnf_cis_watch", asof=TODAY, ticker=x["t"], call="WATCH (BNF mean reversion, 5d)", px=x["px"], variant=x["variant"], kairi=x["kairi"], catalyst=x["exit"], kill=x["kill"], note="paper only; not advice"))
    return out
EMERGE = [("BIG.PA", "Bigben Interactive", "FR", "2026-12-09", "plan hearing (proceeding extended to 17 Dec 2026)"), ("NACON.PA", "Nacon", "FR", "2027-03-02", "end of extended observation period"),
          ("3383.HK", "Agile Group", "HK/CN", "2026-11-16", "RSA launch (JUDGEMENT date)"), ("BRNK.DE", "Branicks Group", "DE", "2027-03-31", "plan effective by end-2026 or 31 Mar 2027 at the latest"),
          ("1B0.SI", "mm2 Asia", "SG", "2026-11-04", "scheme meetings; moratorium to 21 Nov"), ("6158.HK", "Zhenro Properties", "HK/CN", "2026-11-09", "adjourned petition hearing"),
          ("1813.HK", "KWG Group", "HK/CN", "2027-03-31", "scheme timetable not announced (JUDGEMENT window)"), ("1622.HK", "Redco Properties", "HK/CN", "2027-03-31", "sanction hearing not announced (JUDGEMENT window)"),
          ("1608.HK", "VPower Group", "HK", "2027-03-31", "meeting notice to follow (JUDGEMENT window)"), ("FOOD.TO", "Goodfood Market", "CA", "2027-03-31", "SISP milestones (JUDGEMENT window)")]
def emerge_ledger():
    h = have("reorg_watch"); out = []
    for t, n, c, d, why in EMERGE:
        P = BC.pxv(t); px = P[-1][1] if P else None
        r = dict(t=t, name=n, country=c, date=d, why=why, px=px, px_date=P[-1][0] if P else None,
                 kill="Plan/scheme rejected, case converted to liquidation, or equity cancelled with no recovery (existing equity is usually diluted 90-100% in debt-for-equity)")
        out.append(r)
        if (t, TODAY) not in h and px:
            K.append(dict(kind="reorg_watch", asof=TODAY, ticker=t, call="WATCH (calendar; M3 vetoed by Quant Validation)", px=px, catalyst=f"{d}: {why}", kill=r["kill"], note="paper only; existing equity may be wiped; not advice"))
    return out
def comtrade():
    R = json.load(open(f"{DATA}/xasset/v4/comtrade_china_exports.json")); by = collections.defaultdict(dict)
    for r in R: by[(r["cmd"], r["desc"])][r["period"]] = r["kg"] or 0
    out = []
    names = {"811292": "Ga/Ge (LPTH germanium-free optics; 5N Plus)", "8110": "antimony (UAMY, LRV.AX)", "2846": "rare-earth compounds (UCU.V, ARA.TO, IXR.AX, AREC)", "280530": "rare-earth metals (UCU.V, ARA.TO)", "250410": "natural graphite (GPH.V)", "810194": "tungsten (TUN.L, GMET.L)"}
    for (c, d), m in by.items():
        ps = sorted(m); last = ps[-1]; l12 = ps[-12:]; p12 = ps[-24:-12]
        a = sum(m[p] for p in l12); b = sum(m[p] for p in p12) if len(p12) == 12 else None
        out.append(dict(hs=c, desc=d, names=names.get(c, ""), last_month=last, kg_last12=round(a), kg_prior12=round(b) if b else None, yoy_pct=round(100 * (a / b - 1)) if b else None, months=len(ps)))
    return out
def h41():
    p = f"{DATA}/xasset/v4/h41_pit.json"
    if not os.path.exists(p): return {}
    d = json.load(open(p)); ok = [k for k, v in d.items() if v.get("total_assets_m")]
    return dict(releases=len(ok), first=min(ok) if ok else None, last=max(ok) if ok else None)
def run():
    J = dict(asof=TODAY, bnf_live=bnf_ledger(), emergences=emerge_ledger(), comtrade=comtrade(), h41=h41(), ledger=K.verify())
    json.dump(J, open(f"{DATA}/edge_addendum.json", "w"), indent=1, default=str); print(J["ledger"], len(J["bnf_live"]), len(J["emergences"]), J["h41"]); [print(c) for c in J["comtrade"]]
if __name__ == "__main__": run()
