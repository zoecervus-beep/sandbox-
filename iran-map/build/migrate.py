"""One-off migration: research/*.json (region-and-layer model) -> data-src/ (atom-and-polity model).

Run once; afterwards data-src/ is the source of truth and research/ is an archive.
"""
import json, re, os, collections
from shapely.ops import unary_union
import geom

ROOT = geom.ROOT
SRC = ROOT + "data-src/"
if os.path.exists(SRC + "control.jsonl") and "--force" not in __import__("sys").argv:
    raise SystemExit("data-src/ already exists and is now edited by hand; re-running the migration would overwrite it.")
os.makedirs(SRC, exist_ok=True)
fr = json.load(open(ROOT + "research/frontier.json"))
inn = json.load(open(ROOT + "research/internal.json"))

# ---------------------------------------------------------------- polities
P = lambda name, fa, kind, **kw: {"name": name, "name_fa": fa, "kind": kind, **kw}
POLITIES = {
    "iran": P("Iran", "ایران", "state", regimes=[
        {"name": "Qajar", "from": "1789", "to": "1925-12-15"},
        {"name": "Pahlavi", "from": "1925-12-15", "to": "1979-02-11"},
        {"name": "Islamic Republic", "from": "1979-02-11", "to": None}]),
    "russia": P("Russian Empire", "امپراتوری روسیه", "state", to="1917-11-07"),
    "ussr": P("Soviet Union", "اتحاد جماهیر شوروی", "state", **{"from": "1917-11-07", "to": "1991-12-26"}),
    "ottoman": P("Ottoman Empire", "امپراتوری عثمانی", "state", to="1922-11-01"),
    "britain": P("Britain and British India", "بریتانیا و هند بریتانیا", "state"),
    "iraq": P("Iraq", "عراق", "state", **{"from": "1932-10-03"}),
    "afghanistan": P("Afghanistan", "افغانستان", "state"),
    "oman": P("Sultanate of Muscat and Oman", "سلطنت مسقط و عمان", "state"),
    "bahrain": P("Bahrain (Al Khalifa)", "بحرین (آل خلیفه)", "sheikhdom"),
    "qawasim": P("Qasimi shaykhdoms of Sharjah and Ras al-Khaimah", "قواسم شارجه و رأس‌الخیمه", "sheikhdom"),
    "herat": P("Principality of Herat", "حکومت هرات", "principality"),
    "kandahar": P("Principality of Kandahar", "حکومت قندهار", "principality"),
    "ganja": P("Ganja Khanate", "خانات گنجه", "khanate"),
    "karabakh": P("Karabakh Khanate", "خانات قره‌باغ", "khanate"),
    "shaki": P("Shaki Khanate", "خانات شکی", "khanate"),
    "shirvan": P("Shirvan Khanate", "خانات شیروان", "khanate"),
    "baku": P("Baku Khanate", "خانات باکو", "khanate"),
    "quba": P("Quba Khanate", "خانات قبه", "khanate"),
    "talysh": P("Talysh Khanate", "خانات طالش", "khanate"),
    "nakhchivan": P("Nakhchivan Khanate", "خانات نخجوان", "khanate"),
    "shuragel": P("Shuragel sultanate", "سلطان‌نشین شوره‌گل", "khanate"),
    "dagestan": P("Dagestani khanates and free societies", "خانات و جوامع آزاد داغستان", "tribal"),
    "tekke": P("Tekke Turkmen", "ترکمن‌های تکه", "tribal"),
    "merv_turkmen": P("Turkmen of Merv and Sarakhs", "ترکمن‌های مرو و سرخس", "tribal"),
    "yomut_goklen": P("Yomut and Goklen Turkmen", "ترکمن‌های یموت و گوکلان", "tribal"),
    "turkmen_councils": P("Turkmen People's Councils", "شوراهای خلق ترکمن", "movement"),
    "baban": P("Baban emirate", "امارت بابان", "principality"),
    "ardalan": P("Ardalan valis of Kurdistan", "والیان اردلان", "principality"),
    "mukri": P("Mukri khans of Mukriyan", "خوانین مکری", "tribal"),
    "kalhor": P("Kalhor chiefs", "ایل کلهر", "tribal"),
    "shikak": P("Shikak under Simko", "ایل شکاک (سمکو)", "tribal"),
    "jalali": P("Jalali and Haydaranlu Kurds", "کردهای جلالی و حیدرانلو", "tribal"),
    "ubeydullah": P("Sheikh Ubeydullah's Kurdish host", "سپاه شیخ عبیدالله نهری", "movement"),
    "jk_komala": P("Society for the Revival of Kurdistan", "کومله ژ.ک", "movement"),
    "mahabad": P("Republic of Mahabad", "جمهوری مهاباد", "movement"),
    "kdpi": P("Kurdish parties (KDPI, Komala)", "حزب دموکرات کردستان و کومله", "movement"),
    "zafaranlu": P("Za'faranlu Kurds of Quchan", "ایل زعفرانلو", "tribal"),
    "shadlu": P("Shadlu Kurds of Bojnurd", "ایل شادلو", "tribal"),
    "pishkuh_lurs": P("Lur tribes of Pish-e Kuh", "ایلات لر پیشکوه", "tribal"),
    "pushtkuh_valis": P("Valis of Pusht-e Kuh", "والیان پشتکوه", "principality"),
    "bakhtiari": P("Bakhtiari confederation", "ایل بختیاری", "tribal"),
    "boir_ahmad": P("Kohgiluyeh and Boir Ahmad khans", "خوانین کهگیلویه و بویراحمد", "tribal"),
    "qashqai": P("Qashqai confederation", "ایل قشقایی", "tribal"),
    "southern_tribes_1946": P("Southern tribes' movement of 1946", "نهضت جنوب", "movement"),
    "shahsevan": P("Shahsevan", "ایل شاهسون", "tribal"),
    "kaab": P("Ka'b sheikhdom of Fallahiyeh", "شیخ‌نشین بنی‌کعب", "sheikhdom"),
    "muhaysin": P("Muhaysin sheikhdom of Mohammerah", "شیخ‌نشین محمره", "sheikhdom"),
    "qawasim_lengeh": P("Qasimi sheikhs of Lengeh", "قواسم بندر لنگه", "sheikhdom"),
    "bastak": P("Khans of Bastak", "خوانین بستک", "tribal"),
    "tangestan": P("Khans of Tangestan, Dashtestan and Dashti", "خوانین تنگستان و دشتستان", "tribal"),
    "baluch_bampur": P("Baluch sardars of Bampur and Saravan", "سرداران بلوچ بمپور و سراوان", "tribal"),
    "baluch_sarhad": P("Baluch chiefs of Sarhad", "سرداران بلوچ سرحد", "tribal"),
    "makran_baluch": P("Gichki and Baluch sardars of Makran", "سرداران گچکی و بلوچ مکران", "tribal"),
    "sistan_chiefs": P("Sistani chiefs", "سرداران سیستان", "tribal"),
    "afsharid": P("Afsharid remnant at Mashhad", "بازماندگان افشاریه در مشهد", "principality"),
    "salar": P("Salar's revolt in Khorasan", "شورش سالار", "movement"),
    "qarai": P("Qara'i khans of Torbat", "خوانین قرائی تربت", "tribal"),
    "qaenat": P("Khozeimeh 'Alam amirs of Qa'enat", "امیران خزیمه قائنات", "principality"),
    "tabas": P("Hereditary governors of Tabas", "حاکمان موروثی طبس", "principality"),
    "constitutionalists": P("Constitutionalist forces", "مشروطه‌خواهان", "movement"),
    "lari": P("Sayyed Abd al-Hosayn Lari's government", "حکومت سید عبدالحسین لاری", "movement"),
    "salar_dowleh": P("Salar al-Dowleh's forces", "سپاه سالارالدوله", "movement"),
    "national_govt_1915": P("National Government at Kermanshah", "حکومت ملی کرمانشاه", "movement"),
    "fars_gendarmerie_1915": P("Pro-German Gendarmerie of Fars", "ژاندارمری هوادار آلمان در فارس", "movement"),
    "jangali": P("Jangal movement and Gilan Soviet Republic", "نهضت جنگل و جمهوری شوروی گیلان", "movement"),
    "azadistan": P("Azadistan (Khiabani)", "آزادیستان (خیابانی)", "movement"),
    "pesyan": P("Pesyan's Khorasan government", "قیام کلنل پسیان", "movement"),
    "urmia_1918": P("Assyrian and Armenian forces at Urmia", "نیروهای آشوری و ارمنی ارومیه", "movement"),
    "adp": P("Azerbaijan People's Government", "حکومت ملی آذربایجان", "movement"),
    "babis": P("Babis of Zanjan", "بابیان زنجان", "movement"),
}

