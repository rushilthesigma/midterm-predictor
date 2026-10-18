# Fills county gaps on today's outlines (counties-1960.json on) by shading counties created since an
# election with the county they were part of: adds them to each year's partOf, which the map resolves.
# Run after the builders that write those files (build_1960_1972.py, build_census_counties.py,
# build_best_counties.py). Only counties without votes of their own are added.
# usage: python3 add_parents.py ..
import json, sys

out_dir = sys.argv[1]
PARENT = {
    "04012": "04027",  # La Paz, AZ: from Yuma, 1983
    "08014": "08013",  # Broomfield, CO: from Boulder (mostly), 2001
    "35006": "35061",  # Cibola, NM: from Valencia, 1981
    "55078": "55115",  # Menominee, WI: from Shawano, 1961
    "15005": "15009",  # Kalawao, HI: votes with Maui
    "51595": "51081", "51600": "51059", "51620": "51175", "51678": "51163", "51683": "51153",
    "51685": "51153", "51735": "51199", "51775": "51161",  # Virginia's newer independent cities
}

for year in range(1960, 2025, 4):
    path = f"{out_dir}/counties-{year}.json"
    d = json.load(open(path))
    added = {f: p for f, p in PARENT.items() if f not in d["counties"] and p in d["counties"]}
    if not added:
        continue
    d["partOf"] = dict(sorted({**d.get("partOf", {}), **added}.items()))
    json.dump(d, open(path, "w"), separators=(",", ":"))
    print(year, "partOf +", sorted(added))
