# MCA Data: What’s Paid and Free Workarounds

## How MCA “View Public Documents” works

| Action | Cost | Notes |
|--------|------|--------|
| **View** documents on screen | **Free** | No login. Search by CIN → select category (e.g. Annual Returns and Balance Sheet) → view in browser. |
| **Download** documents (PDF etc.) | **Paid** | ₹100 per company/LLP; up to 5 documents per company per transaction; 3-hour window to download after payment; files available in “My Workspace” for 7 days. Requires MCA21 login. |

So the portal itself is not “subscription paid,” but **downloading** AOC-4/financials is **₹100 per company**. For 50+50 companies that’s ₹10,000+ if you download everything from MCA.

---

## Workarounds (free or cheaper)

### 1. **BSE / NSE – listed companies (best free option)**

Many wilful defaulters and most non-defaulters in our list are or were **BSE/NSE listed**. For listed companies, **annual reports and financial statements are published for free** on the exchanges.

- **BSE:** [bseindia.com](https://www.bseindia.com) → Corporate filings / company search → select company → Annual Reports / financial statements.  
- **NSE:** [nseindia.com](https://www.nseindia.com) → Company filings / Annual Reports (e.g. [Corporate Filings - Annual Reports](https://www.nseindia.com/companies-listing/corporate-filings-annual-reports)).

**Practical approach:**  
- Mark in your CSV which companies are **listed** (BSE/NSE symbol if known).  
- For those, **skip MCA download** and get the same (or better) annual report PDFs from BSE/NSE.  
- You can do this manually (search by company name or symbol) or, later, automate via BSE/NSE company pages (respect robots.txt and rate limits).

**Coverage:** A large share of the 50 wilful defaulters (e.g. Gitanjali Gems, ABG Shipyard, Deccan Chronicle, Kingfisher, HDIL, etc.) were listed; non-defaulters (Titan, L&T, etc.) are almost all listed. So a big part of the dataset can be covered **without paying MCA**.

---

### 2. **Company website – Investor Relations**

Listed (and some unlisted) companies host **annual reports** on their own site under “Investor Relations” or “Annual Report.”  
- Free.  
- Quality is same as or better than AOC-4 (often the full annual report).  
- Downside: need to find the right URL per company; some defaulter sites may be down or removed.

Use this to supplement BSE/NSE when a company is listed but a particular year is missing on the exchange.

---

### 3. **Screener.in / Moneycontrol – financial metrics (not full AOC-4)**

- **Screener.in:** Free access to **financial metrics** for 5000+ listed companies (P&amp;L, balance sheet ratios, ROCE, debt, etc.). Good for **feature engineering** (ratios, growth) if you don’t need the full PDF.  
- **Moneycontrol:** Similar – company financials and annual report links for listed companies.

These don’t replace AOC-4 PDFs but can give you **structured numbers** for listed names without paying MCA. Use when you need ratios/numbers rather than the exact filed form.

---

### 4. **Use MCA only for unlisted companies**

- **Listed:** Use BSE/NSE (and optionally company IR) → **free**.  
- **Unlisted:** Only option for *official* AOC-4 is MCA (view free, **download ₹100/company**) or a third-party that uses MCA (e.g. CorpData, ~₹130/company).

So the **workaround** is: **don’t pay MCA for listed companies**; use BSE/NSE (and IR) for them. Pay (or use a bulk service) only for the **unlisted** subset.

---

### 5. **“View only” on MCA (no download)**

You can **view** documents on MCA without paying. That doesn’t give you a PDF for your pipeline, but you can:  
- Manually note key numbers for a few companies, or  
- Use a print-to-PDF / screenshot approach for personal use (check MCA terms of use; avoid bulk scraping of the view stream).

Not ideal for 50+50 companies; better to rely on BSE/NSE for listed.

---

## Suggested pipeline change

1. **Classify companies** in your CSV as **listed** (BSE/NSE) vs **unlisted** (e.g. add a column `listed_exchange` or `is_listed` and, if known, `bse_symbol` / `nse_symbol`).  
2. **For listed:**  
   - Prefer **BSE/NSE** (and company IR) for annual report / financial PDFs.  
   - Optionally use **Screener.in** (or similar) for structured financials.  
3. **For unlisted:**  
   - Either pay MCA (₹100/company) for AOC-4 download, or use a bulk provider (e.g. CorpData), or leave unlisted out if your analysis can work with listed-only.  
4. **Automation:**  
   - Current `mca_fetcher.py` can remain for unlisted or when you choose to pay MCA.  
   - A separate **BSE/NSE fetcher** (by company name or symbol) can be added to download annual reports for listed companies so most of the data is **free**.

---

## Summary

| Source | Cost | Best for |
|--------|------|----------|
| **BSE / NSE** | Free | Listed companies – annual reports &amp; financials |
| **Company IR** | Free | Same, when exchange is missing a year |
| **Screener.in / Moneycontrol** | Free | Listed – financial metrics / ratios, not full AOC-4 |
| **MCA view** | Free | View only; no bulk PDFs |
| **MCA download** | ₹100/company | Unlisted companies – official AOC-4 |
| **CorpData etc.** | ~₹130/company | Bulk MCA docs if you prefer not to use MCA directly |

**Bottom line:** Your main workaround is **BSE/NSE (and company IR) for all listed companies**; use MCA (or a paid bulk service) only for **unlisted** ones.
