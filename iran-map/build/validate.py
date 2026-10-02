"""Validate data-src/ before a build. Usage: python3 build/validate.py   (exit 1 on errors)

Errors block the build; warnings are printed and written to build/warnings.json.
"""
import json, re, sys, datetime as dt

ROOT = "/home/user/sandbox-/iran-map/"
SRC = ROOT + "data-src/"
MODES = {"administered", "occupied", "autonomous", "independent", "insurgent", "contested"}
CLAIM_KINDS = {"sovereignty", "suzerainty"}
CONF = {None, "high", "medium", "low"}
REGION_KINDS = {"frontier", "internal", "core", "reference"}
POLITY_KINDS = {"state", "principality", "khanate", "sheikhdom", "tribal", "movement"}

def dec(d):
    """'1828-02-21' / '1828-02' / '1828' -> decimal year; None stays None (open-ended)."""
    if d is None:
        return None
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$", str(d).strip())
    if not m:
        raise ValueError(f"bad date {d!r}")
    y, mo, da = int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)
    doy = (dt.date(y, mo, da) - dt.date(y, 1, 1)).days
    days = 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    return round(y + doy / days, 4)

def load():
    jl = lambda f: [json.loads(l) for l in open(SRC + f) if l.strip()]
    return {"polities": json.load(open(SRC + "polities.json")), "regions": json.load(open(SRC + "regions.json")),
            "sources": json.load(open(SRC + "sources.json")), "claims": jl("claims.jsonl"),
            "control": jl("control.jsonl"), "events": jl("events.jsonl")}

