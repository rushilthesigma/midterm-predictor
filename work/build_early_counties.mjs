// Builds counties-YYYY.json for 1796-1856 on the historical county outlines in counties-historical.json,
// from the county tables on Wikipedia's "<year> United States presidential election in <state>" articles
// (parsed by wiki-county-early/parse.py into county-early.csv; see county-early-notes.md there for which
// states have a usable table each year and how their sums compare with the statewide results).
// Only some states have county tables each year (from 2 in 1808 to 21 in 1856, none in 1812); the
// rest show their statewide result on the map, as 1864 does.
// Rows for two counties that voted together ("Centre & Clearfield") go to both outlines, so both show
// the pair's result. Votes are as the tables give them. Columns that aren't one of the year's candidates (scattering,
// unpledged slates) are left out, like 1860's combined columns.
//
// usage: node build_early_counties.mjs <county-early.csv> <counties-historical.json> <results dir> <out dir>
import fs from "node:fs";
import { feature } from "topojson-client";

const [csvPath, histPath, resultsDir, outDir] = process.argv.slice(2);
// Election day as build_historical_shapes.mjs has it: the Tuesday after the first Monday in November,
// standing in, before 1848, for the days in November and December each state voted on
const electionDay = y => {
  const d = new Date(Date.UTC(y, 10, 1));
  return y * 10000 + 1100 + 1 + (8 - d.getUTCDay()) % 7 + 1;
};
// Rows that are independent cities rather than the county of the same name, or that the atlas spells
// differently ("state|row" -> atlas name)
const ALIASES = {
  "Maryland|Baltimore (City)": "Baltimore City", "Maryland|Baltimore City": "Baltimore City",
  "Maryland|Baltimore (County)": "Baltimore", "Maryland|Baltimore County": "Baltimore",
  // Towns inside a county the atlas doesn't separate yet
  "Maryland|Baltimore Town": "Baltimore", "Pennsylvania|Philadelphia City": "Philadelphia",
  "Virginia|City of Williamsburg": "Williamsburg",
  // Misspellings in the tables
  "North Carolina|Tyrell": "Tyrrell", "Virginia|Culpepper": "Culpeper", "Wisconsin|Crawfor": "Crawford",
  "Florida|Sumpter": "Sumter",
};

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
const norm = s => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase()
  .replace(/\bSAINT\b/g, "ST").replace(/\([^)]*\)/g, "").replace(/\b(COUNTY|PARISH|DIST)\b/g, "").replace(/[^A-Z]/g, "");
const isCity = f => /\(city\)| City$/.test(f.properties.name);
// Planar point-in-polygon, for places the atlas doesn't draw yet on the stand-in election day (a county
// formed in the weeks between it and the state's own election): their votes go to the county that
// covered the middle of their earliest outline
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

const years = [...new Set(rows.map(r => +r[col("year")]))].sort();
for (const year of years) {
  const day = electionDay(year);
  const results = JSON.parse(fs.readFileSync(`${resultsDir}/results-${year}.json`, "utf8"));
  // The map reads a county's votes as [dem, rep, then the year's other candidates in order]
  const order = ["dem", "rep", ...Object.keys(results.candidates).filter(p => p !== "dem" && p !== "rep")];
  const live = features.filter(f => f.properties.start <= day && f.properties.end >= day);
  const counties = new Map(), cities = new Map();
  for (const f of live) (isCity(f) ? cities : counties).set(f.properties.state + "|" + norm(f.properties.name), f);

  const out = {}, unmatched = new Set(), placedIn = new Set(), states = new Set();
  for (const r of rows.filter(r => +r[col("year")] === year)) {
    const state = r[col("state")], row = r[col("county")], party = r[col("party")];
    if (!order.includes(party)) continue;
    for (const part of row.split(/\s+&\s+/)) {
      const name = ALIASES[`${state}|${part}`] ?? part;
      const city = /\bcity\b/i.test(name);
      let f = city ? cities.get(state + "|" + norm(name)) ?? counties.get(state + "|" + norm(name))
        : counties.get(state + "|" + norm(name)) ?? cities.get(state + "|" + norm(name));
      if (!f) {
        const earliest = features.filter(g => g.properties.state === state && norm(g.properties.name) === norm(name))
          .sort((a, b) => a.properties.start - b.properties.start)[0];
        const p = earliest && middle(earliest);
        // (never an unorganized area: no one there voted for the county named)
        const host = p && live.find(g => g.properties.state === state && g.properties.name !== "Unorganized area" && contains(g, p));
        if (host) { placedIn.add(`${part}, ${state} → ${host.properties.name}`); f = host; }
      }
      if (!f) { unmatched.add(`${part}, ${state}`); continue; }
      states.add(state);
      const v = out[f.properties.key] ??= Object.fromEntries(order.map(p => [p, 0]));
      v[party] += +r[col("votes")];
    }
  }
  const countiesOut = {};
  for (const [k, v] of Object.entries(out).sort()) {
    const arr = order.map(p => v[p]);
    while (arr.length > 2 && arr.at(-1) === 0) arr.pop();
    if (arr.some(x => x > 0)) countiesOut[k] = arr;
  }
  const voted = Object.values(results.states).filter(s => Object.keys(results.candidates).some(p => s[p] > 0)).length;
  fs.writeFileSync(`${outDir}/counties-${year}.json`, JSON.stringify({
    source: `Wikipedia, "${year} United States presidential election in <state>": results by county, on Newberry Library Atlas of Historical County Boundaries outlines`,
    outlines: "historical",
    date: day,
    ...(states.size < voted ? { note: `Counties for ${states.size} of the ${voted} states with a popular vote; the rest show statewide results` } : {}),
    counties: countiesOut,
  }));
  console.log(year, Object.keys(countiesOut).length, "counties in", states.size, "states;",
    unmatched.size ? "unmatched: " + [...unmatched].join("; ") : "all matched",
    placedIn.size ? "\n   placed in the county covering them: " + [...placedIn].join("; ") : "");
}
