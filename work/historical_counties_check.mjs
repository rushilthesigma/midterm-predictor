// Checks counties-YYYY.json (historical outlines) against results-YYYY.json: each state's county sums
// vs its official vote, and whether the county sums pick the same state winner
// usage: node historical_counties_check.mjs <counties dir> <results dir> [years...]
import fs from "node:fs";
const [dir, resultsDir, ...ys] = process.argv.slice(2);
const years = ys.length ? ys.map(Number) : Array.from({ length: 23 }, (_, i) => 1868 + 4 * i);
const hist = JSON.parse(fs.readFileSync(`${dir}/counties-historical.json`, "utf8"));
const stateOf = new Map(hist.objects.counties.geometries.map(g => [g.properties.key, g.properties.state]));
for (const y of years) {
  const res = JSON.parse(fs.readFileSync(`${resultsDir}/results-${y}.json`, "utf8"));
  const order = Object.keys(res.candidates);
  const { counties } = JSON.parse(fs.readFileSync(`${dir}/counties-${y}.json`, "utf8"));
  const sums = {};
  for (const [k, v] of Object.entries(counties)) {
    const s = (sums[stateOf.get(k)] ??= Object.fromEntries(order.map(p => [p, 0])));
    v.forEach((x, i) => s[order[i]] += x);
  }
  const bad = [];
  for (const [st, s] of Object.entries(sums)) {
    const off = res.states[st];
    if (!off || off.absent || off.legislature) { bad.push(`${st}: counties but no state vote`); continue; }
    const win = o => order.reduce((a, b) => ((o[b] ?? 0) > (o[a] ?? 0) ? b : a));
    if (win(s) !== win(off)) bad.push(`${st}: winner ${win(s)} vs official ${win(off)}`);
    for (const p of order) if ((off[p] ?? 0) > 1000 && Math.abs(s[p] / off[p] - 1) > 0.01)
      bad.push(`${st} ${p} ${s[p]} vs ${off[p]} (${((s[p] / off[p] - 1) * 100).toFixed(1)}%)`);
  }
  const voted = Object.entries(res.states).filter(([, r]) => !r.absent && !r.legislature && !r.partOf).map(([n]) => n);
  const missing = voted.filter(n => !sums[n]);
  console.log(y, `${Object.keys(sums).length}/${voted.length} states`, missing.length ? "missing " + missing.join(",") : "", bad.length ? "\n   " + bad.join("\n   ") : "");
}
