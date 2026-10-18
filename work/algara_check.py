import json, rdata, sys
sys.path.insert(0,'.')
from check import check
atlas = set(json.load(open("atlas-ids.json")))
df = rdata.read_rda("algara/pres.Rdata")["pres_elections_release"]
print(df.columns.tolist()); print(df.election_year.max())
REMAP = {"46113": "46102", "51515": "51019", "51560": "51005", "51780": "51083", "12025": "12086", "30113": "30031"}
for year in [2000,2004,2008,2012,2016,2020]:
    out={}; dropped=[]
    for row in df[df.election_year == year].itertuples():
        f=str(row.fips).zfill(5); d,r=row.democratic_raw_votes,row.republican_raw_votes
        if not d==d or not r==r or d+r<=0: continue
        f2=REMAP.get(f,f)
        if f2 not in atlas: dropped.append(f); continue
        o=out.setdefault(f2,[0,0]); o[0]+=int(d); o[1]+=int(r)
    b=check(year,out); print(year,len(out),"dropped",dropped[:20]); [print("  ",x) for x in b]
