# Builds the midterm files for 1978-2022: districts-YYYY.json, each House district's result, and
# results-YYYY.json, each state's Senate race (states without one marked absent: "norace").
# 1978-2014 from the MIT Election Data and Science Lab's constituency returns
# (github.com/MEDSL/constituency-returns, 1976-2018-house.csv; its 2018 rows are missing many party
# labels); 2018 and 2022 from the FEC's Federal Elections 2018 and 2022 (US House Results by State).
# Blank, void and scattered votes aren't counted. Fusion tickets (New York's, Connecticut's) are summed
# into the candidate's major party. Unopposed candidates whose votes weren't counted (Florida, and
# Louisiana and Arkansas in early years; MEDSL codes them as 1 vote of 1) go under "unopposed".
# A third slot, "oth", carries the strongest other candidate where they took 10%+ or won.
# Senate: MEDSL's 1976-2018-senate.csv for 1978-2014, the FEC for 2018 and 2022. A state with a
# regular and a special election maps the regular one and lists the special under "specials".
# Runoffs (Louisiana's December runoffs, Georgia's, Mississippi's 2018 special) give the result.
# District lines: 1978-2006 from Jeffrey B. Lewis et al., United States Congressional District
# Shapefiles (cdmaps.polisci.ucla.edu), simplified into ucla/cdNNN.json; 2010-2018 reuse the
# presidential district files' shapes; 2022 from the Census 118th Congress cartographic boundaries.
# usage: venv/bin/python build_midterms.py   (from work/)
import csv, json, collections
import openpyxl

OUT = ".."
STATES = { "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas", "06": "California",
  "08": "Colorado", "09": "Connecticut", "10": "Delaware", "12": "Florida",
  "13": "Georgia", "15": "Hawaii", "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa",
  "20": "Kansas", "21": "Kentucky", "22": "Louisiana", "23": "Maine", "24": "Maryland",
  "25": "Massachusetts", "26": "Michigan", "27": "Minnesota", "28": "Mississippi", "29": "Missouri",
  "30": "Montana", "31": "Nebraska", "32": "Nevada", "33": "New Hampshire", "34": "New Jersey",
  "35": "New Mexico", "36": "New York", "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
  "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island", "45": "South Carolina",
  "46": "South Dakota", "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont", "51": "Virginia",
  "53": "Washington", "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming" }
FIPS = {name: f for f, name in STATES.items()}
MIDTERMS = list(range(1978, 2023, 4))
# Each year's district lines: another year's district file to take shapes from (an int), or a
# TopoJSON file of its own
DISTRICT_SHAPES = { 1978: "ucla/cd096.json", 1982: "ucla/cd098.json", 1986: "ucla/cd100.json", 1990: 1986,
  1994: "ucla/cd104.json", 1998: "ucla/cd106.json", 2002: "ucla/cd108.json", 2006: "ucla/cd110.json",
  2010: 2008, 2014: 2012, 2018: 2020, 2022: "cd118/cd118.json" }
LINES = { 1978: "96th Congress (1972\u20131980 lines)", 1982: "98th Congress (1982 lines)",
  1986: "100th Congress (1984\u20131990 lines)", 1990: "102nd Congress (1984\u20131990 lines)",
  1994: "104th Congress (1994 lines)", 1998: "106th Congress (1998 lines)",
  2002: "108th Congress (2002 lines)", 2006: "110th Congress (2006 lines)",
  2010: "111th Congress (2006\u20132010 lines)", 2014: "113th Congress (2012\u20132014 lines)",
  2018: "115th Congress (2018 lines)", 2022: "118th Congress (2022 lines)" }
OTH = { "oth": { "name": "Others", "abbr": "I", "color": "#7a5ea8" } }
THIRD_MIN = 0.10
# Shown with a district's result
NOTES = { (2018, "3709"): "Never certified, over absentee-ballot fraud; a new election was held in 2019" }

def party_of(label):
    # FEC lists a fusion candidate's lines together ("D/WF"), marks some labels ("R*"), and writes
    # write-in candidates as "W(D)"
    parts = [p.strip().strip("*").removeprefix("w(").rstrip(")") for p in (label or "").lower().split("/")]
    if any(p.startswith("democrat") or p in ("d", "dem", "dfl", "dnl") for p in parts): return "dem"
    if any(p.startswith("republican") or p in ("r", "rep") for p in parts): return "rep"
    return "oth"
NOT_VOTES = __import__("re").compile(r"blank|scatter|void|^other$|over ?vote|under ?vote", __import__("re").I)

# { year: { district id: [ { name, party, votes, unopposed } ] } }
races = collections.defaultdict(lambda: collections.defaultdict(dict))

