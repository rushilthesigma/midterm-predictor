# Builds results-YYYY.json for 1796-1856 from the "Results by state" tables on Wikipedia's
# presidential election articles (saved API parse output: <dir>/<year>.json).
#
# Before the 1830s many states had no statewide popular vote: legislatures appointed electors,
# and district-elected electors left counts that survive only in part. So each state gets one of
#   { party: votes, ... }        a complete statewide popular vote
#   { "legislature": party }     the legislature appointed the electors ("Method of choosing
#                                electors" table); party is whoever got most of its electoral votes
#   { "electors": party }        voters chose electors, but no complete statewide count survives
#   { "partOf": state }          Maine voted as part of Massachusetts until 1820
#   { "absent": reason }         not yet a state
# Keeps every candidate who took MIN_SHARE of some state's vote or carried a state.
import json, re, sys
from io import StringIO
import pandas as pd
from check import SF

STATES = set(SF.values())
MIN_SHARE = 0.10
src_dir, years = sys.argv[1], [int(y) for y in sys.argv[2:]] or range(1796, 1857, 4)

# Party label at the end of a candidate column header -> key
PARTY_KEYS = {"Democratic-Republican": "dr", "Federalist": "fed", "National Republican": "nr", "Democratic": "dem",
              "Whig": "whig", "Anti-Masonic": "am", "Nullifier": "nul", "Liberty": "lib", "Free Soil": "fs",
              "Republican": "rep", "American": "amer"}
PARTY_NAMES = {"dr": "Democratic-Republican", "fed": "Federalist", "nr": "National Republican", "whig": "Whig",
               "am": "Anti-Masonic", "nul": "Nullifier", "lib": "Liberty", "fs": "Free Soil", "amer": "American"}
# Candidates who share a party label with another candidate that year get their own key
CANDIDATE_KEYS = {(1808, "Monroe"): "monroe", (1812, "Clinton"): "clinton",
                  (1824, "Jackson"): "jackson", (1824, "Adams"): "adams", (1824, "Clay"): "clay",
                  (1824, "Crawford"): "crawford", (1836, "White"): "white", (1836, "Webster"): "webster",
                  (1836, "Mangum"): "mangum"}
CANDIDATE_PARTY = {"monroe": "Democratic-Republican (Monroe)", "clinton": "Clintonian (Federalist-backed)",
                   "jackson": "Democratic-Republican (Jackson)", "adams": "Democratic-Republican (Adams)",
                   "clay": "Democratic-Republican (Clay)", "crawford": "Democratic-Republican (Crawford)",
                   "white": "Whig (White)", "webster": "Whig (Webster)", "mangum": "Whig (Mangum)"}
# Federalist slates that ran without a named nominee: the surname to show for them
UNNAMED = {1804: "Pinckney", 1816: "King", 1820: "Federalist electors"}
COLORS = {"dr": "#2e8b57", "fed": "#d9822b", "nr": "#8c5bb5", "whig": "#c9971a", "am": "#6b8e23", "nul": "#3f8f93",
          "lib": "#7d7d7d", "fs": "#3d9a3d", "amer": "#b5651d", "monroe": "#7fb07f", "clinton": "#b36b2e",
          "jackson": "#1f5fbf", "adams": "#8c5bb5", "clay": "#c9971a", "crawford": "#2e8b57",
          "white": "#d98a00", "webster": "#a0522d", "mangum": "#7d7d7d"}
ABBR = {"dr": "DR", "fed": "F", "nr": "NR", "whig": "W", "am": "AM", "nul": "N", "lib": "L", "fs": "FS", "amer": "Am",
        "monroe": "DR", "clinton": "C", "jackson": "DR", "adams": "DR", "clay": "DR", "crawford": "DR",
        "white": "W", "webster": "W", "mangum": "W"}
# First presidential election each state voted in; the original thirteen voted from 1789
FIRST_VOTE = {"Vermont": 1792, "Kentucky": 1792, "Tennessee": 1796, "Ohio": 1804, "Louisiana": 1812,
              "Indiana": 1816, "Mississippi": 1820, "Illinois": 1820, "Alabama": 1820, "Maine": 1820,
              "Missouri": 1820, "Arkansas": 1836, "Michigan": 1836, "Florida": 1848, "Texas": 1848, "Iowa": 1848,
              "Wisconsin": 1848, "California": 1852, "Minnesota": 1860, "Oregon": 1860, "Kansas": 1864,
              "West Virginia": 1864, "Nevada": 1864, "Nebraska": 1868, "Colorado": 1876, "Montana": 1892,
              "North Dakota": 1892, "South Dakota": 1892, "Washington": 1892, "Idaho": 1892, "Wyoming": 1892,
              "Utah": 1896, "Oklahoma": 1908, "Arizona": 1912, "New Mexico": 1912, "Alaska": 1960, "Hawaii": 1960,
              "District of Columbia": 1964}
