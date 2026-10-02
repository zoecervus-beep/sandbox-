"""Build the map atlas from data-src/.

  python3 build/build_atlas.py

1. validate data-src/ (errors stop the build)
2. resolve every region to a shape (build/geom.py)
3. overlay all regions into atoms: the planar partition in which each piece is covered by exactly
   the same set of regions. Records stay keyed to regions; atoms are only a build product.
4. resolve claims and control per atom at every change point to get the area series
5. write data/atlas.topo.json (atoms + basemap, shared-arc TopoJSON) and data/atlas.json (everything else)

Resolution rules, mirrored in index.html:
  claims   - among active claims of the focal polity covering an atom, the claim on the smallest region wins
  control  - every active record is drawn (solid, fuzzy, then crisp passes). The per-atom summary used for
             areas, outlines, divergence and tooltips is the record with the highest precedence, then the
             most severe loss of control (foreign > rival > contested > independent > autonomous > direct),
             then the smallest region, then the latest start
"""
import json, subprocess, sys, os, datetime as dt
from collections import defaultdict
import shapely
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
import geom
from validate import load, validate, dec

ROOT = geom.ROOT
T0, T1 = 1800.0, 2026.75
FOCAL = "iran"
BBOX = box(34.5, 21.0, 75.5, 46.5)
GRID = 0.0005            # snapping grid in degrees (~50 m)

D = load()
E, W = validate(D, geom.cat)
for w in W: print("warning:", w)
if E:
    for e in E: print("ERROR:", e)
    sys.exit(f"{len(E)} validation errors; build stopped")
warnings = list(W)
def warn(m):
    warnings.append(m); print("warning:", m)

# ---------------------------------------------------------------- regions -> shapes
shapes = geom.resolve_regions(D["regions"], warn)
shapes = {k: geom.clean(shapely.set_precision(g, GRID)) for k, g in shapes.items() if not g.is_empty}
rids = list(shapes)
rarea = {k: geom.km2(g) for k, g in shapes.items()}

# ---------------------------------------------------------------- atoms
lines = unary_union([shapes[k].boundary for k in rids])
faces = [f for f in polygonize(lines) if f.area > 0]
tree = STRtree([shapes[k] for k in rids])
def members(f):
    pt = f.representative_point()
    return frozenset(rids[j] for j in tree.query(pt, predicate="intersects"))
face_m = [members(f) for f in faces]
keep = [i for i, m in enumerate(face_m) if m]
faces = [faces[i] for i in keep]; face_m = [face_m[i] for i in keep]
face_a = [geom.km2(f) for f in faces]

# slivers: thin or tiny faces from near-coincident borders of different source datasets take
# the membership of the neighbour they share most border with
import math
def is_sliver(i):
    a, p = face_a[i], faces[i].length * 111.0
    q = 4 * math.pi * a / (p * p) if p else 1
    return a < 0.3 or (a < 25 and q < 0.05)
ftree = STRtree(faces)
merged_km2 = 0.0
for i in sorted(range(len(faces)), key=lambda i: face_a[i]):
    if not is_sliver(i):
        continue
    best, best_len = None, 0.0
    for j in ftree.query(faces[i], predicate="intersects"):
        if j == i or face_m[j] == face_m[i]:
            continue
        L = faces[i].boundary.intersection(faces[j].boundary).length
        if L > best_len:
            best, best_len = j, L
    if best is not None:
        face_m[i] = face_m[best]
        merged_km2 += face_a[i]

groups = defaultdict(list)
for f, m in zip(faces, face_m):
    groups[m].append(f)
atom_keys = sorted(groups, key=lambda m: sorted(m))
atoms = [geom.clean(unary_union(groups[m])) for m in atom_keys]
atom_area = [geom.km2(a) for a in atoms]
region_atoms = defaultdict(list)
for i, m in enumerate(atom_keys):
    for rid in m:
        region_atoms[rid].append(i)
for rid in rids:
    got = sum(atom_area[i] for i in region_atoms.get(rid, []))
    if not region_atoms.get(rid):
        warn(f"region {rid} has no atoms left after sliver removal")
    elif abs(got - rarea[rid]) > max(2.0, 0.02 * rarea[rid]):
        warn(f"region {rid}: atoms cover {got:.0f} km2 of {rarea[rid]:.0f} km2")
print(f"{len(faces)} faces -> {len(atoms)} atoms; slivers reassigned: {merged_km2:.1f} km2")

# ---------------------------------------------------------------- records
def timed(r):
    r = dict(r); r["t0"] = dec(r.get("from")); r["t1"] = dec(r.get("to")); return r
claims = [timed(r) for r in D["claims"]]
control = [timed(r) for r in D["control"]]
events = []
for e in D["events"]:
    e = dict(e); e["t"] = dec(e.get("date")); e["t_end"] = dec(e.get("end_date")); events.append(e)
events.sort(key=lambda e: (e["t"] is None, e["t"] or 0))

def active(rs, t):
    return [r for r in rs if r["t0"] <= t and (r["t1"] is None or t < r["t1"])]

def resolve(t):
    """Per-atom claim record and control record at time t (same rules as index.html)."""
    cl = [None] * len(atoms)
    for r in sorted(active([c for c in claims if c["polity"] == FOCAL], t), key=lambda r: -rarea.get(r["region"], 0)):
        for i in region_atoms.get(r["region"], []):
            cl[i] = r
    ct = [None] * len(atoms)
    for r in sorted(active(control, t), key=control_rank):
        for i in region_atoms.get(r["region"], []):
            ct[i] = r
    return cl, ct

