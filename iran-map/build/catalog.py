"""Build a catalog of modern admin units (stable keys) used as building blocks for historical shapes."""
import json
from shapely.geometry import shape
from shapely.strtree import STRtree
R="raw/"
def feats(f): return json.load(open(R+f))["features"]
# region of interest bbox (lon/lat) to keep RUS/TUR/PAK/AFG manageable
BBOX=(38,23,72,45)
def inbox(g):
    x0,y0,x1,y1=g.bounds; return not (x1<BBOX[0] or x0>BBOX[2] or y1<BBOX[1] or y0>BBOX[3])
spec=[("IRN","ADM1",None),("IRN","ADM2","IRN-ADM1"),("AZE","ADM2","AZE-ADM1"),("ARM","ADM1",None),("GEO","ADM1",None),("GEO","ADM2","GEO-ADM1"),
      ("RUS","ADM2","RUS-ADM1"),("TUR","ADM1",None),("TUR","ADM2","TUR-ADM1"),("IRQ","ADM1",None),("IRQ","ADM2","IRQ-ADM1"),("AFG","ADM1",None),("AFG","ADM2","AFG-ADM1"),
      ("PAK","ADM2",None),("PAK","ADM3","PAK-ADM2"),("TKM","ADM1",None),("TKM","ADM2","TKM-ADM1"),("BHR","ADM1",None),("ARE","ADM1",None),("OMN","ADM1",None)]
cat={}
parents_cache={}
for iso,lvl,par in spec:
    fs=feats(f"gb-{iso}-{lvl}.geojson")
    pf=None
    if par:
        pf=[(x["properties"]["shapeName"],shape(x["geometry"]).buffer(0)) for x in feats(f"gb-{par}.geojson")]
        tree=STRtree([g for _,g in pf])
    for i,x in enumerate(fs):
        g=shape(x["geometry"]).buffer(0)
        if not inbox(g): continue
        p=None
        if pf:
            pt=g.representative_point()
            for j in tree.query(pt):
                if pf[j][1].contains(pt): p=pf[j][0];break
        if iso=="RUS" and p not in ("Dagestan","Chechnya"): continue
        if iso=="TUR" and lvl=="ADM2" and p not in ("Iğdır","Ağrı","Van","Hakkâri","Kars","Ardahan","Erzurum"): continue
        if iso=="TUR" and lvl=="ADM1" and g.centroid.x<38: continue
        if iso=="PAK" and lvl=="ADM2" and g.centroid.x>67.5: continue
        if iso=="PAK" and lvl=="ADM3" and g.centroid.x>66.5: continue
        if iso=="AFG" and lvl=="ADM2" and p not in ("Herat","Farah","Nimruz","Badghis","Helmand","Ghor","Kandahar"): continue
        key=f"{iso}{lvl[-1]}_{i}"
        c=g.centroid
        cat[key]={"iso":iso,"level":lvl,"name":x["properties"]["shapeName"],"parent":p,"lon":round(c.x,3),"lat":round(c.y,3),"area_km2":None}
json.dump(cat,open("build/catalog.json","w"),ensure_ascii=False,indent=0)
# human-readable listing
with open("build/catalog.md","w") as o:
    o.write("# Modern admin-unit catalog (geoBoundaries gbOpen, simplified)\nKey format: <ISO3><ADM level>_<index>. Use keys to define historical extents.\n")
    cur=None
    for k,v in cat.items():
        h=f"{v['iso']} {v['level']}"
        if h!=cur: o.write(f"\n## {h}\n"); cur=h
        o.write(f"- {k}: {v['name']}" + (f" (in {v['parent']})" if v['parent'] else "") + f" @ {v['lon']},{v['lat']}\n")
print(len(cat))
