"""Build map data for the Iran territorial map.

Inputs
  research/*.json        region definitions + de jure / de facto records + events (see research/SCHEMA.md)
  build/catalog.json     modern admin-unit keys -> source files
  raw/                   geoBoundaries + Natural Earth source geometry

Outputs
  data/geo.json          TopoJSON: basemap, core, regions, per-interval dissolved extents
  data/history.json      region metadata, layer records, events, area series
"""
import json, glob, math, re, subprocess, sys, datetime as dt
from functools import lru_cache
from shapely.geometry import shape, mapping, box, Point, Polygon, MultiPolygon, LineString, GeometryCollection
from shapely.ops import unary_union, split, transform
from shapely import make_valid
import pyproj

ROOT = "/home/user/sandbox-/iran-map/"
BBOX = box(34.5, 21.0, 75.5, 46.5)
cat = json.load(open(ROOT + "build/catalog.json"))
warnings = []

def warn(msg):
    warnings.append(msg)
    print("WARN", msg, file=sys.stderr)

# ---------- source geometry ----------
_files = {}
def gb(iso, lvl):
    k = (iso, lvl)
    if k not in _files:
        _files[k] = json.load(open(f"{ROOT}raw/gb-{iso}-{lvl}.geojson"))["features"]
    return _files[k]

def clean(g):
    g = make_valid(g)
    if isinstance(g, GeometryCollection):
        g = unary_union([p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")])
    return g.buffer(0)

@lru_cache(None)
def unit(key):
    if key not in cat:
        raise KeyError(key)
    v = cat[key]
    idx = int(key.split("_")[1])
    return clean(shape(gb(v["iso"], v["level"])[idx]["geometry"]))

modern_iran = clean(unary_union([shape(f["geometry"]) for f in gb("IRN", "ADM1")]))

# ---------- custom geometry helpers ----------
def side_of(line, pt, side):
    """True if pt lies on `side` of polyline (north/south/east/west) at pt's x (or y)."""
    xs = [c[0] for c in line.coords]; ys = [c[1] for c in line.coords]
    if side in ("north", "south"):
        # interpolate line y at pt.x
        cs = sorted(line.coords)
        x = min(max(pt.x, cs[0][0]), cs[-1][0])
        for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
            if x0 <= x <= x1:
                y = y0 + (y1 - y0) * ((x - x0) / (x1 - x0) if x1 != x0 else 0)
                return pt.y > y if side == "north" else pt.y < y
        return False
    cs = sorted(line.coords, key=lambda c: c[1])
    y = min(max(pt.y, cs[0][1]), cs[-1][1])
    for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
        if y0 <= y <= y1:
            x = x0 + (x1 - x0) * ((y - y0) / (y1 - y0) if y1 != y0 else 0)
            return pt.x > x if side == "east" else pt.x < x
    return False

def extend(line, d=5.0):
    c = list(line.coords)
    def ext(a, b):
        dx, dy = a[0] - b[0], a[1] - b[1]; n = math.hypot(dx, dy) or 1
        return (a[0] + dx / n * d, a[1] + dy / n * d)
    return LineString([ext(c[0], c[1])] + c + [ext(c[-1], c[-2])])

def clip_side(geom, line_coords, side):
    line = extend(LineString(line_coords))
    parts = split(geom, line)
    keep = [p for p in parts.geoms if side_of(line, p.representative_point(), side)]
    return unary_union(keep) if keep else Polygon()

def km_circle(lon, lat, r_km):
    p = pyproj.Proj(proj="aeqd", lat_0=lat, lon_0=lon)
    fwd = lambda x, y: p(x, y); inv = lambda x, y: p(x, y, inverse=True)
    return transform(inv, Point(0, 0).buffer(r_km * 1000, 32))

def resolve_custom(c, base):
    """Interpret a `custom` spec. Supported:
       {"polygon": [[lon,lat],...]}                       (optionally "within_units" to intersect)
       {"op": "clip_<side>_of", "line": [...], "within_units": [...]}
       {"point": [lon,lat], "radius_km": r}
       {"buffer_line": [[lon,lat],...], "width_km": w}    (thin strip, e.g. a river channel)
       {"ref_region": id} handled by caller
    """
    if not c:
        return base
    within = None
    if c.get("within_units"):
        within = unary_union([unit(k) for k in c["within_units"]])
    g = None
    op = c.get("op", "")
    if c.get("polygon") or op in ("polygon",):
        poly = c.get("polygon") or c.get("coords")
        if poly and isinstance(poly[0][0], (int, float)):
            g = clean(Polygon(poly))
        else:
            g = clean(unary_union([Polygon(p) for p in poly]))
        if within is not None:
            g = g.intersection(within)
    elif op.startswith("clip_") and c.get("line"):
        side = op.split("_")[1]
        src = within if within is not None else base
        g = clip_side(src, c["line"], side)
    elif c.get("point"):
        lon, lat = c["point"]
        g = km_circle(lon, lat, c.get("radius_km", 3))
        if within is not None and c.get("clip_to_units", False):
            g = g.intersection(within)
    elif c.get("buffer_line"):
        ln = LineString(c["buffer_line"])
        # degrees -> approx km at this latitude
        w = c.get("width_km", 1) / 111.0
        g = ln.buffer(w / 2, cap_style=2)
    if g is None:
        warn(f"custom spec not understood: {json.dumps(c)[:200]}")
        return base
    if base is not None and not base.is_empty and c.get("combine") == "union":
        return unary_union([base, g])
    if base is not None and not base.is_empty and c.get("combine") == "intersect":
        return base.intersection(g)
    if base is not None and not base.is_empty and c.get("combine") == "difference":
        return base.difference(g)
    return g

# ---------- dates ----------
def dec(d):
    """'1828-02-21' / '1828-02' / '1828' / None -> decimal year (None = open)."""
    if d is None or d == "" or str(d).lower() in ("null", "present", "none"):
        return None
    m = re.match(r"^c?\.?\s*(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", str(d).strip())
    if not m:
        warn(f"bad date {d!r}")
        return None
    y = int(m.group(1)); mo = int(m.group(2) or 1); da = int(m.group(3) or 1)
    try:
        doy = (dt.date(y, mo, da) - dt.date(y, 1, 1)).days
    except ValueError:
        doy = 0
    days = 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    return round(y + doy / days, 4)

T0, T1 = 1800.0, 2026.75

# ---------- load research ----------
sources = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else ROOT + "research/*.json"))
regions, dejure, defacto, events = {}, [], [], {}
for f in sources:
    d = json.load(open(f))
    for r in d.get("regions", []):
        if r["id"] in regions:
            warn(f"duplicate region id {r['id']} in {f}")
        r["_src"] = f.split("/")[-1]
        regions[r["id"]] = r
    for rec in d.get("dejure", []):
        rec["_src"] = f.split("/")[-1]; dejure.append(rec)
    for rec in d.get("defacto", []):
        rec["_src"] = f.split("/")[-1]; defacto.append(rec)
    for e in d.get("events", []):
        if e["id"] in events:
            warn(f"duplicate event id {e['id']}")
        events[e["id"]] = e