SEVERITY = {"direct": 0, "focal_occupied": 0, "autonomous": 1, "independent": 2, "contested": 3, "rival": 4, "foreign": 5}
def control_rank(r):
    """Ascending: the last record assigned to an atom is its summary state."""
    return (r.get("precedence", 1), SEVERITY[category(r)], -rarea.get(r["region"], 0), r["t0"])

def category(r):
    if r is None: return None
    m, c, a = r["mode"], r["controller"], r.get("allegiance")
    if m == "contested": return "contested"
    if m == "insurgent": return "rival"
    if m == "independent": return "independent"
    if c == FOCAL: return "direct" if m == "administered" else "focal_occupied"
    if a == FOCAL and m == "autonomous": return "autonomous"
    return "foreign"

cps = sorted({T0} | {t for r in claims + control for t in (r["t0"], r["t1"]) if t is not None and T0 <= t <= T1})
series = []
for t in cps:
    cl, ct = resolve(t + 1e-5)
    s = {"t": t, "claim": 0.0, "held": 0.0, "direct": 0.0, "contested": 0.0}
    for i, a in enumerate(atom_area):
        if cl[i]: s["claim"] += a
        c = category(ct[i])
        if c in ("direct", "focal_occupied", "autonomous"): s["held"] += a
        if c in ("direct", "focal_occupied"): s["direct"] += a
        if c == "contested": s["contested"] += a
    series.append({k: (round(v) if k != "t" else v) for k, v in s.items()})

# ---------------------------------------------------------------- basemap + topology
tmp = ROOT + "build/tmp/"
os.makedirs(tmp, exist_ok=True)
def fc(feats): return {"type": "FeatureCollection", "features": feats}
def dump(name, feats): json.dump(fc(feats), open(tmp + name + ".geojson", "w"))
dump("atoms", [{"type": "Feature", "properties": {"i": i}, "geometry": mapping(a)} for i, a in enumerate(atoms)])
dump("modern", [{"type": "Feature", "properties": {}, "geometry": mapping(shapes["modern_iran"])}])
ne = json.load(open(ROOT + "raw/ne_10m_admin_0_countries.geojson"))["features"]
dump("countries", [{"type": "Feature", "properties": {"iso": f["properties"]["ADM0_A3"]},
                    "geometry": mapping(geom.clean(shape(f["geometry"]).intersection(BBOX)))}
                   for f in ne if shape(f["geometry"]).intersects(BBOX)])
dump("lakes", [{"type": "Feature", "properties": {}, "geometry": mapping(geom.clean(shape(f["geometry"])))}
               for f in json.load(open(ROOT + "raw/ne_10m_lakes.geojson"))["features"]
               if shape(f["geometry"]).intersects(BBOX) and geom.km2(shape(f["geometry"])) > 150])
RIV = {"Aras", "Atrek", "Kura", "Shatt al Arab", "Tigris", "Dicle", "Euphrates", "Al Furat", "Firat", "Harirud", "Helmand",
       "Karkheh", "Amu  Darya", "Qezel Owzan", "Sefid", "Talkeh", "Murat", "Volga"}
dump("rivers", [{"type": "Feature", "properties": {}, "geometry": mapping(shape(f["geometry"]).intersection(BBOX))}
                for f in json.load(open(ROOT + "raw/ne_10m_rivers_lake_centerlines.geojson"))["features"]
                if f["properties"].get("name") in RIV and shape(f["geometry"]).intersects(BBOX)])
layers = ["atoms", "modern", "countries", "lakes", "rivers"]
cmd = ["mapshaper", "-i", *[tmp + n + ".geojson" for n in layers], "combine-files", "snap", "snap-interval=0.0005",
       "-simplify", "weighted", "keep-shapes", "interval=900",
       "-o", ROOT + "data/atlas.topo.json", "format=topojson", "quantization=100000", "force"]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr)

# ---------------------------------------------------------------- atlas.json
def rmeta(rid):
    v = D["regions"][rid]; g = shapes[rid]; p = g.representative_point()
    return {"name": v.get("name"), "name_fa": v.get("name_fa"), "kind": v["kind"],
            "geometry_confidence": v.get("geometry_confidence"), "geometry_note": v.get("geometry_note"),
            "area_km2": round(rarea[rid]), "label": [round(p.x, 3), round(p.y, 3)], "atoms": region_atoms.get(rid, [])}
def strip(r):
    return {k: v for k, v in r.items() if v is not None or k in ("to", "t1", "allegiance")}
out = {
    "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "range": [T0, T1], "focal": FOCAL,
    "polities": D["polities"],
    "regions": {rid: rmeta(rid) for rid in rids},
    "atom_area": [round(a, 2) for a in atom_area],
    "sources": D["sources"],
    "claims": [strip(r) for r in claims],
    "control": [strip(r) for r in control],
    "events": [strip(e) for e in events],
    "series": series,
}
json.dump(out, open(ROOT + "data/atlas.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(warnings, open(ROOT + "build/warnings.json", "w"), indent=1)
print(f"regions {len(rids)}  atoms {len(atoms)}  claims {len(claims)}  control {len(control)}  events {len(events)}  change points {len(cps)}")
print(f"atlas.topo.json {os.path.getsize(ROOT + 'data/atlas.topo.json') // 1024} KB, atlas.json {os.path.getsize(ROOT + 'data/atlas.json') // 1024} KB, warnings {len(warnings)}")
