import sys,sqlite3;sys.path.insert(0,'/workspace/deepagents/experiments/triage_os')
import capstack
con=sqlite3.connect('/workspace/triage_os_data/triage.db'); capstack.ensure(con); con.execute("delete from cap_structure")
U={"nfe":"https://www.sec.gov/Archives/edgar/data/1749723/000174972326000106/nfe-20260630.htm",
 "echostar":"https://www.sec.gov/Archives/edgar/data/1415404/000110465926089370/sats-20260630x10q.htm",
 "trinseo":"https://www.sec.gov/Archives/edgar/data/1519061/000110465926091910/tse-20260630x10q.htm",
 "qvc":"https://www.sec.gov/Archives/edgar/data/1254699/000125469926000018/qvc-20260630.htm"}
# (key, issuer, tranche, lien, amount_usd_m, coupon, maturity, fv_pct_of_carrying)
R=[("nfe","New Fortress Energy","Senior Secured Notes due Nov 2029","senior secured",2727.3,None,"2029-11",None),
("nfe","New Fortress Energy","Senior Secured Notes due Sep 2026","senior secured",510.8,"6.50%","2026-09",None),
("nfe","New Fortress Energy","Senior Secured Notes due Mar 2029","senior secured",234.6,"8.75%","2029-03",None),
("nfe","New Fortress Energy","Revolving Facility","senior secured",660.4,None,None,None),
("nfe","New Fortress Energy","Term Loan A due Jul 2027","senior secured",285.9,None,"2027-07",None),
("nfe","New Fortress Energy","Term Loan B due Oct 2028","senior secured",1183.7,None,"2028-10",None),
("nfe","New Fortress Energy","Vessel/Tugboat/Turbine sale-leaseback financings","asset-level",962.5,None,"2036-2042",None),
("nfe","New Fortress Energy","PortoCem Debentures due Sep 2040 (Brazil)","asset-level",937.7,None,"2040-09",None),
("nfe","New Fortress Energy","New Brazil Notes due Nov 2029","asset-level",876.1,None,"2029-11",None),
("nfe","New Fortress Energy","BNDES Term Loan due Oct 2045","asset-level",380.2,None,"2045-10",None),
("nfe","New Fortress Energy","EB-5 Loan due Jul 2028","asset-level",99.2,None,"2028-07",None),
("nfe","New Fortress Energy","TOTAL debt (current portion $6,727.2M)","total",8858.4,None,None,None),
("echostar","EchoStar","5 1/4% Senior Secured Notes due 2026 (HSSC)","senior secured",627.3,"5.25%","2026",85.6),
("echostar","EchoStar","6 5/8% Senior Notes due 2026 (HSSC)","unsecured",750.0,"6.625%","2026",58.0),
("echostar","EchoStar","3 3/8% Convertible Notes due 2026 (DISH)","unsecured",45.2,"3.375%","2026",98.0),
("echostar","EchoStar","11 3/4% Senior Secured Notes due 2027 (DISH)","senior secured",3500.0,"11.75%","2027",102.8),
("echostar","EchoStar","DISH 2021 Intercompany Loan 2028 tranche","intercompany",2844.4,None,"2028",100.0),
("echostar","EchoStar","10 3/4% Senior Secured Notes due 2029 (ECHO)","senior secured",5506.0,"10.75%","2029",108.1),
("echostar","EchoStar","3 7/8% Convertible Secured Notes due 2030 (ECHO)","senior secured (convertible)",1942.6,"3.875%","2030",311.2),
("echostar","EchoStar","6 3/4% Senior Secured Notes due 2030 (ECHO)","senior secured",2372.7,"6.75%","2030",101.7),
("echostar","EchoStar","TOTAL principal subtotal","total",17630.1,None,None,124.3),
("trinseo","Trinseo","OpCo DIP Facility","DIP super-priority",279.9,"12.758% eff.","2027-05",None),
("trinseo","Trinseo","Super HoldCo DIP Facility","DIP super-priority",163.3,"6.008% eff.","2027-05",None),
("trinseo","Trinseo","2026 AR Facility","DIP / receivables",144.7,"various","2027-05",None),
("trinseo","Trinseo","2028 Refinance Term Loans (prepetition)","senior secured",1161.2,"12.169% eff.","2028-05",None),
("trinseo","Trinseo","2028 Term Loan B (prepetition)","senior secured",716.3,"7.939% eff.","2028-05",None),
("trinseo","Trinseo","OpCo Super-Priority Revolver","super-priority",164.1,"various","2028-02",None),
("trinseo","Trinseo","2029 Refinance Senior Notes","senior secured",391.0,"7.625%","2029-05",None),
("trinseo","Trinseo","TOTAL (LSTC $2,432.6M)","total",3024.1,None,None,None),
("qvc","QVC Inc","Senior secured credit facility","senior secured",2900,None,None,None),
("qvc","QVC Inc","4.750% Senior Secured Notes due 2027","senior secured",44,"4.75%","2027",None),
("qvc","QVC Inc","4.375% Senior Secured Notes due 2028","senior secured",72,"4.375%","2028",None),
("qvc","QVC Inc","6.875% Senior Secured Notes due 2029","senior secured",605,"6.875%","2029",None),
("qvc","QVC Inc","5.45% Senior Secured Notes due 2034","senior secured",400,"5.45%","2034",None),
("qvc","QVC Inc","5.95% Senior Secured Notes due 2043","senior secured",300,"5.95%","2043",None),
("qvc","QVC Inc","6.375% Senior Secured Notes due 2067","senior secured",225,"6.375%","2067",None),
("qvc","QVC Inc","6.25% Senior Secured Notes due 2068","senior secured",500,"6.25%","2068",None),
("qvc","QVC Inc","TOTAL (all reclassified to LSTC $5,046M)","total",5047,None,None,None)]
for k,iss,t,l,a,c,m,f in R:
  con.execute("insert or replace into cap_structure values (?,?,?,?,?,?,?,?,?,?,?,?,'unverified')",(k,iss,t,l,a*1e6,"carrying/par",c,m,f,"2026-06-30","10-Q debt footnote, 30 Jun 2026",U[k]))
for k,like in [("medallia","%medallia%"),("convey","%convey health%"),("telepacific","%telepacific%"),("barracuda","barracuda parent%"),
 ("medsol","%medical solutions%"),("scaledagile","%scaled agile%"),("loparex","%loparex%"),("kaseya","%kaseya%"),
 ("cornerstone","%cornerstone ondemand%"),("symplr","%symplr%"),("peraton","%peraton%"),("solera","%solera%")]:
  print(k,capstack.store_private(con,k,like))
con.commit(); print(con.execute("select count(*) from cap_structure").fetchone())
