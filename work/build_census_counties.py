# Converts Census "USA Counties" ELE01.xls (county presidential vote, 1980-2004) to counties-YYYY.json
import json, sys, xlrd
from collections import defaultdict

src, atlas_ids_path = sys.argv[1], sys.argv[2]
atlas = set(json.load(open(atlas_ids_path)))
cols = {}
book = xlrd.open_workbook(src)
for s in book.sheets():
    head = s.row_values(0)
    fips = s.col_values(head.index("STCOU"))
    for j, h in enumerate(head):
        cols[h] = dict(zip(fips, s.col_values(j)))

# FIPS changes between these elections and the us-atlas 2017 outlines
REMAP = {"46113": "46102", "51515": "51019", "51560": "51005", "51780": "51083", "12025": "12086", "30113": "30031"}
for year in range(1980, 2005, 4):
    yy = ("1" if year < 2000 else "2") + str(year)[2:]
    dem, rep = cols[f"ELE020{yy}D"], cols[f"ELE030{yy}D"]
    out, dropped = defaultdict(lambda: [0, 0]), []
    for f in dem:
        if len(f) != 5 or f.endswith("000") or f.startswith("02"):
            continue
        d, r = dem[f], rep[f]
        if not isinstance(d, float) or d + r <= 0:
            continue
        f2 = REMAP.get(f, f)
        if f2 not in atlas:
            dropped.append(f); continue
        out[f2][0] += int(d); out[f2][1] += int(r)
    # 2004 Jackson County, MO omits Kansas City, which reported separately; add it back
    # (Missouri's official total minus the sum of its counties)
    if year == 2004:
        out["29095"][0] += 104625; out["29095"][1] += 36061
    json.dump({"source": "U.S. Census Bureau, USA Counties (ELE01), from CQ Press America Votes",
               "counties": dict(sorted(out.items()))}, open(f"counties-{year}.json", "w"), separators=(",", ":"))
    print(year, len(out), "counties; dropped", dropped)
