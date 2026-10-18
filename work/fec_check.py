import pypdf,re,json,logging,sys;logging.disable(logging.CRITICAL)
AB={"AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California","CO":"Colorado","CT":"Connecticut","DE":"Delaware","DC":"District of Columbia","FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming"}
for y in map(int,sys.argv[1:]):
    r=pypdf.PdfReader(f'fec/fe{y}.pdf')
    for p in r.pages[:40]:
        t=p.extract_text()
        if "PRESIDENTIAL ELECTORAL AND POPULAR VOTE" in t.upper().replace("  "," ") and "\nAL " in t: break
    else: print(y,"table not found"); continue
    hdr=t[:400]; dem_first = hdr.find("(D)") < hdr.find("(R)")
    st=json.load(open(f"../results-{y}.json"))["states"]; n=0
    for line in t.splitlines():
        m=re.match(r"\s*([A-Z]{2})\b(.*)",line)
        if not m or m.group(1) not in AB: continue
        nums=[int(x.replace(",","")) for x in re.findall(r"\d[\d,]*",m.group(2))]
        if len(nums)<4: continue
        a,b=nums[-4],nums[-3]; d,rr=(a,b) if dem_first else (b,a); n+=1
        s=st[AB[m.group(1)]]
        if (s["dem"],s["rep"])!=(d,rr): print(y,AB[m.group(1)],"results",s["dem"],s["rep"],"FEC",d,rr)
    print(y,"states parsed",n)
