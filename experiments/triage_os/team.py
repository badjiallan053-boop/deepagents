"""TRIAGE OS agent team: append-only message bus, per-case state, gated roles.

Design: /workspace/triage_os_data/team_research.md (GSD phase contracts, CCG
hard stop + state lock, Ponytail unknowns/skipped/risks footer). Zero
third-party code. Roles are deterministic stubs; each exposes an `llm` hook
(callable(role, case, inbox) -> dict of extra claims/unknowns) where a model
can be plugged in later. No role contacts anyone or takes external action:
`external_action` raises unless a human DECISION approving it is on the bus.
"""
import datetime as dt
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

MSG_TYPES = {"HANDOFF", "REQUEST", "CHALLENGE", "ABSTAIN", "VERIFY", "DECISION"}
CONFIDENCE = {"verified", "inferred", "unknown"}
MAX_SUMMARY_TOKENS = 200
MAX_REVISE_LOOPS = 2
CRITICAL_INPUTS = ("title", "debt", "occupancy", "legal_status")
DESK_LEAD = "desk_lead"
HUMAN = "human_ic"

REJECTION_REASONS = {
    "NO_PROVENANCE": "Key facts cannot be tied to a document, page and date",
    "DUPLICATE": "Same situation already tracked",
    "ENTITY_UNRESOLVED": "Owner/borrower/asset cannot be resolved with confidence",
    "NO_IDENTIFIABLE_ASSET": "No specific asset or claim that could transact",
    "CRITICAL_UNKNOWN": "Title, debt, occupancy or legal status unverifiable",
    "CAPITAL_STACK_OPAQUE": "Debt, liens or fulcrum cannot be reconstructed",
    "NO_SELLER_CONSTRAINT": "No evidence the owner must or will transact",
    "TIMELINE_PASSED": "Auction/bid/sale deadline already passed",
    "TOO_SMALL": "Below desk minimum size",
    "OUT_OF_MANDATE": "Asset class or geography outside scope",
    "NO_BUYER_FIT": "No verified buyer mandate fits",
    "LEGAL_OR_CONFLICT": "Litigation, MNPI or conflict wall issue",
    "CONTRARIAN_KILL": "Red-team kill thesis not rebutted after max revise loops",
    "VERIFIER_FAIL": "Provenance QA failed",
    "HUMAN_REJECTED": "Human IC declined",
}
DEADLINE_FIELDS = ("petition_date", "bid_deadline", "auction_date", "sale_hearing",
                   "objection_deadline", "bar_date", "debt_maturity",
                   "forbearance_expiry", "delisting_deadline")

FULL_READ_ROLES = {"verifier", "ic_secretary"}

class GateError(Exception):
    pass

class HumanGateRequired(GateError):
    pass

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def tokens(text):
    return len((text or "").split())