# Per-record mapping: key = source file letter + index in its defacto list.
# value = (controller, allegiance, mode, contested_with)
I, R, B, O = "iran", "russia", "britain", "ottoman"
M = {
 "f000": (R, None, "occupied"), "f001": ("shuragel", I, "autonomous"), "f002": ("shuragel", R, "autonomous"),
 "f003": ("ganja", I, "autonomous"), "f004": (R, None, "administered"), "f005": (I, None, "occupied"),
 "f006": ("karabakh", I, "autonomous"), "f007": ("karabakh", R, "autonomous"), "f008": (I, None, "occupied"),
 "f009": ("karabakh", I, "autonomous"), "f010": (R, None, "occupied"), "f011": ("shaki", I, "autonomous"),
 "f012": ("shaki", R, "autonomous"), "f013": ("shirvan", I, "autonomous"), "f014": ("shirvan", R, "autonomous"),
 "f015": (I, None, "occupied"), "f016": ("baku", I, "autonomous"), "f017": (R, None, "administered"),
 "f018": ("quba", I, "autonomous"), "f019": (R, None, "occupied"), "f020": ("quba", I, "autonomous"),
 "f021": (R, None, "occupied"), "f022": ("dagestan", None, "independent"), "f023": ("talysh", I, "autonomous"),
 "f024": ("talysh", R, "contested", [I]), "f025": (R, None, "occupied"), "f026": (I, None, "occupied"),
 "f027": ("talysh", I, "autonomous"), "f028": ("talysh", R, "contested", [I]), "f029": ("talysh", I, "autonomous"),
 "f031": (R, None, "occupied"), "f033": (R, None, "contested", [I]), "f034": (R, None, "occupied"),
 "f035": ("nakhchivan", I, "autonomous"), "f036": (R, None, "occupied"), "f037": ("nakhchivan", I, "autonomous"),
 "f038": (R, None, "occupied"), "f040": (R, None, "administered"), "f043": ("ussr", None, "administered"),
 "f044": ("tekke", None, "independent"), "f045": (R, None, "administered"), "f046": ("merv_turkmen", None, "independent"),
 "f047": ("merv_turkmen", None, "independent"), "f049": (R, None, "administered"), "f050": (I, None, "occupied"),
 "f051": ("baban", None, "contested", [O, I]), "f052": (O, None, "contested", [I]), "f054": (I, None, "occupied"),
 "f055": (O, None, "contested", [I]), "f056": ("jalali", I, "autonomous"), "f057": ("muhaysin", I, "autonomous"),
 "f058": ("iraq", None, "contested", [I]), "f060": ("iraq", None, "contested", [I]),
 "f062": (I, None, "occupied"), "f063": (I, None, "occupied"), "f064": (I, None, "occupied"),
 "f065": (I, None, "occupied"), "f066": (I, None, "occupied"),
 "f067": ("herat", None, "administered"), "f068": ("herat", I, "autonomous"), "f069": ("herat", None, "administered"),
 "f070": ("herat", I, "autonomous"), "f071": ("herat", None, "contested", [I]), "f072": ("herat", None, "administered"),
 "f074": (I, None, "occupied"), "f075": ("kandahar", None, "administered"), "f076": (B, None, "occupied"),
 "f077": ("sistan_chiefs", None, "independent"), "f078": (I, None, "contested", ["afghanistan"]),
 "f079": ("makran_baluch", None, "independent"), "f080": ("makran_baluch", None, "independent"),
 "f082": (B, None, "contested", [I]), "f083": ("oman", None, "administered"), "f085": ("bahrain", B, "administered"),
 "f086": ("qawasim", B, "administered"), "f087": ("qawasim", None, "contested", [I]), "f089": ("qawasim", B, "administered"),
 "f091": ("qawasim", B, "administered"), "f093": ("qawasim_lengeh", I, "autonomous"), "f095": (O, None, "contested", [I]),
 "f097": ("baluch_sarhad", I, "autonomous"),
 "i000": (R, None, "occupied"), "i001": ("azadistan", None, "insurgent"), "i002": ("bakhtiari", I, "autonomous"),
 "i003": ("baluch_bampur", None, "independent"), "i004": ("baluch_bampur", I, "autonomous"),
 "i005": ("baluch_sarhad", None, "independent"), "i006": (B, None, "occupied"), "i007": ("baluch_sarhad", I, "autonomous"),
 "i008": (B, None, "occupied"), "i009": ("bastak", I, "autonomous"), "i010": ("shadlu", I, "autonomous"),
 "i011": (B, None, "occupied"), "i012": (B, None, "occupied"), "i013": ("oman", None, "administered"),
 "i014": ("constitutionalists", None, "insurgent"), "i015": (R, None, "occupied"),
 "i016": ("jangali", None, "contested", [R, B, I]), "i017": ("jangali", None, "insurgent"),
 "i018": (R, None, "occupied"), "i019": (O, None, "occupied"), "i020": (R, None, "occupied"), "i021": (B, None, "occupied"),
 "i022": (B, None, "occupied"), "i023": (I, None, "contested", ["iraq"]), "i024": ("iraq", None, "occupied"),
 "i025": ("iraq", None, "occupied"), "i026": ("iraq", None, "contested", [I]), "i027": ("iraq", None, "occupied"),
 "i028": ("iraq", None, "contested", [I]), "i029": ("iraq", None, "occupied"), "i030": ("iraq", None, "occupied"),
 "i031": ("bakhtiari", None, "insurgent"), "i032": ("kalhor", I, "autonomous"),
 "i033": ("salar_dowleh", None, "contested", [I]), "i034": ("national_govt_1915", None, "insurgent"),
 "i035": (R, None, "occupied"), "i036": (O, None, "occupied"), "i037": (R, None, "occupied"), "i038": (B, None, "occupied"),
 "i039": (B, None, "occupied"), "i040": (B, None, "occupied"), "i041": ("kaab", I, "autonomous"),
 "i042": ("muhaysin", I, "autonomous"), "i043": ("boir_ahmad", I, "autonomous"), "i044": ("boir_ahmad", None, "contested", [I]),
 "i045": ("boir_ahmad", I, "autonomous"), "i046": ("kdpi", None, "contested", [I]), "i047": ("lari", None, "insurgent"),
 "i048": ("qawasim_lengeh", I, "autonomous"), "i049": ("pishkuh_lurs", None, "independent"),
 "i050": ("pishkuh_lurs", None, "contested", [I]), "i051": ("mukri", I, "autonomous"),
 "i052": ("jk_komala", None, "independent"), "i053": ("mahabad", None, "insurgent"), "i054": ("kdpi", None, "insurgent"),
 "i055": ("kdpi", None, "contested", [I]), "i056": ("afsharid", None, "insurgent"), "i057": ("salar", None, "insurgent"),
 "i058": ("muhaysin", I, "autonomous"), "i059": (O, None, "contested", [I]), "i060": ("muhaysin", I, "autonomous"),
 "i061": (B, None, "occupied"), "i062": ("muhaysin", I, "autonomous"), "i063": ("oman", None, "administered"),
 "i064": (O, None, "occupied"), "i065": ("pesyan", None, "insurgent"), "i066": ("pushtkuh_valis", I, "autonomous"),
 "i067": ("qaenat", I, "autonomous"), "i068": ("qashqai", I, "autonomous"), "i069": ("qashqai", None, "contested", [I]),
 "i070": ("qashqai", None, "independent"), "i071": ("qashqai", I, "autonomous"),
 "i072": ("southern_tribes_1946", None, "contested", [I]), "i073": ("qashqai", I, "autonomous"),
 "i074": ("qashqai", None, "contested", [I]), "i075": (B, None, "occupied"), "i076": ("zafaranlu", I, "autonomous"),
 "i077": (R, None, "occupied"), "i078": ("salar", None, "insurgent"), "i079": ("ardalan", I, "autonomous"),
 "i080": ("kdpi", None, "contested", [I]), "i081": ("shahsevan", None, "independent"), "i082": ("shikak", None, "independent"),
 "i083": ("shikak", None, "independent"), "i084": ("sistan_chiefs", None, "independent"), "i085": ("qaenat", I, "autonomous"),
 "i086": (B, None, "occupied"), "i087": ("qaenat", I, "autonomous"), "i088": (B, None, "occupied"),
 "i089": ("tabas", I, "autonomous"), "i090": ("constitutionalists", None, "insurgent"), "i091": (R, None, "occupied"),
 "i092": (O, None, "occupied"), "i093": ("tangestan", I, "autonomous"), "i094": ("tangestan", None, "contested", [B]),
 "i095": ("qarai", I, "autonomous"), "i096": ("yomut_goklen", None, "independent"), "i097": ("yomut_goklen", I, "autonomous"),
 "i098": ("turkmen_councils", None, "contested", [I]), "i099": ("ubeydullah", None, "contested", [I]),
 "i100": ("urmia_1918", None, "independent"), "i101": (O, None, "occupied"), "i102": (B, None, "occupied"),
 "i103": ("ussr", None, "occupied"), "i104": ("adp", None, "insurgent"), "i105": ("ussr", None, "occupied"),
 "i106": ("ussr", None, "occupied"), "i107": ("baluch_sarhad", I, "autonomous"), "i108": ("ussr", None, "occupied"),
 "i109": (R, None, "occupied"), "i110": ("qashqai", I, "autonomous"), "i111": ("fars_gendarmerie_1915", None, "insurgent"),
 "i112": ("babis", None, "contested", [I]), "i113": (R, None, "occupied"), "i114": (B, None, "occupied"),
 "i115": (B, None, "occupied"), "i116": (B, None, "occupied"),
}

