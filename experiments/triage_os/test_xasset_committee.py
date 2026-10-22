import json, os, hashlib
import committee as C
def test_mining_json():
    J = json.load(open("/workspace/triage_os_data/mining.json"))
    assert len(J["events"]) == 4 and all(e["found"] and "mofcom.gov.cn" in e["url"] for e in J["events"])
    assert len(J["claims"]["sites"]) == 5 and J["gaps"]
    assert any(d["pillar"] == "Reserve-currency share" and "2026" in d["value"] for d in J["regime"])
def test_chain_verifies_and_detects_tamper(tmp_path):
    ok, n = C.verify(); assert ok and n >= 20
    lines = open(C.LEDGER).read().splitlines(); r = json.loads(lines[0]); r["entry"] = 1.0
    p = tmp_path / "t.jsonl"; p.write_text("\n".join([json.dumps(r)] + lines[1:]) + "\n")
    old = C.LEDGER; C.LEDGER = str(p)
    try: assert C.verify()[0] is False
    finally: C.LEDGER = old
def test_every_agent_speaks_twice_and_paper_only():
    v, how, rnd, log = C.debate("SPY", "2020-03-31")
    assert len(log) >= 2 and all(k in log[0] and k in log[1] for k in C.ROLES)
    assert all(json.loads(l)["paper_only"] for l in open(C.LEDGER))
def test_backtest_has_baselines():
    b = json.load(open("/workspace/triage_os_data/committee/backtest.json"))
    for p in ("risk_neutral", "risk_averse"):
        assert {"committee", "equal_weight", *C.ROLES} <= set(b[p]["full"])