# --- Bus --------------------------------------------------------------------
def bus_connect(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS bus (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, msg_id TEXT UNIQUE NOT NULL,
      case_id TEXT NOT NULL, ts TEXT NOT NULL, from_role TEXT NOT NULL,
      to_roles TEXT NOT NULL, type TEXT NOT NULL, phase TEXT NOT NULL,
      summary TEXT NOT NULL, claims TEXT NOT NULL, unknowns TEXT NOT NULL,
      skipped TEXT NOT NULL, risks TEXT NOT NULL, next_action TEXT,
      requires_human INTEGER NOT NULL, parent_msg_id TEXT, payload TEXT);
    CREATE TRIGGER IF NOT EXISTS bus_no_update BEFORE UPDATE ON bus
      BEGIN SELECT RAISE(ABORT, 'bus is append-only'); END;
    CREATE TRIGGER IF NOT EXISTS bus_no_delete BEFORE DELETE ON bus
      BEGIN SELECT RAISE(ABORT, 'bus is append-only'); END;
    """)
    return con

def normalize_claim(claim):
    c = dict(claim)
    c.setdefault("confidence", "unknown")
    if c["confidence"] not in CONFIDENCE:
        c["confidence"] = "unknown"
    if not (c.get("source_url") and c.get("as_of")):
        if c["confidence"] != "unknown":
            c["downgraded"] = True
        c["confidence"] = "unknown"
    return c

def post(con, case_id, from_role, to, mtype, phase, summary, claims=None,
         unknowns=None, skipped=None, risks=None, next_action=None,
         requires_human=False, parent_msg_id=None, payload=None):
    if mtype not in MSG_TYPES:
        raise ValueError(f"bad message type {mtype}")
    if tokens(summary) > MAX_SUMMARY_TOKENS:
        raise ValueError("summary exceeds 200 tokens")
    for name, v in (("unknowns", unknowns), ("skipped", skipped), ("risks", risks)):
        if v is None:
            raise ValueError(f"{name} is mandatory (may be an empty list)")
    if mtype == "DECISION" and from_role != HUMAN:
        raise GateError("only the human IC may post DECISION")
    msg = {"msg_id": uuid.uuid4().hex, "case_id": case_id, "ts": now(),
           "from": from_role, "to": list(to), "type": mtype, "phase": phase,
           "summary": summary, "claims": [normalize_claim(c) for c in claims or []],
           "unknowns": list(unknowns), "skipped": list(skipped), "risks": list(risks),
           "next_action": next_action, "requires_human": bool(requires_human),
           "parent_msg_id": parent_msg_id, "payload": payload or {}}
    con.execute("""INSERT INTO bus (msg_id, case_id, ts, from_role, to_roles, type, phase,
        summary, claims, unknowns, skipped, risks, next_action, requires_human,
        parent_msg_id, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (msg["msg_id"], case_id, msg["ts"], from_role, json.dumps(msg["to"]), mtype, phase,
         summary, json.dumps(msg["claims"]), json.dumps(msg["unknowns"]),
         json.dumps(msg["skipped"]), json.dumps(msg["risks"]), next_action,
         int(msg["requires_human"]), parent_msg_id, json.dumps(msg["payload"])))
    con.commit()
    return msg

def messages(con, case_id, to_role=None, mtype=None):
    rows = con.execute("""SELECT msg_id, ts, from_role, to_roles, type, phase, summary, claims,
        unknowns, skipped, risks, next_action, requires_human, parent_msg_id, payload
        FROM bus WHERE case_id=? ORDER BY seq""", (case_id,)).fetchall()
    out = []
    for r in rows:
        m = {"msg_id": r[0], "ts": r[1], "from": r[2], "to": json.loads(r[3]), "type": r[4],
             "phase": r[5], "summary": r[6], "claims": json.loads(r[7]),
             "unknowns": json.loads(r[8]), "skipped": json.loads(r[9]), "risks": json.loads(r[10]),
             "next_action": r[11], "requires_human": bool(r[12]), "parent_msg_id": r[13],
             "payload": json.loads(r[14] or "{}")}
        if to_role and to_role not in m["to"] and "*" not in m["to"]:
            continue
        if mtype and m["type"] != mtype:
            continue
        out.append(m)
    return out

# --- Case state (only DeskLead mutates, under an O_EXCL lock) ----------------
class CaseStore:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, case_id):
        return self.root / case_id / "case.json"

    def read(self, case_id):
        return json.loads(self.path(case_id).read_text())

    @contextmanager
    def lock(self, case_id, role):
        if role != DESK_LEAD:
            raise GateError(f"{role} may not mutate case state; only {DESK_LEAD}")
        d = self.root / case_id
        d.mkdir(parents=True, exist_ok=True)
        lock = d / "case.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise GateError(f"case {case_id} is locked")
        try:
            os.write(fd, role.encode())
            yield
        finally:
            os.close(fd)
            lock.unlink()

    def write(self, case_id, role, state):
        with self.lock(case_id, role):
            state = dict(state, updated_at=now())
            tmp = self.path(case_id).with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2))
            tmp.replace(self.path(case_id))
            return state

