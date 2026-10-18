# Builds results-YYYY.json for 1860-1972 from the "Results by state" tables on Wikipedia's
# presidential election articles (saved API parse output: <dir>/<year>.json).
# Keeps the Democratic and Republican nominees plus any other candidate who took at least
# MIN_SHARE of some state's vote, so regional third parties (Breckinridge, Weaver, Thurmond,
# Wallace...) can carry states on the map.
import json, re, sys
from io import StringIO
import pandas as pd
from check import SF

STATES = set(SF.values())
MIN_SHARE = 0.10
src_dir, years = sys.argv[1], [int(y) for y in sys.argv[2:]] or range(1860, 1973, 4)

# Party label (end of the column header) -> (key, display party name). dem/rep are the two majors.
PARTIES = [
    ("(Northern) Democratic", "dem", "Democratic"), ("(Southern) Democratic", "sd", "Southern Democratic"),
    ("Democratic/Liberal Republican", "dem", "Democratic"), ("Democratic/Populist", "dem", "Democratic"),
    ("Straight-Out Democrat", "sod", "Straight-Out Democratic"), ("National Democrat", "nd", "National Democratic"),
    ("Unpledged Democratic", "unp", "Unpledged electors"), ("Southern Democrat/ Texas Regulars", "tr", "Texas Regulars"),
    ("Democratic", "dem", "Democratic"), ("National Union", "rep", "Republican"), ("Republican", "rep", "Republican"),
    ("Constitutional Union", "cu", "Constitutional Union"), ('Progressive "Bull Moose"', "prog", "Progressive"),
    ("Progressive", "prog", "Progressive"), ("Dixiecrat", "dix", "States' Rights Democratic"),
    ("States' Rights", "unp", "Unpledged electors"), ("American Independent", "ai", "American Independent"),
    ("Populist", "pop", "Populist"), ("People's", "pop", "Populist"), ("Greenback", "gb", "Greenback"),
    ("Socialist Labor", "sl", "Socialist Labor"), ("Social Democratic", "soc", "Socialist"), ("Socialist", "soc", "Socialist"),
    ("National Prohibition", "np", "National Prohibition"), ("Prohibition", "pro", "Prohibition"), ("Union Labor", "ul", "Union Labor"), ("Union", "un", "Union"),
    ("Farmer-Labor", "fl", "Farmer-Labor"), ("Communist", "com", "Communist"), ("Libertarian", "lib", "Libertarian"),
    ("Anti-Masonic", "am", "Anti-Masonic"), ("Independence", "ind", "Independence"), ("American", "amer", "American"),
]
# Map colors and short labels for third parties; anything else is gray and abbreviated by its first word
COLORS = {"sd": "#1e8a5a", "cu": "#d98a00", "pop": "#3d9a3d", "prog": "#7a3fa6", "dix": "#d98a00",
          "unp": "#d98a00", "ai": "#d98a00", "tr": "#d98a00", "soc": "#b8326e", "gb": "#3d9a3d", "fus": "#3f8f93"}
ABBR = {"fus": "Fus", "sd": "SD", "cu": "CU", "pop": "Pop", "prog": "Prog", "dix": "SRD", "unp": "Unp", "ai": "AI",
        "tr": "TR", "soc": "Soc", "gb": "GB", "ul": "UL", "fl": "FL", "amer": "Am", "un": "Union"}
# First presidential election each state (or DC) voted in, to explain the gaps on the map
FIRST_VOTE = {"Kansas": 1864, "West Virginia": 1864, "Nevada": 1864, "Nebraska": 1868, "Colorado": 1876,
              "Montana": 1892, "North Dakota": 1892, "South Dakota": 1892, "Washington": 1892, "Idaho": 1892,
              "Wyoming": 1892, "Utah": 1896, "Oklahoma": 1908, "Arizona": 1912, "New Mexico": 1912,
              "Alaska": 1960, "Hawaii": 1960, "District of Columbia": 1964}
CONFEDERATE = {"Alabama", "Arkansas", "Florida", "Georgia", "Louisiana", "Mississippi", "North Carolina",
               "South Carolina", "Tennessee", "Texas", "Virginia"}
# Wartime votes under Union occupation that Congress refused to count (Tennessee's are rough estimates)
NOT_COUNTED = {(1864, "Louisiana"), (1864, "Tennessee")}
SURNAME_FIX = {"Follette": "La Follette", "Electors": "Unpledged", "electors": "Unpledged",
               "Regulars": "Texas Regulars"}
