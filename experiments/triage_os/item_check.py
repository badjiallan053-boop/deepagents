"""Verifier item-text check: flag 8-K items whose text contradicts the coded item.

Read-only, offline: callers pass the filing text. Returns (status, reason).
"""
import re

EMERGENCE = [r"emerged from (the )?chapter 11", r"plan became effective", r"effective date[^.]{0,80}(occurred|satisfied)",
             r"conditions to (the )?effectiveness of the plan were satisfied"]
NEW_FILING = [r"filed (a )?voluntary petitions?", r"commenced (a )?voluntary (case|cases|proceedings?)", r"\(the [\"“]petition date[\"”]\)"]
NO_DEFAULT = [r"no default or event of default (shall )?exist", r"no event of default (has occurred|exists)"]
CHANGE_OF_CONTROL = [r"merger was consummated", r"change of control", r"closing of the merger"]
REAL_DEFAULT = [r"event of default (has )?occurred", r"accelerat(ed|ion) of (the )?(obligations|indebtedness)", r"forbearance agreement", r"failed to (make|pay)"]


def _any(pats, text):
    return any(re.search(p, text) for p in pats)


def check_items(items, text):
    t = re.sub(r"\s+", " ", (text or "").lower())
    items = {str(i) for i in items}
    flags = []
    if "1.03" in items and _any(EMERGENCE, t) and not _any(NEW_FILING, t):
        flags.append("1.03 = emergence/plan effective, not a new filing")
    if "2.04" in items and not _any(REAL_DEFAULT, t) and (_any(NO_DEFAULT, t) or _any(CHANGE_OF_CONTROL, t)):
        flags.append("2.04 = change-of-control/amendment trigger, no default stated")
    if not t:
        return "unverified", "no filing text"
    return ("false_positive", "; ".join(flags)) if flags and len(flags) == len(items & {"1.03", "2.04"}) else (
        ("partial", "; ".join(flags)) if flags else ("confirmed", "item text consistent"))
