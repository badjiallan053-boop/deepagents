# GitHub / tooling survey (22 Oct 2026)

Rule: read for patterns; run nothing third-party; reimplement in our own code. Licences checked on the repo LICENSE / official page this pass.

| Project | Licence (checked) | What it unlocks | What we reimplemented |
|---|---|---|---|
| opensanctions/followthemoney | MIT ([LICENSE](https://github.com/opensanctions/followthemoney/blob/main/LICENSE)) | Entity/relationship model (Company, Ownership, Directorship, Security, Debt) for investigative graphs | `datasets.norm/tight` name keys; `edges2` typed edges with evidence URL + match-quality field (EIN > LEI > tight-name > strict-name), modelled on FtM statements |
| opensanctions/opensanctions (code) | MIT code; **data CC BY-NC 4.0** ([docs](https://www.opensanctions.org/docs/commercial/exemption/)) | Consolidated sanctions/PEP data | Not used (NC licence + PEP data = individuals). We ingest the primary lists directly: OFAC SDN + ALT, EU FSF (entities only) |
| opensanctions/yente / rigour | MIT ([opensource](https://www.opensanctions.org/docs/opensource/)) | Name matching / normalisation | Tight-name matcher with legal-form stripping; proven by the Blackstone→vessel SALINA false-positive test |
| alephdata/aleph | MIT ([LICENSE.txt](https://github.com/alephdata/aleph/blob/develop/LICENSE.txt)); sunset Dec 2025 | Cross-dataset search UI over FtM | Local app: entity graph + evidence links + badges (stdlib HTTP + SQLite, no Elasticsearch) |
| ICIJ Offshore Leaks data | ODbL (db) / CC BY-SA (contents) ([page](https://offshoreleaks.icij.org/pages/database)) | Offshore entities, intermediaries, relationships | `datasets.icij` loads entities + corporate intermediaries + their relationships only (officers/individuals excluded). Attribution: ICIJ |
| fedspendingtransparency/usaspending-api | CC0 ([LICENSE](https://github.com/fedspendingtransparency/usaspending-api/blob/master/LICENSE)) | Federal awards by recipient | `apis.usaspending` calls the public `spending_by_award` endpoint; exact normalised recipient match |
| ClearAerospace/faa-aircraft-registry | MIT ([repo](https://github.com/ClearAerospace/faa-aircraft-registry)) | MASTER/ACFTREF join | `datasets.faa` reimplements the MASTER⇄ACFTREF join; drops individual / co-owned registrants (types 1, 4, 9) |
| kismetwireless create_icao_db.py | GPL-2.0 (not reused) | Notes FAA blocks robot UAs | Pattern only: browser UA for the FAA download |
| jeffrobot494/labor-scraper | no licence file seen → not reused | 5500 sponsor fuzzy match | Our own join: Schedule SB ⇄ Form 5500 on ACK_ID, then EIN ⇄ SEC EDGAR EIN (exact identifier, no fuzzy) |
| SEC-API-io sec-edgar-mcp (docs) | commercial API | ADV 7.B.1 field map (auditors, PBs, custodians) | Field mapping used to parse the SEC's own FOIA ADV CSVs (7B1, 7B1A23, 7B1A24) |
| iamlemec/fastpat, AakaashRao/patents | (fork; licence unclear) | USPTO assignment XML parsing, conveyance "SECURITY INTEREST" | Not built: USPTO bulk/API now require an ODP API key (HTTP 401) - open gap |
