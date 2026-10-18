# Cross-checks results-YYYY.json (1868-1972, from Wikipedia) against state sums of Algara & Amlani's
# county returns; prints states whose Democratic or Republican vote differs by more than tol
import json, sys, warnings
import rdata
from check import SF
warnings.filterwarnings("ignore")
df = rdata.read_rda(sys.argv[1])["pres_elections_release"]
tol = 0.02
for year in range(1868, 1973, 4):
    st = json.load(open(f"../results-{year}.json"))["states"]
    sums = df[df.election_year == year].groupby("sfips")[["democratic_raw_votes", "republican_raw_votes"]].sum()
    bad = []
    for sf, (d, r) in sums.iterrows():
        name = SF.get(sf); t = st.get(name, {})
        if "dem" not in t:
            if d + r > 0: bad.append(f"{name}: no wiki result, algara {int(d)}/{int(r)}")
            continue
        for k, v in (("dem", d), ("rep", r)):
            if abs(v - t[k]) > max(tol * max(t[k], 1), 50):
                bad.append(f"{name} {k} algara {int(v)} vs wiki {t[k]}")
    print(year, len(bad), *bad, sep="\n  " if bad else " ")
