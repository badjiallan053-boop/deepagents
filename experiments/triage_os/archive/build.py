"""TRIAGE OS - static, timestamped watchlist archive (no deployment).

publish(csv, site_dir, snapshot_id, published_at): copies the CSV into
snapshots/<id>/, records its SHA-256, and (re)renders index.html, one page per
snapshot, and scoring.html, which compares each archived prediction with recorded
outcomes (outcomes.csv: entity,outcome,outcome_date,source_url). Snapshots are append-only:
re-publishing an id with different bytes raises. The git commit of the site directory gives
an independent timestamp; an OpenTimestamps proof (`ots stamp manifest.json`) can be added.
"""
import csv, datetime as dt, hashlib, html, json, os, shutil, sys
from pathlib import Path

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _page(title, body):
    return (f"<!doctype html><html lang=en><meta charset=utf-8><title>{html.escape(title)}</title>"
            "<style>body{font:14px system-ui;max-width:1100px;margin:2em auto;padding:0 1em}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:4px;text-align:left;vertical-align:top}"
            "code{font-size:12px}</style>"
            f"<h1>{html.escape(title)}</h1>{body}<p><small>Public-data research, unverified signals, not investment advice.</small></p></html>")

def load_manifest(site):
    p = Path(site) / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {"snapshots": []}

def publish(csv_path, site, snapshot_id, published_at=None):
    site = Path(site); site.mkdir(parents=True, exist_ok=True)
    man = load_manifest(site)
    digest = sha256(csv_path)
    sid = f"{int(snapshot_id):03d}"
    for s in man["snapshots"]:
        if s["id"] == sid:
            if s["sha256"] != digest:
                raise ValueError(f"snapshot {sid} already published with a different hash")
            break
    else:
        d = site / "snapshots" / sid; d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(csv_path, d / "watchlist.csv")
        man["snapshots"].append({"id": sid, "sha256": digest, "file": f"snapshots/{sid}/watchlist.csv",
                                 "published_at": published_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    (site / "manifest.json").write_text(json.dumps(man, indent=1))
    render(site, man)
    return man

def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def score(site, man, horizon_days=180):
    outcomes = {}
    op = Path(site) / "outcomes.csv"
    if op.exists():
        for r in _rows(op):
            outcomes.setdefault(r["entity"].strip().lower(), []).append(r)
    res = []
    for s in man["snapshots"]:
        t0 = dt.datetime.fromisoformat(s["published_at"])
        for r in _rows(Path(site) / s["file"]):
            hit = None
            for o in outcomes.get(r["entity"].strip().lower(), []):
                od = dt.datetime.fromisoformat(o["outcome_date"]).replace(tzinfo=t0.tzinfo or dt.timezone.utc)
                if t0 <= od <= t0 + dt.timedelta(days=horizon_days):
                    hit = o
            res.append({"snapshot": s["id"], "rank": r["rank"], "entity": r["entity"], "score": r["score"],
                        "outcome": hit["outcome"] if hit else "", "outcome_date": hit["outcome_date"] if hit else "",
                        "lead_days": (dt.datetime.fromisoformat(hit["outcome_date"]).date() - t0.date()).days if hit else "",
                        "source_url": hit["source_url"] if hit else ""})
    return res

def render(site, man):
    site = Path(site)
    items = "".join(f"<tr><td><a href='snapshots/{s['id']}/index.html'>#{s['id']}</a></td><td>{s['published_at']}</td>"
                    f"<td><code>{s['sha256']}</code></td><td><a href='{s['file']}'>CSV</a></td></tr>" for s in man["snapshots"])
    (site / "index.html").write_text(_page("TRIAGE OS - pre-filing watchlist archive",
        "<p>Each snapshot is frozen when published; its SHA-256 is listed here and in <a href='manifest.json'>manifest.json</a>. "
        "Verify with <code>sha256sum watchlist.csv</code>. <a href='scoring.html'>Scoring vs outcomes</a>.</p>"
        f"<table><tr><th>Snapshot</th><th>Published (UTC)</th><th>SHA-256</th><th>File</th></tr>{items}</table>"))
    for s in man["snapshots"]:
        rows = _rows(site / s["file"])
        cols = ["rank", "score", "entity", "signal_types", "evidence_1"]
        body = "".join("<tr>" + "".join(f"<td>{_link(r.get(c, ''))}</td>" for c in cols) + "</tr>" for r in rows)
        (site / "snapshots" / s["id"] / "index.html").write_text(_page(f"Snapshot #{s['id']} - {s['published_at']}",
            f"<p>SHA-256 <code>{s['sha256']}</code></p><table><tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr>{body}</table>"))
    res = score(site, man)
    hits = [r for r in res if r["outcome"]]
    body = (f"<p>{len(hits)} of {len(res)} archived predictions matched an outcome within 180 days "
            f"(outcomes recorded in outcomes.csv with a source).</p><table><tr><th>Snap</th><th>Rank</th><th>Entity</th>"
            "<th>Score</th><th>Outcome</th><th>Date</th><th>Lead days</th><th>Source</th></tr>" +
            "".join(f"<tr><td>{r['snapshot']}</td><td>{r['rank']}</td><td>{html.escape(r['entity'])}</td><td>{r['score']}</td>"
                    f"<td>{html.escape(r['outcome'])}</td><td>{r['outcome_date']}</td><td>{r['lead_days']}</td><td>{_link(r['source_url'])}</td></tr>"
                    for r in res) + "</table>")
    (site / "scoring.html").write_text(_page("Scoring: predictions vs outcomes", body))

def _link(v):
    v = str(v)
    import re
    m = re.search(r"https://\S+", v)
    if not m:
        return html.escape(v)
    u = m.group(0)
    return html.escape(v[:m.start()]) + f"<a href='{html.escape(u)}'>source</a>"

if __name__ == "__main__":
    csv_path, site, sid = sys.argv[1:4]
    print(json.dumps(publish(csv_path, site, sid, sys.argv[4] if len(sys.argv) > 4 else None), indent=1))
