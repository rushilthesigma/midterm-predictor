import sys, json, re, csv
parsed = json.load(open(sys.argv[1])); out_csv = sys.argv[2]; out_md = sys.argv[3]
res = {y: json.load(open(f'/Users/rushilkelapure/us-map/results-{y}.json'))['states'] for y in (1860, 1864)}
KEYS = ['rep', 'dem', 'sd', 'cu', 'fusion', 'other']
UNOFFICIAL = re.compile(r'not included in (the )?official|too late to be included|after the deadline|not counted in the totals|did not arrive in time|rejected by the Board|Not included in official canvass', re.I)
MANUAL = {
 '1860_Iowa': ['"Various candidates / Other parties" column (Breckinridge + Bell combined, not split by county) stored under `other`; `sd`/`cu` blank.'],
 '1860_Ohio': ['"Various candidates / Other parties" column (Breckinridge + Bell + others combined) stored under `other`; `sd`/`cu` blank.'],
 '1860_New_Jersey': ['Only Lincoln and a combined Douglas/Breckinridge/Bell **fusion** column; fusion votes under `fusion`. Page notes fusion slate = 3 Douglas, 2 Breckinridge, 2 Bell electors; non-fusion straight-ticket electors also got votes but are not in the county table.', 'results-1860.json has dem/sd/cu = 0 for NJ (fusion not represented there).'],
 '1860_New_York': ['Only Lincoln and a **fusion** (Douglas/Bell/Breckinridge) column; fusion votes under `fusion`.', 'Hamilton County is included in Fulton (no separate Hamilton row).', 'New York City also has a separate by-ward table on the page; not used (the "New York" county row is used).', 'results-1860.json has dem/sd/cu = 0 for NY (fusion not represented there).'],
 '1860_Rhode_Island': ['Only Lincoln and a **fusion** (Douglas/Breckinridge/Bell) column; fusion votes under `fusion`. results-1860.json stores the same 7,707 under `dem`.'],
 '1860_Pennsylvania': ['Columns: Lincoln, Breckinridge/Douglas **fusion** ticket (`fusion`), straight Douglas ticket (`dem`), Bell (`cu`). No separate Breckinridge column (`sd` blank). results-1860.json has sd = 0 and no fusion figure.'],
 '1860_Texas': ['No Douglas column: Douglas write-ins (18 statewide) are given only as a state total per the page; `dem` blank.', 'Page notes no returns located for Clay County (no row).'],
 '1860_Missouri': ['Douglas County votes are included in Ozark (per footnote).'],
 '1860_North_Carolina': ['Wilson County is included in Edgecombe (per footnote).'],
 '1860_Tennessee': ['Cheatham County vote is included in Davidson, Montgomery and Robertson (per footnote).', 'Davidson row: candidate votes sum to 6,665 but the table\'s total column says 5,665 (apparent typo in the table; kept as written). Candidate column sums match the table total row exactly; the total column sums to 145,147 vs the table\'s 146,147 because of this.'],
 '1860_Virginia': ['Includes counties now in West Virginia (state was undivided in 1860).', 'Some rows are independent cities reported separately: Norfolk City (plus Norfolk County), Richmond City (plus Richmond County), Petersburg, Portsmouth, Williamsburg; "Alexandria" is a single row (county vs. city not distinguished).'],
 '1860_Maryland': ['Baltimore City and Baltimore County are separate rows ("Baltimore (City)", "Baltimore (County)").'],
 '1864_Maryland': ['Baltimore City and Baltimore County are separate rows.', 'County rows sum to 37,353 Lincoln / 32,418 McClellan, but the table total row (and results-1864.json) is 40,153 / 32,739. The gap (2,800 / 321) is not explained in the table; it is most likely the soldiers\' vote, which has no row. Not verified - do not treat county sums as the state total.'],
 '1864_Nevada': ['Only Churchill and Nye counties have numbers; Douglas, Esmeralda, Humboldt, Lander, Lyon, Ormsby, Storey, "Washoe & Roop" and Soldiers show "-" (no data) and are omitted from the CSV. Effectively NOT usable for a county map.'],
 '1864_Minnesota': ['Two rows have obviously wrong values in the table\'s total column: Carver total = 1 (candidates sum to 1,094) and Wright total = 184 (candidates sum to 884). Kept as written in the CSV.'],
 '1864_New_York': ['Hamilton County is included in Fulton.', 'New York City by-ward table also on page; not used.'],
 '1864_California': ['Includes a "Soldiers" row (not a county). Counted in the sum check.'],
 '1864_Michigan': ['Includes a "Soldiers" row (not a county).', '16 counties are footnoted "Not included in official canvass" (see list) - so county sums exceed the table total.', 'The table total row (85,352 / 67,370) differs from results-1864.json (79,149 / 68,513) by a lot; the source page and the JSON disagree. Not resolved here.'],
 '1864_Wisconsin': ['Includes a "Soldiers" row (counted soldier vote only; footnote says rejected soldier vote was 2,477 Lincoln / 584 McClellan).', 'Several rows\' totals include Scattering votes not shown as a column (Door 66, Dunn 131, St. Croix 218, Oconto 2, Ozaukee 1), so the `total` exceeds rep+dem there; `other` left blank.', 'Table total row excludes Ashland/Eau Claire (late; the total-row footnote says "Adams and Eau Claire"), Kewaunee (rejected) and rejected soldier votes; results-1864.json (83,458 / 65,884) is higher than both.'],
 '1860_Michigan': ['Several rows\' totals include Scattering votes not shown as a column (Berrien 6, Branch 12, Eaton 6, Genesee 30, Gratiot 11, Hillsdale 8, Macomb 25, Monroe 36, Saginaw 18, St. Clair 5), so `total` > sum of candidates; `other` left blank.', 'Table total row gives Bell 405, but its own footnote says county results add up to 415.'],
 '1860_Wisconsin': ['Some rows\' totals include Scattering votes not shown as a column (Brown 10, Jefferson 7, Racine 41); `other` left blank.'],
 '1860_Illinois': ['Gerrit Smith (Radical Abolitionist) column stored under `other`.', 'Table total row (172,161 / 160,215) is higher than results-1860.json (171,106 / 158,264); county sums equal the table total exactly.', '15 rows where the total column differs slightly from the sum of candidate columns (kept as written).'],
 '1860_California': ['Scattering/write-in column stored under `other`.'],
 '1864_California_extra': [],
 '1860_Iowa_extra': [],
}
MANUAL['1864_California'].append('Scattering/write-in column stored under `other`.')
MANUAL['1860_Iowa'].append('Wright County votes come from Burnham (no vote in manuscript returns), per footnote.')
NE = {'Connecticut', 'Maine', 'Massachusetts', 'New Hampshire', 'Rhode Island', 'Vermont'}

