# Exports Algara & Amlani's county presidential returns (Harvard Dataverse doi:10.7910/DVN/DGUMFI, CC0)
# for 1868-1956 to CSV for build_historical_counties.mjs: year,fips,county,state,dem,rep,total
import sys, warnings, rdata
warnings.filterwarnings("ignore")
df = rdata.read_rda(sys.argv[1])["pres_elections_release"]
df = df[(df.election_year >= 1868) & (df.election_year <= 1956)]
out = df[["election_year", "fips", "county_name", "state", "democratic_raw_votes", "republican_raw_votes",
          "raw_county_vote_totals"]].copy()
out.columns = ["year", "fips", "county", "state", "dem", "rep", "total"]
out["year"] = out.year.astype(int)
out.to_csv(sys.argv[2], index=False)
print(len(out), "rows")
