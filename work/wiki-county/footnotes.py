import sys, json, os, re
from bs4 import BeautifulSoup
for f in sys.argv[2:]:
    d = json.load(open(os.path.join(sys.argv[1], f + '.json')))
    soup = BeautifulSoup(d['parse']['text'], 'lxml')
    notes = []
    for ol in soup.select('div.reflist ol.references, ol.references'):
        for li in ol.find_all('li', recursive=False):
            tx = li.get_text(' ', strip=True)
            if not re.search(r'\b(ISBN|Retrieved|pp?\.|Archived)\b', tx) or len(tx) > 200:
                notes.append(tx[:500])
    print('=====', f); [print('   -', n) for n in notes[:25]]