# overrides (manual corrections applied after research/verification)
try:
    ov = json.load(open(ROOT + "build/overrides.json"))
except FileNotFoundError:
    ov = {}
for rid, patch in ov.get("regions", {}).items():
    if rid in regions: regions[rid].update(patch)
    else: regions[rid] = patch | {"id": rid}

# ---------- geometry per region ----------
geoms = {}
for rid, r in regions.items():
    base = None
    if r.get("units"):
        try:
            base = unary_union([unit(k) for k in r["units"]])
        except KeyError as e:
            warn(f"{rid}: unknown unit {e}")
            base = unary_union([unit(k) for k in r["units"] if k in cat])
    if r.get("minus_units"):
        base = base.difference(unary_union([unit(k) for k in r["minus_units"] if k in cat]))
    c = r.get("custom")
    if c and isinstance(c, dict) and (c.get("polygon") or c.get("op") or c.get("point") or c.get("buffer_line") or c.get("coords")):
        g = resolve_custom(c, base)
    else:
        g = base
    if g is None or g.is_empty:
        warn(f"{rid}: empty geometry")
        continue
    geoms[rid] = clean(g)

# ---------- projection for areas ----------
albers = pyproj.Transformer.from_crs("EPSG:4326",
    "+proj=aea +lat_1=28 +lat_2=40 +lat_0=33 +lon_0=54 +datum=WGS84 +units=m", always_xy=True)
def proj(g): return transform(albers.transform, g)
def km2(g): return proj(g).area / 1e6

frontier_ids = [r for r in geoms if r.startswith("f_")]
internal_ids = [r for r in geoms if r.startswith("i_")]

# core = modern Iran minus frontier parcels (which carry their own records)
parcels_in_iran = unary_union([geoms[r] for r in frontier_ids if geoms[r].intersects(modern_iran)]) if frontier_ids else Polygon()
core = clean(modern_iran.difference(parcels_in_iran))

# overlap diagnostics among frontier regions (they should tile)
for i, a in enumerate(frontier_ids):
    for b in frontier_ids[i + 1:]:
        if geoms[a].intersects(geoms[b]):
            ov_km = km2(geoms[a].intersection(geoms[b]))
            if ov_km > 50:
                warn(f"frontier overlap {a} x {b}: {ov_km:.0f} km2")