def new_case(signal):
    return {"case_id": "case-" + uuid.uuid4().hex[:10], "created_at": now(),
            "status": "OPEN", "phase": "DISCOVER", "signal": signal,
            "gates": {}, "revise_loops": 0, "deadlines": {k: None for k in DEADLINE_FIELDS},
            "rejection_reason": None, "rejection_note": None,
            "critical_inputs": {k: "unknown" for k in CRITICAL_INPUTS},
            "human_decision": None}

# --- Roles (deterministic stubs with LLM hook points) -------------------------
def _hook(llm, role, case, inbox):
    return (llm(role, case, inbox) or {}) if llm else {}

def _signal_claim(case, text, value, confidence="verified"):
    s = case["signal"]
    return {"text": text, "value": value, "source_url": s.get("url"),
            "doc_page": s.get("doc_page", "n/a"), "as_of": s.get("event_date"),
            "confidence": confidence}

def signal_scout(case, inbox, llm=None):
    s = case["signal"]
    ok = bool(s.get("url", "").startswith("https://") and s.get("event_date"))
    extra = _hook(llm, "signal_scout", case, inbox)
    return dict(type="HANDOFF" if ok else "ABSTAIN", phase="DISCOVER",
                summary=f"Signal: {s.get('title')}. Type {s.get('signal_type')}.",
                claims=[_signal_claim(case, "Public record exists", s.get("signal_type"))] + extra.get("claims", []),
                unknowns=["whether the record reflects a transactable asset"] + extra.get("unknowns", []),
                skipped=["did not read underlying document text (stub)"],
                risks=[] if ok else ["missing provenance"], to=["entity_graph"])

def entity_graph(case, inbox, llm=None):
    s = case["signal"]
    extra = _hook(llm, "entity_graph", case, inbox)
    ent = s.get("entity")
    return dict(type="HANDOFF", phase="RESOLVE",
                summary=f"Primary entity from filing caption: {ent}. Sponsor, lenders, subsidiaries not resolved.",
                claims=[_signal_claim(case, "Named entity", ent, "inferred")] + extra.get("claims", []),
                unknowns=["sponsor/owner", "lender group", "asset-level legal entities"] + extra.get("unknowns", []),
                skipped=["no corporate-registry or UCC lookup"], risks=["name collisions"],
                to=["credit_analyst", "property_analyst"],
                payload={"entity_confidence": 0.6 if ent else 0.0})

def credit_analyst(case, inbox, llm=None):
    extra = _hook(llm, "credit_analyst", case, inbox)
    known = extra.get("critical_inputs", {})
    debt = known.get("debt", "unknown")
    return dict(type="HANDOFF" if debt != "unknown" else "ABSTAIN", phase="ANALYZE",
                summary="Capital stack, liens, covenants and fulcrum not reconstructed from cited documents." if debt == "unknown" else "Capital stack reconstructed.",
                claims=extra.get("claims", []), unknowns=["capital stack", "liens", "covenants", "fulcrum security", "distress stage"],
                skipped=["did not open credit agreement / DIP motion"], risks=["recovery cannot be estimated"],
                to=["valuation", "verifier"], payload={"critical_inputs": {"debt": debt, "legal_status": known.get("legal_status", "unknown")}})

def property_analyst(case, inbox, llm=None):
    extra = _hook(llm, "property_analyst", case, inbox)
    known = extra.get("critical_inputs", {})
    ok = all(known.get(k, "unknown") != "unknown" for k in ("title", "occupancy"))
    return dict(type="HANDOFF" if ok else "ABSTAIN", phase="ANALYZE",
                summary="Title, leases, occupancy, capex not verified." if not ok else "Asset facts verified.",
                claims=extra.get("claims", []), unknowns=["title", "occupancy", "leases", "capex", "reuse"],
                skipped=["no county-record or title search"], risks=["asset may not be real-estate/industrial"],
                to=["valuation", "verifier"], payload={"critical_inputs": {"title": known.get("title", "unknown"), "occupancy": known.get("occupancy", "unknown")}})

