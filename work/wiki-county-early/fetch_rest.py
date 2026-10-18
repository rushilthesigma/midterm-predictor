# Refetches articles the parse API rate-limited, from the REST page/html endpoint, saved in the
# same {"parse": {"title", "text"}} shape (a 404 is saved as {"error": ...}); backs off on 429s
import json, sys, time, urllib.request, urllib.error, glob
out = sys.argv[1]
import os
for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pages.txt')):
    y, s = line.split(); f = f'{out}/{y}_{s}.json'
    raw = open(f).read() if os.path.exists(f) else ''
    if raw.startswith('{') and ('"parse"' in raw or '"error"' in raw): continue
    page = f'{y}_{s}'
    title = f'{y}_United_States_presidential_election_in_{s}'
    req = urllib.request.Request('https://en.wikipedia.org/api/rest_v1/page/html/' + title,
                                 headers={'User-Agent': 'us-map-research/1.0'})
    for wait in (0, 30, 60, 120, 240):
        time.sleep(wait or 3)
        try:
            html = urllib.request.urlopen(req).read().decode()
            json.dump({'parse': {'title': title.replace('_', ' '), 'text': html}}, open(f, 'w'))
            print('ok', page, flush=True); break
        except urllib.error.HTTPError as e:
            if e.code == 429: continue  # rate-limited: back off and retry
            json.dump({'error': e.code}, open(f, 'w')); print(e.code, page, flush=True); break
