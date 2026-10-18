// Builds counties-YYYY.json for 1868-1956 on the historical county outlines in
// counties-historical.json (build_historical_shapes.mjs), from Algara & Amlani's county returns
// (Harvard Dataverse doi:10.7910/DVN/DGUMFI, CC0; exported by export_algara.py).
//
// Counties are keyed by the Newberry atlas's county id (stable across boundary changes), each
// [dem, rep, ...third parties], the third parties in the order of that year's results-YYYY.json.
//
// Algara records votes by party line, not by candidate, and lumps every minor party into the total.
// So each state's columns are matched to the candidates in results-YYYY.json by their statewide sums:
// the Democratic line was Thurmond's in Alabama in 1948, the Republican line Roosevelt's in
// California in 1912, and so on. The remaining "other" votes go to the year's leading third party
// where it made up at least half of them statewide (scaled down to its share), and are dropped
// otherwise. Each column is then scaled so the state's counties add up to its official total,
// unless that would change it by more than MAX_SCALE (then it's reported and left as is).
//
// usage: node build_historical_counties.mjs <pres_1868_1956.csv> <counties-historical.json> <results dir> <out dir> [years...]
import fs from "node:fs";
import { feature } from "topojson-client";

const [csvPath, histPath, resultsDir, outDir, ...yearArgs] = process.argv.slice(2);
const YEARS = yearArgs.length ? yearArgs.map(Number) : Array.from({ length: 23 }, (_, i) => 1868 + 4 * i);
const MAX_SCALE = 0.2;
const ABBR = { AL: "Alabama", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut",
  DE: "Delaware", FL: "Florida", GA: "Georgia", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
  KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts",
  MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska",
  NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina",
  ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island",
  SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont",
  VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming" };
const electionDay = y => {
  const d = new Date(Date.UTC(y, 10, 1));
  return y * 10000 + 1100 + 1 + (8 - d.getUTCDay()) % 7 + 1;
};

// --- inputs
const rows = fs.readFileSync(csvPath, "utf8").trim().split("\n").slice(1).map(line => {
  const [year, fips, county, state, dem, rep, total] = line.split(",");
  const d = +dem || 0, r = +rep || 0;
  return { year: +year, fips: fips || null, county, state: ABBR[state], dem: d, rep: r,
    other: Math.max(0, (+total || 0) - d - r) };
});
// Algara's Baltimore County row includes Baltimore City (which also has its own row) in most years
for (const city of rows.filter(r => r.fips === "24510")) {
  const county = rows.find(r => r.year === city.year && r.fips === "24005");
  if (county && county.dem >= city.dem && county.rep >= city.rep) {
    county.dem -= city.dem; county.rep -= city.rep; county.other = Math.max(0, county.other - city.other);
  }
}
const topo = JSON.parse(fs.readFileSync(histPath, "utf8"));
const features = feature(topo, topo.objects.counties).features;

// --- geometry helpers (planar, in the projected frame)
const rings = f => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates);
const ringArea = r => r.reduce((a, [x0, y0], i) => { const [x1, y1] = r[(i + 1) % r.length]; return a + x0 * y1 - x1 * y0; }, 0) / 2;
function interiorPoint(f) {
  // centroid of the largest ring
  let best = null, bestA = 0;
  for (const poly of rings(f)) { const a = Math.abs(ringArea(poly[0])); if (a > bestA) { bestA = a; best = poly[0]; } }
  let cx = 0, cy = 0, a = 0;
  best.forEach(([x0, y0], i) => { const [x1, y1] = best[(i + 1) % best.length]; const c = x0 * y1 - x1 * y0; a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c; });
  return [cx / (3 * a), cy / (3 * a)];
}
const inRing = ([x, y], r) => {
  let inside = false;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
};
const contains = (f, p) => rings(f).some(poly => inRing(p, poly[0]) && !poly.slice(1).some(h => inRing(p, h)));
const byFipsAll = new Map();
for (const f of features) if (f.properties.fips) {
  if (!byFipsAll.has(f.properties.fips)) byFipsAll.set(f.properties.fips, []);
  byFipsAll.get(f.properties.fips).push(f);
}
const d3sum = a => a.reduce((x, y) => x + y, 0);
const norm = s => String(s).toUpperCase().replace(/\([^)]*\)/g, "").replace(/[^A-Z]/g, "");