def valuation(case, inbox, llm=None):
    missing = [k for k in CRITICAL_INPUTS if case["critical_inputs"].get(k, "unknown") == "unknown"]
    if missing:
        return dict(type="ABSTAIN", phase="VALUE",
                    summary=f"Abstain: critical inputs unknown ({', '.join(missing)}). No valuation issued.",
                    claims=[], unknowns=missing, skipped=["downside/base/upside cases"],
                    risks=["any number here would be unsupported"], to=[DESK_LEAD],
                    payload={"rejection_reason": "CRITICAL_UNKNOWN"})
    extra = _hook(llm, "valuation", case, inbox)
    return dict(type="HANDOFF", phase="VALUE", summary="Scenarios built from cited inputs.",
                claims=extra.get("claims", []), unknowns=extra.get("unknowns", []),
                skipped=[], risks=extra.get("risks", []), to=["contrarian", "verifier"])

def contrarian(case, inbox, llm=None):
    extra = _hook(llm, "contrarian", case, inbox)
    kill = extra.get("kill_thesis") or (
        "Signal is a public filing headline only; no evidence of an identifiable asset, "
        "seller constraint or buyer. Treat as unproven." )
    veto = extra.get("veto", True)
    return dict(type="CHALLENGE", phase="CHALLENGE", summary=f"Kill thesis: {kill}",
                claims=[], unknowns=["seller constraint", "asset identity"],
                skipped=[], risks=[kill], to=[DESK_LEAD], payload={"veto": veto})

def verifier(case, inbox, llm=None):
    checked = [c for m in inbox for c in m["claims"] if c.get("source_url")]
    bad = [c["text"] for m in inbox for c in m["claims"]
           if c["confidence"] == "verified" and not (c.get("source_url") and c.get("as_of"))]
    bad += [c["text"] for c in checked
            if c["confidence"] != "unknown" and not str(c["source_url"]).startswith("https://")]
    downgraded = [c["text"] for m in inbox for c in m["claims"] if c.get("downgraded")]
    ok = not bad
    return dict(type="VERIFY", phase="VERIFY",
                summary=("Provenance PASS" if ok else "Provenance FAIL") + f": {len(checked)} sourced claim(s) checked; {len(downgraded)} claim(s) downgraded to unknown.",
                claims=[], unknowns=downgraded, skipped=["did not re-fetch source documents (stub)"],
                risks=bad, to=[DESK_LEAD], payload={"pass": ok, "checked": len(checked)})

def buyer_matcher(case, inbox, llm=None):
    extra = _hook(llm, "buyer_matcher", case, inbox)
    mandates = extra.get("verified_mandates", [])
    return dict(type="HANDOFF", phase="MATCH",
                summary=f"{len(mandates)} verified buyer mandate(s) fit. No outreach performed.",
                claims=extra.get("claims", []), unknowns=[] if mandates else ["buyer fit"],
                skipped=["no contact with any buyer (forbidden pre-DECISION)"],
                risks=[] if mandates else ["no commercial path"], to=["ic_secretary"],
                payload={"mandates": mandates})

def ic_secretary(case, inbox, llm=None):
    unk = sorted({u for m in inbox for u in m["unknowns"]})
    risks = sorted({r for m in inbox for r in m["risks"]})
    claims, seen = [], set()
    for m in inbox:
        for c in m["claims"]:
            key = (c.get("text"), c.get("value"), c.get("source_url"))
            if c["confidence"] != "unknown" and c.get("source_url") and key not in seen:
                seen.add(key)
                claims.append(dict(c, from_role=m["from"]))
    return dict(type="REQUEST", phase="IC_PACK",
                summary=f"IC pack for {case['signal'].get('entity')}: {len(claims)} cited claim(s), {len(unk)} unresolved unknown(s). Human DECISION required.",
                claims=claims, unknowns=unk, skipped=["no valuation (abstained)"] if case["gates"].get("G4") == "abstain" else [],
                risks=risks, to=[HUMAN], requires_human=True,
                next_action="Human IC: approve research conclusions / further diligence, or kill with reason",
                payload={"recommendation": "REQUEST_DOCUMENTS" if unk else "REVIEW"})

