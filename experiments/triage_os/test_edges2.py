import sqlite3, tempfile, unittest, edges2 as e
class T(unittest.TestCase):
    def test_strict(self):
        self.assertFalse(e.strict("investment")); self.assertFalse(e.strict("alta")); self.assertTrue(e.strict("cornerstone ondemand")); self.assertTrue(e.strict("echostar"))
    def test_tight(self):
        self.assertEqual(e.tight("Blackstone Inc."), "blackstone"); self.assertNotEqual(e.tight("4612 Group, LLC"), e.tight("LLC Group 99"))
    def test_spv(self):
        self.assertEqual(e.spv_tags("Loparex Midco B.V."), ["bv", "midco"]); self.assertIn("bidco", e.spv_tags("Lacker Bidco Limited"))
    def test_pension_edge_ein_join(self):
        db = tempfile.mktemp(); c = sqlite3.connect(db)
        c.execute("create table watchlist(nkey,name,source,reason,source_url,cik,ein,inc_state)"); c.execute("insert into watchlist values('acme','Acme Inc','signal','x','u','1','123','DE')")
        c.execute("create table pension_sb(ack_id,ein,sponsor,nkey,plan,plan_year,funding_target,actuarial_assets,shortfall,funded_pct,at_risk,participants,source_url)")
        c.execute("insert into pension_sb values('A1','123','ACME','acme','Acme Plan','2024',100e6,80e6,20e6,80,'1',10,'u')")
        for t, cols in [("usaspending_awards", 8), ("faa_aircraft", 15), ("epa_cases", 9), ("gleif_l2", 12), ("icij_entities", 9), ("uk_corporate_psc", 11), ("sanctions", 8), ("f13_holdings", 11), ("adv_funds", 12)]:
            c.execute(f"create table {t}({','.join('c%d'%i for i in range(cols))})")
        c.execute("drop table usaspending_awards"); c.execute("create table usaspending_awards(nkey,query,recipient,award_id,amount,agency,end_date,source_url)")
        for t, cols in [("faa_aircraft", "n_number,serial,owner,nkey,registrant_type,mfr,model,seats,year,state,country,status,cert_date,other_names,source_url"), ("epa_cases", "case_number,defendant,nkey,case_name,fiscal_year,status,outcome,penalty_and_cost_usd,source_url"),
                        ("gleif_l2", "nkey,query,lei,legal_name,jurisdiction,direct_parent_lei,direct_parent,direct_parent_jur,ultimate_parent_lei,ultimate_parent,ultimate_parent_jur,source_url"), ("icij_entities", "node_id,name,nkey,jurisdiction,countries,incorporation_date,status,source,service_provider"),
                        ("uk_corporate_psc", "company_number,psc_name,nkey,kind,legal_form,registered_in,reg_number,control,notified_on,ceased_on,source_url"), ("sanctions", "list,uid,name,nkey,type,program,country,source_url"),
                        ("f13_holdings", "accession,filer,issuer_key,issuer,cusip,value,shares,putcall,period,source_url,status"), ("adv_funds", "filing_id,reference_id,adviser,adviser_nkey,crd,fund,fund_id,fund_type,country,gav,filed,source_url")]:
            c.execute(f"drop table {t}"); c.execute(f"create table {t}({cols})")
        c.commit(); r = e.build(db)
        self.assertEqual(r, {"pension_underfunding": 1})
if __name__ == "__main__": unittest.main()
