# Parses the county tables on Wikipedia's "<year> United States presidential election in <state>"
# articles for 1796-1856 (fetched by fetch.sh / fetch_rest.py) into a long CSV for
# build_early_counties.mjs: year,state,county,party,votes,source_page. Columns are matched to the
# candidates in results-<year>.json by surname; anything else (scattering, unpledged) is "other".
# Values are copied as written (footnote markers stripped); "-", "**" and blanks are no data.
# Also writes a notes file comparing each state's county sums with the table's total row and with
# results-<year>.json.
# usage: python parse.py <html dir> <results dir> <out csv> <out notes.md>
import sys, json, os, io, re, glob, csv
import pandas as pd
from bs4 import BeautifulSoup

src, results_dir, out_csv, out_md = sys.argv[1:5]

def clean(s):
    s = re.sub(r'\[[^\]]*\]', '', str(s))
    return re.sub(r'\s+', ' ', s).strip()

def num(v):
    s = clean(v).replace(',', '').replace('−', '-').replace('–', '-').strip()
    if s in ('', '-', '—', 'nan', 'N/A', '?', '**', '*', 'n/a', 'No returns', 'No Returns'): return None
    if re.fullmatch(r'-?\d+', s): return int(s)
    if re.fullmatch(r'\d+\.0', s): return int(s[:-2])  # read as a float by pandas
    if re.fullmatch(r'\d{1,3}(\.\d{3})+', s): return int(s.replace('.', ''))  # "1.923", a typo for 1,923
    return 'BAD:' + s

COUNTY_HEAD = re.compile(r'^(county|parish|counties|county or city|county/city|city or county|unnamed: 0_level_0)\b', re.I)
TABLE_HEAD = re.compile(r'by (county|parish)|county results|results by county', re.I)

# Party labels, for columns that name a slate rather than a candidate ("Unpledged electors Federalist")
PARTY = {'dr': 'democratic-republican', 'fed': 'federalist', 'whig': 'whig', 'dem': 'democratic', 'rep': 'republican',
         'amer': 'know nothing', 'fs': 'free soil', 'nr': 'national republican', 'am': 'anti-masonic'}
deaccent = lambda s: __import__('unicodedata').normalize('NFD', s).encode('ascii', 'ignore').decode()

def keyfor(top, candidates):
    t = deaccent(top).lower()
    if 'margin' in t or 'swing' in t: return None
    if t.startswith('total') or 'total votes' in t or t == 'votes cast': return 'total'
    if COUNTY_HEAD.match(t): return 'county'
    # Longest surname first, so "Van Buren" wins over a "Buren" substring and so on
    for key, name in sorted(candidates.items(), key=lambda kv: -len(kv[1])):
        if name.lower() == 'federalist electors':
            if 'federalist' in t: return key
        elif re.search(r'\b' + re.escape(deaccent(name).lower()) + r'\b', t): return key
    if 'unpledged' in t or 'elector' in t:
        for key, label in sorted(PARTY.items(), key=lambda kv: -len(kv[1])):
            if key in candidates and label in t: return key
    return 'other'

def find_tables(soup):
    out = []
    for t in soup.select('table.wikitable'):
        h = t.find_previous(['h2', 'h3', 'h4'])
        ht = h.get_text(' ', strip=True) if h else ''
        if TABLE_HEAD.search(ht) and 'swing' not in ht.lower(): out.append((ht, t))
    return out

def parse_table(t, candidates):
    for sup in t.find_all('sup'): sup.decompose()
    for sp in t.select('[style*="display:none"]'): sp.decompose()
    df = pd.read_html(io.StringIO(str(t)), thousands=',')[0]
    mapping = []
    for i, c in enumerate(df.columns.tolist()):
        top, sub = (clean(c[0]), clean(c[-1])) if isinstance(c, tuple) else (clean(c), clean(c))
        k = keyfor(top, candidates)
        if k is None: continue
        if k == 'county':
            if any(m[1] == 'county' for m in mapping): continue
        elif sub in ('%', 'Percent', 'Percentage') or sub.endswith('%'): continue
        mapping.append((i, k, top, sub))
    rows = []
    for _, r in df.iterrows():
        rec = {'county': None, 'votes': {}}
        for i, k, top, sub in mapping:
            v = r.iloc[i]
            if k == 'county': rec['county'] = clean(v)
            elif k == 'total': rec['total'] = num(v)
            else:
                n = num(v)
                if isinstance(n, int): rec['votes'][k] = rec['votes'].get(k, 0) + n
                elif n is not None: rec.setdefault('bad', []).append(n)
        rows.append(rec)
    return mapping, rows

def fmt(n): return '' if n is None else f'{n:,}'