# --- Specialist roles (signal pack 2) -----------------------------------------
# Each reads case["signal"]["evidence"]: a list of signals2-style rows
# {signal, entity, value, detail, source_url, as_of}. Read-only; no contact.
def _ev(case, *kinds):
    return [e for e in case["signal"].get("evidence", []) if e.get("signal") in kinds]

def _ev_claims(rows, confidence="inferred"):
    return [{"text": f"{r['signal']}: {r.get('entity')}", "value": r.get("detail"), "source_url": r.get("source_url"),
             "doc_page": "n/a", "as_of": r.get("as_of"), "confidence": confidence} for r in rows]

def forced_seller_monitor(case, inbox, llm=None):
    rows = _ev(case, "bdc_asset_coverage", "nport_outflow_stressed", "cross_markdown", "forced_seller")
    hot = [r for r in rows if "BELOW" in (r.get("detail") or "") or "FORCED-SELLER" in (r.get("detail") or "") or r["signal"] == "cross_markdown"]
    extra = _hook(llm, "forced_seller_monitor", case, inbox)
    return dict(type="HANDOFF" if hot else "ABSTAIN", phase="ANALYZE",
                summary=f"{len(hot)} forced-seller indicator(s) of {len(rows)} checked (coverage <170%, fund outflow + stressed holding, multi-holder markdown).",
                claims=_ev_claims(hot) + extra.get("claims", []), unknowns=["actual sale intent", "covenant headroom in credit facility"],
                skipped=["did not read BDC credit agreements"], risks=[] if hot else ["no seller constraint evidenced"],
                to=["buyer_matcher", "verifier"], payload={"forced_seller_count": len(hot)})

def trade_claims_desk(case, inbox, llm=None):
    rows = _ev(case, "trade_claims_top20")
    free = [r for r in rows if r.get("value")]
    return dict(type="HANDOFF" if free else "ABSTAIN", phase="ANALYZE",
                summary=f"{len(free)} free RECAP document(s) that may carry the top unsecured creditor list; creditor table not parsed.",
                claims=_ev_claims(free), unknowns=["claim amounts", "disputed/contingent flags", "503(b)(9) status"],
                skipped=["no PACER purchase (declined)", "no contact with any creditor"], risks=["individual creditors must be excluded"],
                to=["buyer_matcher", "verifier"], payload={"free_docs": len(free)})

def exposure_mapper(case, inbox, llm=None):
    rows = _ev(case, "exposure_10k_mention", "cmbs_tenant_distress")
    cps = sorted({r.get("entity") for r in rows})
    return dict(type="HANDOFF" if rows else "ABSTAIN", phase="RESOLVE",
                summary=f"{len(cps)} counterparty/property exposure candidate(s) from 10-K concentration text and CMBS rent rolls.",
                claims=_ev_claims(rows), unknowns=["revenue share actually attributable", "lease guarantees"],
                skipped=["did not read full 10-K concentration notes"], risks=["name-match false positives"],
                to=["credit_analyst", "verifier"], payload={"exposed": cps})

def investor_relations(case, inbox, llm=None):
    """Drafts an internal/investor update from the case; never sends. Human gate required."""
    cited = [c for m in inbox for c in m["claims"] if c.get("source_url")]
    draft = "DO NOT SEND - DRAFT\n" + f"Case {case['case_id']} ({case['signal'].get('entity')}): {len(cited)} cited claim(s); status {case['status']}."
    return dict(type="REQUEST", phase="IC_PACK", summary="Investor-update draft prepared (DO NOT SEND). Human approval required before any external use.",
                claims=[], unknowns=[], skipped=["no email or post sent"], risks=["MNPI / selective-disclosure review needed"],
                to=[HUMAN], requires_human=True, next_action="Human: review draft; only a DECISION may approve external use",
                payload={"draft": draft})

SPECIALISTS = ("forced_seller_monitor", "trade_claims_desk", "exposure_mapper", "investor_relations")