def add(year, did, key, name, party, votes, unopposed=False):
    c = races[year][did].setdefault(key, { "name": name, "parties": set(), "votes": 0, "unopposed": False })
    c["parties"].add(party)
    c["votes"] += votes
    c["unopposed"] |= unopposed

# MEDSL 1976-2018: regular general elections; a runoff (Louisiana's December runoffs) replaces the general
all_medsl = list(csv.DictReader(open("medsl-house/house-1976-2018.csv", encoding="latin-1")))
FEC_YEARS = { 2018: ("medsl-house/fe2018.xlsx", "2018 US House Results by State"),
  2022: ("medsl-house/fe2022.xlsx", "8. US House Results by State") }
medsl = [r for r in all_medsl if int(r["year"]) in MIDTERMS and int(r["year"]) not in FEC_YEARS
         and not NOT_VOTES.search(r["candidate"])]
# Texas's court-redrawn districts held open special elections on Election Day 2006 instead of a
# general; use a district's special election only where it has no regular one
regular = {(r["year"], r["state_po"], r["district"]) for r in medsl if r["special"] == "FALSE" and r["stage"] == "gen"}
medsl = [r for r in medsl if r["special"] == "FALSE" and r["stage"] == "gen"
         or r["special"] == "TRUE" and r["year"] == "2006" and (r["year"], r["state_po"], r["district"]) not in regular]
# Some candidates are missing their party (much of 2018, a few earlier): take it from the same
# candidate's other races in the same state, nearest year first
labeled = collections.defaultdict(list)
for r in all_medsl:
    if party_of(r["party"]) != "oth": labeled[(r["state_po"], r["candidate"])].append((int(r["year"]), r["party"]))
def medsl_party(r):
    if r["party"] not in ("", "NA") or r["candidate"] in ("", "NA"): return party_of(r["party"])
    known = sorted(labeled.get((r["state_po"], r["candidate"]), []), key=lambda yp: abs(yp[0] - int(r["year"])))
    return party_of(known[0][1]) if known else "oth"
runoffs = {(r["year"], r["state_po"], r["district"]) for r in medsl if r["runoff"] == "TRUE"}
for r in medsl:
    fips = f'{int(r["state_fips"]):02d}'
    if fips not in STATES: continue
    if (r["year"], r["state_po"], r["district"]) in runoffs and r["runoff"] != "TRUE": continue
    name = r["candidate"]
    if name in ("NA", "") or r["writein"] == "TRUE" and r["party"] in ("NA", ""):
        name = None
    votes = int(r["candidatevotes"]) if r["candidatevotes"].lstrip("-").isdigit() else 0
    unopposed = votes == 1 and r["totalvotes"] == "1"
    did = fips + f'{int(r["district"]):02d}'
    add(int(r["year"]), did, name or f"(other {len(races[int(r['year'])][did])})", name, medsl_party(r),
        0 if unopposed else max(votes, 0), unopposed)

# Ranked-choice races go by their final round. FEC 2022 has the rounds in columns (Y, AA, AC);
# 2018's Maine 2nd gives its final round only in a footnote. Candidates out before it count 0.
RCV_FINAL = { (2018, "2302"): { "Golden": 142440, "Poliquin": 138931 } }
RCV_COLS = (28, 26, 24)
def last_round(r):
    return next((r[i] for i in RCV_COLS if len(r) > i and isinstance(r[i], (int, float))), None)

# FEC: a candidate per FEC id, summed across party lines
for year, (path, sheet) in FEC_YEARS.items():
  rows = list(openpyxl.load_workbook(path, read_only=True)[sheet].iter_rows(values_only=True))[1:]
  final_col = {}  # district → the latest round column used there
  for r in rows:
    if r[2] in FIPS and str(r[3] or "").strip()[:2].isdigit() and year == 2022:
      for i in RCV_COLS:
        if len(r) > i and isinstance(r[i], (int, float)):
          k = FIPS[r[2]] + f"{int(str(r[3]).strip()[:2]):02d}"
          final_col[k] = max(final_col.get(k, 0), i)
  for r in rows:
    _, st, state, dist, fecid, _, first, last, full, _, party, *_ = r
    gen = r[15]
    if state not in FIPS or not str(dist or "").strip()[:2].isdigit() or fecid in (None, "n/a") or gen in (None, ""): continue
    unopposed = isinstance(gen, str) and gen.strip().lower() == "unopposed"
    if not unopposed and not isinstance(gen, (int, float)): continue
    name = " ".join(x.strip() for x in (first or "", last or "") if x and x.strip()) or full
    did = FIPS[state] + f"{int(str(dist).strip()[:2]):02d}"
    if did in final_col:
      gen = r[final_col[did]] if isinstance(r[final_col[did]], (int, float)) else 0
    if (year, did) in RCV_FINAL:
      gen = RCV_FINAL[(year, did)].get((last or "").strip(), 0)
    add(year, did, fecid.strip(), name, party_of(party), 0 if unopposed else int(gen), unopposed)

