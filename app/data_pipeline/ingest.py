"""Biomedical data ingestion modules for PubMed and PDF sources."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List, Optional
import logging
from xml.etree import ElementTree as ET

from Bio import Entrez
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.document import Document
from app.models.search_session import SearchSession
from app.models.user import User
from app.models import SessionLocal


@dataclass
class PubMedRecord:
    pmid: str
    title: str
    abstract: str
    authors: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None


class PubMedIngestor:
    """Fetch biomedical abstracts from PubMed via NCBI Entrez API."""

    def __init__(self, email: str, db: Session) -> None:
        if not email:
            raise ValueError("Entrez requires a valid email address.")
        Entrez.email = email
        self.db = db

    def search(self, query: str, top_n: int = 5, retries: int = 3) -> List[PubMedRecord]:
        """Search PubMed and return up to top_n records."""
        for attempt in range(retries):
            try:
                handle = Entrez.esearch(db="pubmed", term=query, retmax=top_n, sort="relevance")
                record = Entrez.read(handle)
                handle.close()
                pmids = record.get("IdList", [])
                if not pmids:
                    return []

                handle = Entrez.efetch(db="pubmed", id=pmids, retmode="xml")
                tree = ET.parse(handle)
                handle.close()
                root = tree.getroot()

                records: List[PubMedRecord] = []
                for article in root.findall(".//PubmedArticle"):
                    try:
                        medline = article.find(".//MedlineCitation")
                        pmid_elem = medline.find("PMID") if medline is not None else None
                        pmid = pmid_elem.text if pmid_elem is not None else ""

                        article_data = medline.find("Article") if medline is not None else None
                        title_elem = article_data.find("ArticleTitle") if article_data is not None else None
                        title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""

                        abstract_elem = article_data.find("Abstract/AbstractText") if article_data is not None else None
                        abstract = "".join(abstract_elem.itertext()).strip() if abstract_elem is not None else ""

                        authors_list = []
                        for author in article_data.findall(".//Author") if article_data is not None else []:
                            last = author.find("LastName")
                            fore = author.find("ForeName")
                            if last is not None:
                                name = last.text or ""
                                if fore is not None:
                                    name = f"{fore.text or ''} {name}".strip()
                                authors_list.append(name)
                        authors = "; ".join(authors_list) if authors_list else None

                        journal_elem = article_data.find("Journal/Title") if article_data is not None else None
                        journal = "".join(journal_elem.itertext()).strip() if journal_elem is not None else None

                        year_elem = None
                        if article_data is not None:
                            year_elem = article_data.find("Journal/JournalIssue/PubDate/Year")
                        year = year_elem.text if year_elem is not None else None

                        records.append(
                            PubMedRecord(
                                pmid=pmid,
                                title=title,
                                abstract=abstract,
                                authors=authors,
                                journal=journal,
                                year=year,
                            )
                        )
                    except Exception as exc:
                        logger.warning(f"Warning: failed to parse article: {exc}")
                        continue
                return records
            except Exception as exc:
                logger.error(f"PubMed fetch attempt {attempt + 1} failed: {exc}")
                time.sleep(2 ** attempt)
        return []

    def save(self, records: List[PubMedRecord], session_id: int, source_type: str = "pubmed") -> int:
        """Save records to the Document table. Returns count of new documents."""
        saved = 0
        for rec in records:
            try:
                existing = (
                    self.db.query(Document)
                    .filter(Document.title == rec.title, Document.session_id == session_id)
                    .first()
                )
                if existing:
                    continue

                source_url = f"https://pubmed.ncbi.nlm.nih.gov/{rec.pmid}/" if rec.pmid else None
                doc = Document(
                    session_id=session_id,
                    title=rec.title or "Untitled",
                    source_url=source_url,
                    source_type=source_type,
                    content=rec.abstract or None,
                )
                self.db.add(doc)
                saved += 1
            except Exception as exc:
                logger.warning(f"Warning: failed to save document '{rec.title}': {exc}")
                continue
        self.db.commit()
        return saved


class PDFIngestor:
    """Extract text from local PDF files and store them as documents."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def extract_text(self, path: str) -> str:
        """Extract clean text from a PDF using PyMuPDF, stripping headers/footers."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"PDF not found: {path}")

        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ImportError("PyMuPDF is required. Install with: pip install pymupdf") from exc

        doc = fitz.open(path)
        page_texts: List[str] = []
        for page in doc:
            text = page.get_text()
            page_texts.append(text)
        doc.close()

        cleaned_pages: List[str] = []
        for text in page_texts:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                cleaned_pages.append("")
                continue
            lines = [line for line in lines if not line.isdigit()]
            cleaned_pages.append("\n".join(lines))

        full_text = "\n\n".join(cleaned_pages)

        marker = None
        for marker_candidate in ["REFERENCES", "References", "Bibliography"]:
            if marker_candidate in full_text:
                marker = marker_candidate
                break
        if marker:
            idx = full_text.index(marker)
            full_text = full_text[:idx]

        return full_text.strip()

    def save(self, path: str, session_id: int, title: Optional[str] = None, source_url: Optional[str] = None) -> Document:
        """Extract text from PDF and save as a Document."""
        text = self.extract_text(path)
        if not text:
            raise ValueError(f"No text extracted from {path}")

        doc_title = title or os.path.basename(path)
        doc = Document(
            session_id=session_id,
            title=doc_title,
            source_url=source_url or f"file://{os.path.abspath(path)}",
            source_type="pdf",
            content=text,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc
