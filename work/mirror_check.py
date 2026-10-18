import csv, json, sys
from collections import defaultdict
from check import check
atlas = set(json.load(open("atlas-ids.json")))
REMAP = {"46113": "46102", "51515": "51019", "51560": "51005", "51780": "51083", "12025": "12086", "30113": "30031"}
def load(path):
    rows = defaultdict(lambda: defaultdict(lambda: [0,0]))  # (year,fips) -> mode -> [d,r]
    other = defaultdict(list)
    for r in csv.DictReader(open(path)):
        p = r["party"]
        if p not in ("DEMOCRAT","REPUBLICAN"): continue
        f = r["county_fips"]
        if f in ("","NA"): other[int(r["year"])].append((r["state_po"],r["county_name"],r["mode"],p,r["candidatevotes"])); continue
        f = str(int(float(f))).zfill(5)
        v = int(float(r["candidatevotes"])) if r["candidatevotes"] not in ("","NA") else 0
        rows[(int(r["year"]),f)][r["mode"]][0 if p=="DEMOCRAT" else 1] += v
    res = defaultdict(dict); drop = defaultdict(list)
    for (y,f),modes in rows.items():
        dr = modes["TOTAL"] if "TOTAL" in modes else [sum(m[0] for m in modes.values()), sum(m[1] for m in modes.values())]
        f2 = REMAP.get(f,f)
        if f2 not in atlas: drop[y].append((f,dr)); continue
        o = res[y].setdefault(f2,[0,0]); o[0]+=dr[0]; o[1]+=dr[1]
    return res, drop, other
if __name__=="__main__":
    res,drop,other = load(sys.argv[1])
    for y in sorted(res):
        print(y,len(res[y]),"dropped",[d for d in drop[y] if not d[0].startswith("02")][:10], "nofips",other[y][:6])
        [print("  ",x) for x in check(y,res[y]) if "Alaska" not in x]