def main_party(c):
    return "dem" if "dem" in c["parties"] else "rep" if "rep" in c["parties"] else "oth"

for year in MIDTERMS:
    states = collections.defaultdict(lambda: { "dem": 0, "rep": 0, "oth": 0 })
    seats = collections.defaultdict(lambda: { "dem": 0, "rep": 0, "oth": 0 })
    districts, names, unopposed = {}, {}, {}
    for did, cands in sorted(races[year].items()):
        state = STATES[did[:2]]
        best = {}  # strongest candidate per party
        for c in cands.values():
            p = main_party(c)
            states[state][p] += c["votes"]
            if c["name"] and (p not in best or c["votes"] > best[p]["votes"] or c["unopposed"]):
                best[p] = c
        lone = [c for c in cands.values() if c["unopposed"]]
        if lone:
            p = main_party(lone[0])
            seats[state][p] += 1
            unopposed[did] = p
            names[did] = [best.get(q, {}).get("name") if q == p else None for q in ("dem", "rep", "oth")]
            continue
        total = sum(c["votes"] for c in cands.values())
        if not total: continue
        winner = max(cands.values(), key=lambda c: c["votes"])
        seats[state][main_party(winner)] += 1
        v = [best.get("dem", {}).get("votes", 0), best.get("rep", {}).get("votes", 0)]
        nm = [best.get("dem", {}).get("name"), best.get("rep", {}).get("name")]
        o = best.get("oth")
        if o and (o["votes"] >= THIRD_MIN * total or o is winner):
            v.append(o["votes"]); nm.append(o["name"])
        districts[did] = v
        names[did] = nm

    national = { p: sum(s[p] for s in seats.values()) for p in ("dem", "rep", "oth") }
    source = (f"FEC, Federal Elections {year}" if year in FEC_YEARS
              else "MIT Election Data and Science Lab, U.S. House 1976\u20132018 (github.com/MEDSL/constituency-returns)")
    print(year, "House", national, "unopposed", len(unopposed))
    # A district's third slot is "oth", which every midterm results file names
    d = { "source": source, "lines": LINES[year], "race": "house", "districts": districts,
          "names": names, "unopposed": unopposed,
          "notes": { k: n for (y, k), n in NOTES.items() if y == year },
          "national": { p: n for p, n in national.items() if n } }
    src = DISTRICT_SHAPES[year]
    if isinstance(src, int):
        d["shapesFrom"] = src
        shapes = json.load(open(f"{OUT}/districts-{src}.json"))["shapes"]
    else:
        shapes = d["shapes"] = json.load(open(src))
    ids = { g["id"] for g in shapes["objects"]["districts"]["geometries"] }
    have = set(districts) | set(unopposed)
    print("  missing results:", sorted(ids - have), "no shape:", sorted(have - ids))
    json.dump(d, open(f"{OUT}/districts-{year}.json", "w"), separators=(",", ":"))

# Senate. { year: { state: { "regular" | "special": { key: candidate } } } }
senate = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(dict)))
def add_sen(year, state, kind, key, name, party, votes):
    c = senate[year][state][kind].setdefault(key, { "name": name, "parties": set(), "votes": 0, "unopposed": False })
    c["parties"].add(party)
    c["votes"] += votes
# Nonpartisan labels (Mississippi's 2018 special) and write-ins, by last name
NAME_PARTY = { (2018, "Hyde-Smith"): "rep", (2018, "Espy"): "dem", (2018, "McDaniel"): "rep" }
# Results given outright: MEDSL mixes Louisiana's primary and December runoff rows (and has the 2014
# runoff off by a million for both candidates), swaps Wyoming 1978's vote counts, and misspells
# Illinois 1978's candidates. Checked against Wikipedia's results for every midterm.
SEN_RUNOFF = { (1978, "Wyoming"): { ("Alan K. Simpson", "rep"): 82908, ("Raymond B. Whitaker", "dem"): 50456 },
  (1978, "Illinois"): { ("Charles H. Percy", "rep"): 1698711, ("Alex Seith", "dem"): 1448187 }, (2002, "Louisiana"): { ("Mary L. Landrieu", "dem"): 638654, ("Suzanne Haik Terrell", "rep"): 596642 },
  (2014, "Louisiana"): { ("Bill Cassidy", "rep"): 712379, ("Mary L. Landrieu", "dem"): 561210 } }

unopposed_sen = {}
all_sen = list(csv.DictReader(open("medsl-house/senate-1976-2018.csv", encoding="latin-1")))
sen_labeled = collections.defaultdict(list)
for r in all_sen:
    if party_of(r["party"]) != "oth": sen_labeled[(r["state_po"], r["candidate"])].append((int(r["year"]), r["party"]))
