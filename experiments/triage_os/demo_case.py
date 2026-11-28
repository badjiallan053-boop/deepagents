"""Run one case end-to-end from the top stored signal. Stops at the human gate."""
import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path

def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

desk, team = _load("desk"), _load("team")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--signals-db", required=True)
    p.add_argument("--workdir", required=True)
    a = p.parse_args()
    top = desk.rank(sqlite3.connect(a.signals_db), 1)[0]
    signal = {k: top[k] for k in ("title", "entity", "url", "event_date", "signal_type", "source", "priority")}
    wd = Path(a.workdir); wd.mkdir(parents=True, exist_ok=True)
    bus = team.bus_connect(wd / "bus.db")
    case = team.DeskLead(bus, team.CaseStore(wd / "cases")).run(signal)
    print(json.dumps({"case": case, "messages": [
        {k: m[k] for k in ("from", "type", "phase", "summary")} for m in team.messages(bus, case["case_id"])]}, indent=2))
    try:
        team.external_action(bus, case["case_id"], "contact_seller")
    except team.HumanGateRequired as e:
        print("HUMAN GATE:", e)

if __name__ == "__main__":
    main()