def validate(D, catalog):
    E, W = [], []
    P, Rg, S = D["polities"], D["regions"], D["sources"]
    ev_ids = {e["id"] for e in D["events"]}

    def check_dates(tag, r):
        try:
            a, b = dec(r.get("from")), dec(r.get("to"))
        except ValueError as e:
            E.append(f"{tag}: {e}"); return None, None
        if a is None:
            E.append(f"{tag}: missing 'from'")
        if a is not None and b is not None and b <= a:
            E.append(f"{tag}: 'to' {r['to']} is not after 'from' {r['from']}")
        return a, b

    def check_cites(tag, r):
        for c in r.get("cites", []):
            sid = c["src"] if isinstance(c, dict) else c
            if sid not in S:
                E.append(f"{tag}: unknown source {sid}")

    def check_events(tag, r):
        for k in ("start_event", "end_event"):
            if r.get(k) and r[k] not in ev_ids:
                E.append(f"{tag}: {k} {r[k]} not in events")

    def lifespan_warn(tag, pid, a, b):
        p = P.get(pid, {})
        pa, pb = dec(p.get("from")), dec(p.get("to"))
        if pb is not None and a is not None and a >= pb:
            W.append(f"{tag}: polity {pid} ended {p['to']} before this record starts")
        elif pb is not None and (b is None or b > pb + 0.01):
            W.append(f"{tag}: runs past the end of polity {pid} ({p['to']})")
        if pa is not None and a is not None and a < pa - 0.01:
            W.append(f"{tag}: starts before polity {pid} existed ({p['from']})")

    for pid, p in P.items():
        if p.get("kind") not in POLITY_KINDS:
            E.append(f"polity {pid}: kind {p.get('kind')!r}")
        if not p.get("name"):
            E.append(f"polity {pid}: no name")

    for rid, r in Rg.items():
        if r.get("kind") not in REGION_KINDS:
            E.append(f"region {rid}: kind {r.get('kind')!r}")
        if not (r.get("units") or r.get("custom")):
            E.append(f"region {rid}: needs units or a custom shape")
        for k in r.get("units", []) + r.get("minus_units", []) + (r.get("custom") or {}).get("within_units", []):
            if k not in catalog:
                E.append(f"region {rid}: unknown unit {k}")
        for m in r.get("minus_regions", []) + ([r["clip_to_region"]] if r.get("clip_to_region") else []):
            if m not in Rg:
                E.append(f"region {rid}: refers to unknown region {m}")
        if r.get("geometry_confidence") not in CONF:
            E.append(f"region {rid}: geometry_confidence {r.get('geometry_confidence')!r}")

    seen = set()
    by_pr = {}
    for r in D["claims"]:
        tag = f"claim {r.get('id')}"
        if r.get("id") in seen: E.append(f"{tag}: duplicate id")
        seen.add(r.get("id"))
        if r.get("polity") not in P: E.append(f"{tag}: unknown polity {r.get('polity')}")
        if r.get("region") not in Rg: E.append(f"{tag}: unknown region {r.get('region')}")
        if r.get("kind") not in CLAIM_KINDS: E.append(f"{tag}: kind {r.get('kind')!r}")
        if r.get("date_confidence") not in CONF: E.append(f"{tag}: date_confidence {r.get('date_confidence')!r}")
        a, b = check_dates(tag, r)
        check_cites(tag, r); check_events(tag, r)
        by_pr.setdefault((r.get("polity"), r.get("region")), []).append((a, b, r.get("id")))

    by_r = {}
    for r in D["control"]:
        tag = f"control {r.get('id')}"
        if r.get("id") in seen: E.append(f"{tag}: duplicate id")
        seen.add(r.get("id"))
        if r.get("region") not in Rg: E.append(f"{tag}: unknown region {r.get('region')}")
        for k in ("controller", "allegiance"):
            if r.get(k) is not None and r[k] not in P:
                E.append(f"{tag}: unknown {k} {r[k]}")
        if r.get("controller") is None: E.append(f"{tag}: no controller")
        if r.get("mode") not in MODES: E.append(f"{tag}: mode {r.get('mode')!r}")
        vs = r.get("contested_with", [])
        for v in vs:
            if v not in P: E.append(f"{tag}: unknown contested_with {v}")
        if (r.get("mode") == "contested") != bool(vs):
            W.append(f"{tag}: mode is {r.get('mode')} but contested_with is {vs or 'empty'}")
        if r.get("allegiance") and r.get("mode") != "autonomous":
            W.append(f"{tag}: allegiance set on a {r.get('mode')} record")
        if not isinstance(r.get("precedence", 1), int): E.append(f"{tag}: precedence must be an integer")
        if r.get("date_confidence") not in CONF: E.append(f"{tag}: date_confidence {r.get('date_confidence')!r}")
        a, b = check_dates(tag, r)
        check_cites(tag, r); check_events(tag, r)
        for pid in [r.get("controller"), r.get("allegiance")] + vs:
            if pid and pid in P:
                lifespan_warn(tag, pid, a, b)
        by_r.setdefault(r.get("region"), []).append((a, b, r.get("id")))

    for groups, what in ((by_pr, "claims"), (by_r, "control records")):
        for key, rs in groups.items():
            rs = sorted([x for x in rs if x[0] is not None])
            for (a0, a1, ia), (b0, b1, ib) in zip(rs, rs[1:]):
                if a1 is None or a1 > b0 + 0.001:
                    E.append(f"overlapping {what} for {key}: {ia} and {ib}")

    for e in D["events"]:
        tag = f"event {e.get('id')}"
        if e["id"] in seen: E.append(f"{tag}: duplicate id")
        seen.add(e["id"])
        try:
            dec(e.get("date")); dec(e.get("end_date"))
        except ValueError as x:
            E.append(f"{tag}: {x}")
        check_cites(tag, e)
        for l in e.get("layers", []):
            if l not in ("dejure", "defacto"): E.append(f"{tag}: layer {l!r}")

    cited = {(c["src"] if isinstance(c, dict) else c) for r in D["claims"] + D["control"] + D["events"] for c in r.get("cites", [])}
    for sid in S:
        if sid not in cited:
            W.append(f"source {sid} is never cited")
    return E, W

if __name__ == "__main__":
    catalog = json.load(open(ROOT + "build/catalog.json"))
    E, W = validate(load(), catalog)
    for w in W: print("warning:", w)
    for e in E: print("ERROR:", e)
    print(f"{len(E)} errors, {len(W)} warnings")
    sys.exit(1 if E else 0)
