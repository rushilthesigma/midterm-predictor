# Converts Algara & Amlani's county presidential returns (Harvard Dataverse doi:10.7910/DVN/DGUMFI,
# CC0) to counties-YYYY.json for elections the Census file doesn't cover (1976)
import json, sys, rdata
from collections import defaultdict

src, atlas_ids_path, years = sys.argv[1], sys.argv[2], [int(y) for y in sys.argv[3:]] or [1976]
atlas = set(json.load(open(atlas_ids_path)))
df = rdata.read_rda(src)["pres_elections_release"]

# FIPS changes between these elections and the us-atlas 2017 outlines
REMAP = {"46113": "46102", "51515": "51019", "51560": "51005", "51780": "51083", "12025": "12086", "30113": "30031",
         "46131": "46071"}  # Washabaugh merged into Jackson, SD in 1983
for year in years:
    out, dropped = defaultdict(lambda: [0, 0]), []
    for row in df[df.election_year == year].itertuples():
        f = str(row.fips)
        if f.startswith("02"):
            continue
        d, r = row.democratic_raw_votes, row.republican_raw_votes
        if not d == d or not r == r or d + r <= 0:  # NaN
            continue
        f2 = REMAP.get(f, f)
        if f2 not in atlas:
            dropped.append(f); continue
        out[f2][0] += int(d); out[f2][1] += int(r)
    json.dump({"source": "Algara & Amlani, U.S. county presidential returns 1868-2020 (Harvard Dataverse)",
               "counties": dict(sorted(out.items()))}, open(f"counties-{year}.json", "w"), separators=(",", ":"))
    print(year, len(out), "counties; dropped", dropped)