# 1860's anti-Lincoln fusion tickets (Douglas, Breckinridge and Bell men on one slate), which
# Wikipedia files under "Other"; Rhode Island's ran as Douglas and is already in his column
FUSION_1860 = {"New York", "New Jersey", "Pennsylvania"}
# Electors chosen by the state legislature, with no popular vote
LEGISLATURE = {(1860, "South Carolina"): "sd", (1868, "Florida"): "rep", (1876, "Colorado"): "rep"}

def num(v):
    s = re.sub(r"\[[^\]]*\]", "", str(v)).replace(",", "").strip()
    return int(float(s)) if re.fullmatch(r"\d+(\.\d+)?", s) else 0

def split_header(h):
    h = re.sub(r"\[[^\]]*\]", "", h).strip()
    for label, key, party in sorted(PARTIES, key=lambda p: -len(p[0])):
        if h.endswith(label):
            name = h[: -len(label)].strip()
            if name == "No Candidate":
                name = party
            surname = name.split("/")[0].strip().split()[-1] if name else ""
            surname = SURNAME_FIX.get(surname, surname)
            return key, surname, party
    return None

def state_table(html):
    for t in pd.read_html(StringIO(html)):
        if isinstance(t.columns, pd.MultiIndex) and t.shape[0] > 20 \
                and any(c[1] in ("#", "Votes") for c in t.columns) and any("State" in str(x) for x in t.columns[0]):
            return t
    raise ValueError("no state table")

for year in years:
    t = state_table(json.load(open(f"{src_dir}/{year}.json"))["parse"]["text"])
    names = [re.sub(r"\[[^\]]*\]|[*†‡§]", "", str(v)).strip() for v in t.iloc[:, 0]]
    names = ["District of Columbia" if n.replace(" ", "") == "D.C." else n for n in names]
    cands = {}  # key -> (surname, party, column)
    for col in t.columns:
        if col[1] not in ("#", "Votes"):
            continue
        if year == 1860 and col[0] == "Other":
            cands["fus"] = ("Fusion", "Anti-Lincoln fusion", col)
            continue
        parsed = split_header(col[0])
        if not parsed or not parsed[1] or parsed[1] == "Candidate":
            continue
        key, surname, party = parsed
        if key in cands:
            raise ValueError(f"{year}: duplicate key {key} for {col[0]}")
        cands[key] = (surname, party, col)

    states, totals = {}, {}
    for i, name in enumerate(names):
        if name not in STATES:
            continue
        row = {k: num(t[c].iloc[i]) for k, (_, _, c) in cands.items()}
        if "fus" in row and name not in FUSION_1860:
            del row["fus"]
        if (year, name) in NOT_COUNTED:
            continue
        if (year, name) in LEGISLATURE:
            states[name] = {"legislature": LEGISLATURE[(year, name)]}
        elif sum(row.values()) > 0:
            states[name] = row
            totals[name] = sum(row.values())

    keep = {"dem", "rep"} | {k for k in cands if any(r.get(k, 0) >= MIN_SHARE * totals[s]
                                                    for s, r in states.items() if s in totals)}
    for r in states.values():
        for k in list(r):
            if k not in keep and k != "legislature":
                del r[k]
    for name in STATES - set(states):
        if name == "West Virginia" and year == 1860:
            states[name] = {"partOf": "Virginia"}
        elif year < FIRST_VOTE.get(name, 0):
            states[name] = {"absent": "dc" if name == "District of Columbia" else "territory"}
        elif (year, name) in NOT_COUNTED:
            states[name] = {"absent": "uncounted"}
        elif year == 1864 and name in CONFEDERATE:
            states[name] = {"absent": "seceded"}
        elif year == 1868 and name in CONFEDERATE:
            states[name] = {"absent": "unreconstructed"}
        else:
            raise ValueError(f"{year}: no result for {name}")

    order = ["dem", "rep"] + [k for k in cands if k in keep - {"dem", "rep"}]
    out = {
        "source": f"Wikipedia, \"{year} United States presidential election\": results by state",
        "candidates": {k: cands[k][0] for k in order},
    }
    third = order[2:]
    if third:
        out["parties"] = {k: {"name": cands[k][1], "abbr": ABBR.get(k, cands[k][1].split()[0]),
                                "color": COLORS.get(k, "#7d7d7d")} for k in third}
    out["states"] = dict(sorted(states.items()))
    json.dump(out, open(f"../results-{year}.json", "w"), indent=2)
    print(year, len(states), "states", out["candidates"])