const report = [];
for (const year of YEARS) {
  const day = electionDay(year);
  const results = JSON.parse(fs.readFileSync(`${resultsDir}/results-${year}.json`, "utf8"));
  const thirds = Object.keys(results.candidates).filter(k => k !== "dem" && k !== "rep");
  const live = features.filter(f => f.properties.start <= day && f.properties.end >= day);
  const liveByFips = new Map(), liveByName = new Map();
  for (const f of live) {
    if (f.properties.fips) liveByFips.set(f.properties.fips, f);
    liveByName.set(f.properties.state + "|" + norm(f.properties.name), f);
  }

  // 1. Each Algara county to the county outline in force on election day: by FIPS, else by name,
  //    else the outline containing the nearest-dated version of that FIPS (a county created or
  //    renamed around the election, whose votes the atlas puts in its parent)
  const sums = new Map(); // key -> { state, dem, rep, other }
  const unplaced = [];
  for (const row of rows.filter(r => r.year === year && r.state)) {
    let f = row.fips && liveByFips.get(row.fips);
    if (f && f.properties.state !== row.state) f = null;
    f ??= liveByName.get(row.state + "|" + norm(row.county));
    if (!f && row.fips && byFipsAll.has(row.fips)) {
      const nearest = byFipsAll.get(row.fips).slice()
        .sort((a, b) => Math.min(Math.abs(a.properties.start - day), Math.abs(a.properties.end - day))
          - Math.min(Math.abs(b.properties.start - day), Math.abs(b.properties.end - day)))[0];
      const p = interiorPoint(nearest);
      f = live.find(g => g.properties.state === row.state && contains(g, p));
    }
    if (!f) { if (row.dem + row.rep + row.other > 0) unplaced.push(`${row.county} ${row.state} (${row.fips})`); continue; }
    const k = f.properties.key;
    if (!sums.has(k)) sums.set(k, { state: f.properties.state, dem: 0, rep: 0, other: 0 });
    const s = sums.get(k);
    s.dem += row.dem; s.rep += row.rep; s.other += row.other;
  }

  // 2. Per state, match the dem/rep/other columns to candidates and scale to the official totals
  const byState = new Map();
  for (const [k, s] of sums) {
    if (!byState.has(s.state)) byState.set(s.state, []);
    byState.get(s.state).push([k, s]);
  }
  const counties = {}, notes = [];
  const order = ["dem", "rep", ...thirds];
  for (const [state, list] of byState) {
    const off = results.states[state];
    if (!off || off.absent || off.legislature || off.partOf) continue;
    const A = { dem: 0, rep: 0, other: 0 };
    for (const [, s] of list) { A.dem += s.dem; A.rep += s.rep; A.other += s.other; }
    const offTotal = Object.values(off).reduce((a, b) => a + b, 0);
    const near = (a, b) => Math.abs(a - b) <= 0.1 * Math.max(a, b);
    // A party line goes to a third party only when it matches that party's statewide vote and
    // clearly doesn't match its own nominee's (Thurmond on Alabama's Democratic line in 1948)
    const line = (col, own, taken) => {
      if (near(A[col], off[own] ?? 0)) return own;
      return thirds.find(k => !taken.has(k) && near(A[col], off[k] ?? 0)
        && Math.abs(A[col] - (off[own] ?? 0)) > 0.25 * Math.max(A[col], 1)) ?? own;
    };
    const demTo = line("dem", "dem", new Set());
    const repTo = line("rep", "rep", new Set([demTo]));
    // "Other" first makes up a nominee's shortfall on his main line (fusion and faction tickets:
    // Greeley's Liberal Republicans, Bryan's Populist fusion, New York's Liberal and American Labor
    // lines, Independents for Eisenhower), then goes to the leading remaining third party when it
    // was at least half of what's left
    const otherShare = {};
    let left = A.other;
    for (const [col, k] of [["dem", demTo], ["rep", repTo]]) {
      const short = (off[k] ?? 0) - A[col];
      if (left > 0 && short > 0.03 * (off[k] ?? 0)) {
        const take = Math.min(short, left);
        otherShare[k] = take / A.other; left -= take;
      }
    }
    const rest = order.filter(k => k !== demTo && k !== repTo && !otherShare[k] && (off[k] ?? 0) > 0)
      .sort((a, b) => off[b] - off[a])[0];
    if (rest && left > 0 && off[rest] >= 0.5 * left) otherShare[rest] = Math.min(left, off[rest]) / A.other;

    const raw = new Map(list.map(([k, s]) => {
      const v = Object.fromEntries(order.map(p => [p, 0]));
      v[demTo] += s.dem; v[repTo] += s.rep;
      for (const [p, f] of Object.entries(otherShare)) v[p] += s.other * f;
      return [k, v];
    }));
    // Scale each candidate to the official statewide vote, unless it's too far off to trust. The two
    // majors scale together or not at all, so a shortfall in one can't flip the state's counties.
    const scale = {}, flags = [];
    const ratio = p => { const sum = d3sum([...raw.values()].map(v => v[p])); return sum ? (off[p] ?? 0) / sum : null; };
    const bad = p => ratio(p) != null && Math.abs(ratio(p) - 1) > MAX_SCALE;
    const majors = order.filter(p => p === demTo || p === repTo || otherShare[p] && (p === "dem" || p === "rep"));
    const majorsOk = !majors.some(bad);
    for (const p of order) {
      if (ratio(p) == null) continue;
      if (majors.includes(p) ? majorsOk : !bad(p)) scale[p] = ratio(p);
      else { scale[p] = 1; flags.push(`${p} ${((1 / ratio(p) - 1) * 100).toFixed(0)}%`); }
    }
    const mapping = [demTo !== "dem" && `dem line→${demTo}`, repTo !== "rep" && `rep line→${repTo}`,
      ...Object.entries(otherShare).map(([p, f]) => `other→${p} ${(f * 100).toFixed(0)}%`)].filter(Boolean);
    if (mapping.length) notes.push(`${state}: ${mapping.join(", ")}`);
    if (flags.length) report.push(`${year} ${state}: not scaled: ${flags.join("; ")}`);
    for (const [k, v] of raw) {
      const arr = order.map(p => Math.round(v[p] * (scale[p] ?? 1)));
      while (arr.length > 2 && arr.at(-1) === 0) arr.pop();
      if (arr.some(x => x > 0)) counties[k] = arr;
    }
  }
  const out = {
    source: "Algara & Amlani, U.S. county presidential returns 1868-2020 (Harvard Dataverse), on Newberry Library Atlas of Historical County Boundaries outlines",
    outlines: "historical",
    date: day,
    counties: Object.fromEntries(Object.entries(counties).sort()),
  };
  fs.writeFileSync(`${outDir}/counties-${year}.json`, JSON.stringify(out));
  console.log(year, Object.keys(counties).length, "counties of", live.length, "outlines;",
    unplaced.length ? `unplaced: ${unplaced.join(", ")}` : "all placed");
  for (const n of notes) console.log("   ", n);
}
console.log("\n" + report.join("\n"));
