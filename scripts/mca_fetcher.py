#!/usr/bin/env python3
"""
MCA portal automation: search by CIN and fetch company report / public documents.

Uses Playwright for browser automation. MCA requires CAPTCHA on search; this module
pauses for manual CAPTCHA entry (do not use --headless).

Flow:
  1. Open MCA View Public Documents, enter CIN (and ROC if needed), solve CAPTCHA.
  2. Submit search; after results, try to open document list for this company.
  3. Select category "Annual Returns and Balance Sheet eForms", select year(s).
  4. Collect document links and attempt to download PDFs to data/mca/reports/{cin}/.

Note: MCA may require login for some downloads; max 5 docs per transaction. If download
fails, screenshot and HTML are still saved under _debug/ for inspection.

Usage:
  - Run as script: python scripts/mca_fetcher.py --cin L27100MH1995PLC084207
  - Or via pipeline: python scripts/cibil_mca_pipeline.py run --input data/cibil/wilful_defaulters_50.csv
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Optional

# ROC (Registrar of Companies) can be derived from CIN: chars 3-4 are state code.
# MCA dropdown often uses ROC name; we use "Company Registration Number" + CIN.
MCA_VIEW_PUBLIC_DOCS = "https://www.mca.gov.in/content/mca/global/en/mca/document-related-services/view-public-documents-v3.html"
MCA_DOC_CATEGORIES = "https://www.mca.gov.in/content/mca/global/en/mca/document-related-services/view-public-documents-v3/document-categories.html"

# Default rate limit: ~100-150 requests/hour per plan.
DEFAULT_DELAY_SECONDS = 30


def cin_to_roc_hint(cin: str) -> str:
    """
    CIN format: [L/U][0-9]{2}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}.
    Characters at index 2-3 (0-based) are often used for ROC/state.
    Return a hint for ROC dropdown; MCA may still require exact ROC name.
    """
    cin = (cin or "").strip().upper()
    if len(cin) < 4:
        return ""
    return cin[2:4]


def run_mca_fetch_with_playwright(
    cin: str,
    output_dir: Path,
    *,
    headless: bool = False,
    delay_after_search: float = DEFAULT_DELAY_SECONDS,
    document_category: str = "5",  # "Annual Returns and Balance Sheet eForms"
) -> dict:
    """
    Use Playwright to open MCA, search by CIN, and fetch document list.
    CAPTCHA is handled by pausing for manual entry unless a solver is provided.

    Returns a dict with keys: success, message, documents_found, saved_paths.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "success": False,
            "message": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "documents_found": 0,
            "saved_paths": [],
        }

    cin = cin.strip().upper()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result: dict = {"success": False, "message": "", "documents_found": 0, "saved_paths": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1) Open View Public Documents
            page.goto(MCA_VIEW_PUBLIC_DOCS, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            # 2) Find search form: Company Registration Number and ROC (or State).
            # Page structure may use IDs/names; we use placeholder selectors - adjust after inspecting live page.
            crn_selector = 'input[name*="registration"], input[id*="registration"], input[placeholder*="Registration"], input[placeholder*="CIN"]'
            crn = page.query_selector(crn_selector)
            if crn:
                crn.fill(cin)
            else:
                # Fallback: try first visible text input that looks like registration number
                inputs = page.query_selector_all('input[type="text"]')
                for inp in inputs:
                    if inp.is_visible():
                        inp.fill(cin)
                        break

            # 3) ROC: MCA often requires selecting ROC. CIN chars 3-4 can hint state/ROC.
            roc_hint = cin_to_roc_hint(cin)
            # Try to select ROC dropdown if present
            select_roc = page.query_selector('select[name*="roc"], select[id*="roc"], select[name*="ROC"]')
            if select_roc and roc_hint:
                try:
                    select_roc.select_option(label=re.compile(roc_hint, re.I))
                except Exception:
                    pass

            # 4) CAPTCHA: wait for user to solve if not headless
            if not headless:
                print("\n>>> Solve CAPTCHA in the browser, then press Enter here to continue...")
                input()

            # 5) Submit search
            submit = page.query_selector('input[type="submit"], button[type="submit"], input[value*="Search"], button:has-text("Search")')
            if submit:
                submit.click()
            else:
                result["message"] = "Could not find search submit button on MCA page"
                return result

            time.sleep(min(5, delay_after_search))

            safe_cin = re.sub(r"[^\w\-]", "_", cin)
            company_dir = output_dir / safe_cin
            company_dir.mkdir(parents=True, exist_ok=True)
            debug_dir = output_dir / "_debug"
            debug_dir.mkdir(exist_ok=True)

            body_text = page.inner_text("body")
            if "no result" in body_text.lower() or "not found" in body_text.lower():
                result["message"] = "No company/document found for this CIN"
                page.screenshot(path=debug_dir / f"{safe_cin}_after_search.png")
                with open(debug_dir / f"{safe_cin}_after_search.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                return result

            result["success"] = True

            # 6) Look for direct PDF links on the result page; click each to trigger download
            saved_paths: list[str] = []
            pdf_links = page.query_selector_all('a[href*=".pdf"], a[href*=".PDF"]')
            for i, link in enumerate(pdf_links[:10]):
                try:
                    with page.expect_download(timeout=20000) as download_info:
                        link.click()
                    download = download_info.value
                    fname = download.suggested_filename or f"doc_{i+1}.pdf"
                    dest = company_dir / re.sub(r'[^\w\-.]', '_', fname)
                    download.save_as(dest)
                    saved_paths.append(str(dest))
                    result["documents_found"] += 1
                    time.sleep(1)
                    page.go_back()
                    time.sleep(1)
                except Exception:
                    try:
                        page.go_back()
                    except Exception:
                        pass

            result["saved_paths"] = saved_paths
            if saved_paths:
                result["message"] = f"Downloaded {len(saved_paths)} file(s) to {company_dir}"
            else:
                # No PDF links on first page: try to open document categories (user may need to complete flow manually)
                try:
                    cat_link = page.query_selector('a[href*="document-categories"], a:has-text("Annual"), a:has-text("Balance Sheet"), a:has-text("Document")')
                    if cat_link:
                        cat_link.click()
                        time.sleep(3)
                        page.screenshot(path=company_dir / "after_category.png")
                        result["message"] = "Search OK; opened document section. Check data/mca/reports/ for screenshot; MCA may require login to download."
                    else:
                        result["message"] = "Search OK; no PDF links on this page. Check _debug/ for screenshot; you may need to select document category and year manually on MCA."
                except Exception:
                    result["message"] = "Search OK. Check _debug/ for screenshot; MCA may require login for document download."

            page.screenshot(path=debug_dir / f"{safe_cin}_after_search.png")
            with open(debug_dir / f"{safe_cin}_after_search.html", "w", encoding="utf-8") as f:
                f.write(page.content())

        except Exception as e:
            result["message"] = str(e)
        finally:
            browser.close()

    return result


def mca_fetch_report(
    cin: str,
    output_dir: Optional[Path] = None,
    *,
    headless: bool = False,
) -> dict:
    """
    Fetch MCA report for one CIN. Wrapper around run_mca_fetch_with_playwright.

    output_dir: default data/mca/reports
    """
    base = Path(__file__).resolve().parent.parent
    output_dir = output_dir or (base / "data" / "mca" / "reports")
    return run_mca_fetch_with_playwright(cin, output_dir, headless=headless)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch MCA report for a company by CIN")
    ap.add_argument("--cin", required=True, help="Corporate Identification Number (21 chars)")
    ap.add_argument("--output-dir", type=Path, default=None, help="Directory to save reports (default: data/mca/reports)")
    ap.add_argument("--headless", action="store_true", help="Run browser headless (CAPTCHA will fail)")
    args = ap.parse_args()

    result = mca_fetch_report(args.cin, args.output_dir, headless=args.headless)
    print("Success:", result["success"])
    print("Message:", result["message"])
    print("Documents found:", result["documents_found"])


if __name__ == "__main__":
    main()
