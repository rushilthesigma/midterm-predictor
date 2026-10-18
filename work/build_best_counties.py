# Rebuilds counties-YYYY.json for 2000-2024 by choosing, for each state, the county-level source whose
# county sums best match the certified state totals in results-YYYY.json. Sources:
#   C  the existing counties-YYYY.json (Census ELE01 for 2000-2004, tonmcg for 2008-2024)
#   A  Algara & Amlani county presidential returns (Harvard Dataverse doi:10.7910/DVN/DGUMFI), 2000-2020
#   M  MIT Election Lab countypres_2000-2016 (github.com/MEDSL/county-returns)
#   X  MIT Election Lab countypres_2000-2024 v20250821 (doi:10.7910/DVN/VOQCHQ, via a GitHub mirror)
# Usage: python build_best_counties.py algara/pres.Rdata medsl-gh/countypres_2000-2016.csv mirror/countypres.csv
import csv, json, sys
from collections import defaultdict
from check import SF

algara_path, medsl_path, mirror_path = sys.argv[1:4]
atlas = set(json.load(open("atlas-ids.json")))
YEARS = [2000, 2004, 2008, 2012, 2016, 2020, 2024]
# FIPS changes between these elections and the us-atlas 2017 outlines; Kansas City, MO reports
# separately from Jackson County (MEDSL codes it 2938000, or 36000 in the 2000-2016 release)
REMAP = {"46113": "46102", "51515": "51019", "51560": "51005", "51780": "51083", "12025": "12086", "30113": "30031",
         "2938000": "29095"}

def add(out, f, d, r):
    f = REMAP.get(f, f)
    if f in atlas and not f.startswith("02"):  # Alaska reports by house district, not borough
        o = out.setdefault(f, [0, 0]); o[0] += d; o[1] += r

def load_current():
    return {y: json.load(open(f"../counties-{y}.json"))["counties"] for y in YEARS}

def load_algara():
    import rdata
    df = rdata.read_rda(algara_path)["pres_elections_release"]
    res = defaultdict(dict)
    for row in df[df.election_year >= 2000].itertuples():
        d, r = row.democratic_raw_votes, row.republican_raw_votes
        if d == d and r == r and d + r > 0:
            add(res[int(row.election_year)], str(row.fips).zfill(5), int(d), int(r))
    return res

def load_medsl_2016():
    res = defaultdict(dict)
    for row in csv.DictReader(open(medsl_path)):
        p = row["party"]
        if p not in ("democrat", "republican") or row["FIPS"] in ("", "NA"):
            continue
        f = "2938000" if row["FIPS"] == "36000" else str(int(float(row["FIPS"]))).zfill(5)
        v = int(float(row["candidatevotes"])) if row["candidatevotes"] not in ("", "NA") else 0
        add(res[int(row["year"])], f, v if p == "democrat" else 0, v if p == "republican" else 0)
    return res

def load_medsl_2024():
    seen, modes = set(), defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in csv.DictReader(open(mirror_path)):
        p = row["party"]
        if p not in ("DEMOCRAT", "REPUBLICAN") or row["county_fips"] in ("", "NA"):
            continue
        key = tuple(row.values())
        if key in seen:  # the mirror repeats some rows verbatim
            continue
        seen.add(key)
        f = str(int(float(row["county_fips"]))).zfill(5)
        v = int(float(row["candidatevotes"])) if row["candidatevotes"] not in ("", "NA") else 0
        modes[(int(row["year"]), f)][row["mode"]][0 if p == "DEMOCRAT" else 1] += v
    res = defaultdict(dict)
    for (y, f), m in modes.items():
        d, r = m["TOTAL"] if "TOTAL" in m else [sum(x[0] for x in m.values()), sum(x[1] for x in m.values())]
        add(res[y], f, d, r)
    return res

def by_state(c):
    out = defaultdict(dict)
    for f, v in c.items():
        out[SF[f[:2]]][f] = v
    return out

def err(counties, total):
    d, r = sum(v[0] for v in counties.values()), sum(v[1] for v in counties.values())
    return max(abs(d / total["dem"] - 1), abs(r / total["rep"] - 1))

sources = {"C": load_current(), "A": load_algara(), "M": load_medsl_2016(), "X": load_medsl_2024()}
atlas_by_state = defaultdict(set)
for f in atlas:
    if f[:2] in SF and not f.startswith("02"):
        atlas_by_state[SF[f[:2]]].add(f)
report = {}
for y in YEARS:
    totals = json.load(open(f"../results-{y}.json"))["states"]
    per = {k: by_state(s.get(y, {})) for k, s in sources.items()}
    out, picks = {}, {}
    for st in sorted(atlas_by_state):
        cands, most = [], max(len(per[k].get(st, {})) for k in "CAMX")
        for k in "CAMX":  # ties go to the earlier source
            c = per[k].get(st)
            # a source must cover (nearly) as many counties as the most complete one
            if c and len(c) >= 0.98 * most:
                cands.append((round(err(c, totals[st]), 4), k, c))
        if not cands:
            picks[st] = None; continue
        e, k, c = min(cands, key=lambda x: x[0])
        out.update(c); picks[st] = (k, e)
    src = sorted({p[0] for p in picks.values() if p})
    json.dump({"source": "Best match per state to certified totals: " + ", ".join(
                   {"C": json.load(open(f"../counties-{y}.json"))["source"], "A": "Algara & Amlani (Harvard Dataverse doi:10.7910/DVN/DGUMFI)",
                    "M": "MIT Election Lab countypres_2000-2016", "X": "MIT Election Lab countypres_2000-2024 (doi:10.7910/DVN/VOQCHQ)"}[k] for k in src),
               "counties": dict(sorted(out.items()))}, open(f"counties-{y}.json", "w"), separators=(",", ":"))
    report[y] = picks
    print(y, len(out), "counties;", {k: sum(1 for p in picks.values() if p and p[0] == k) for k in "CAMX"},
          "worst", sorted(((p[1], s, p[0]) for s, p in picks.items() if p), reverse=True)[:4],
          "missing", [s for s, p in picks.items() if p is None])
json.dump({y: {s: p for s, p in v.items()} for y, v in report.items()}, open("best_counties_report.json", "w"), indent=1)
