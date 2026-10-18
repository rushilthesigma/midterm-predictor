// Builds shapes-albers.json (counties + states) from the Census 2017 full-resolution TIGER/Line
// county boundaries, clipped to the 1:500k cartographic coastline (TIGER counties run out into
// lakes and the ocean). Much more detailed than us-atlas's 1:10m outlines. Same 2017 county FIPS
// set and same AlbersUSA frame (scale 1300, translate [487.5, 305]) as us-atlas, so results,
// districts and zoom math are unchanged. States are dissolved from the counties so borders line up.
// usage: node --max-old-space-size=8192 build_shapes.mjs <tl_2017_us_county.shp> <cb_2017_us_county_500k.shp> <out dir>
//   (needs mapshaper, d3-geo, d3-geo-projection)
import fs from "node:fs";
import mapshaper from "mapshaper";
import { geoAlbersUsa, geoArea } from "d3-geo";
import { geoProject } from "d3-geo-projection";

const [tigerShp, cbShp, outDir] = process.argv.slice(2);
const shapefile = (name, shp) => ({ [`${name}.shp`]: fs.readFileSync(shp),
  [`${name}.dbf`]: fs.readFileSync(shp.replace(/\.shp$/, ".dbf")),
  [`${name}.prj`]: fs.readFileSync(shp.replace(/\.shp$/, ".prj"), "utf8") });
const STATES = { "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas", "06": "California",
  "08": "Colorado", "09": "Connecticut", "10": "Delaware", "11": "District of Columbia", "12": "Florida",
  "13": "Georgia", "15": "Hawaii", "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa",
  "20": "Kansas", "21": "Kentucky", "22": "Louisiana", "23": "Maine", "24": "Maryland",
  "25": "Massachusetts", "26": "Michigan", "27": "Minnesota", "28": "Mississippi", "29": "Missouri",
  "30": "Montana", "31": "Nebraska", "32": "Nevada", "33": "New Hampshire", "34": "New Jersey",
  "35": "New Mexico", "36": "New York", "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
  "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island", "45": "South Carolina",
  "46": "South Dakota", "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont", "51": "Virginia",
  "53": "Washington", "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming" };

// 1. Read, drop territories, keep id + name, clip to land, export lon/lat GeoJSON
const keep = JSON.stringify(Object.keys(STATES));
const raw = await mapshaper.applyCommands([
  "-i tiger.shp name=counties",
  `-filter '${keep}.indexOf(STATEFP) > -1'`,
  "-each 'id=GEOID, name=NAME'",
  "-filter-fields id,name",
  "-i cb.shp name=land",
  "-dissolve target=land",
  "-clip land target=counties remove-slivers",
  "-o out.json format=geojson target=counties",
].join(" "), { ...shapefile("tiger", tigerShp), ...shapefile("cb", cbShp) });

// 2. Project into us-atlas's AlbersUSA frame
const projection = geoAlbersUsa().scale(1300).translate([487.5, 305]);
const geo = JSON.parse(raw["out.json"]);
// d3 wants clockwise outer rings; flip any polygon that came out inside-out (area > hemisphere)
for (const f of geo.features) {
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  for (const rings of polys)
    if (geoArea({ type: "Polygon", coordinates: rings }) > 2 * Math.PI) rings.forEach(r => r.reverse());
}
const projected = geoProject(geo, projection);
for (const f of projected.features) f.id = f.properties.id;

// 3. Simplify in screen units (detail down to ~0.4 px at the map's 40x max zoom), dissolve
//    states, and write TopoJSON
const stateNames = JSON.stringify(STATES);
const out = await mapshaper.applyCommands([
  "-i counties.json name=counties",
  "-simplify interval=0.01 keep-shapes",
  "-clean",
  "-each 'state=id.slice(0,2)'",
  "-dissolve state copy-fields= + name=states",
  `-each 'id=state, name=${stateNames}[state]' target=states`,
  "-filter-fields id,name target=states",
  "-filter-fields id,name target=counties",
  "-o counties-albers.json format=topojson target=counties,states id-field=id quantization=2e5",
].join(" "), { "counties.json": JSON.stringify(projected) });
fs.writeFileSync(`${outDir}/shapes-albers.json`, out["counties-albers.json"]);
console.log("wrote", `${outDir}/shapes-albers.json`, out["counties-albers.json"].length, "bytes");
