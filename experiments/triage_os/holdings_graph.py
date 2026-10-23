"""Interconnected holdings graph from public data already in triage.db (all UNVERIFIED).

Edge types:
  mark_dispersion  - two BDCs mark the same borrower differently in the same period
  crossholder      - one holder across >=2 instruments/tranches of the same issuer
  cre_pari_passu   - same CRE property split across >=2 CMBS trusts (shared lender exposure)
  forced_seller    - fund holding a loan priced <70 (proxy for CCC/NAIC 5-6 bucket pressure)
"""
import argparse, sqlite3
from collections import defaultdict

DDL = """create table if not exists holdings_graph (
 edge_type, src, dst, issuer_key, weight real, detail, evidence_url, period, status default 'UNVERIFIED')"""

def mark_dispersion(con, min_gap=10.0, min_par=1e6):
    rows = con.execute("""select borrower_key, bdc, period, sum(par), sum(fv), min(source_url)
        from bdc_marks where par>0 and borrower_key!='' group by borrower_key,bdc,period""").fetchall()
    g = defaultdict(list)
    for k, bdc, per, par, fv, url in rows:
        if par and par >= min_par: g[(k, per)].append((bdc, 100.0 * fv / par, par, url))
    out = []
    for (k, per), lst in g.items():
        if len(lst) < 2: continue
        lst.sort(key=lambda x: x[1])
        lo, hi = lst[0], lst[-1]
        gap = hi[1] - lo[1]
        if gap >= min_gap:
            out.append(("mark_dispersion", lo[0], hi[0], k, round(gap, 1),
                        f"{lo[0]} {lo[1]:.1f} vs {hi[0]} {hi[1]:.1f} (par {lo[2]/1e6:.1f}m / {hi[2]/1e6:.1f}m)",
                        lo[3] + " | " + hi[3], per))
    return out

def crossholders(con):
    rows = con.execute("""select issuer_key, holder, count(distinct coalesce(cusip,instrument)), sum(value_usd),
        group_concat(distinct instrument), min(source_url), max(period) from holders group by issuer_key, holder""").fetchall()
    return [("crossholder", h, k, k, round((v or 0) / 1e6, 2), f"{n} instruments: {ins[:160]}", url, per)
            for k, h, n, v, ins, url, per in rows if n >= 2]

def forced_sellers(con, px=70.0):
    rows = con.execute("""select holder, issuer_key, instrument, price, value_usd, source_url, period
        from holders where price is not null and price < ?""", (px,)).fetchall()
    return [("forced_seller", h, k, k, round((v or 0) / 1e6, 2), f"{ins} @ {p}", url, per)
            for h, k, ins, p, v, url, per in rows]

def cre_pari(con):
    rows = con.execute("""select lower(trim(propertyName)), propertyCity, trust,
        cast(reportPeriodEndActualBalanceAmount as real), stress_score, mostRecentSpecialServicerTransferDate, source_url
        from cmbs_loans where propertyName!='' and lower(trim(propertyName)) not in ('na','n/a','various','')""").fetchall()
    g = defaultdict(list)
    for name, city, trust, bal, s, ss, url in rows: g[(name, city)].append((trust, bal or 0, int(s or 0), ss, url))
    out = []
    for (name, city), lst in g.items():
        trusts = sorted({t[0] for t in lst})
        if len(trusts) < 2: continue
        stress = max(t[2] for t in lst)
        out.append(("cre_pari_passu", trusts[0], trusts[1], f"{name} ({city})", stress,
                    f"{len(trusts)} trusts, {sum(t[1] for t in lst)/1e6:.0f}m; SS={','.join(sorted({t[3] for t in lst if t[3]}))}",
                    lst[0][4], ""))
    return out

def f13_holders(con, keys=("echostar", "nfe", "clear_channel_outdoor", "qvc", "trinseo"), min_usd=1e6):
    try:
        rows = con.execute(f"""select filer, issuer_key, max(value), putcall, source_url, period from f13_holdings
            where issuer_key in ({','.join('?' * len(keys))}) group by filer, issuer_key, putcall having max(value) >= ?""", (*keys, min_usd)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [("f13_holder", f, k, k, round(v / 1e6, 2), f"13F {pc or 'long'} ${v/1e6:.1f}m", url, per) for f, k, v, pc, url, per in rows]

OWN = ("mark_dispersion", "crossholder", "forced_seller", "cre_pari_passu", "f13_holder")

def build(db):
    con = sqlite3.connect(db); con.execute(DDL)
    con.execute(f"delete from holdings_graph where edge_type in ({','.join('?' * len(OWN))})", OWN)
    edges = mark_dispersion(con) + crossholders(con) + forced_sellers(con) + cre_pari(con) + f13_holders(con)
    con.executemany("insert into holdings_graph (edge_type,src,dst,issuer_key,weight,detail,evidence_url,period) values (?,?,?,?,?,?,?,?)", edges)
    con.commit(); con.close(); return len(edges)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); a = ap.parse_args()
    print(build(a.db), "edges")
