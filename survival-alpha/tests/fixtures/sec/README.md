# SEC tender-offer fixtures

Real public EDGAR submissions (full `.txt` submission files) used to test
`special_situations.py`. Graphic/PDF/ZIP/XML documents were stripped to keep
the fixtures small; text/HTML documents are unmodified. Source URL pattern:
`https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession}.txt`

| File | Issuer (CIK) | Form | Filed | Notes |
|---|---|---|---|---|
| utmd_sc_to_i_0001096906-26-001428 | Utah Medical Products (706698) | SC TO-I (+SC 13E3) | 2026-09-24 | Fixed $75.00, expires 2026-10-07, odd-lot priority with record-date ownership requirement (2026-09-21) |
| utmd_sc_to_i_a1_0001096906-26-001481 | Utah Medical Products | SC TO-I/A | 2026-09-29 | Amendment No. 1, not a results filing |
| abus_sc_to_i_0001104659-26-100002 | Arbutus Biopharma (1447028) | SC TO-I | 2026-08-24 | Modified Dutch auction US$5.00-5.75, expires 2026-09-29, odd-lot priority, no financing/minimum condition |
| abus_sc_to_i_a_prelim_0001104659-26-112115 | Arbutus Biopharma | SC TO-I/A | 2026-09-30 | Preliminary results (must NOT finalize) |
| abus_sc_to_i_a_final_0001104659-26-112579 | Arbutus Biopharma | SC TO-I/A | 2026-10-01 | Final results: 46,000,000 shares at US$5.00, ~55.6% proration |
| exfy_sc_to_i_0001476840-26-000044 | Expensify (1476840) | SC TO-I | 2026-05-13 | Modified Dutch auction $0.98-1.20, expires 2026-06-10, odd-lot priority |
| exfy_sc_to_i_a_final_0001476840-26-000063 | Expensify | SC TO-I/A | 2026-06-12 | Final results: 6,053,023 shares at $1.20 |
