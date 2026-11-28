"""Live out-of-sample hit log: append-only JSONL, each entry sha256-chained to the previous one, UTC timestamps.
snapshot(): log current signals as predictions. check_outcomes(): later evidence (court/SEC filing, BDC mark drop, WARN notice).
precision_at_trade(): pseudo out-of-sample on free data - BDC marks Q1-26 (signal) -> Q2-26 (outcome)."""
import datetime as dt, hashlib, json, os, re, sqlite3
GENESIS = "0" * 64
def _norm(s): return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
def _hash(e): return hashlib.sha256(json.dumps({k: e[k] for k in sorted(e) if k != "hash"}, sort_keys=True).encode()).hexdigest()
def _last(path):
    if not os.path.exists(path): return GENESIS, 0
    lines = [l for l in open(path) if l.strip()]
    return (json.loads(lines[-1])["hash"], len(lines)) if lines else (GENESIS, 0)
def append(path, record, now=None):
    prev, n = _last(path)
    e = dict(record, seq=n, ts_utc=(now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds"), prev=prev)
    e["hash"] = _hash(e)
    with open(path, "a") as f: f.write(json.dumps(e, sort_keys=True) + "\n")
    return e
def verify_chain(path):
    prev = GENESIS
    for i, l in enumerate(open(path)):
        e = json.loads(l)
        if e["prev"] != prev or e["seq"] != i or _hash(e) != e["hash"]: return False, i
        prev = e["hash"]
    return True, None
def snapshot(db, path, kinds=("covenant_waiver_8k", "auditor_change_plus_nt10k", "cross_markdown", "bdc_asset_coverage", "uk_late_accounts", "trade_claims_top20", "cmbs_tenant_distress")):
    c = sqlite3.connect(db, timeout=120)
    seen = {(json.loads(l).get("kind"), json.loads(l).get("entity")) for l in open(path)} if os.path.exists(path) else set()
    n = 0
    for sig, ent, val, url in c.execute(f"select signal,entity,value,source_url from signals2 where signal in ({','.join('?'*len(kinds))})", kinds):
        if (f"signal:{sig}", ent) in seen: continue
        append(path, {"kind": f"signal:{sig}", "entity": ent, "value": val, "source_url": url, "prediction": "distress event within 180d"}); n += 1
    return n
def check_outcomes(db, path, out_path):
    """Outcome = later court/SEC distress filing, WARN notice, or BDC mark <80 for the entity, dated after the hit."""
    c = sqlite3.connect(db, timeout=120)
    sigs = [(_norm(t), e or "", u) for t, e, u in c.execute("select title,event_date,url from signals where source in ('courtlistener','sec')")]
    warn = [(_norm(co), d, u) for co, d, u in c.execute("select company,notice_date,source_url from warn_state_notices")]
    res = []
    for l in open(path):
        h = json.loads(l); key = _norm(h["entity"]).split(" ")
        key = " ".join(key[:2]) if len(key) > 1 else (key[0] if key else "")
        if len(key) < 5: continue
        hits = [("filing", d, u) for t, d, u in sigs if key in t and d >= h["ts_utc"][:10]] + [("warn", d, u) for t, d, u in warn if key in t and (d or "") >= h["ts_utc"][:10]]
        if hits: res.append({"hit_seq": h["seq"], "entity": h["entity"], "outcome": hits[0][0], "date": hits[0][1], "url": hits[0][2]})
    for r in res: append(out_path, dict(r, kind="outcome"))
    return res
def precision_at_trade(db, lo=80.0, drop=5.0):
    """Signal at Q1-26: tranche marked < lo. Outcome by Q2-26: same tranche marked >= drop points lower. Precision = hits / signals."""
    c = sqlite3.connect(db, timeout=120)
    q = "select a.bdc,a.identifier,a.mark,b.mark from bdc_marks a join bdc_marks b on a.bdc=b.bdc and a.identifier=b.identifier where a.period='2026-03-31' and b.period='2026-06-30' and a.mark>0 and b.mark>=0"
    pairs = c.execute(q).fetchall()
    sig = [p for p in pairs if p[2] < lo]; hit = [p for p in sig if p[3] <= p[2] - drop]
    base = [p for p in pairs if p[2] >= lo]; base_hit = [p for p in base if p[3] <= p[2] - drop]
    return {"signals": len(sig), "hits": len(hit), "precision": round(len(hit) / len(sig), 3) if sig else None,
            "base_rate": round(len(base_hit) / len(base), 3) if base else None, "pairs": len(pairs)}
if __name__ == "__main__":
    D = "/workspace/triage_os_data"; db = f"{D}/triage.db"
    print("logged", snapshot(db, f"{D}/hit_log.jsonl"), "chain", verify_chain(f"{D}/hit_log.jsonl"))
    print("outcomes", len(check_outcomes(db, f"{D}/hit_log.jsonl", f"{D}/hit_outcomes.jsonl")))
    print("precision", precision_at_trade(db))
