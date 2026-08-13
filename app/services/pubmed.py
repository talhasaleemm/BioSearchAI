import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import httpx
import logging

logger = logging.getLogger(__name__)

class PubMedService:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, requests_per_second: int = 3):
        self.rate_limit_delay = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def search_pubmed(self, query: str, max_results: int = 10) -> List[str]:
        """Search PubMed and return a list of PMIDs."""
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(max_results)
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                pmids = data.get("esearchresult", {}).get("idlist", [])
                return pmids
            except Exception as e:
                logger.error(f"PubMed search failed: {e}")
                raise RuntimeError(f"PubMed search failed: {e}")

    async def fetch_pubmed_abstracts(self, pmids: List[str]) -> List[Dict]:
        """Fetch abstract and metadata for a list of PMIDs."""
        if not pmids:
            return []
            
        await self._rate_limit()
        
        pmid_str = ",".join(pmids)
        url = f"{self.BASE_URL}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid_str,
            "retmode": "xml"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                xml_data = response.text
                return self._parse_pubmed_xml(xml_data)
            except Exception as e:
                logger.error(f"PubMed fetch failed: {e}")
                raise RuntimeError(f"PubMed fetch failed: {e}")

    def _parse_pubmed_xml(self, xml_data: str) -> List[Dict]:
        results = []
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed XML: {e}")
            raise RuntimeError(f"Failed to parse PubMed XML: {e}")

        for article in root.findall('.//PubmedArticle'):
            pmid = article.findtext('.//PMID')
            if not pmid:
                continue

            title = article.findtext('.//ArticleTitle')
            
            # Handle structured abstracts
            abstract_parts = []
            for abst_elem in article.findall('.//AbstractText'):
                label = abst_elem.get('Label')
                text = abst_elem.text
                if text:
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            
            abstract = "\n\n".join(abstract_parts) if abstract_parts else ""
            
            # Extract PubDate (Year, and optionally Month/Day)
            pub_date_elem = article.find('.//PubDate')
            year = ""
            if pub_date_elem is not None:
                year_elem = pub_date_elem.find('Year')
                if year_elem is not None and year_elem.text:
                    year = year_elem.text
                else:
                    medline_date = pub_date_elem.find('MedlineDate')
                    if medline_date is not None and medline_date.text:
                        # E.g. "2020 Jan-Feb" -> just grab first 4 digits
                        import re
                        match = re.search(r'\d{4}', medline_date.text)
                        if match:
                            year = match.group(0)

            results.append({
                "pmid": pmid,
                "title": title or "Untitled",
                "abstract": abstract,
                "year": year
            })

        return results

pubmed_service = PubMedService()
