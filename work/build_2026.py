# Builds districts-2026.json for the 2026 House prediction: every district on the lines in force for
# the November 2026 election, with its 2024 presidential vote and current incumbent.
# Votes and incumbents from The Downballot's presidential results by 2026 district (July 2026 release;
# the-downballot.com/p/the-downballots-calculations-of-presidential), saved as db2026/districts.csv.
# Shapes: nine states redrew for 2026 (as the Redistricting Data Hub's 120th Congress readme lists them,
# and as The Downballot's votes differ from 2024's); the other 41 keep 2024's lines, taken from
# districts-2024.json. The nine come from each state's own published plan (NEW below), downloaded into
# new2026/, clipped to the 2024 coastline, and fitted to their neighbors with mapshaper's -clean, which
# fills the slivers where a state's detailed lines and its neighbors' simplified ones don't meet.
# usage: python3 build_2026.py   (from work/; needs npx for mapshaper)
import csv, json, os, subprocess, tempfile, urllib.request, zipfile, glob

OUT = ".."
MAPSHAPER = ["npx", "-y", "mapshaper@0.6.102"]
FIPS = { "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10",
  "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
  "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
  "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
  "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
  "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56" }
PARTY = { "(D)": "dem", "(R)": "rep", "(I)": "oth" }
# The redrawn states: plan, download URL, and the field holding the district number. Ohio publishes only
# a block assignment file (2020 block GEOID → district, as a spreadsheet), so its districts are dissolved
# from the Census's 2020 TIGER blocks: its entry names the block file and the blocks' URL.
NEW = {
  "TX": ("PLANC2333 (2025)", "https://data.capitol.texas.gov/dataset/748c952b-e926-4f44-8d01-a738884b3ec8/resource/5712ebe1-d777-4d4a-b836-0534e17bca01/download/planc2333.zip", "District"),
  "CA": ("AB 604 (Proposition 50, 2025)", "https://statewidedatabase.org/pub/data/d25/AB604%202025-08-16.zip", "DISTRICT"),
  "FL": ("EOGPCRP2026 (2026)", "https://www.edr.state.fl.us/Content/redistricting/2026redistricting/EOGPCRP2026.zip", "DISTRICT"),
  "NC": ("S.L. 2025-95 (2025)", "https://webservices.ncleg.gov/ViewBillDocument/2025/7667/0/SL%202025-95%20-%20Shapefile", "DISTRICT"),
  "OH": ("Ohio Redistricting Commission plan of Oct. 31, 2025", "https://redistricting.ohio.gov/api/public/districtmaps/430/download",
         { "blocks": "https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_39_tabblock20.zip" }),
  "AL": ("2023 legislative plan (reinstated by the Supreme Court, June 2026), via the Alabama GeoHub", "https://services7.arcgis.com/jF2q3LPxL7PETdYk/arcgis/rest/services/2023_CONG_LEGISLATIVE_PLAN/FeatureServer/0/query?where=1%3D1&outFields=DISTRICT&outSR=4326&f=geojson", "DISTRICT"),
  "LA": ("Act 2 (2026 Regular Session)", "https://redist.legis.la.gov/2026_Files/Act2Congress/Shapefile/Shapefile%20-%20Act_2_(2026_RS).zip", "DISTRICT_I"),
  "TN": ("2026 plan (May 2026), via TNMap", "https://tnmap.tn.gov/arcgis/rest/services/ADMINISTRATIVE_BOUNDARIES/LEGISLATIVE_DISTRICTS/MapServer/2/query?where=1%3D1&outFields=DISTRICT&outSR=4326&f=geojson", "DISTRICT"),
  "UT": ("Court-ordered map (2025), via UGRC", "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/political_us_congress_districts_2026_to_2032/FeatureServer/0/query?where=1%3D1&outFields=DISTRICT&f=geojson", "DISTRICT"),
}
# Gaps up to this size between a redrawn state and its neighbors go to the adjoining district
GAP_FILL = "25km2"

def did_of(label):
    st, d = label.split("-")
    return FIPS[st] + ("00" if d == "AL" else f"{int(d):02d}")

rows = list(csv.reader(open("db2026/districts.csv", encoding="utf-8")))[4:]
districts, incumbents, labels = {}, {}, {}
for r in rows:
    if not r or "-" not in r[0]: continue
    did = did_of(r[0])
    districts[did] = [int(r[4].replace(",", "")), int(r[5].replace(",", ""))]
    incumbents[did] = [r[1], PARTY[r[2]]]
    labels[did] = r[0]
