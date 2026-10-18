# Lists, per fetched article, the headings of its wikitables that look like county/town results
import json, glob, re, sys
from bs4 import BeautifulSoup
for f in sorted(glob.glob(sys.argv[1] + '/*.json')):
    try: d = json.load(open(f))
    except Exception: print(f, "PENDING"); continue
    name = f.split('/')[-1][:-5]
    if 'parse' not in d: print(name, 'MISSING'); continue
    s = BeautifulSoup(d['parse']['text'], 'lxml')
    hs = []
    for t in s.select('table.wikitable'):
        h = t.find_previous(['h2', 'h3', 'h4'])
        ht = h.get_text(' ', strip=True) if h else ''
        if re.search(r'count|parish|town|district', ht, re.I): hs.append((ht, len(t.find_all('tr'))))
    print(name, hs)
