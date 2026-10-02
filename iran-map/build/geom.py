"""Geometry helpers: modern admin units, custom shapes, and region resolution.

A region definition (data-src/regions.json) may combine:
  units          list of admin-unit keys (build/catalog.json); their union is the base shape
  minus_units    unit keys to subtract
  custom         a hand-made shape (see resolve_custom); replaces the base unless it says "combine"
  minus_regions  ids of other regions to subtract (resolved first)
  clip_to_region id of a region to intersect with (resolved first)
"""
import json, math
from functools import lru_cache
from shapely.geometry import shape, Point, Polygon, LineString, GeometryCollection
from shapely.ops import unary_union, split, transform
from shapely import make_valid
import pyproj

ROOT = "/home/user/sandbox-/iran-map/"
cat = json.load(open(ROOT + "build/catalog.json"))

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
    v = cat[key]
    return clean(shape(gb(v["iso"], v["level"])[int(key.split("_")[1])]["geometry"]))

@lru_cache(None)
def modern_iran():
    return clean(unary_union([shape(f["geometry"]) for f in gb("IRN", "ADM1")]))

@lru_cache(None)
def neighbour(iso):
    for f in json.load(open(ROOT + "raw/ne_10m_admin_0_countries.geojson"))["features"]:
        if f["properties"]["ADM0_A3"] == iso:
            return clean(shape(f["geometry"]))
    raise KeyError(iso)

def km_circle(lon, lat, r_km):
    p = pyproj.Proj(proj="aeqd", lat_0=lat, lon_0=lon)
    return transform(lambda x, y: p(x, y, inverse=True), Point(0, 0).buffer(r_km * 1000, 32))

def _side_of(line, pt, side):
    if side in ("north", "south"):
        cs = sorted(line.coords); x = min(max(pt.x, cs[0][0]), cs[-1][0])
        for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
            if x0 <= x <= x1:
                y = y0 + (y1 - y0) * ((x - x0) / (x1 - x0) if x1 != x0 else 0)
                return pt.y > y if side == "north" else pt.y < y
        return False
    cs = sorted(line.coords, key=lambda c: c[1]); y = min(max(pt.y, cs[0][1]), cs[-1][1])
    for (x0, y0), (x1, y1) in zip(cs, cs[1:]):
        if y0 <= y <= y1:
            x = x0 + (x1 - x0) * ((y - y0) / (y1 - y0) if y1 != y0 else 0)
            return pt.x > x if side == "east" else pt.x < x
    return False

def _extend(line, d=5.0):
    c = list(line.coords)
    def ext(a, b):
        dx, dy = a[0] - b[0], a[1] - b[1]; n = math.hypot(dx, dy) or 1
        return (a[0] + dx / n * d, a[1] + dy / n * d)
    return LineString([ext(c[0], c[1])] + c + [ext(c[-1], c[-2])])