VOTE_COLS, EV_COLS = {"#", "Votes", "Votes cast", "No."}, {"Electoral votes", "electoral votes", "E.V."}
SKIP_GROUPS = re.compile(r"^(Unnamed|Margin|State|Total|Other|Not cast|Citation|Ref|Cit\.|E\.V\.|Electoral votes)")

LEGIS, MISSING, PARTIAL = "legislature", "missing", "partial"

def cell(v):
    """A popular vote cell: a count, 0 for no ballots, or LEGIS / MISSING / PARTIAL."""
    s = re.sub(r"\[[^\]]*\]|`", "", str(v)).replace(",", "").strip()
    low = s.lower()
    if low in ("no popular vote", "*"):
        return LEGIS
    if low in ("no data", "**", "nan", "") or s.startswith("?"):
        return MISSING
    if s.endswith("+"):
        return PARTIAL
    if re.fullmatch(r"\d+", s):
        return int(s)
    return 0  # no ballots, dashes

def ev(v):
    s = re.sub(r"\[[^\]]*\]", "", str(v)).strip()
    return int(float(s)) if re.fullmatch(r"\d+(\.0)?", s) else 0

def state_of(raw):
    """(state, is_district_row) for a row label like 'Maryland–3[e]', 'Maine-York' or 'Kentucky (12-0)'."""
    s = re.sub(r"\[[^\]]*\]|[*†‡§]|\(.*?\)", "", str(raw)).strip()
    for name in sorted(STATES, key=len, reverse=True):
        if s == name:
            return name, False
        if re.match(re.escape(name) + r"\s*[–-]", s):
            return name, True
    return None, False

def split_header(year, h):
    h = re.sub(r"\[[^\]]*\]", "", h).strip()
    for label in sorted(PARTY_KEYS, key=len, reverse=True):
        if h.endswith(label):
            name = h[: -len(label)].strip()
            if name.startswith(("Unpledged", "No candidate")):
                surname = UNNAMED[year]
            else:
                surname = name.split("/")[0].strip().split()[-1]
                if name.split("/")[0].strip().endswith("Van Buren"):
                    surname = "Van Buren"
            return CANDIDATE_KEYS.get((year, surname), PARTY_KEYS[label]), surname, label
    return None

def tables(year):
    return pd.read_html(StringIO(json.load(open(f"{src_dir}/{year}.json"))["parse"]["text"]["*"]))

def find_results_table(ts):
    for t in ts:
        if isinstance(t.columns, pd.MultiIndex) and t.shape[0] > 5 and "State" in str(t.columns[0]) \
                and any(c[1] in VOTE_COLS for c in t.columns):
            return t
    raise ValueError("no results table")

def find_ev_table(ts):
    """1808 and 1812 keep electoral votes in their own table: {state: {surname: ev}}."""
    for t in ts:
        if isinstance(t.columns, pd.MultiIndex) and any(c[0] == "For President" for c in t.columns):
            out = {}
            for i in range(t.shape[0]):
                state, _ = state_of(t.iloc[i, 0])
                if state:
                    out[state] = {c[1].split()[-1]: ev(t[c].iloc[i]) for c in t.columns if c[0] == "For President"}
            return out
    raise ValueError("no electoral vote table")

# Tennessee's legislature named, county by county, the men who then chose its electors
INDIRECT = {(1796, "Tennessee"), (1800, "Tennessee")}

def legislature_states(ts, voting):
    """States whose legislature appointed the electors, per the article's "Method of choosing
    electors" table; a row naming "(all other states)" covers every voting state not listed."""
    for t in ts:
        if str(t.columns[0]).startswith("Method"):
            out, listed, rest_legislature = set(), set(), False
            for method, states in zip(t.iloc[:, 0], t.iloc[:, 1]):
                by_legislature = "legislature" in str(method)
                if "all other states" in str(states):
                    rest_legislature = by_legislature
                    continue
                rest = str(states)
                for name in sorted(STATES, key=len, reverse=True):
                    if re.search(r"\b" + re.escape(name) + r"\b", rest):
                        listed.add(name)
                        if by_legislature:
                            out.add(name)
                        rest = rest.replace(name, "")
            return out | (set(voting) - listed if rest_legislature else set())
    return set()

