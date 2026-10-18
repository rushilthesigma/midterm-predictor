import csv, json, sys
from check import check
atlas = set(json.load(open("atlas-ids.json")))
REMAP = {"46113": "46102", "51515": "51019", "51560": "51005", "51780": "51083", "12025": "12086", "30113": "30031"}
def load(path, years):
    res = {y:{} for y in years}; drop={y:set() for y in years}
    for row in csv.DictReader(open(path)):
        y=int(row["year"])
        if y not in res or row["party"].lower() not in ("democrat","republican"): continue
        if row["FIPS"] in ("","NA"): drop[y].add(row["county"]); continue
        f=str(int(float(row["FIPS"]))).zfill(5)
        if f.startswith("02"): continue
        f=REMAP.get(f,f)
        if f not in atlas: drop[y].add(f); continue
        v=int(float(row["candidatevotes"])) if row["candidatevotes"] not in ("","NA") else 0
        o=res[y].setdefault(f,[0,0]); o[0 if row["party"].lower()=="democrat" else 1]+=v
    return res, drop
if __name__=="__main__":
    years=[int(y) for y in sys.argv[2:]]
    res,drop=load(sys.argv[1],years)
    for y in years:
        print(y,len(res[y]),"dropped",sorted(drop[y])[:20]); [print("  ",x) for x in check(y,res[y])]