# ---------------------------------------------------------------- ids
def strip(i):
    return re.sub(r"^[fi]_", "", i)
rid_map, eid_map, dup = {}, {}, []
for d in (fr, inn):
    for r in d["regions"]:
        n = strip(r["id"])
        assert n not in rid_map.values(), f"region id collision {n}"
        rid_map[r["id"]] = n
    for e in d["events"]:
        n = re.sub(r"^[fi]_ev_", "ev_", e["id"])
        if n in eid_map.values():
            dup.append(n)  # both research passes recorded this event: merged below
        eid_map[e["id"]] = n

# ---------------------------------------------------------------- bibliography
import unicodedata
works, bib_key = {}, {}
def fold(t):
    t = unicodedata.normalize("NFKD", t)
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c) and c not in "ʿʾ'’")).lower().strip(" .,;:")
def split_note(s):
    """Separate a pinpoint note (pages, dates, 'cross-check only') from the work itself."""
    notes = []
    m = re.match(r"^(.*?)\s*\(([^()]*cross-check[^()]*)\)\s*$", s)
    if m: s, n = m.group(1), m.group(2); notes.append(n)
    m = re.match(r"^(.*?)\s*\[\s*([^\]]+)\]\s*$", s)
    if m: s = m.group(1); notes.insert(0, m.group(2))
    m = re.match(r"^(.*\))\s*:\s*(.+)$", s)
    if m: s = m.group(1); notes.insert(0, m.group(2))
    m = re.match(r"^(Treaty of [A-Za-z]+ \(\d{4}\)),\s*(Arts?\.\s*[^,(]+?)\s*(,.*)?$", s)
    if m: s = m.group(1) + (m.group(3) or ""); notes.insert(0, m.group(2))
    return s.strip(), "; ".join(notes) or None