def fmt(n): return '' if n is None else f'{n:,}'
rows_out = []; md = []
md.append('# County-level presidential results, 1860 and 1864 (from English Wikipedia)\n')
md.append('Source: per-state articles "<year> United States presidential election in <State>", fetched via the MediaWiki parse API (Oct 2026). Only the "Results by county/parish" wikitable was used. Values are copied as written (footnote markers stripped); nothing is imputed. Blank = column not in the table, or "-" in the table.\n')
md.append('Columns: rep=Lincoln, dem=Douglas (1860) / McClellan (1864), sd=Breckinridge, cu=Bell, fusion=anti-Lincoln fusion ticket (NJ, NY, RI, PA 1860), other=scattering/other/combined columns, total=table\'s own "Total votes cast" column (can include scattering not otherwise shown).\n')
md.append('Sum check: "diff" = county sum minus reference total, as % of the reference total-vote count. **FLAG** if total-vote diff or any single candidate diff exceeds 1% of the state total.\n')
summary = []
for name, e in parsed.items():
    y = int(name[:4]); st = name[5:].replace('_', ' ')
    src = 'https://en.wikipedia.org/wiki/' + e['title'].replace(' ', '_')
    sec = [f'\n## {y} {st}\n', f'Page: {src}\n']
    if not e['tables']:
        sec.append('- **NOT FOUND**: page has no county-level table (only statewide results).')
        summary.append((y, st, '**not found**', 0, ' | ')); md += sec; continue
    t = e['tables'][0]
    totrow = None; recs = []; empty = []; unoff = []; rowmis = []
    for r in t['rows']:
        c = r['county']
        if re.match(r'^(total|totals)\b', c, re.I): totrow = r; continue
        op = [x for x in r['other_parts'] if x is not None]
        rec = {k: r.get(k) for k in KEYS if k != 'other'}
        rec['other'] = sum(op) if op else None
        rec['total'] = r.get('total'); rec['county'] = c; rec['notes'] = r.get('notes', [])
        assert not any(isinstance(v, str) and v.startswith('BAD') for v in rec.values()), (name, rec)
        if all(rec[k] is None for k in KEYS + ['total']): empty.append(c); continue
        if any(UNOFFICIAL.search(n) for n in rec['notes']): unoff.append(c)
        cs = sum(rec[k] or 0 for k in KEYS)
        if rec['total'] is not None and cs != rec['total']: rowmis.append((c, cs, rec['total']))
        recs.append(rec)
    for r in recs:
        rows_out.append({'year': y, 'state': st, 'county': r['county'], **{k: '' if r[k] is None else r[k] for k in KEYS}, 'total': '' if r['total'] is None else r['total'], 'source_page': src})
    present = [k for k in KEYS if any(r[k] is not None for r in recs)]
    def sums(rs): return {k: sum(r[k] or 0 for r in rs) for k in present + ['total']}
    sa = sums(recs); so = sums([r for r in recs if r['county'] not in unoff])
    soldiers = [r['county'] for r in recs if re.search(r'soldier', r['county'], re.I)]
    sec.append(f'- **FOUND**: heading "{t["heading"]}"; {len(recs)} rows written' + (f' (incl. non-county row(s): {", ".join(soldiers)})' if soldiers else '') + f'; candidate columns: {", ".join(present)}.')
    if st in NE: sec.append('- New England: table is by **county** (not by town), so no aggregation was needed.')
    ref = None; reflabel = None
    if totrow:
        op = [x for x in totrow['other_parts'] if x is not None]
        ref = {k: totrow.get(k) for k in KEYS if k != 'other'}; ref['other'] = sum(op) if op else None; ref['total'] = totrow.get('total')
        reflabel = 'table total row'
    jt = res[y].get(st, {})
    jtot = sum(v for k, v in jt.items() if k in ('rep', 'dem', 'sd', 'cu') and isinstance(v, int))
    sec.append('')
    sec.append('| | ' + ' | '.join(present + ['total']) + ' |')
    sec.append('|---' * (len(present) + 2) + '|')
    sec.append('| county sum (all rows) | ' + ' | '.join(fmt(sa[k]) for k in present + ['total']) + ' |')
    if unoff: sec.append('| county sum excl. late/rejected rows | ' + ' | '.join(fmt(so[k]) for k in present + ['total']) + ' |')
    if ref: sec.append('| table total row | ' + ' | '.join(fmt(ref.get(k)) for k in present + ['total']) + ' |')
    sec.append('| results-%d.json | ' % y + ' | '.join(fmt(jt.get(k)) if k in jt else '' for k in present) + f' | {fmt(jtot)} (rep+dem+sd+cu) |')
    sec.append('')
    # sanity check vs table total (preferred) else json
    def check(s, refd, label):
        reft = refd.get('total') or sum(refd.get(k) or 0 for k in present)
        st_sum = s['total'] if refd.get('total') else sum(s[k] for k in present)
        worst = []
        d_tot = st_sum - reft
        msgs = [f'total {d_tot:+,} ({100*d_tot/reft:+.2f}%)']
        flag = abs(d_tot) > 0.01 * reft
        for k in present:
            if refd.get(k) is None: continue
            dk = s[k] - refd[k]
            if dk: msgs.append(f'{k} {dk:+,} ({100*dk/reft:+.2f}% of state total)')
            if abs(dk) > 0.01 * reft: flag = True
        return flag, f'- vs {label}: ' + '; '.join(msgs) + (' -> **FLAG: mismatch > 1%**' if flag else ' -> OK (within 1%)')
    tstat = 'no total row'; jstat = 'n/a'
    if ref:
        f1, m1 = check(sa, ref, 'table total row (all rows)'); sec.append(m1)
        tstat = '**FLAG**' if f1 else 'ok'
        if unoff:
            f2, m2 = check(so, ref, 'table total row (excl. late/rejected rows)'); sec.append(m2)
            tstat = ('**FLAG** (all rows); ' + ('ok' if not f2 else '**FLAG**') + ' excl. late/rejected rows') if f1 else 'ok'
    jref = {k: jt[k] for k in ('rep', 'dem', 'sd', 'cu') if isinstance(jt.get(k), int) and k in present}
    if jref:
        jref['total'] = None
        s_use = so if unoff else sa
        tmp = {k: jref[k] for k in jref if k != 'total'}
        reft = jtot
        msgs = []; flag = False
        for k, v in tmp.items():
            dk = s_use[k] - v
            if dk: msgs.append(f'{k} {dk:+,} ({100*dk/reft:+.2f}%)')
            if abs(dk) > 0.01 * reft: flag = True
        sec.append(f'- vs results-{y}.json (matching candidate keys only{", excl. late/rejected rows" if unoff else ""}): ' + ('; '.join(msgs) if msgs else 'exact match') + (' -> **FLAG: mismatch > 1%**' if flag else ' -> OK (within 1%)'))
        jstat = '**FLAG**' if flag else 'ok'
    else:
        jstat = 'not comparable (fusion / no matching keys)' if not jref else jstat
    odd = list(MANUAL.get(name, []))
    if unoff: odd.append('Rows footnoted as late / not in official canvass / rejected (included in CSV): ' + ', '.join(unoff) + '.')
    if empty: odd.append('Rows with no data ("-") omitted from CSV: ' + ', '.join(empty) + '.')
    if rowmis and name not in ('1860_Michigan', '1860_Wisconsin', '1864_Wisconsin', '1864_Minnesota', '1860_Tennessee', '1860_Illinois'):
        odd.append('Rows where the table total column != sum of candidate columns (kept as written): ' + '; '.join(f'{c} (sum {a:,} vs {b:,})' for c, a, b in rowmis) + '.')
    other_notes = sorted({n for r in recs for n in r['notes'] if not UNOFFICIAL.search(n) and not re.search(r'margin|Scattering|Includes Hamilton|included with|counted with|Cheatham|Retrieved|Tribune|Burnham', n, re.I)})
    for n in other_notes: odd.append('Table footnote: ' + n)
    if odd: sec.append('- Oddities:'); sec += ['  - ' + o for o in odd]
    md += sec
    summary.append((y, st, 'found', len(recs), tstat + ' | ' + jstat))
with open(out_csv, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['year', 'state', 'county'] + KEYS + ['total', 'source_page'])
    w.writeheader(); w.writerows(rows_out)
head = ['\n## Summary\n', '| year | state | status | rows | sum vs table total row | sum vs results-json |', '|---|---|---|---|---|---|']
head += [f'| {y} | {s} | {stt} | {n or ""} | {fl} |' for y, s, stt, n, fl in summary]
i = 4
md = md[:i] + head + md[i:]
open(out_md, 'w').write('\n'.join(md) + '\n')
print(len(rows_out), 'rows')
for s in summary: print(*s)
