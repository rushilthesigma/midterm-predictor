# Builds counties-YYYY.json for 1960-1972 (results-YYYY.json come from build_historical_results.py).
#   Counties: Algara & Amlani's county presidential returns (Harvard Dataverse doi:10.7910/DVN/DGUMFI, CC0)
#   State totals to check against: Wikipedia's "Results by state" tables, wikitext in wiki60/
# Where a third ticket carried states it's kept as the third value ([dem, rep, third] per county;
# the third candidate's key is in that year's results-YYYY.json):
# Mississippi's unpledged electors in 1960, Alabama's in 1964 (Johnson wasn't on the ballot), and
# Wallace in 1968. Algara files votes by party line, so Alabama needs its columns reassigned.
# Alabama 1960 is left out here: its Democratic line counts only the Kennedy electors, not the unpledged
# electors who outpolled them; build_alabama_1960.py adds its counties from Wikipedia afterwards.
# usage: venv/bin/python build_1960_1972.py algara/pres.Rdata atlas-ids.json ..
import json, sys, rdata
from collections import defaultdict
from parse_wiki_states import parse

src, atlas_ids_path, out_dir = sys.argv[1:4]
atlas = set(json.load(open(atlas_ids_path)))
df = rdata.read_rda(src)["pres_elections_release"]

# Counties merged since: votes go to today's county
REMAP = {"12025": "12086", "32025": "32510", "46113": "46102", "46131": "46071", "51123": "51800",
         "51129": "51550", "51785": "51550", "51151": "51810", "51515": "51019", "51560": "51005",
         "51780": "51083"}
# Counties and cities split off since: shaded with the county they were part of
PARENT = {"04012": "04027", "08014": "08013", "35006": "35061", "55078": "55115", "51595": "51081",
          "51600": "51059", "51620": "51175", "51678": "51163", "51683": "51153", "51685": "51153",
          "51735": "51199", "51775": "51161"}

ELECTIONS = {
    1960: dict(dem="Kennedy", rep="Nixon", other=("Electors",), other_states={"28"}),
    1964: dict(dem="Johnson", rep="Goldwater", other=("electors",), other_states={"01"}),
    1968: dict(dem="Humphrey", rep="Nixon", other=("Wallace",), other_states=None),
    1972: dict(dem="McGovern", rep="Nixon", other=None),
}
STATE_FIPS = {"Alabama": "01", "Alaska": "02", "Arizona": "04", "Arkansas": "05", "California": "06", "Colorado": "08",
  "Connecticut": "09", "Delaware": "10", "District of Columbia": "11", "Florida": "12", "Georgia": "13", "Hawaii": "15",
  "Idaho": "16", "Illinois": "17", "Indiana": "18", "Iowa": "19", "Kansas": "20", "Kentucky": "21", "Louisiana": "22",
  "Maine": "23", "Maryland": "24", "Massachusetts": "25", "Michigan": "26", "Minnesota": "27", "Mississippi": "28",
  "Missouri": "29", "Montana": "30", "Nebraska": "31", "Nevada": "32", "New Hampshire": "33", "New Jersey": "34",
  "New Mexico": "35", "New York": "36", "North Carolina": "37", "North Dakota": "38", "Ohio": "39", "Oklahoma": "40",
  "Oregon": "41", "Pennsylvania": "42", "Rhode Island": "44", "South Carolina": "45", "South Dakota": "46",
  "Tennessee": "47", "Texas": "48", "Utah": "49", "Vermont": "50", "Virginia": "51", "Washington": "53",
  "West Virginia": "54", "Wisconsin": "55", "Wyoming": "56"}
ALIASES = {"D.C.": "District of Columbia", "Washington, D.C.": "District of Columbia"}

def fix_1968(out, states):
    """Algara's 1968 "other" is every vote not on the Democratic or Republican line, which is more than
    Wallace: minor parties everywhere, Humphrey's Liberal line in New York, and St. Louis County's
    total is doubled. Patch those, then scale each state's column to its official total."""
    by_state = defaultdict(list)
    for f, v in out.items():
        by_state[f[:2]].append(v)
    official = {STATE_FIPS[n]: r for n, r in states.items()}
    out["29189"][2] = official["29"]["other"] - sum(v[2] for f, v in out.items() if f[:2] == "29" and f != "29189")
    ny = by_state["36"]
    liberal = official["36"]["dem"] - sum(v[0] for v in ny)
    ny_other = sum(v[2] for v in ny)
    for v in ny:
        moved = v[2] * liberal / ny_other
        v[0] += moved; v[2] -= moved
    for st, vs in by_state.items():
        cols = [2] + ([0] if st == "01" else [])  # Alabama's Humphrey column is a residual too
        for i in cols:
            k = official[st][["dem", "rep", "other"][i]] / max(sum(v[i] for v in vs), 1)
            for v in vs:
                v[i] *= k
    for v in out.values():
        v[:] = [round(x) for x in v]


for year, e in ELECTIONS.items():
    has_other = lambda st: e["other"] and (e["other_states"] is None or st in e["other_states"])

    # States
    _, table = parse(f"{out_dir}/work/wiki60/{year}.wiki")
    states = {}
    for name, v in table.items():
        name = ALIASES.get(name, name)
        if name not in STATE_FIPS or (year == 1960 and name == "Alabama"):
            continue
        r = {"dem": v[e["dem"]], "rep": v[e["rep"]]}
        if has_other(STATE_FIPS[name]):
            r["other"] = v[e["other"][0]]
        states[name] = r

    # Counties
    out, dropped = defaultdict(lambda: [0, 0, 0]), []
    for row in df[df.election_year == year].itertuples():
        f = str(row.fips)
        d, r, total = row.democratic_raw_votes, row.republican_raw_votes, row.raw_county_vote_totals
        if f.startswith("02") or (year == 1960 and f.startswith("01")) or not d == d or not r == r or d + r <= 0:  # Alaska has no counties; NaN
            continue
        o = total - d - r
        if f.startswith("01") and year == 1964:    # "Democratic" line was the unpledged slate
            d, o = 0, d
        elif f.startswith("01") and year == 1968:  # Wallace ran on the Democratic line, Humphrey as National Democrat
            d, o = o, d
        f2 = REMAP.get(f, f)
        if f2 not in atlas:
            dropped.append(f); continue
        c = out[f2]
        c[0] += int(d); c[1] += int(r); c[2] += int(o)
    if year == 1968:
        fix_1968(out, states)
    counties = {f: (v if has_other(f[:2]) else v[:2]) for f, v in sorted(out.items())}
    json.dump({"source": "Algara & Amlani, U.S. county presidential returns 1868-2020 (Harvard Dataverse)",
               "counties": counties, "partOf": PARENT},
              open(f"{out_dir}/counties-{year}.json", "w"), separators=(",", ":"))
    print(year, len(counties), "counties; dropped", dropped)

    # Check county sums against the state totals
    sums = defaultdict(lambda: [0, 0, 0])
    for f, v in counties.items():
        for i, x in enumerate(v):
            sums[f[:2]][i] += x
    for name, r in states.items():
        s = sums.get(STATE_FIPS[name])
        if not s:
            continue
        for i, k in enumerate(["dem", "rep", "other"]):
            if k in r and abs(s[i] - r[k]) > max(0.01 * r[k], 500):
                print(f"   {name} {k}: counties {s[i]:,} vs state {r[k]:,} ({(s[i] - r[k]) / max(r[k], 1):+.1%})")
