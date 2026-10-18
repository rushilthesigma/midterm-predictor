#!/bin/sh
# Simplifies the UCLA historical congressional district shapefiles (Lewis et al.,
# cdmaps.polisci.ucla.edu/shp/districtsNNN.zip, unzipped to ucla/dNNN/) into ucla/cdNNN.json for
# build_midterms.py: one feature per district, id = state FIPS + 2-digit district (00 at-large).
# The files also carry each state's at-large outline for whenever it has one seat; it's dropped
# where the state has numbered districts that Congress. 1978's lines skip -clean, which loses
# Tennessee's 8th to an overlap.
# usage: sh build_ucla_districts.sh   (from work/)
set -e
cd ucla
MS=${MAPSHAPER:-mapshaper}
LOOKUP=$(python3 -c "
import json, re
s = open('../build_midterms.py').read()
d = eval(re.search(r'STATES = (\{.*?\})', s, re.S).group(1)); d['11'] = 'District of Columbia'
print(json.dumps({v: k for k, v in d.items()}))")
for c in 096 098 100 104 106 108 110; do
  $MS d$c/districts$c.shp -o attrs.csv format=csv force
  MULTI=$(python3 -c "
import csv, json
print(json.dumps(sorted({r['STATENAME'] for r in csv.DictReader(open('attrs.csv')) if r['DISTRICT'] not in ('0', '')})))")
  if [ $c = 096 ]; then PCT=1.6%; CLEAN=; else PCT=0.9%; CLEAN=-clean; fi
  $MS d$c/districts$c.shp -filter "!(DISTRICT == 0 && $MULTI.includes(STATENAME))" \
    -each "id = ($LOOKUP)[STATENAME] ? ($LOOKUP)[STATENAME] + String(DISTRICT).padStart(2,'0') : null" \
    -filter 'id != null' -dissolve id -rename-layers districts -simplify $PCT keep-shapes $CLEAN \
    -o format=topojson id-field=id quantization=100000 cd$c.json force
done
rm -f attrs.csv