ALIASES = {"Genocide in Iraq": "hrw-anfal", "Administration Report 1911-1914": "pg-admin-report-1911-14",
           "Babi Uprising in Zanjan": "babi-zanjan-iranian-studies", "Bahaipedia": "bahaipedia-zanjan"}
def work_key(s):
    for frag, key in ALIASES.items():
        if frag in s:
            return "alias:" + key
    m = re.search(r"International Boundary Study No\. (\d+)", s)
    if m: return "ibs" + m.group(1)
    m = re.match(r"Encyclopaedia Iranica, '([^']+)'", s)
    if m: return "iranica:" + fold(m.group(1).split(". ")[0])
    if s.startswith("Wikipedia, "):
        return "wikipedia:" + "|".join(sorted(fold(t) for t in re.findall(r"'([^']+)'", s)))
    m = re.match(r"(Treaty of [A-Za-z]+ \(\d{4}\))", s)
    if m: return "treaty:" + fold(m.group(1))
    m = re.search(r"https?://[^\s)\]]+", s)
    if m: return "url:" + re.sub(r"^https?://(www\.)?|/$", "", m.group(0).rstrip(".,;")).lower()
    return "text:" + fold(re.split(r" \(", s)[0])
def cite(s):
    w, note = split_note(s)
    k = work_key(w)
    if k not in bib_key:
        bib_key[k] = f"s{len(bib_key) + 1:03d}"
        works[bib_key[k]] = {"text": w}
    elif len(w) > len(works[bib_key[k]]["text"]):
        works[bib_key[k]]["text"] = w  # keep the fullest form of the reference
    sid = bib_key[k]
    return {"src": sid, "note": note} if note else sid
