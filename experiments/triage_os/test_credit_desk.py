import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
def test_flagship_json():
    d = json.load(open("/workspace/triage_os_data/flagship.json"))
    assert len(d["partners"]) == 10 and len(d["tiers"]) >= 3 and d["ledger"]["ok"]
def test_quant_gate():
    sys.path.insert(0, HERE); import team
    assert team.quant_validation_gate(dict(status="KILLED", oos=dict(n=50), oos_start="2019-01-01", pit=True))[0] is False
    assert len(team.DESK_AGENTS) == 6
def test_anchor_idempotent():
    r1 = subprocess.run([sys.executable, "anchor_ledger.py"], cwd=HERE, capture_output=True, text=True, timeout=300)
    r2 = subprocess.run([sys.executable, "anchor_ledger.py"], cwd=HERE, capture_output=True, text=True, timeout=300)
    assert r1.returncode == 0 and r2.returncode == 0 and "unchanged" in r2.stdout
def test_bottleneck():
    d = json.load(open("/workspace/triage_os_data/bottleneck.json"))
    assert len(d["top"]) == 15 and d["ledger_ok"] and all(c["kill"] and c["cat"][0] for c in d["top"])
    assert "100x" not in json.dumps(d["top"]).replace("claims 100x", "")
def test_edge_lab():
    d = json.load(open("/workspace/triage_os_data/edge_lab.json"))["results"]
    kept = [k for k, v in d.items() if v["status"] == "KEPT"]
    for k in kept: assert d[k]["OOS"]["n"] >= 8 and d[k]["OOS"]["mean"] > 0
    assert len(d) >= 7
def test_reorg_bnf_live():
    r = json.load(open("/workspace/triage_os_data/reorg_ww.json")); b = json.load(open("/workspace/triage_os_data/bnf_cis.json"))
    assert r["counts"]["events"] > 0 and "missing_as_minus100" in r["survivorship"] and len(b["results"]) >= 15
    sys.path.insert(0, HERE); import live_service
    assert live_service.is_open("7203.T", __import__("datetime").datetime(2026, 10, 23, 1, 0, tzinfo=__import__("datetime").timezone.utc))