assert len(districts) == 435, len(districts)

def mapshaper(*args):
    subprocess.run(MAPSHAPER + [str(a) for a in args], check=True)

def fetch(st, url):
    """The state's plan as a local .shp, .geojson or .xlsx, downloading it once"""
    folder = f"new2026/{st}"
    if not os.path.isdir(folder):
        os.makedirs(folder)
        path = f"{folder}/download"
        req = urllib.request.Request(url, headers={ "User-Agent": "Mozilla/5.0" })
        with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f: f.write(r.read())
        if zipfile.is_zipfile(path):
            zipfile.ZipFile(path).extractall(folder)
            os.remove(path)
        else:
            os.rename(path, f"{folder}/plan.geojson")
    found = [f for ext in ("shp", "geojson", "xlsx") for f in glob.glob(f"{folder}/**/*.{ext}", recursive=True)]
    assert len(found) == 1, (st, found)
    return found[0]

base = json.load(open(f"{OUT}/districts-2024.json"))["shapes"]
changed = sorted(FIPS[st] for st in NEW)
with tempfile.TemporaryDirectory() as tmp:
    json.dump(base, open(f"{tmp}/base.json", "w"))
    # Unchanged states, and the land outline (2024's districts dissolved) to clip the redrawn ones to
    mapshaper("-i", f"{tmp}/base.json", "-filter", f"{json.dumps(changed)}.indexOf(FID.slice(0, 2)) < 0",
              "-rename-fields", "id=FID", "-filter-fields", "id", "-o", f"{tmp}/kept.geojson")
    mapshaper("-i", f"{tmp}/base.json", "-dissolve", "-o", f"{tmp}/land.geojson")
    layers = [f"{tmp}/kept.geojson"]
    for st, (plan, url, field) in NEW.items():
        out = f"{tmp}/{st}.geojson"
        src = fetch(st, url)
        if isinstance(field, dict):
            # Block assignment spreadsheet: block GEOID, district; joined to the blocks and dissolved
            import openpyxl
            sheet = openpyxl.load_workbook(src, read_only=True).worksheets[0].iter_rows(values_only=True)
            next(sheet)
            with open(f"{tmp}/{st}.csv", "w") as f:
                f.write("GEOID20,district\n")
                for block, dist in sheet:
                    if block: f.write(f"{str(block).zfill(15)},{int(dist)}\n")
            blocks = fetch(f"{st}-blocks", field["blocks"])
            mapshaper("-i", blocks, "-filter-fields", "GEOID20", "-join", f"{tmp}/{st}.csv", "keys=GEOID20,GEOID20",
                      "string-fields=GEOID20", "-dissolve", "district", "-o", f"{tmp}/{st}-plan.shp")
            src, field = f"{tmp}/{st}-plan.shp", "district"
        mapshaper("-i", src, "-proj", "wgs84",
                  "-each", f"id = '{FIPS[st]}' + String(+{field}).padStart(2, '0')", "-filter-fields", "id",
                  "-dissolve", "id", "-simplify", "interval=150", "keep-shapes", "-o", out)
        layers.append(out)
    mapshaper("-i", *layers, "combine-files", "-merge-layers", "force", "name=districts",
              "-clip", f"{tmp}/land.geojson", "-clean", f"gap-fill-area={GAP_FILL}",
              "-o", f"{tmp}/cd.json", "format=topojson", "id-field=id", "quantization=100000")
    topo = json.load(open(f"{tmp}/cd.json"))

topo["objects"] = { "districts": next(iter(topo["objects"].values())) }
ids = [g.get("id") for g in topo["objects"]["districts"]["geometries"]]
assert len(ids) == len(set(ids)), "duplicate district ids"
d = { "source": "The Downballot, 2024 presidential results by 2026 district", "lines": "2026 lines",
      "plans": { st: plan for st, (plan, _, _) in NEW.items() },
      "race": "house", "districts": districts, "incumbents": incumbents, "labels": labels, "shapes": topo }
print("districts", len(districts), "shapes", len(ids), "missing shapes:", sorted(set(districts) - set(ids)),
      "extra shapes:", sorted(set(ids) - set(districts)))
json.dump(d, open(f"{OUT}/districts-2026.json", "w"), separators=(",", ":"))
