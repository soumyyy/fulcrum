#!/usr/bin/env python3
"""
RBI wilful defaulter ingestion helper.

Capabilities:
- Build a manifest of RBI wilful defaulter PDF links from the RBI publications page.
- Download and cache the PDFs listed in the manifest.
- Parse the downloaded PDFs into a normalized CSV for downstream processing.

Dependencies (install via pip):
    requests pandas camelot-py[cv] pdfplumber
External tools: Camelot needs Ghostscript and a Tk/Qt backend installed on the host.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import requests
from requests import Response, Session


RAW_DIR = Path("data/raw/rbi")
PROCESSED_DIR = Path("data/processed")
MANIFEST_PATH = Path("data/rbi_manifest.csv")
# RBI "Gist of RBI Schemes of Defaulter Lists" – scheme doc only (63417). Quarterly company lists may be on other pages.
DEFAULT_LISTING_URLS = [
    "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=7320",
]
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
KEYWORDS = ("wilful", "willful", "defaulter", "default")
# When no keyword match, prefer these URL path patterns (actual publication PDFs, not generic content).
PREFERRED_PDF_PATTERNS = ("/Publications/PDFs/", "PublicationReport", "rdocs/Publications/")

# Map messy header variants to normalized names.
COLUMN_ALIASES = {
    "name of the borrower": "company_name",
    "borrower name": "company_name",
    "name": "company_name",
    "cin": "cin",
    "pan": "pan",
    "name of bank": "bank_name",
    "bank name": "bank_name",
    "bank": "bank_name",
    "branch name": "branch",
    "branch": "branch",
    "state": "state",
    "amount outstanding": "amount",
    "outstanding amount": "amount",
    "amount (rs. in lakhs)": "amount",
    "amount (rs.in lacs)": "amount",
    "amount (rs. in lacs)": "amount",
    "amount": "amount",
    "date of classification": "classification_date",
    "date of npa": "classification_date",
    "date of wilful default": "classification_date",
}


@dataclass
class ManifestEntry:
    quarter: str
    url: str
    filename: str
    template_hint: str = ""


class _RbiLinkParser(HTMLParser):
    """Collects PDF links and their surrounding text."""

    def __init__(self) -> None:
        super().__init__()
        self.links: List[tuple[str, str]] = []
        self._current_href: Optional[str] = None
        self._current_text: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        href = href.strip().strip("'\"")
        if not href.lower().endswith(".pdf"):
            return
        if not href.startswith("http"):
            href = "https://rbidocs.rbi.org.in" + href if href.startswith("/") else "https://www.rbi.org.in" + ("/" + href if not href.startswith("/") else href)
        self._current_href = href
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            text = " ".join(t for t in self._current_text if t).lower()
            self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def fetch_listing_links(url: str) -> List[tuple[str, str]]:
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=60)
    resp.raise_for_status()
    parser = _RbiLinkParser()
    parser.feed(resp.text)
    return parser.links


def build_manifest(listing_url: str) -> List[ManifestEntry]:
    anchors = fetch_listing_links(listing_url)
    if not anchors:
        return []
    def matches(href: str, text: str) -> bool:
        haystacks = (href.lower(), text.lower())
        return any(k in h for h in haystacks for k in KEYWORDS)

    def preferred(href: str) -> bool:
        return any(p in href for p in PREFERRED_PDF_PATTERNS)

    filtered = [(href, text) for href, text in anchors if matches(href, text)]
    if filtered:
        chosen = filtered
        print(f"[info] matched {len(filtered)}/{len(anchors)} PDF links by keyword filter")
    else:
        preferred_links = [(href, text) for href, text in anchors if preferred(href)]
        chosen = preferred_links if preferred_links else anchors
        if preferred_links:
            print(f"[info] no keyword match; using {len(preferred_links)} PDF(s) from Publications/PDFs")
        else:
            print(f"[warn] no keyword or path match; using all {len(anchors)} PDF links from page")

    seen_urls: set[str] = set()
    entries: List[ManifestEntry] = []
    for href, _text in chosen:
        url = href if href.startswith("http") else f"https://www.rbi.org.in{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)
        filename = url.rsplit("/", 1)[-1].split("?")[0]
        quarter = Path(filename).stem
        entries.append(ManifestEntry(quarter=quarter, url=url, filename=filename))
    return entries


def write_manifest(entries: List[ManifestEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["quarter", "url", "filename", "template_hint"])
        for entry in entries:
            writer.writerow([entry.quarter, entry.url, entry.filename, entry.template_hint])


def append_manifest_entry(path: Path, url: str, quarter: Optional[str] = None) -> ManifestEntry:
    """Append one PDF URL to the manifest. Returns the new entry."""
    url = url.strip()
    filename = url.rsplit("/", 1)[-1].split("?")[0]
    if not filename.lower().endswith(".pdf"):
        filename = filename or "document.pdf"
    quarter = quarter or Path(filename).stem
    entry = ManifestEntry(quarter=quarter, url=url, filename=filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(["quarter", "url", "filename", "template_hint"])
        writer.writerow([entry.quarter, entry.url, entry.filename, entry.template_hint])
    return entry


def read_manifest(path: Path) -> List[ManifestEntry]:
    entries: List[ManifestEntry] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            url = (row.get("url") or "").strip()
            if not url:
                continue
            entries.append(
                ManifestEntry(
                    quarter=row.get("quarter", ""),
                    url=url,
                    filename=row.get("filename") or url.rsplit("/", 1)[-1].split("?")[0],
                    template_hint=row.get("template_hint", ""),
                )
            )
    return entries


def download_pdf(entry: ManifestEntry, session: Session) -> Path:
    dest = RAW_DIR / entry.filename
    if dest.exists():
        return dest
    resp: Response = session.get(entry.url, timeout=180)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    sha = hashlib.sha256(resp.content).hexdigest()[:12]
    print(f"[downloaded] {entry.filename} ({sha})")
    return dest


def normalize_header(value: str | int | float | None) -> str:
    raw = value if value is not None else ""
    key = re.sub(r"\s+", " ", str(raw)).strip().lower()
    return COLUMN_ALIASES.get(key, key)


def clean_amount(value: str) -> Optional[float]:
    if value is None or value == "":
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_tables(pdf_path: Path) -> List[pd.DataFrame]:
    tables: List[pd.DataFrame] = []
    try:
        import camelot  # type: ignore

        for flavor in ("lattice", "stream"):
            try:
                result = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor, strip_text="\n")
            except Exception:
                continue
            for table in result:
                tables.append(table.df)
            if tables:
                return tables
    except ImportError:
        print("Camelot not installed; skipping camelot parsing", file=sys.stderr)

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_table()
                if extracted:
                    df = pd.DataFrame(extracted[1:], columns=extracted[0])
                    tables.append(df)
    except ImportError:
        print("pdfplumber not installed; skipping pdfplumber parsing", file=sys.stderr)
    except Exception as exc:
        print(f"pdfplumber failed on {pdf_path.name}: {exc}", file=sys.stderr)

    return tables


def normalize_table(df: pd.DataFrame, source_pdf: str, template_hint: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    # Ensure all column names are strings (Camelot can yield 0,1,2 when no header row).
    df.columns = [str(c) for c in df.columns]
    df = df.replace({"": pd.NA, None: pd.NA})

    # If the first row looks like headers, promote it.
    first_row = " ".join(str(val).lower() for val in df.iloc[0].tolist())
    if "borrower" in first_row and "name" in first_row:
        df.columns = [str(x) for x in df.iloc[0].tolist()]
        df = df.iloc[1:]

    df.columns = [normalize_header(col) for col in df.columns]
    df = df.replace({"": pd.NA, "nan": pd.NA}).dropna(how="all")

    if "amount" in df.columns:
        df["amount"] = df["amount"].map(clean_amount)
    if "classification_date" in df.columns:
        df["classification_date"] = pd.to_datetime(df["classification_date"], errors="coerce")
    if "company_name" in df.columns:
        df["company_name"] = df["company_name"].astype(str).str.strip()
    if "bank_name" in df.columns:
        df["bank_name"] = df["bank_name"].astype(str).str.strip()

    df["source_pdf"] = source_pdf
    df["template_hint"] = template_hint
    return df


def parse_pdfs(entries: Iterable[ManifestEntry]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for entry in entries:
        pdf_path = RAW_DIR / entry.filename
        if not pdf_path.exists():
            print(f"[skip] missing PDF for {entry.filename}", file=sys.stderr)
            continue
        tables = extract_tables(pdf_path)
        if not tables:
            print(f"[warn] no tables extracted from {entry.filename}", file=sys.stderr)
            continue
        for table in tables:
            normalized = normalize_table(table, source_pdf=entry.filename, template_hint=entry.template_hint)
            if normalized.empty:
                continue
            # Skip tables that have no defaulter-like columns (avoid junk from narrative PDFs).
            defaulter_cols = {"company_name", "cin", "amount", "bank_name"}
            if not defaulter_cols.intersection(normalized.columns):
                continue
            frames.append(normalized)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    # Reorder common columns first.
    preferred = ["company_name", "cin", "bank_name", "branch", "state", "amount", "classification_date"]
    ordered = [col for col in preferred if col in combined.columns]
    remaining = [col for col in combined.columns if col not in ordered]
    return combined[ordered + remaining]


def cmd_manifest(args: argparse.Namespace) -> None:
    ensure_dirs()
    urls = getattr(args, "listing_urls", None) or DEFAULT_LISTING_URLS
    all_entries: List[ManifestEntry] = []
    seen: set[str] = set()
    for url in urls:
        entries = build_manifest(url)
        for e in entries:
            if e.url not in seen:
                seen.add(e.url)
                all_entries.append(e)
    if not all_entries:
        print("No PDF links found from the given URL(s). Add URLs manually with: manifest add-url <pdf_url>", file=sys.stderr)
        sys.exit(1)
    write_manifest(all_entries, Path(args.manifest))
    print(f"Wrote manifest with {len(all_entries)} entries to {args.manifest}")


def cmd_add_url(args: argparse.Namespace) -> None:
    entry = append_manifest_entry(Path(args.manifest), args.url, quarter=args.quarter)
    print(f"Appended to {args.manifest}: {entry.filename}")

def cmd_download(args: argparse.Namespace) -> None:
    ensure_dirs()
    manifest = Path(args.manifest)
    if not manifest.exists():
        print(f"Manifest {manifest} not found. Run the manifest step first.", file=sys.stderr)
        sys.exit(1)
    entries = read_manifest(manifest)
    with requests.Session() as session:
        for entry in entries:
            try:
                download_pdf(entry, session=session)
            except Exception as exc:
                print(f"[error] failed to download {entry.filename}: {exc}", file=sys.stderr)


def cmd_parse(args: argparse.Namespace) -> None:
    ensure_dirs()
    manifest = Path(args.manifest)
    if not manifest.exists():
        print(f"Manifest {manifest} not found. Run the manifest step first.", file=sys.stderr)
        sys.exit(1)
    entries = read_manifest(manifest)
    df = parse_pdfs(entries)
    output_path = Path(args.output)
    if df.empty:
        print(
            "No defaulter table data extracted. PDF 63417 is the scheme document (policy text), not the company list. "
            "Use a quarterly wilful defaulter list PDF when RBI provides one, or add its URL to the manifest.",
            file=sys.stderr,
        )
        # Write empty CSV with expected columns so downstream doesn't break.
        pd.DataFrame(columns=["company_name", "cin", "bank_name", "amount", "classification_date", "source_pdf"]).to_csv(
            output_path, index=False
        )
        print(f"Wrote empty placeholder to {output_path}")
        return
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} rows to {output_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RBI wilful defaulter ingestion helper")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("manifest", help="Scrape RBI listing page(s) and write a manifest CSV")
    manifest.add_argument(
        "--listing-url",
        action="append",
        dest="listing_urls",
        default=None,
        help="RBI listing URL (repeat for multiple). Default: PublicationsView id=7320.",
    )
    manifest.add_argument("--manifest", default=str(MANIFEST_PATH), help="Path to write manifest CSV")
    manifest.set_defaults(func=cmd_manifest)

    add_url = sub.add_parser(
        "add-url",
        help="Append one PDF URL to the manifest (e.g. when you have a direct link to a quarterly list)",
    )
    add_url.add_argument("url", help="Full URL of the PDF")
    add_url.add_argument("--quarter", default=None, help="Label for this entry (default: from filename)")
    add_url.add_argument("--manifest", default=str(MANIFEST_PATH), help="Path to manifest CSV")
    add_url.set_defaults(func=cmd_add_url)

    download = sub.add_parser("download", help="Download PDFs listed in the manifest")
    download.add_argument("--manifest", default=str(MANIFEST_PATH), help="Path to manifest CSV")
    download.set_defaults(func=cmd_download)

    parse = sub.add_parser("parse", help="Parse downloaded PDFs into a normalized CSV")
    parse.add_argument("--manifest", default=str(MANIFEST_PATH), help="Path to manifest CSV")
    parse.add_argument(
        "--output", default=str(PROCESSED_DIR / "rbi_defaulters.csv"), help="Path for parsed CSV output"
    )
    parse.set_defaults(func=cmd_parse)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