ROLES = {"signal_scout": signal_scout, "entity_graph": entity_graph,
         "credit_analyst": credit_analyst, "property_analyst": property_analyst,
         "valuation": valuation, "contrarian": contrarian, "verifier": verifier,
         "buyer_matcher": buyer_matcher, "ic_secretary": ic_secretary,
         "forced_seller_monitor": forced_seller_monitor, "trade_claims_desk": trade_claims_desk,
         "exposure_mapper": exposure_mapper, "investor_relations": investor_relations}
FULL_READ_ROLES = FULL_READ_ROLES | {"investor_relations"}

# --- Desk Lead -----------------------------------------------------------------
class DeskLead:
    def __init__(self, bus, store, llm=None):
        self.bus, self.store, self.llm = bus, store, llm

    def _run(self, role, case):
        # Verifier and IC Secretary audit the whole case; others see only their inbox.
        inbox = messages(self.bus, case["case_id"],
                         to_role=None if role in FULL_READ_ROLES else role)
        out = ROLES[role](case, inbox, self.llm)
        to = out.pop("to")
        out["mtype"] = out.pop("type")
        return post(self.bus, case["case_id"], role, to, **out)

    def _set(self, case, **changes):
        case.update(changes)
        return self.store.write(case["case_id"], DESK_LEAD, case)

    def specialist_pass(self, case):
        """Run the four specialist roles on an existing case; posts to the bus only."""
        return [self._run(r, case) for r in SPECIALISTS]

    def kill(self, case, reason, note):
        if reason not in REJECTION_REASONS:
            raise ValueError(f"unknown rejection reason {reason}")
        post(self.bus, case["case_id"], DESK_LEAD, ["*"], "HANDOFF", "KILL",
             f"Killed: {reason}. {note}"[:1000], unknowns=[], skipped=[], risks=[],
             payload={"outcome_label": "negative", "rejection_reason": reason})
        return self._set(case, status="KILLED", rejection_reason=reason, rejection_note=note)

    def run(self, signal, deadlines=None):
        case = new_case(signal)
        case["deadlines"].update(deadlines or {})
        self.store.root.joinpath(case["case_id"]).mkdir(parents=True, exist_ok=True)
        case = self._set(case)
        m = self._run("signal_scout", case)                       # G1
        if m["type"] == "ABSTAIN":
            return self.kill(case, "NO_PROVENANCE", m["summary"])
        case["gates"]["G1"] = "advance"
        m = self._run("entity_graph", self._set(case, phase="RESOLVE"))  # G2
        case["gates"]["G2"] = "advance" if m["payload"].get("entity_confidence", 0) >= 0.5 else "escalate"
        if case["gates"]["G2"] != "advance":
            return self.kill(case, "ENTITY_UNRESOLVED", m["summary"])
        case = self._set(case, phase="ANALYZE")
        for role in ("credit_analyst", "property_analyst"):        # independent
            m = self._run(role, case)
            case["critical_inputs"].update(m["payload"].get("critical_inputs", {}))
        v = self._run("verifier", case)                            # G3
        case["gates"]["G3"] = "advance" if v["payload"]["pass"] else "kill"
        if not v["payload"]["pass"]:
            return self.kill(case, "VERIFIER_FAIL", v["summary"])
        m = self._run("valuation", self._set(case, phase="VALUE"))   # G4
        case["gates"]["G4"] = "abstain" if m["type"] == "ABSTAIN" else "advance"
        case = self._set(case, phase="CHALLENGE")
        while True:                                                # G5
            c = self._run("contrarian", case)
            if not c["payload"].get("veto"):
                case["gates"]["G5"] = "advance"
                break
            if case["revise_loops"] >= MAX_REVISE_LOOPS:
                case["gates"]["G5"] = "escalate"
                break
            case = self._set(case, revise_loops=case["revise_loops"] + 1)
        self._run("buyer_matcher", self._set(case, phase="MATCH"))   # G6
        self._run("ic_secretary", self._set(case, phase="IC_PACK"))  # G7
        return self._set(case, phase="IC_PACK", status="AWAITING_HUMAN")