for rid in internal_ids:
    out = km2(geoms[rid].difference(modern_iran))
    if out > 200:
        warn(f"internal region {rid} extends {out:.0f} km2 outside modern Iran")

# ---------- normalise records ----------
def norm(rec, layer):
    r = dict(rec)
    r["layer"] = layer
    r["t0"] = dec(rec.get("from")) or T0
    r["t1"] = dec(rec.get("to"))
    if r["region"] not in geoms and r["region"] != "core":
        warn(f"{layer} record references missing region {r['region']}")
    return r
dejure = [norm(r, "dejure") for r in dejure]
defacto = [norm(r, "defacto") for r in defacto]

for layer, recs in (("dejure", dejure), ("defacto", defacto)):
    byr = {}
    for r in recs: byr.setdefault(r["region"], []).append(r)
    for rid, rs in byr.items():
        rs.sort(key=lambda r: r["t0"])
        for a, b in zip(rs, rs[1:]):
            if a["t1"] is None or a["t1"] > b["t0"] + 0.01:
                warn(f"{layer} overlap in {rid}: {a.get('from')}-{a.get('to')} vs {b.get('from')}-{b.get('to')}")
for e in events.values():
    e["t"] = dec(e.get("date"))
    e["t_end"] = dec(e.get("end_date"))
for recs in (dejure, defacto):
    for r in recs:
        for k in ("start_event", "end_event"):
            if r.get(k) and r[k] not in events:
                warn(f"{r['layer']} {r['region']}: {k} {r[k]} not in events")

def active(recs, t):
    return [r for r in recs if r["t0"] <= t and (r["t1"] is None or t < r["t1"])]

IRANIAN = {"direct", "indirect", "iranian_held"}
LOST = {"none", "foreign_occupation", "breakaway"}  # contested counted separately

def state_at(t):
    dj = active(dejure, t); df = active(defacto, t)
    claim = [core] + [geoms[r["region"]] for r in dj if r["region"] in geoms]
    claim_g = unary_union(claim)
    # de facto: core direct minus internal exceptions; plus frontier regions held
    held_parts = [core] + [geoms[r["region"]] for r in df if r["status"] in IRANIAN and r["region"].startswith("f_") and r["region"] in geoms]
    held = unary_union(held_parts)
    not_held = [geoms[r["region"]] for r in df if r["status"] in LOST and r["region"].startswith("i_") and r["region"] in geoms]
    contested = [geoms[r["region"]] for r in df if r["status"] == "contested" and r["region"] in geoms]
    indirect = [geoms[r["region"]] for r in df if r["status"] == "indirect" and r["region"].startswith("i_") and r["region"] in geoms]
    # frontier records with a non-Iranian status remove that region from held as well
    f_not = [geoms[r["region"]] for r in df if r["status"] not in IRANIAN and r["region"].startswith("f_") and r["region"] in geoms]
    lost_g = unary_union(not_held + f_not + contested) if (not_held or f_not or contested) else Polygon()
    held = held.difference(lost_g)
    direct = held.difference(unary_union(indirect + [geoms[r["region"]] for r in df if r["status"] == "indirect" and r["region"].startswith("f_") and r["region"] in geoms])) if True else held
    return claim_g, held, direct, (unary_union(contested) if contested else Polygon())

# change points
cps = {T0}
for r in dejure + defacto:
    cps.add(r["t0"])
    if r["t1"] is not None: cps.add(r["t1"])
cps = sorted(t for t in cps if T0 <= t <= T1)

series, dj_extents, df_extents = [], [], []
def closing(g, d=0.03):
    return clean(g.buffer(d, 4).buffer(-d, 4))

prev_dj_key = prev_df_key = None
for i, t in enumerate(cps):
    t_next = cps[i + 1] if i + 1 < len(cps) else None
    probe = t + 1e-5
    claim_g, held, direct, cont = state_at(probe)
    series.append({"t": t, "claim": round(km2(claim_g)), "held": round(km2(held)), "direct": round(km2(direct)), "contested": round(km2(cont))})
    dj_key = tuple(sorted(r["region"] for r in active(dejure, probe)))
    df_key = (tuple(sorted((r["region"], r["status"]) for r in active(defacto, probe))))
    if dj_key != prev_dj_key:
        if dj_extents: dj_extents[-1]["t1"] = t
        dj_extents.append({"t0": t, "t1": None, "geom": closing(claim_g)})
        prev_dj_key = dj_key
    if df_key != prev_df_key:
        if df_extents: df_extents[-1]["t1"] = t
        df_extents.append({"t0": t, "t1": None, "geom": closing(held, 0.02)})
        prev_df_key = df_key