for year in years:
    ts = tables(year)
    t = find_results_table(ts)
    cands = {}  # key -> {surname, party, votes col, ev col}
    for col in t.columns:
        if SKIP_GROUPS.match(col[0]):
            continue
        parsed = split_header(year, col[0])
        if not parsed:
            raise ValueError(f"{year}: unrecognized column {col}")
        key, surname, label = parsed
        c = cands.setdefault(key, {"surname": surname, "party": label})
        if c["surname"] != surname:
            raise ValueError(f"{year}: {key} is both {c['surname']} and {surname}")
        if col[1] in VOTE_COLS:
            c["votes"] = col
        elif col[1] in EV_COLS:
            c["ev"] = col
    ev_table = None if all("ev" in c for c in cands.values()) else find_ev_table(ts)

    # Per state: the statewide row's votes if there is one (in 1828 Maine and New York report both
    # at-large and district rows), else the districts' summed; electoral votes from every row
    rows = {}
    for i in range(t.shape[0]):
        state, district = state_of(t.iloc[i, 0])
        if not state:
            continue
        r = rows.setdefault(state, {"statewide": None, "districts": [], "ev": {k: 0 for k in cands}})
        votes = {k: cell(t[c["votes"]].iloc[i]) if "votes" in c else 0 for k, c in cands.items()}
        (r["districts"].append(votes) if district else r.__setitem__("statewide", votes))
        for k, c in cands.items():
            if "ev" in c:
                r["ev"][k] += ev(t[c["ev"]].iloc[i])
    if ev_table:
        for state, by_surname in ev_table.items():
            r = rows.setdefault(state, {"statewide": None, "districts": [], "ev": {}})
            r["ev"] = {k: by_surname.get(c["surname"], 0) for k, c in cands.items()}
            # Electoral votes for candidates the popular table doesn't list (George Clinton in 1808)
            extra = sum(by_surname.values()) - sum(r["ev"].values())
            if extra and max(by_surname.values()) > max(r["ev"].values()):
                raise ValueError(f"{year} {state}: most electoral votes went to an unlisted candidate {by_surname}")

    legislature = legislature_states(ts, rows) | {s for y, s in INDIRECT if y == year} \
        | {s for s, r in rows.items() if r["statewide"] and any(v == LEGIS for v in r["statewide"].values())}

    def total_votes(r):
        if r["statewide"] is not None:
            parts = [r["statewide"]]
        else:
            parts = r["districts"]
        out = {}
        for k in cands:
            vals = [p[k] for p in parts]
            if any(v in (LEGIS, MISSING, PARTIAL) for v in vals):
                return None
            out[k] = sum(vals)
        return out if sum(out.values()) > 0 else None

    states, carried = {}, set()
    for state, r in rows.items():
        ev_winner = max(r["ev"], key=r["ev"].get) if r["ev"] and max(r["ev"].values()) > 0 else None
        votes = total_votes(r)
        if votes:
            states[state] = votes
            carried.add(max(votes, key=votes.get))
        elif ev_winner:
            states[state] = {"legislature" if state in legislature else "electors": ev_winner}
            carried.add(ev_winner)
        else:
            raise ValueError(f"{year} {state}: no popular vote and no electoral votes")

    keep = carried | {k for k in cands for s in states.values()
                      if isinstance(s.get(k), int) and s[k] >= MIN_SHARE * sum(v for v in s.values() if isinstance(v, int))}
    for s in states.values():
        for k in list(s):
            if k in cands and k not in keep:
                del s[k]

    for name in STATES - set(states):
        if name == "Maine" and year < 1820:
            states[name] = {"partOf": "Massachusetts"}
        elif name == "West Virginia":
            states[name] = {"partOf": "Virginia"}
        elif year < FIRST_VOTE.get(name, 0):
            states[name] = {"absent": "dc" if name == "District of Columbia" else "territory"}
        else:
            raise ValueError(f"{year}: no result for {name}")

    # Check: electoral votes per candidate against the table's totals row
    ev_sum = {k: sum(r["ev"].get(k, 0) for r in rows.values()) for k in cands}
    order = [k for k in cands if k in keep]
    out = {
        "source": f"Wikipedia, \"{year} United States presidential election\": results by state",
        "candidates": {k: cands[k]["surname"] for k in order},
        "parties": {k: {"name": CANDIDATE_PARTY.get(k, PARTY_NAMES.get(k, cands[k]["party"])),
                        "abbr": ABBR[k], "color": COLORS[k]} for k in order if k not in ("dem", "rep")},
        "states": dict(sorted(states.items())),
    }
    if not out["parties"]:
        del out["parties"]
    json.dump(out, open(f"../results-{year}.json", "w"), indent=2)
    kinds = {}
    for s in states.values():
        kind = next((k for k in ("legislature", "electors", "partOf", "absent") if k in s), "popular")
        kinds[kind] = kinds.get(kind, 0) + 1
    print(year, out["candidates"], "EV", ev_sum, kinds)
