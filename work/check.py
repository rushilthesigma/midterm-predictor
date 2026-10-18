import json, sys
SF = {"01":"Alabama","02":"Alaska","04":"Arizona","05":"Arkansas","06":"California","08":"Colorado","09":"Connecticut","10":"Delaware","11":"District of Columbia","12":"Florida","13":"Georgia","15":"Hawaii","16":"Idaho","17":"Illinois","18":"Indiana","19":"Iowa","20":"Kansas","21":"Kentucky","22":"Louisiana","23":"Maine","24":"Maryland","25":"Massachusetts","26":"Michigan","27":"Minnesota","28":"Mississippi","29":"Missouri","30":"Montana","31":"Nebraska","32":"Nevada","33":"New Hampshire","34":"New Jersey","35":"New Mexico","36":"New York","37":"North Carolina","38":"North Dakota","39":"Ohio","40":"Oklahoma","41":"Oregon","42":"Pennsylvania","44":"Rhode Island","45":"South Carolina","46":"South Dakota","47":"Tennessee","48":"Texas","49":"Utah","50":"Vermont","51":"Virginia","53":"Washington","54":"West Virginia","55":"Wisconsin","56":"Wyoming"}
def check(year, counties=None, tol=0.005):
    st = json.load(open(f"../results-{year}.json"))["states"]
    c = counties if counties is not None else json.load(open(f"../counties-{year}.json"))["counties"]
    sums = {}
    for f,(d,r) in c.items():
        s = sums.setdefault(SF[f[:2]], [0,0]); s[0]+=d; s[1]+=r
    bad = []
    for name,(d,r) in sums.items():
        t = st[name]
        for k,v in (("dem",d),("rep",r)):
            if t[k] == 0 or abs(v/t[k]-1) > tol: bad.append(f"{name} {k} {v} vs {t[k]} ({(v/t[k]-1)*100 if t[k] else 0:+.2f}%)")
    return bad
if __name__ == "__main__":
    for y in sys.argv[1:]:
        b = check(int(y)); print(y, len(b)); [print("  ",x) for x in b]