def cites(lst):
    out = []
    for s in lst or []:
        c = cite(s)
        if c not in out:
            out.append(c)
    return out

# ---------------------------------------------------------------- regions
mi = geom.modern_iran()
regions = {}
for d, kind in ((fr, "frontier"), (inn, "internal")):
    for r in d["regions"]:
        out = {k: r[k] for k in ("name", "name_fa") if r.get(k)}
        out["kind"] = kind
        for k in ("units", "minus_units", "custom"):
            if r.get(k):
                out[k] = r[k]
        if kind == "internal":
            out["clip_to_region"] = "modern_iran"
        for k in ("geometry_confidence", "geometry_note"):
            if r.get(k):
                out[k] = r[k]
        regions[rid_map[r["id"]]] = out

# modern Iran, and the core: modern Iran minus every frontier parcel that carries its own records
iran_units = [k for k, v in geom.cat.items() if v["iso"] == "IRN" and v["level"] == "ADM1"]
regions["modern_iran"] = {"name": "Modern Iran", "name_fa": "ایران امروز", "kind": "reference", "units": iran_units,
                          "geometry_confidence": "high", "geometry_note": "Modern provincial boundaries (geoBoundaries)."}
shapes = geom.resolve_regions({k: v for k, v in regions.items() if v["kind"] in ("frontier", "reference")}, print)
parcels, inside = [], {}
for rid, v in regions.items():
    if v["kind"] != "frontier":
        continue
    g = shapes[rid]
    ov = geom.km2(g.intersection(mi)) if g.intersects(mi) else 0
    if ov > 0.5:
        parcels.append(rid)
    inside[rid] = ov / max(geom.km2(g), 1e-9)