# ---------- basemap ----------
ne = json.load(open(ROOT + "raw/ne_10m_admin_0_countries.geojson"))["features"]
countries = []
for f in ne:
    g = shape(f["geometry"])
    if not g.intersects(BBOX): continue
    countries.append({"type": "Feature", "properties": {"name": f["properties"]["NAME_EN"], "iso": f["properties"]["ADM0_A3"]},
                      "geometry": mapping(clean(g.intersection(BBOX)))})
lakes = []
for f in json.load(open(ROOT + "raw/ne_10m_lakes.geojson"))["features"]:
    g = shape(f["geometry"])
    if g.intersects(BBOX) and km2(g) > 150:
        lakes.append({"type": "Feature", "properties": {"name": f["properties"].get("name")}, "geometry": mapping(clean(g))})
RIV = {"Aras", "Atrek", "Kura", "Shatt al Arab", "Tigris", "Dicle", "Euphrates", "Al Furat", "Firat", "Harirud", "Helmand", "Karkheh", "Amu  Darya", "Qezel Owzan", "Sefid", "Talkeh", "Murat", "Volga"}
rivers = []
for f in json.load(open(ROOT + "raw/ne_10m_rivers_lake_centerlines.geojson"))["features"]:
    n = f["properties"].get("name")
    g = shape(f["geometry"])
    if n in RIV and g.intersects(BBOX):
        rivers.append({"type": "Feature", "properties": {"name": n.replace("  ", " ")}, "geometry": mapping(g.intersection(BBOX))})

def fc(feats): return {"type": "FeatureCollection", "features": feats}
region_feats = []
for rid, g in geoms.items():
    region_feats.append({"type": "Feature", "properties": {"id": rid}, "geometry": mapping(g)})
ext_feats_dj = [{"type": "Feature", "properties": {"t0": e["t0"], "t1": e["t1"]}, "geometry": mapping(e["geom"])} for e in dj_extents]
ext_feats_df = [{"type": "Feature", "properties": {"t0": e["t0"], "t1": e["t1"]}, "geometry": mapping(e["geom"])} for e in df_extents]
modern = [{"type": "Feature", "properties": {"id": "modern_iran"}, "geometry": mapping(modern_iran)}]
core_f = [{"type": "Feature", "properties": {"id": "core"}, "geometry": mapping(core)}]

tmp = ROOT + "build/tmp/"
subprocess.run(["mkdir", "-p", tmp])
layers = {"countries": countries, "lakes": lakes, "rivers": rivers, "regions": region_feats, "core": core_f,
          "modern": modern, "dj_extent": ext_feats_dj, "df_extent": ext_feats_df}
for name, feats in layers.items():
    json.dump(fc(feats), open(tmp + name + ".geojson", "w"))
files = [tmp + n + ".geojson" for n in layers]
cmd = ["mapshaper", "-i", *files, "combine-files", "snap", "snap-interval=0.002",
       "-simplify", "weighted", "keep-shapes", "interval=600",
       "-o", ROOT + "data/geo.json", "format=topojson", "quantization=100000", "force"]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)

# ---------- history.json ----------
def rmeta(rid):
    r = regions[rid]; g = geoms[rid]; c = g.representative_point()
    return {"id": rid, "name": r.get("name"), "name_fa": r.get("name_fa"), "kind": "frontier" if rid.startswith("f_") else "internal",
            "geometry_confidence": r.get("geometry_confidence"), "geometry_note": r.get("geometry_note"),
            "area_km2": round(km2(g)), "label": [round(c.x, 3), round(c.y, 3)]}
KEEP = ("region", "from", "to", "t0", "t1", "status", "controller", "start_event", "end_event", "note", "date_confidence", "sources")
out = {
    "generated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    "range": [T0, T1],
    "core_area_km2": round(km2(core)), "modern_area_km2": round(km2(modern_iran)),
    "regions": {rid: rmeta(rid) for rid in geoms},
    "dejure": [{k: r.get(k) for k in KEEP} for r in sorted(dejure, key=lambda r: (r["region"], r["t0"]))],
    "defacto": [{k: r.get(k) for k in KEEP} for r in sorted(defacto, key=lambda r: (r["region"], r["t0"]))],
    "events": sorted([{k: e.get(k) for k in ("id", "date", "end_date", "t", "t_end", "title", "type", "summary", "layers", "sources")} for e in events.values()],
                     key=lambda e: (e["t"] or 0)),
    "series": series,
}
json.dump(out, open(ROOT + "data/history.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(warnings, open(ROOT + "build/warnings.json", "w"), indent=1)
import os
print("regions", len(geoms), "dejure", len(dejure), "defacto", len(defacto), "events", len(events), "changepoints", len(cps),
      "dj_ext", len(dj_extents), "df_ext", len(df_extents))
print("geo.json", os.path.getsize(ROOT + "data/geo.json") // 1024, "KB; history.json", os.path.getsize(ROOT + "data/history.json") // 1024, "KB; warnings", len(warnings))
