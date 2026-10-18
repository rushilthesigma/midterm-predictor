import sys, json, os, io, re, glob
import pandas as pd
from bs4 import BeautifulSoup

def clean(s):
    s = re.sub(r'\[[^\]]*\]', '', str(s))
    return re.sub(r'\s+', ' ', s).strip()

def keyfor(top, year):
    t = top.lower()
    if 'margin' in t: return None
    if 'total' in t: return 'total'
    if 'lincoln' in t: return 'rep'
    if 'mcclellan' in t: return 'dem'
    if 'fusion' in t: return 'fusion'
    if 'douglas' in t: return 'dem'
    if 'breckinridge' in t: return 'sd'
    if 'bell' in t: return 'cu'
    if t in ('county', 'parish', 'unnamed: 0_level_0') or t.startswith('county') or t.startswith('parish'): return 'county'
    return 'other'

def num(v):
    s = clean(v).replace(',', '').replace('−', '-').replace('–','-').strip()
    if s in ('', '-', '—', 'nan', 'N/A', '?'): return None
    if re.fullmatch(r'-?\d+', s): return int(s)
    return 'BAD:' + s

def find_tables(soup):
    out = []
    for t in soup.select('table.wikitable'):
        h = t.find_previous(['h2', 'h3', 'h4'])
        ht = h.get_text(' ', strip=True) if h else ''
        if re.search(r'by (county|parish)', ht, re.I):
            out.append((ht, t))
    return out

def parse_table(t, year, soup=None):
    rownotes = []
    for tr in t.find_all('tr'):
        ns = []
        first = tr.find(['th', 'td'])
        for sup in tr.find_all('sup'):
            a = sup.find('a', href=True)
            if not a or not a['href'].startswith('#'): continue
            li = soup.find(id=a['href'][1:]) if soup is not None else None
            if li is not None:
                tx = li.get_text(' ', strip=True)
                tx = re.sub(r'^\^\s*([a-z]\s+)*', '', tx)
                ns.append(tx[:300])
        rownotes.append((first.get_text(' ', strip=True) if first else '', ns))
    for sup in t.find_all('sup'): sup.decompose()
    for sp in t.select('[style*="display:none"]'): sp.decompose()
    df = pd.read_html(io.StringIO(str(t)), thousands=',')[0]
    cols = df.columns.tolist()
    mapping = []  # (colindex, key, toplabel, sublabel)
    for i, c in enumerate(cols):
        top, sub = (c if isinstance(c, tuple) else (c, c))[:2] if isinstance(c, tuple) else (c, c)
        k = keyfor(clean(top), year)
        if k is None: continue
        if k == 'county':
            if any(m[1] == 'county' for m in mapping): continue
            mapping.append((i, k, clean(top), clean(sub))); continue
        if isinstance(c, tuple) and clean(sub) in ('%', 'Percent'): continue
        mapping.append((i, k, clean(top), clean(sub)))
    rows = []
    for _, r in df.iterrows():
        rec = {'county': None, 'other_parts': []}
        for i, k, top, sub in mapping:
            v = r.iloc[i]
            if k == 'county': rec['county'] = clean(v)
            elif k == 'other': rec['other_parts'].append(num(v))
            else:
                if k in rec: rec[k + '_dup'] = num(v)
                else: rec[k] = num(v)
        rows.append(rec)
    # attach notes by matching cleaned first-cell text
    nd = {}
    for name, ns in rownotes:
        nd.setdefault(clean(name), []).extend(ns)
    for rec in rows:
        rec['notes'] = sorted(set(nd.get(rec['county'], [])))
    return mapping, rows

if __name__ == '__main__':
    src = sys.argv[1]; out = sys.argv[2]
    result = {}
    for f in sorted(glob.glob(os.path.join(src, '*.json'))):
        name = os.path.basename(f)[:-5]
        d = json.load(open(f))
        p = d['parse']
        soup = BeautifulSoup(p['text'], 'lxml')
        tabs = find_tables(soup)
        entry = {'title': p['title'], 'tables': []}
        for ht, t in tabs:
            mapping, rows = parse_table(t, int(name[:4]), soup)
            entry['tables'].append({'heading': ht, 'mapping': [m[1:] for m in mapping], 'rows': rows})
        result[name] = entry
    json.dump(result, open(out, 'w'), indent=1, default=str)