regions["iran_core"] = {"name": "Iran within its modern borders", "name_fa": "ایران در مرزهای امروز", "kind": "core",
                        "units": iran_units, "minus_regions": sorted(parcels), "geometry_confidence": "high",
                        "geometry_note": "Modern Iran minus the border parcels whose status changed; those carry their own records."}

# ---------------------------------------------------------------- records
def dated(rec, keys=("from", "to")):
    return {k: rec.get(k) for k in keys}
claims = [{"id": "c000", "polity": "iran", "region": "iran_core", "from": "1800", "to": None, "kind": "sovereignty",
           "note": "Claimed throughout. Border parcels whose status changed are recorded separately.", "date_confidence": "high",
           "cites": []}]
for i, r in enumerate(fr["dejure"]):
    claims.append({"id": f"c{i + 1:03d}", "polity": "iran", "region": rid_map[r["region"]], **dated(r),
                   "kind": {"integral": "sovereignty", "suzerainty": "suzerainty"}[r["status"]],
                   **({"start_event": eid_map[r["start_event"]]} if r.get("start_event") else {}),
                   **({"end_event": eid_map[r["end_event"]]} if r.get("end_event") else {}),
                   "note": r.get("note"), "date_confidence": r.get("date_confidence"), "cites": cites(r.get("sources"))})

