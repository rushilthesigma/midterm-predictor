// Builds counties-1860.json and counties-1864.json on the historical county outlines in
// counties-historical.json, from the county tables on Wikipedia's "<year> United States presidential
// election in <state>" articles (scraped into wiki-county/county-1860-1864.csv; see the notes there).
// Algara & Amlani's returns start in 1868, so these two years come from here instead.
//
// 1860 has every state that voted. 1864 has the 9 states whose articles have a usable county table
// (CA, DE, MD, MI, MN, MO, NY, OH, WI; Nevada's has votes for only 2 of its 11 counties, so it's left
// out as INCOMPLETE), plus Kentucky, transcribed from The Tribune Almanac for
// 1865, p. 61 (rows with that source_page in the CSV). Its 101 reporting counties match the almanac's
// home total for Lincoln (26,592) but sum 100 short of its McClellan total (61,478); every row was
// checked against the scan, so the gap is the almanac's own. Soldiers voted by regiment, not county.
// The rest fall back to their state color on the map.
// Votes are as the tables give them, not scaled to the state totals, including counties that
// reported too late for the official canvass. "Soldiers" rows have no county and are left out.
// Iowa and Ohio's 1860 tables lump Breckinridge and Bell together, so those votes are left out too.
//
// usage: node build_1860_1864_counties.mjs <county-1860-1864.csv> <counties-historical.json> <results dir> <out dir>
import fs from "node:fs";
import { feature } from "topojson-client";

const [csvPath, histPath, resultsDir, outDir] = process.argv.slice(2);
const ELECTION_DAY = { 1860: 18601106, 1864: 18641108 };
// Rows that are independent cities rather than the county of the same name
const CITIES = { Maryland: { "Baltimore (City)": "Baltimore City" },
  Virginia: { "Norfolk City": "Norfolk", "Richmond City": "Richmond", Petersburg: "Petersburg",
    Portsmouth: "Portsmouth", Williamsburg: "Williamsburg" } };
// County tables too incomplete to map: the state shows its statewide result instead
const INCOMPLETE = new Set(["1864|Nevada"]);
// Columns -> results-YYYY.json candidates. Rhode Island's 1860 fusion slate ran as Douglas.
const column = (year, state, col) => col === "fusion" ? (state === "Rhode Island" ? "dem" : "fus") : col;

const parseCsv = text => text.trim().split("\n").map(line => {
  const out = []; let cur = "", q = false;
  for (const ch of line) {
    if (ch === '"') q = !q;
    else if (ch === "," && !q) { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out;
});
const [header, ...rows] = parseCsv(fs.readFileSync(csvPath, "utf8"));
const col = name => header.indexOf(name);

const topo = JSON.parse(fs.readFileSync(histPath, "utf8"));
const features = feature(topo, topo.objects.counties).features;
// Wikipedia spellings that differ from the atlas
const ALIASES = { "Iowa|Poweshuck": "Poweshiek", "Kentucky|Edmondson": "Edmonson" };
const norm = s => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase()
  .replace(/\bSAINT\b/g, "ST").replace(/\([^)]*\)/g, "").replace(/\bCOUNTY\b/g, "").replace(/[^A-Z]/g, "");
const isCity = f => /\(city\)/.test(f.properties.name);
// Planar point-in-polygon, for places the atlas doesn't draw yet on election day (Fresno before 1862,
// Petersburg, Portsmouth and Williamsburg before they became separate cities): their votes go to the
// county that covered the middle of their earliest outline
const rings = f => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates);
const inRing = ([x, y], r) => {
  let inside = false;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
};
const contains = (f, p) => rings(f).some(poly => inRing(p, poly[0]) && !poly.slice(1).some(h => inRing(p, h)));
function middle(f) {
  const ring = rings(f).map(p => p[0]).sort((a, b) => b.length - a.length)[0];
  let cx = 0, cy = 0, a = 0;
  ring.forEach(([x0, y0], i) => { const [x1, y1] = ring[(i + 1) % ring.length]; const c = x0 * y1 - x1 * y0; a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c; });
  return [cx / (3 * a), cy / (3 * a)];
}

for (const year of [1860, 1864]) {
  const day = ELECTION_DAY[year];
  const results = JSON.parse(fs.readFileSync(`${resultsDir}/results-${year}.json`, "utf8"));
  const order = Object.keys(results.candidates);
  const live = features.filter(f => f.properties.start <= day && f.properties.end >= day);
  const counties = new Map(), cities = new Map();
  for (const f of live) (isCity(f) ? cities : counties).set(f.properties.state + "|" + norm(f.properties.name), f);

  const out = {}, unmatched = [], placedIn = [];
  for (const r of rows.filter(r => +r[col("year")] === year)) {
    const state = r[col("state")], name = ALIASES[`${state}|${r[col("county")]}`] ?? r[col("county")];
    if (/^soldiers/i.test(name) || INCOMPLETE.has(`${year}|${state}`)) continue;
    const cityName = CITIES[state]?.[name];
    let f = cityName ? cities.get(state + "|" + norm(cityName)) ?? counties.get(state + "|" + norm(cityName))
      : counties.get(state + "|" + norm(name)) ?? cities.get(state + "|" + norm(name));
    if (!f) {
      const target = norm(cityName ?? name);
      const earliest = features.filter(g => g.properties.state === state && norm(g.properties.name) === target)
        .sort((a, b) => a.properties.start - b.properties.start)[0];
      const p = earliest && middle(earliest);
      const host = p && live.find(g => g.properties.state === state && contains(g, p));
      if (host) { placedIn.push(`${name} → ${host.properties.name}`); f = host; }
    }
    if (!f) { unmatched.push(`${name}, ${state}`); continue; }
    const v = out[f.properties.key] ??= Object.fromEntries(order.map(p => [p, 0]));
    for (const c of ["dem", "rep", "sd", "cu", "fusion"]) {
      const n = parseInt(r[col(c)], 10);
      if (n > 0) v[column(year, state, c)] += n;
    }
  }
  const countiesOut = {};
  for (const [k, v] of Object.entries(out).sort()) {
    const arr = order.map(p => v[p] ?? 0);
    while (arr.length > 2 && arr.at(-1) === 0) arr.pop();
    if (arr.some(x => x > 0)) countiesOut[k] = arr;
  }
  fs.writeFileSync(`${outDir}/counties-${year}.json`, JSON.stringify({
    source: `Wikipedia, "${year} United States presidential election in <state>": results by county${year === 1864 ? "; Kentucky from The Tribune Almanac for 1865" : ""}, on Newberry Library Atlas of Historical County Boundaries outlines`,
    outlines: "historical",
    date: day,
    ...(year === 1864 ? { note: "Counties for 10 of the 25 states that voted; the rest show statewide results" } : {}),
    counties: countiesOut,
  }));
  console.log(year, Object.keys(countiesOut).length, "counties;", unmatched.length ? "unmatched: " + unmatched.join("; ") : "all matched",
    placedIn.length ? "\n   placed in the county covering them: " + placedIn.join("; ") : "");
}