out_rows, md, summary = [], [], []
md.append('# County-level presidential results, 1796-1856 (from English Wikipedia)\n')
md.append('Source: per-state articles "<year> United States presidential election in <State>" (Oct 2026). Only the "Results by county/parish" wikitable was used; values copied as written. States whose article has no such table, or whose table has no county numbers, are not in the CSV and show their statewide result on the map.\n')
md.append('FLAG = county sum differs from the reference by more than 1% of the state total.\n')
for f in sorted(glob.glob(os.path.join(src, '*.json'))):
    name = os.path.basename(f)[:-5]; year = int(name[:4]); state = name[5:].replace('_', ' ')
    d = json.load(open(f))
    if 'parse' not in d: summary.append((year, state, 'no article', 0, '', '')); continue
    results = json.load(open(f'{results_dir}/results-{year}.json'))
    cands = results['candidates']
    soup = BeautifulSoup(d['parse']['text'], 'lxml')
    page = 'https://en.wikipedia.org/wiki/' + d['parse']['title'].replace(' ', '_')
    tabs = find_tables(soup)
    sec = [f'\n## {year} {state}\n', f'Page: {page}\n']
    chosen = None
    for ht, t in tabs:
        mapping, rows = parse_table(t, cands)
        if not any(m[1] == 'county' for m in mapping): continue
        recs = [r for r in rows if r['county'] and not re.match(r'^(totals?|state total)\b', r['county'], re.I) and r['votes']]
        if recs: chosen = (ht, mapping, rows, recs); break
    if not chosen:
        sec.append('- no county table with numbers' if tabs else '- no county table')
        summary.append((year, state, 'none', 0, '', '')); md += sec; continue
    ht, mapping, rows, recs = chosen
    totrow = next((r for r in rows if r['county'] and re.match(r'^(totals?|state total)\b', r['county'], re.I)), None)
    bad = [(r['county'], r['bad']) for r in recs if r.get('bad')]
    cols = sorted({k for r in recs for k in r['votes']}, key=lambda k: list(cands).index(k) if k in cands else 99)
    sec.append(f'- heading "{ht}"; {len(recs)} county rows; columns: ' + ', '.join(f'{k} ("{top}")' for _, k, top, _ in mapping if k not in ('county', 'total')))
    if bad: sec.append('- unparsed cells (left out): ' + '; '.join(f'{c}: {b}' for c, b in bad))
    sums = {k: sum(r['votes'].get(k, 0) for r in recs) for k in cols}
    st = results['states'].get(state, {})
    st_tot = sum(v for k, v in st.items() if k in cands and isinstance(v, int))
    sec += ['', '| | ' + ' | '.join(cols) + ' |', '|---' * (len(cols) + 1) + '|',
            '| county sum | ' + ' | '.join(fmt(sums[k]) for k in cols) + ' |']
    def off(ref, limit):
        tot = sum(v for v in ref.values() if v) or 1
        return any(abs(sums.get(k, 0) - (ref.get(k) or 0)) > limit * tot for k in cands if k in ref or k in sums)
    tflag = jflag = ''
    jref = {k: v for k, v in st.items() if k in cands}
    if totrow:
        sec.append('| table total row | ' + ' | '.join(fmt(totrow['votes'].get(k)) for k in cols) + ' |')
        tflag = 'FLAG' if off(totrow['votes'], 0.01) else 'ok'
    sec.append(f'| results-{year}.json | ' + ' | '.join(fmt(st.get(k)) for k in cols) + ' |')
    jflag = 'FLAG' if off(jref, 0.01) else 'ok'
    # Share of the statewide vote the reporting counties account for
    cover = sum(sums.get(k, 0) for k in cands) / st_tot if st_tot else 0
    sec.append(f'\n- counties sum to {cover:.0%} of the statewide vote in results-{year}.json')
    # Left off the map (the state keeps its statewide color): tables where fewer than half the listed
    # counties have numbers, and tables whose county sums are more than 5% off both the table's own
    # total row and the statewide results (1852 Maryland's county rows give Scott the state Pierce won)
    listed = [r for r in rows if r['county'] and not re.match(r'^(totals?|state total)\b', r['county'], re.I)]
    status = 'used'
    if len(recs) < len(listed) / 2: status = f'left out: only {len(recs)} of {len(listed)} counties have numbers'
    elif off(jref, 0.05) and (not totrow or off(totrow['votes'], 0.05)): status = 'left out: county sums more than 5% off the state totals'
    sec.append(f'- **{status}**')
    if status == 'used':
        for r in recs:
            for k, v in r['votes'].items():
                out_rows.append({'year': year, 'state': state, 'county': r['county'], 'party': k, 'votes': v, 'source_page': page})
    summary.append((year, state, status, len(recs), tflag, f'{jflag} ({cover:.0%})'))
    md += sec

with open(out_csv, 'w', newline='') as fh:
    w = csv.DictWriter(fh, ['year', 'state', 'county', 'party', 'votes', 'source_page']); w.writeheader(); w.writerows(out_rows)
head = ['\n## Summary\n', '| year | state | status | rows | vs table total | vs results json (coverage) |', '|---|---|---|---|---|---|']
head += [f'| {y} | {s} | {st} | {n or ""} | {a} | {b} |' for y, s, st, n, a, b in summary]
open(out_md, 'w').write('\n'.join(md[:3] + head + md[3:]) + '\n')
found = [s for s in summary if s[2] == 'used']
print(len(found), 'state-years used;', len(out_rows), 'rows')
for s in summary:
    if s[2].startswith('left out'): print('  ', s[0], s[1], s[2])