def resolve_custom(c, base, warn):
    """Hand-made shapes. Supported forms:
       {"polygon": [[lon,lat],...]}  or a list of rings     (optional within_units to intersect)
       {"point"|"center": [lon,lat], "radius_km": r}  / {"op": "circle", ...}
       {"op": "circles", "circles": [{"center": [...], "radius_km": r}, ...]}
       {"op": "clip_<north|south|east|west>_of", "line": [...], "within_units": [...]}
       {"op": "clip_to_polygon", "polygon": [...], "within_units": [...]}
       {"op": "border_strip", "border": "Iran-Iraq", "width_km": w, "within_units": [...]}
       {"buffer_line": [[lon,lat],...], "width_km": w}
       optional "combine": "union" | "intersect" | "difference" with the unit-based base
    """
    within = unary_union([unit(k) for k in c["within_units"]]) if c.get("within_units") else None
    op = c.get("op", "")
    g = None
    if op.startswith("clip_") and op != "clip_to_polygon" and c.get("line"):
        side = op.split("_")[1]
        src = within if within is not None else base
        parts = split(src, _extend(LineString(c["line"])))
        keep = [p for p in parts.geoms if _side_of(_extend(LineString(c["line"])), p.representative_point(), side)]
        g = unary_union(keep) if keep else Polygon()
    elif op == "clip_to_polygon":
        src = within if within is not None else (base if base is not None and not base.is_empty else modern_iran())
        g = src.intersection(clean(Polygon(c["polygon"])))
    elif op == "border_strip":
        iso = {"Iran-Iraq": "IRQ", "Iran-Turkey": "TUR", "Iran-Afghanistan": "AFG", "Iran-Pakistan": "PAK",
               "Iran-Turkmenistan": "TKM", "Iran-Azerbaijan": "AZE", "Iran-Armenia": "ARM"}[c["border"]]
        line = modern_iran().boundary.intersection(neighbour(iso).buffer(0.02))
        g = line.buffer(c.get("width_km", 10) / 111.0).intersection(within if within is not None else modern_iran())
    elif op == "circles":
        g = unary_union([km_circle(*cc["center"], cc.get("radius_km", 3)) for cc in c["circles"]])
    elif op == "circle" or c.get("point") or c.get("center"):
        lon, lat = c.get("center") or c.get("point")
        g = km_circle(lon, lat, c.get("radius_km", 3))
        if within is not None and c.get("clip_to_units"):
            g = g.intersection(within)
    elif c.get("polygon") or c.get("coords"):
        poly = c.get("polygon") or c.get("coords")
        g = clean(Polygon(poly)) if isinstance(poly[0][0], (int, float)) else clean(unary_union([Polygon(p) for p in poly]))
        if within is not None:
            g = g.intersection(within)
    elif c.get("buffer_line"):
        g = LineString(c["buffer_line"]).buffer(c.get("width_km", 1) / 111.0 / 2, cap_style=2)
    if g is None:
        warn(f"custom shape not understood: {json.dumps(c)[:160]}")
        return base
    comb = c.get("combine")
    if base is not None and not base.is_empty and comb:
        return {"union": base.union, "intersect": base.intersection, "difference": base.difference}[comb](g)
    return g

def has_custom(c):
    return isinstance(c, dict) and any(c.get(k) for k in ("polygon", "op", "point", "center", "buffer_line", "coords", "circles"))

def resolve_regions(defs, warn):
    """defs: {id: region definition}. Returns {id: shapely geometry}; resolves dependencies first."""
    out, busy = {}, set()
    def res(rid):
        if rid in out:
            return out[rid]
        if rid in busy:
            raise ValueError(f"region dependency cycle at {rid}")
        busy.add(rid)
        r = defs[rid]
        base = unary_union([unit(k) for k in r.get("units", [])]) if r.get("units") else None
        if r.get("minus_units") and base is not None:
            base = base.difference(unary_union([unit(k) for k in r["minus_units"]]))
        g = resolve_custom(r["custom"], base, warn) if has_custom(r.get("custom")) else base
        if g is None or g.is_empty:
            warn(f"region {rid}: empty shape")
            g = Polygon()
        g = clean(g)
        if r.get("clip_to_region"):
            clipped = g.intersection(res(r["clip_to_region"]))
            # keep small islands drawn as circles whose source polygon is missing from the clip region
            if clipped.area > 0.3 * g.area:
                g = clean(clipped)
        if r.get("minus_regions"):
            g = clean(g.difference(unary_union([res(m) for m in r["minus_regions"]])))
        busy.discard(rid)
        out[rid] = g
        return g
    for rid in defs:
        res(rid)
    return out

# equal-area projection for areas (Albers conic centred on Iran)
_albers = pyproj.Transformer.from_crs("EPSG:4326",
    "+proj=aea +lat_1=28 +lat_2=40 +lat_0=33 +lon_0=54 +datum=WGS84 +units=m", always_xy=True)
def km2(g):
    return transform(_albers.transform, g).area / 1e6
