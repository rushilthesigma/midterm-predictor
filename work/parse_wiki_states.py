# Parses the "Results by state" table from a Wikipedia presidential-election article (raw wikitext)
# into {state: {candidate surname: votes}} (rows: state, [state electors,] then # / % / electors per candidate) for the candidates in the table header
import re, sys, json

def parse(path):
    text = open(path).read()
    sec = text[re.search(r"===\s*Results by state\s*===", text).start():]
    table = sec[sec.index('{| class="wikitable sortable'):]
    table = table[:table.index("\n|}")]
    rows = re.split(r"\n\|-[^\n]*", table)
    cands = re.findall(r'colspan="?3"?[^|\n]*\|\s*([^<\n]+?)\s*<br', table)
    surnames = [c.split("/")[0].split()[-1] for c in cands]
    out = {}
    for row in rows:
        cells = [re.sub(r'^[^|\[]*?style="[^"]*"\s*\|', "", l[1:]).strip()
                 for l in row.strip().split("\n") if l.startswith("|") and not l.startswith("|}")]
        if len(cells) < 2:
            continue
        m = re.search(r"\[\[[^|\]]*\|([^\]]+)\]\]", cells[0]) or re.search(r"\[\[([^\]]+)\]\]", cells[0])
        name = (m.group(1) if m else cells[0]).strip()
        # Some tables have no per-state electoral-vote column before the candidates
        rest = cells[1:] if "," in cells[1] else cells[2:]
        if len(rest) < 3 * len(surnames):
            continue
        num = lambda s: int(re.sub(r"[^\d]", "", s) or 0)
        out[name] = {s: num(rest[3 * i]) for i, s in enumerate(surnames)}
    return surnames, out

if __name__ == "__main__":
    s, out = parse(sys.argv[1])
    print(s, len(out)); print(json.dumps(out)[:600])