control = [{"id": "k000", "region": "iran_core", "from": "1800", "to": None, "controller": "iran", "allegiance": None,
            "mode": "administered", "precedence": 0,
            "note": "Baseline: direct rule from the centre, except where a more specific record applies.",
            "date_confidence": "high", "cites": []}]
n = 1
for letter, d in (("f", fr), ("i", inn)):
    for i, r in enumerate(d["defacto"]):
        key = f"{letter}{i:03d}"
        if r["status"] == "direct":
            ctl, alg, mode, vs = I, None, ("occupied" if "occupying" in (r.get("controller") or "") else "administered"), []
        else:
            t = M[key]
            ctl, alg, mode = t[:3]
            vs = t[3] if len(t) > 3 else []
        rid = rid_map[r["region"]]
        # records of frontier parcels inside modern Iran are baselines: internal exceptions override them
        prec = 0 if (letter == "f" and inside.get(rid, 0) > 0.5) else 1
        control.append({"id": f"k{n:03d}", "region": rid, **dated(r), "controller": ctl, "allegiance": alg, "mode": mode,
                        **({"contested_with": vs} if vs else {}), "precedence": prec,
                        "controller_note": r.get("controller"),
                        **({"start_event": eid_map[r["start_event"]]} if r.get("start_event") else {}),
                        **({"end_event": eid_map[r["end_event"]]} if r.get("end_event") else {}),
                        "note": r.get("note"), "date_confidence": r.get("date_confidence"), "cites": cites(r.get("sources"))})
        n += 1

events = {}
for d in (fr, inn):
    for e in d["events"]:
        ev = {"id": eid_map[e["id"]], "date": e.get("date"), "end_date": e.get("end_date"), "title": e["title"],
              "type": e.get("type"), "summary": e.get("summary"), "cites": cites(e.get("sources"))}
        if ev["id"] in events:
            a = events[ev["id"]]
            print(f"merge event {ev['id']}: {a['date']} / {ev['date']}")
            if len(ev["summary"] or "") > len(a["summary"] or ""):
                a.update({k: ev[k] for k in ("date", "end_date", "title", "type", "summary")})
            a["cites"] += [c for c in ev["cites"] if c not in a["cites"]]
        else:
            events[ev["id"]] = ev
events = sorted(events.values(), key=lambda e: str(e["date"]))

# ---------------------------------------------------------------- write
def jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if v is not None or k in ("to", "allegiance")}, ensure_ascii=False) + "\n")
json.dump(POLITIES, open(SRC + "polities.json", "w"), ensure_ascii=False, indent=1)
json.dump(regions, open(SRC + "regions.json", "w"), ensure_ascii=False, indent=1)
json.dump(works, open(SRC + "sources.json", "w"), ensure_ascii=False, indent=1)
jsonl(SRC + "claims.jsonl", claims)
jsonl(SRC + "control.jsonl", control)
jsonl(SRC + "events.jsonl", events)
print(f"polities {len(POLITIES)}  regions {len(regions)}  claims {len(claims)}  control {len(control)}  events {len(events)}")
print(f"citations folded into {len(works)} bibliography entries; parcels inside modern Iran: {len(parcels)}")
used = collections.Counter(c["controller"] for c in control) + collections.Counter(c["allegiance"] for c in control if c["allegiance"])
print("unused polities:", [p for p in POLITIES if p not in used and not any(p in c.get("contested_with", []) for c in control)])