def record_decision(bus, store, case_id, approver, decision, approved_actions=(), note=""):
    """Human IC decision. Only path to unlock external actions."""
    if decision not in {"APPROVE", "REJECT", "REQUEST_DOCUMENTS"}:
        raise ValueError("bad decision")
    post(bus, case_id, HUMAN, [DESK_LEAD], "DECISION", "DECISION",
         f"{decision} by {approver}. {note}", unknowns=[], skipped=[], risks=[],
         payload={"decision": decision, "approver": approver,
                  "approved_actions": list(approved_actions)})
    case = store.read(case_id)
    case["human_decision"] = {"decision": decision, "approver": approver, "at": now()}
    if decision == "REJECT":
        case.update(status="KILLED", rejection_reason="HUMAN_REJECTED", rejection_note=note)
    return store.write(case_id, DESK_LEAD, case)

def external_action(bus, case_id, action):
    """Hard stop: any outreach/bid/publication needs a human APPROVE naming it.
    Even when approved, this function does not perform the action; it only
    returns permission for a human-operated step."""
    for m in reversed(messages(bus, case_id, mtype="DECISION")):
        p = m["payload"]
        if m["from"] == HUMAN and p.get("decision") == "APPROVE" and action in p.get("approved_actions", []):
            return {"permitted": True, "action": action, "approver": p["approver"]}
    raise HumanGateRequired(f"'{action}' blocked: no human DECISION approving it")


def evidence_from_db(con, like):
    """signals2 rows whose entity/key matches `like` (SQL LIKE), as role evidence dicts."""
    cur = con.execute("select signal, entity, value, detail, source_url, as_of from signals2 where lower(entity) like ? or lower(key) like ?",
                      (like.lower(), like.lower()))
    return [dict(zip(("signal", "entity", "value", "detail", "source_url", "as_of"), r)) for r in cur]

# --- Desk agents added 23 Oct 2026 (created by the user; roles recorded here) ---------------------------
DESK_AGENTS = {
    "quant_validation": dict(veto=True, owns=["signals.py", "committee_v2.py", "backtest hygiene"],
        charter="Backtest hygiene for every signal and committee: point-in-time data (ALFRED vintages), publication lags, "
                "survivorship, multiple testing, costs and capacity, kill rule. May only veto, never add. Nothing reaches the "
                "PDF, the app or the ledger without its pass."),
    "commodities_shipping": dict(veto=False, owns=["EIA", "SHFE/CME/LME stocks", "Comtrade", "AIS (gap)"],
        charter="Physical-flow data and commodity signals; weekly balances and squeeze watchlist."),
    "crypto_flows": dict(veto=False, owns=["stablecoins", "funding/OI", "ETF flows", "unlocks", "estate & government wallets"],
        charter="Mechanical crypto supply/demand, including estate distributions as forced sellers."),
    "macro_regime": dict(veto=False, owns=["regime dashboard", "ALFRED vintages"],
        charter="Dalio-style regime with point-in-time data; supplies the macro context to the credit product."),
    "mining_geologist": dict(veto=False, owns=["BLM MLRS", "USGS/GA deposits", "Sentinel/FIRMS sites"],
        charter="Joins deposits, tenure and owners; maintains staking and site-activity layers."),
    "ledger_compliance": dict(veto=True, owns=["anchor_ledger.py", "verify_ledger.py", "licensing memo"],
        charter="Daily OpenTimestamps anchor (routine 23:30 SGT), chain checks, keeps output impersonal; vetoes anything that "
                "reads as personalised advice."),
}

def quant_validation_gate(signal):
    """Veto unless a signal is KEPT, has >= 8 OOS events, states its OOS start, and declares point-in-time handling.
    Returns (passed, reasons). Used before a signal is shown as a recommendation-grade item."""
    reasons = []
    if signal.get("status") != "KEPT": reasons.append(f"status {signal.get('status')}")
    if (signal.get("oos") or {}).get("n", 0) < 8: reasons.append("fewer than 8 OOS events")
    if not signal.get("oos_start"): reasons.append("no stated OOS period")
    if not signal.get("pit"): reasons.append("not point-in-time (revised data or undeclared)")
    return (not reasons), reasons
