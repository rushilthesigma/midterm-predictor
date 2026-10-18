# Adds Alabama's counties to counties-1960.json (run after build_1960_1972.py, which leaves them out
# because Algara's Democratic line there counts only the Kennedy electors).
#   Source: the county table on Wikipedia's "1960 United States presidential election in Alabama"
#   (Our Campaigns), wikitext in wiki-al60/al1960.wiki. It gives each slate's highest elector: the
#   Democratic column is the mixed Kennedy/unpledged slate's top Kennedy elector, so it goes in as
#   the Democratic vote, and the year's note says so. The unpledged electors aren't broken out by county.
# usage: python3 build_alabama_1960.py wiki-al60/al1960.wiki ../shapes-albers.json ../counties-1960.json
import json, re, sys

wiki_path, shapes_path, out_path = sys.argv[1:4]
text = open(wiki_path).read()
table = text[text.index("===Results by county==="):]
table = table[:table.index("\n|}")]

fips = {g["properties"]["name"]: g["id"] for g in json.load(open(shapes_path))["objects"]["counties"]["geometries"]
        if g["id"].startswith("01")}
num = lambda cell: int(re.sub(r"[^\d]", "", cell.split("|")[-1]) or 0)

counties = {}
for row in table.split("|- style")[1:]:
    cells = [c.strip() for c in row.split("\n")[1:] if c.startswith("|")]
    name = re.search(r"\[\[[^|\]]*\|([^\]]+)\]\]", cells[0]).group(1)
    dem, rep = num(cells[1]), num(cells[3])
    counties[fips[name]] = [dem, rep]

assert len(counties) == 67, len(counties)
total = [sum(v[i] for v in counties.values()) for i in (0, 1)]
# The table's (and the state's) totals; its Democratic counties sum one vote over
assert abs(total[0] - 318303) <= 5 and total[1] == 237981, total

out = json.load(open(out_path))
out["counties"].update(counties)
out["counties"] = dict(sorted(out["counties"].items()))
out["note"] = "Alabama's counties count the Democratic slate's Kennedy electors; its unpledged electors aren't broken out by county"
json.dump(out, open(out_path, "w"), separators=(",", ":"))
print(len(counties), "Alabama counties added")
