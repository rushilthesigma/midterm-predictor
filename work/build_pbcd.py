# Builds districts-YYYY.json (presidential vote by congressional district) for 1952-2004 from the
# WWU Atlas of U.S. Presidential Election Results by Congressional District (Kiernan Park-Egan,
# sites.google.com/view/presidentialbycongressionaldis), downloaded by fetch_pbcd.py. Its layers sit
# on Jeffrey B. Lewis et al.'s UCLA district shapes, so each district's ID is SSS CCC CCC DDD (state
# FIPS, first and last Congress of those lines, district; 0 is at-large). The atlas splits a year
# across layers by winner (and odd layers for DC, a city point, or one state); they're merged by ID.
# Field names differ by year. 1964 and much of 1960 have only percentages, which go under "percentOnly" (x100, like
# 2008's). A third slot is kept only for years whose results-YYYY.json name a third party.
# Some shapes overlap (1960s Colorado 2nd covers Denver too); overlaps go to the smaller district.
# usage: python3 build_pbcd.py   (from work/; needs npx mapshaper)
import json, glob, re, subprocess, os, collections

OUT = ".."
YEARS = range(1952, 2005, 4)
DEM = ("DEM_VOT", "DEMVOT", "HHHvot", "DEM")
REP = ("GOP_VOT", "GOPVOT", "NixonVot", "GOP")
THIRD = ("UNP_VOT", "WallaceV", "UNP")
SOURCE = ("Kiernan Park-Egan, Atlas of U.S. Presidential Election Results by Congressional District "
          "(Western Washington University); district lines from Jeffrey B. Lewis et al., UCLA")

def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
def first(p, keys):
    return next((p[k] for k in keys if p.get(k) is not None), None)

os.makedirs("pbcd/build", exist_ok=True)
for year in YEARS:
    congress = (year - 1786) // 2
    results = json.load(open(f"{OUT}/results-{year}.json"))
    third = len(results["candidates"]) > 2
    feats, other = {}, collections.defaultdict(set)
    for f in sorted(glob.glob(f"pbcd/raw/{year}-*.json")):
        for ft in json.load(open(f))["features"]:
            p = ft["properties"]
            if not re.fullmatch(r"\d{12}", str(p.get("ID") or "")) or not ft.get("geometry"): continue
            # The atlas sometimes counts a year on the next Congress's lines (its 1968 figures come
            # from the 1972 Almanac of American Politics, on 1970s lines); keep its lines and say so
            if not int(p["STARTCONG"]) <= congress <= int(p["ENDCONG"]):
                other[p["STATENAME"]].add(int(p["STARTCONG"]))
            did = p["ID"][1:3] + p["ID"][-2:]
            if did[:2] == "11": continue  # DC's delegate seat; DC takes its own color
            v = [first(p, DEM), first(p, REP)] + ([first(p, THIRD) or 0] if third else [])
            if v[0] is None or v[1] is None:  # some of 1960 has only shares
                v = [p.get("DEM_PER"), p.get("GOP_PER")] + ([p.get("UNP_PER") or 0] if third else [])
                if v[0] is None or v[1] is None: v = None
            if did in feats and (feats[did][1] or not v): continue
            feats[did] = (ft["geometry"], v)
    votes, pct = {}, []
    for did, (_, v) in sorted(feats.items()):
        if not v: continue
        if all(x <= 1 for x in v):
            votes[did] = [round(x * 100, 1) for x in v]; pct.append(did)
        else:
            votes[did] = [int(x) for x in v]
    geo = { "type": "FeatureCollection", "features": [
        { "type": "Feature", "properties": { "id": did }, "geometry": g } for did, (g, _) in sorted(feats.items())] }
    src = f"pbcd/build/{year}.geojson"
    json.dump(geo, open(src, "w"))
    topo = f"pbcd/build/{year}.topo.json"
    subprocess.run(["npx", "-y", "mapshaper", "-i", src, "name=districts", "-clean", "overlap-rule=min-area",
                    "-simplify", "dp", "3%", "keep-shapes", "-o", topo, "format=topojson",
                    "id-field=id", "quantization=1e5", "precision=0.00001"], check=True, capture_output=True)
    lines = f"{ordinal(congress)} Congress"
    if other:
        lines += "; " + ", ".join(f"{st} on {'/'.join(ordinal(c) for c in sorted(cs))} Congress lines" for st, cs in sorted(other.items()))
    d = { "source": SOURCE, "lines": lines, "districts": votes,
          **({ "percentOnly": pct } if pct else {}), "shapes": json.load(open(topo)) }
    states = collections.Counter(k[:2] for k in feats)
    json.dump(d, open(f"{OUT}/districts-{year}.json", "w"), separators=(",", ":"))
    print(year, "districts", len(feats), "with votes", len(votes), "pct-only", len(pct),
          "lines", lines, "no votes", sorted(set(feats) - set(votes)), "states", len(states),
          "size", os.path.getsize(f"{OUT}/districts-{year}.json"))