for r in all_sen:
    year = int(r["year"])
    if year not in MIDTERMS or year in FEC_YEARS or NOT_VOTES.search(r["candidate"]) or r["candidate"] in ("", "NA"): continue
    state = r["state"]
    if state not in FIPS or (year, state) in SEN_RUNOFF: continue
    party = party_of(r["party"])
    if party == "oth" and r["party"] in ("", "NA"):
        known = sorted(sen_labeled.get((r["state_po"], r["candidate"]), []), key=lambda yp: abs(yp[0] - year))
        if known: party = party_of(known[0][1])
    votes = int(r["candidatevotes"]) if r["candidatevotes"].isdigit() else 0
    # Unopposed, no votes counted (Louisiana 1978): MEDSL's 1 of 1
    if votes == 1 and r["totalvotes"] == "1": unopposed_sen[(year, state)] = party
    add_sen(year, state, "special" if r["special"] == "TRUE" else "regular", r["candidate"], r["candidate"], party, votes)
for (year, state), cands in SEN_RUNOFF.items():
    for (name, party), votes in cands.items():
        add_sen(year, state, "regular", name, name, party, votes)

SEN_SHEETS = { 2018: "2018 US Senate Results by State", 2022: "7. US Senate Results by State" }
for year, sheet in SEN_SHEETS.items():
    rows = list(openpyxl.load_workbook(FEC_YEARS[year][0], read_only=True)[sheet].iter_rows(values_only=True))[1:]
    # A race with a general runoff goes by the runoff; candidates not in it count 0
    has_runoff = { (r[2], r[3]) for r in rows if isinstance(r[17], (int, float)) and r[8] }
    for r in rows:
        _, st, state, dist, fecid, _, first, last, full, _, party, *_ = r
        gen = r[17] if (state, dist) in has_runoff else r[15]
        if state not in FIPS or fecid in (None, "n/a") or not str(dist or "").upper().startswith("S"): continue
        if (state, dist) in has_runoff and not isinstance(gen, (int, float)): gen = 0
        if not isinstance(gen, (int, float)): continue
        name = " ".join(x.strip() for x in (first or "", last or "") if x and x.strip()) or full
        p = NAME_PARTY.get((year, (last or "").strip()), party_of(party))
        add_sen(year, state, "special" if "UNEXPIRED" in str(dist).upper() else "regular", fecid.strip(), name, p, int(gen))

def race_result(cands):
    """{ votes: { dem, rep, oth? }, names: [dem, rep, oth?], winner }"""
    best = {}
    for c in cands.values():
        p = main_party(c)
        if p not in best or c["votes"] > best[p]["votes"]: best[p] = c
    total = sum(c["votes"] for c in cands.values())
    winner = max(cands.values(), key=lambda c: c["votes"])
    votes = { p: best[p]["votes"] for p in ("dem", "rep") if p in best }
    names = [best.get("dem", {}).get("name"), best.get("rep", {}).get("name")]
    o = best.get("oth")
    if o and (o["votes"] >= THIRD_MIN * total or o is winner):
        votes["oth"] = o["votes"]; names.append(o["name"])
    return { "votes": votes, "names": names, "winner": main_party(winner) }

for year in MIDTERMS:
    states, names, specials = {}, {}, {}
    won = collections.Counter()
    for state, kinds in senate[year].items():
        races_ = { k: race_result(c) for k, c in kinds.items() if c and sum(x["votes"] for x in c.values()) }
        main = races_.get("regular") or races_.get("special")
        if not main: continue
        states[state] = main["votes"]
        names[state] = main["names"]
        for r in races_.values(): won[r["winner"]] += 1
        if "regular" in races_ and "special" in races_:
            specials[state] = { "votes": races_["special"]["votes"], "names": races_["special"]["names"] }
        elif "special" in races_:
            specials[state] = { "only": True }
    for state in FIPS:
        states.setdefault(state, { "absent": "norace" })
    states["District of Columbia"] = { "absent": "nosenate" }
    source = (f"FEC, Federal Elections {year}" if year in FEC_YEARS
              else "MIT Election Data and Science Lab, U.S. Senate 1976\u20132018 (github.com/MEDSL/constituency-returns)")
    results = { "source": source, "race": "senate",
        "candidates": { "dem": "Democrats", "rep": "Republicans", "oth": "Others" }, "parties": OTH,
        "states": dict(sorted(states.items())), "names": dict(sorted(names.items())),
        "specials": specials, "unopposed": { st: p for (y, st), p in unopposed_sen.items() if y == year },
        "national": { p: won[p] for p in ("dem", "rep", "oth") if won[p] } }
    json.dump(results, open(f"{OUT}/results-{year}.json", "w"), indent=2)
    print(year, "Senate races", sum(1 for s in states.values() if "absent" not in s), "specials", len(specials), dict(won))
