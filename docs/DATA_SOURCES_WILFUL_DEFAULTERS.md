# Where to Get Wilful Defaulter Data

## Summary

| Source | What you get | Company-level list? | How to access |
|--------|--------------|----------------------|---------------|
| **CIBIL Suit Filed** | Suit-filed & wilful defaulter data | Yes (search/view by period) | https://suit.cibil.com |
| **RBI (public)** | Scheme document only | No | rbi.org.in/rbidefaulterslist → 63417.pdf |
| **RBI via RTI** | One-off list (e.g. 30 names disclosed 2019) | Yes | File RTI to RBI |
| **dataful.in** | Aggregated counts/amounts from CIBIL | No | Dataset 20588 (summary only) |

---

## 1. CIBIL Suit Filed Database (primary public source)

**URL:** https://suit.cibil.com

RBI entrusted **TransUnion CIBIL** with publishing suit-filed and wilful defaulter lists (from 2003/2004). This is the **main public place** for the actual lists.

**Available on the site:**
- **Suit Filed Accounts – Defaulters Rs 1 crore and above**  
  Select period (month-end dates from 2002 onward) → view:
  - Summary – Credit Institutions Wise List  
  - Summary – State/Union Territory  
- **Suit Filed Accounts – Wilful Defaulters Rs 25 lakh and above**  
  Same: select period → Credit Institutions Wise List or State/UT summary.

**What you can get:**  
Search by period and see summaries by bank/institution and by state. The site may show or let you drill down to **company/borrower names**; check the “Search” and summary views on the site. There is no clear mention of a single “download all companies” PDF/Excel; you may need to use the web interface (and possibly scrape or copy) if you want a company-level list.

**Use for Fulcrum:**  
- Go to https://suit.cibil.com  
- Choose “Suit Filed Accounts – Wilful Defaulters Rs 25 lacs and above”  
- Select period(s) (e.g. 30-06-24, 31-03-24, etc.)  
- Use “Summary – Credit Institutions Wise List” and “Summary – State/Union Territory” to see what’s available; then check if company names are visible or exportable.

---

## 2. RBI (public website)

**URLs:**  
- https://www.rbi.org.in/rbidefaulterslist/index.html  
- https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=7320  

**What you get:**  
- Only the **scheme document** (what RBI’s scheme is, how data is collected and published).  
- The only PDF we get from the current page is **63417.pdf** (policy/scheme text).  
- **No** company-level wilful defaulter list is published here; RBI handed that publication over to CIBIL.

**Use for Fulcrum:**  
- Good for understanding definitions and process.  
- **Not** the source for the actual list of companies (use CIBIL Suit Filed or RTI).

---

## 3. RBI via RTI (Right to Information)

**What’s known:**  
- RBI has disclosed wilful defaulter information in response to RTI (e.g. Nov 2019: 30 wilful defaulters, ~₹50,000 crore).  
- Supreme Court had directed RBI to disclose; CIC had also asked for disclosure.

**What you can do:**  
- File an RTI application to RBI asking for the list of wilful defaulters (e.g. as on a given date, or latest).  
- You may get a one-off list (names/amounts) in whatever format RBI provides (PDF/Excel).  
- Good for a **one-time snapshot** or to supplement CIBIL; not an automated quarterly download.

**Use for Fulcrum:**  
- Optional way to get a company-level list if CIBIL doesn’t offer a convenient download.

---

## 4. dataful.in (aggregated CIBIL data)

**URL:** https://dataful.in/datasets/20588  

**What you get:**  
- Dataset: “Wilful Defaulters: Year-, Month-, and Credit Institution Type- and Name-wise Number of Wilful Financial Defaulters of Rupees 25 Lakhs and above, and the Outstanding Amount, as per Data from CIBIL”.  
- **Aggregated** counts and amounts (by year, month, institution).  
- **No** company names or CINs.

**Use for Fulcrum:**  
- Useful for sector/institution-level analysis or cross-checks, not for building the 50/150 company defaulter list.

---

## 5. News / reported lists

- **Indian Express** (and others) have reported “top 100 wilful defaulters” with names and amounts (e.g. Gitanjali Gems, ABG Shipyard, etc.), often citing RBI/CIBIL data.  
- These are **not** an official download; they are manually compiled from disclosed/RTI data.  
- You could use such articles to get a **starting list of names** and then match to MCA/CIN (e.g. for a first set of 50 companies) while you set up CIBIL or RTI for a full list.

---

## Recommended next step for Fulcrum

1. **Use CIBIL Suit Filed as the main source**  
   - Open https://suit.cibil.com  
   - Go to “Suit Filed Accounts – Wilful Defaulters Rs 25 lacs and above”  
   - Select one or more periods (e.g. latest quarter + a few past quarters)  
   - See whether the interface shows **company/borrower names** and whether you can export or copy them (or need to automate with a browser/script).

2. **If CIBIL doesn’t give a bulk download**  
   - Consider filing an **RTI to RBI** for the latest wilful defaulter list (company names and amounts, as on a specified date).  
   - Use the RTI response PDF/Excel as the “RBI/defaulter list” input to your pipeline (e.g. feed into `rbi_ingest` or a small script that expects company name + optional CIN/amount).

3. **RBI ingest script (current)**  
   - Continues to use RBI’s public page only; it will keep giving **63417.pdf** (scheme doc) until RBI adds direct links to company-level PDFs (which they currently don’t).  
   - For company-level data, rely on **CIBIL Suit Filed** (and optionally RTI), not the current RBI manifest.

Once you confirm whether suit.cibil.com shows company names and in what form (table, search, export), we can design the next step (e.g. CIBIL scraper or RTI-response parser).
