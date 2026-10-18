// Builds counties-historical.json: every county outline in force on some presidential election day
// from 1796 to 1956, from the Newberry Library's Atlas of Historical County Boundaries (generalized
// 0.001° shapefile, US_HistCounties_Gen001). Each version of a county is its own feature, with the
// dates it was in force, so the map can draw the counties as they stood for each election.
// Projected into the same AlbersUSA frame as shapes-albers.json and clipped to its states, so the
// coastline and state borders match the rest of the map.
// usage: node --max-old-space-size=8192 build_historical_shapes.mjs <US_HistCounties_Gen001.shp> <shapes-albers.json> <out dir>
//   (needs mapshaper, d3-geo, d3-geo-projection)
import fs from "node:fs";
import mapshaper from "mapshaper";
import { geoAlbersUsa, geoArea } from "d3-geo";
import { geoProject } from "d3-geo-projection";

const [shp, shapesAlbers, outDir] = process.argv.slice(2);
const STATES = ["Alabama", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
  "Florida", "Georgia", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
  "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
  "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
  "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
  "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"];
// Election day: the Tuesday after the first Monday in November (from 1848; before that each state
// voted on its own day in November or early December, and this date stands in for all of them)
const electionDay = y => {
  const d = new Date(Date.UTC(y, 10, 1));
  const firstMonday = 1 + (8 - d.getUTCDay()) % 7;
  return y * 10000 + 1100 + firstMonday + 1;
};
const DAYS = [];
for (let y = 1796; y <= 1956; y += 4) DAYS.push(electionDay(y));

const shapefile = (name, path) => ({ [`${name}.shp`]: fs.readFileSync(path),
  [`${name}.dbf`]: fs.readFileSync(path.replace(/\.shp$/, ".dbf")),
  [`${name}.prj`]: fs.readFileSync(path.replace(/\.shp$/, ".prj"), "utf8") });

// 1. Keep county versions in force on some election day, in a state at the time
const raw = await mapshaper.applyCommands([
  "-i hist.shp name=counties",
  `-filter '${JSON.stringify(STATES)}.indexOf(STATE_TERR) > -1 && ${JSON.stringify(DAYS)}.some(d => START_N <= d && END_N >= d)'`,
  "-each 'key=ID, num=ID_NUM, name=NAME, fips=FIPS, start=START_N, end=END_N, state=STATE_TERR'",
  "-filter-fields key,num,name,fips,start,end,state",
  "-o out.json format=geojson",
].join(" "), shapefile("hist", shp));

// 2. Project into us-atlas's AlbersUSA frame
const geo = JSON.parse(raw["out.json"]);
for (const f of geo.features) {
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  for (const rings of polys)
    if (geoArea({ type: "Polygon", coordinates: rings }) > 2 * Math.PI) rings.forEach(r => r.reverse());
}
// Display names: the atlas has "ST. LOUIS", "Richmond (IC)" (independent city), "KLAMATH (ext)", and
// "MN NCA 5" for areas outside any county
const label = name => /^[A-Z]{2} NCA\b/.test(name) ? "Unorganized area" : name.replace(/\s*\(ext\)/i, "").replace(/ City \(IC\)/i, " City").replace(/\(IC(, ext)?\)/i, "(city)")
  .toLowerCase().replace(/(^|[\s.'-])([a-z])/g, (m, p, c) => p + c.toUpperCase())
  .replace(/\bMc([a-z])/g, (m, c) => "Mc" + c.toUpperCase()).replace(/\(City\)/, "(city)");
for (const f of geo.features) f.properties.name = label(f.properties.name);
const projected = geoProject(geo, geoAlbersUsa().scale(1300).translate([487.5, 305]));
projected.features = projected.features.filter(f => f.geometry);
console.log(projected.features.length, "county versions");

// 3. Clip to today's state outlines (same coastline as the base map), simplify like shapes-albers
//    (no -clean: versions of a county overlap by design, and -clean would carve them apart)
//    (screen units, ~0.4 px at 40x zoom), and write TopoJSON
const out = await mapshaper.applyCommands([
  "-i albers.json",
  "-drop target=counties",
  "-dissolve target=states name=land",
  "-i counties.json name=hist",
  "-clip land target=hist remove-slivers",
  "-simplify interval=0.01 keep-shapes target=hist",
  "-rename-layers counties target=hist",
  "-o hist.json format=topojson target=counties id-field=num quantization=2e5",
].join(" "), { "counties.json": JSON.stringify(projected), "albers.json": fs.readFileSync(shapesAlbers, "utf8") });
fs.writeFileSync(`${outDir}/counties-historical.json`, out["hist.json"]);
console.log("wrote", `${outDir}/counties-historical.json`, out["hist.json"].length, "bytes");
