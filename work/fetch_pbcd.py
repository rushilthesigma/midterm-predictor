# Downloads the WWU "Atlas of U.S. Presidential Election Results by Congressional District"
# (sites.google.com/view/presidentialbycongressionaldis; Kiernan Park-Egan, on UCLA/Lewis district
# shapes) ArcGIS layers for each year, as GeoJSON with every attribute, into pbcd/raw/.
# usage: python3 fetch_pbcd.py   (from work/)
import json, re, urllib.request, urllib.parse, os

APPS = {}
page = open("pbcd/page.html", encoding="utf-8", errors="ignore").read()
def get(url):
    with urllib.request.urlopen(url, timeout=120) as r: return json.loads(r.read().decode(), strict=False)
for a in dict.fromkeys(re.findall(r"appid%3D([0-9a-f]{32})", page)):
    item = get(f"https://www.arcgis.com/sharing/rest/content/items/{a}?f=json")
    year = int(re.search(r"\d{4}", item["title"]).group())
    APPS[year] = get(f"https://www.arcgis.com/sharing/rest/content/items/{a}/data?f=json")["values"]["webmap"]

def layers(ls):
    for l in ls:
        if l.get("layers"): yield from layers(l["layers"])
        if l.get("url"): yield l

index = {}
for year, wm in sorted(APPS.items()):
    if year > 2004: continue
    data = get(f"https://www.arcgis.com/sharing/rest/content/items/{wm}/data?f=json")
    index[year] = []
    for i, l in enumerate(layers(data.get("operationalLayers", []))):
        url = l["url"]
        feats, off = [], 0
        while True:
            q = urllib.parse.urlencode({ "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
                                         "resultOffset": off, "resultRecordCount": 1000 })
            j = get(f"{url}/query?{q}")
            feats += j.get("features", [])
            if not j.get("properties", {}).get("exceededTransferLimit") and len(j.get("features", [])) < 1000: break
            off += 1000
        out = f"pbcd/raw/{year}-{i}.json"
        json.dump({ "type": "FeatureCollection", "features": feats }, open(out, "w"))
        index[year].append({ "title": l.get("title"), "url": url, "file": out, "n": len(feats) })
        print(year, l.get("title"), len(feats), flush=True)
json.dump(index, open("pbcd/index.json", "w"), indent=1)
