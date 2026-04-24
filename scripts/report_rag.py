#!/usr/bin/env python3
"""Standalone RAG utilities for annual-report evidence retrieval.

This module is intentionally NOT wired into the live report pipeline yet.
It provides a real retrieval layer that can later be connected to report
section generation or report-page Q&A.

Current implementation uses a local TF-IDF retriever so it can run with the
existing project dependencies. That still qualifies as a legitimate RAG layer:
- document chunking
- vectorization / indexing
- retrieval by query or report section
- context assembly for LLM grounding
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

import joblib
import numpy as np
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAG_ROOT = PROJECT_ROOT / "data" / "rag"

SECTION_QUERY_TEMPLATES: dict[str, list[str]] = {
    "company_profile": [
        "company overview main business operations segments products services",
        "management discussion business profile principal activities",
        "segment revenue business description annual report",
    ],
    "model_verdict": [
        "borrowings debt cash flow profitability leverage liquidity annual report",
        "financial performance balance sheet cash flow overview",
    ],
    "balance_sheet_risk": [
        "borrowings debt liabilities equity net worth retained earnings assets",
        "capital structure leverage long term borrowings short term borrowings",
        "balance sheet note debt maturity loans debentures facilities",
    ],
    "liquidity_cash_flow": [
        "cash flow operating activities working capital current liabilities current assets liquidity",
        "debt servicing repayment finance cost interest coverage cash and cash equivalents",
        "borrowings due within one year liquidity management treasury",
    ],
    "profitability_asset_quality": [
        "revenue EBITDA PAT margin profitability cost pressure performance review",
        "return on assets operations margin business performance annual report",
    ],
    "governance_audit": [
        "auditor report qualified opinion adverse disclaimer emphasis of matter",
        "going concern fraud internal financial controls key audit matters",
        "contingent liabilities promoter shareholding corporate governance",
    ],
    "key_red_flags": [
        "liquidity pressure borrowings overdue losses contingent liabilities qualification",
        "default dispute claim impairment going concern stress material uncertainty",
    ],
    "what_could_change_view": [
        "management plans liquidity improvement refinancing capital raise recovery outlook",
        "future outlook order book debt reduction contingent liabilities resolution",
    ],
    "analyst_conclusion": [
        "overall financial position leverage cash flow audit outlook contingent liabilities",
    ],
}

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "auditor_report": ("auditor", "audit report", "key audit matter", "emphasis of matter", "going concern"),
    "notes": ("note", "notes to accounts", "contingent liabilities", "commitments"),
    "cash_flow": ("cash flow", "operating activities", "investing activities", "financing activities"),
    "balance_sheet": ("balance sheet", "assets", "liabilities", "equity", "borrowings"),
    "income_statement": ("statement of profit and loss", "revenue", "income", "expense", "profit"),
    "md&a": ("management discussion", "business overview", "operating performance", "outlook"),
    "shareholding": ("shareholding", "promoter", "share capital"),
}


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", cleaned)
    return [p.strip() for p in parts if p.strip()]


def _infer_section_type(text: str) -> str:
    haystack = text.lower()
    scores: Counter[str] = Counter()
    for section_type, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in haystack:
                scores[section_type] += 1
    return scores.most_common(1)[0][0] if scores else "general"


def extract_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages: list[dict[str, Any]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(
                {
                    "page": i,
                    "text": _clean_text(text),
                }
            )
    return pages


def chunk_pages(
    pages: list[dict[str, Any]],
    *,
    target_chars: int = 1400,
    overlap_sentences: int = 2,
    min_chars: int = 280,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    chunk_id = 0

    for page_obj in pages:
        page = int(page_obj["page"])
        sentences = _split_sentences(str(page_obj.get("text") or ""))
        if not sentences:
            continue

        buffer: list[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if buffer and current_len + sentence_len + 1 > target_chars:
                chunk_text = " ".join(buffer).strip()
                if len(chunk_text) >= min_chars:
                    chunks.append(
                        {
                            "chunk_id": f"chunk_{chunk_id:04d}",
                            "page_start": page,
                            "page_end": page,
                            "section_type": _infer_section_type(chunk_text),
                            "text": chunk_text,
                            "char_count": len(chunk_text),
                            "sentence_count": len(buffer),
                        }
                    )
                    chunk_id += 1
                overlap = buffer[-overlap_sentences:] if overlap_sentences > 0 else []
                buffer = overlap.copy()
                current_len = sum(len(x) for x in buffer) + max(len(buffer) - 1, 0)

            buffer.append(sentence)
            current_len += sentence_len + 1

        if buffer:
            chunk_text = " ".join(buffer).strip()
            if len(chunk_text) >= min_chars or not chunks:
                chunks.append(
                    {
                        "chunk_id": f"chunk_{chunk_id:04d}",
                        "page_start": page,
                        "page_end": page,
                        "section_type": _infer_section_type(chunk_text),
                        "text": chunk_text,
                        "char_count": len(chunk_text),
                        "sentence_count": len(buffer),
                    }
                )
                chunk_id += 1

    return chunks


class TfidfRagIndex:
    def __init__(self, *, vectorizer: TfidfVectorizer, matrix: Any, chunks: list[dict[str, Any]], metadata: dict[str, Any]):
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.chunks = chunks
        self.metadata = metadata

    @classmethod
    def build(cls, chunks: list[dict[str, Any]], *, metadata: dict[str, Any] | None = None) -> "TfidfRagIndex":
        if not chunks:
            raise ValueError("Cannot build RAG index with zero chunks")
        texts = [str(chunk["text"]) for chunk in chunks]
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            norm="l2",
        )
        matrix = vectorizer.fit_transform(texts)
        return cls(vectorizer=vectorizer, matrix=matrix, chunks=chunks, metadata=metadata or {})

    def save(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "vectorizer": self.vectorizer,
            "matrix": self.matrix,
            "chunks": self.chunks,
            "metadata": self.metadata,
        }
        joblib.dump(payload, out_dir / "tfidf_index.joblib")
        (out_dir / "chunks.json").write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")
        (out_dir / "metadata.json").write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, out_dir: Path) -> "TfidfRagIndex":
        payload = joblib.load(out_dir / "tfidf_index.joblib")
        return cls(
            vectorizer=payload["vectorizer"],
            matrix=payload["matrix"],
            chunks=list(payload["chunks"]),
            metadata=dict(payload.get("metadata") or {}),
        )

    def query(self, query_text: str, *, top_k: int = 5, filter_section_type: str | None = None) -> list[dict[str, Any]]:
        query_text = _clean_text(query_text)
        if not query_text:
            return []
        qv = self.vectorizer.transform([query_text])
        scores = (self.matrix @ qv.T).toarray().ravel()
        ranked = np.argsort(-scores)
        hits: list[dict[str, Any]] = []
        for idx in ranked:
            score = float(scores[idx])
            if score <= 0:
                continue
            chunk = self.chunks[int(idx)]
            if filter_section_type and chunk.get("section_type") != filter_section_type:
                continue
            hits.append(
                {
                    **chunk,
                    "score": round(score, 6),
                    "query": query_text,
                }
            )
            if len(hits) >= top_k:
                break
        return hits

    def retrieve_for_section(self, section_id: str, *, top_k: int = 6) -> list[dict[str, Any]]:
        templates = SECTION_QUERY_TEMPLATES.get(section_id)
        if not templates:
            raise KeyError(f"Unknown section template: {section_id}")

        merged: dict[str, dict[str, Any]] = {}
        for template in templates:
            for hit in self.query(template, top_k=top_k):
                existing = merged.get(hit["chunk_id"])
                if existing is None or hit["score"] > existing["score"]:
                    merged[hit["chunk_id"]] = hit

        return sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]

    def build_llm_context(self, section_id: str, *, top_k: int = 6) -> str:
        hits = self.retrieve_for_section(section_id, top_k=top_k)
        blocks = []
        for hit in hits:
            blocks.append(
                f"[page {hit['page_start']}] ({hit['section_type']}, score={hit['score']}) {hit['text']}"
            )
        return "\n\n".join(blocks)


def build_job_rag_index(
    pdf_path: Path,
    out_dir: Path,
    *,
    target_chars: int = 1400,
    overlap_sentences: int = 2,
    min_chars: int = 280,
) -> dict[str, Any]:
    pages = extract_pdf_pages(pdf_path)
    chunks = chunk_pages(
        pages,
        target_chars=target_chars,
        overlap_sentences=overlap_sentences,
        min_chars=min_chars,
    )
    metadata = {
        "pdf_path": str(pdf_path),
        "chunk_count": len(chunks),
        "page_count": len(pages),
        "backend": "tfidf",
        "target_chars": target_chars,
        "overlap_sentences": overlap_sentences,
        "min_chars": min_chars,
    }
    index = TfidfRagIndex.build(chunks, metadata=metadata)
    index.save(out_dir)
    return metadata


def _json_print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone RAG utilities for annual reports")
    sub = parser.add_subparsers(dest="command", required=True)

    build_cmd = sub.add_parser("build", help="Build a local TF-IDF RAG index from a PDF")
    build_cmd.add_argument("--pdf", type=Path, required=True, help="Path to annual report PDF")
    build_cmd.add_argument("--out-dir", type=Path, required=True, help="Directory to store index artifacts")
    build_cmd.add_argument("--target-chars", type=int, default=1400)
    build_cmd.add_argument("--overlap-sentences", type=int, default=2)
    build_cmd.add_argument("--min-chars", type=int, default=280)

    query_cmd = sub.add_parser("query", help="Run a free-text retrieval query against a built index")
    query_cmd.add_argument("--index-dir", type=Path, required=True)
    query_cmd.add_argument("--query", type=str, required=True)
    query_cmd.add_argument("--top-k", type=int, default=5)
    query_cmd.add_argument("--section-type", type=str, default=None)

    section_cmd = sub.add_parser("section", help="Retrieve evidence for a predefined report section")
    section_cmd.add_argument("--index-dir", type=Path, required=True)
    section_cmd.add_argument("--section-id", type=str, required=True, choices=sorted(SECTION_QUERY_TEMPLATES.keys()))
    section_cmd.add_argument("--top-k", type=int, default=6)
    section_cmd.add_argument("--context-only", action="store_true", help="Print only the context block for LLM prompting")

    args = parser.parse_args()

    if args.command == "build":
        meta = build_job_rag_index(
            pdf_path=args.pdf,
            out_dir=args.out_dir,
            target_chars=args.target_chars,
            overlap_sentences=args.overlap_sentences,
            min_chars=args.min_chars,
        )
        _json_print({"status": "ok", **meta})
        return

    if args.command == "query":
        index = TfidfRagIndex.load(args.index_dir)
        hits = index.query(args.query, top_k=args.top_k, filter_section_type=args.section_type)
        _json_print({"query": args.query, "hits": hits, "metadata": index.metadata})
        return

    if args.command == "section":
        index = TfidfRagIndex.load(args.index_dir)
        if args.context_only:
            print(index.build_llm_context(args.section_id, top_k=args.top_k))
        else:
            hits = index.retrieve_for_section(args.section_id, top_k=args.top_k)
            _json_print({"section_id": args.section_id, "hits": hits, "metadata": index.metadata})
        return

    raise RuntimeError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
