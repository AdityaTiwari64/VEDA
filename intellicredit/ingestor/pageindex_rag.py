"""
ingestor/pageindex_rag.py — Ollama-based PageIndex implementation

Uses Ollama for document analysis with reasoning-based retrieval.
Requires Ollama running locally or OpenRouter API key.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import pdfplumber
import pymupdf as fitz
import requests
from dotenv import load_dotenv
from json_repair import repair_json

from ..models import ProvenanceField, IngestorRiskSignal, BorrowerProfile
from ..config import Confidence, RiskSeverity, RED_FLAG_PATTERNS
from .base import BaseParser

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class PageIndexRAG:
    """
    PageIndex-powered document analysis using Ollama or OpenRouter.
    """

    def __init__(self, model_name: Optional[str] = None, provider: Optional[str] = None):
        # Priority: Argument > Environment Variable > Hardcoded Fallback
        self.provider = (provider or os.getenv("DEFAULT_PROVIDER") or "ollama").lower()
        self.model_name = model_name or os.getenv("DEFAULT_MODEL") or "llama3"
        self.api_key = os.getenv("OPENROUTER_API_KEY")

        if self.provider == "openrouter":
            if not self.api_key:
                logger.warning("OPENROUTER_API_KEY not found in environment. Falling back to Ollama.")
                self.provider = "ollama"
            else:
                logger.info(f"✓ Using OpenRouter with model: {self.model_name}")
                return

        if self.provider == "ollama":
            try:
                # Test Ollama connection
                response = requests.get("http://localhost:11434/api/tags", timeout=5)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    model_names = [m['name'] for m in models]

                    # Check if requested model is available
                    if not any(self.model_name in m for m in model_names):
                        logger.warning(f"Model {self.model_name} not found in Ollama. Available: {model_names}")
                        if model_names:
                            self.model_name = model_names[0].split(':')[0]
                            logger.info(f"Using {self.model_name} instead")

                    logger.info(f"✓ Connected to Ollama, using model: {self.model_name}")
                else:
                    raise ConnectionError("Ollama not responding properly")
            except Exception as e:
                logger.error(f"✗ Ollama not available: {e}")
                if self.api_key:
                    logger.info("Switching to OpenRouter since Ollama is unavailable.")
                    self.provider = "openrouter"
                else:
                    raise ConnectionError(
                        "No LLM provider available! Please start Ollama or set OPENROUTER_API_KEY."
                    )

    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call either Ollama or OpenRouter API"""
        if self.provider == "openrouter":
            return self._call_openrouter(prompt, max_tokens)
        else:
            return self._call_ollama(prompt, max_tokens)

    def _call_openrouter(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call OpenRouter API (OpenAI-compatible)"""
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/intellicredit",
                    "X-Title": "IntelliCredit",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.1
                }),
                timeout=60
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return ""
        except Exception as e:
            logger.error(f"OpenRouter call failed: {e}")
            return ""

    def _call_ollama(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call Ollama API"""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.1
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                return response.json()["response"]
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return ""

    def extract_text_from_pdf(self, pdf_path: str) -> Dict[int, str]:
        """
        Extract text from PDF page by page.

        Returns:
            Dict mapping page_number -> text_content
        """
        logger.info(f"Extracting text from {pdf_path}")

        pages_text = {}

        try:
            # Try pdfplumber first (better for tables)
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text:
                        pages_text[i] = text

            logger.info(f"Extracted text from {len(pages_text)} pages using pdfplumber")

        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}, trying PyMuPDF")

            # Fallback to PyMuPDF
            try:
                doc = fitz.open(pdf_path)
                for i, page in enumerate(doc, start=1):
                    text = page.get_text()
                    if text:
                        pages_text[i] = text

                logger.info(f"Extracted text from {len(pages_text)} pages using PyMuPDF")

            except Exception as e2:
                logger.error(f"PyMuPDF also failed: {e2}")

        return pages_text

    def _fix_json(self, text: str) -> str:
        """
        Fix common JSON issues from LLM responses.
        phi3 often returns malformed JSON, this tries to fix it.
        """
        import re

        # Remove markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        # Remove any text before first {
        start = text.find('{')
        if start > 0:
            text = text[start:]

        # Remove any text after last }
        end = text.rfind('}')
        if end > 0:
            text = text[:end+1]

        # Fix common issues
        # Fix unquoted keys: title: -> "title":
        text = re.sub(r'(\w+):', r'"\1":', text)

        # Fix already quoted keys that got double-quoted: ""title"": -> "title":
        text = re.sub(r'""(\w+)"":', r'"\1":', text)

        # Fix single quotes to double quotes
        text = text.replace("'", '"')

        # Fix trailing commas before } or ]
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        return text

    def build_document_index(self, pdf_path: str) -> Dict[str, Any]:
        """
        Build hierarchical index of document using LLM.
        Follows PageIndex standard format with nested nodes.
        """
        logger.info(f"Building PageIndex for {pdf_path} using {self.provider}")

        pages_text = self.extract_text_from_pdf(pdf_path)

        if not pages_text:
            return {"error": "No text extracted", "nodes": []}

        total_pages = max(pages_text.keys()) if pages_text else 0

        # Combine first few pages for TOC detection and overall context
        context_text = ""
        for i in range(1, min(11, total_pages + 1)):
            page_content = pages_text.get(i, "")
            if page_content:
                context_text += f"PAGE {i}:\n{page_content[:2000]}\n\n"

        prompt = f"""Analyze this {total_pages}-page financial document and create a HIERARCHICAL tree index.

DOCUMENT CONTEXT (First {min(10, total_pages)} pages):
{context_text}

Create a nested tree structure. Follow these rules STRICTLY:
1. Return ONLY valid JSON.
2. Use "start_index" and "end_index" (page numbers 1-{total_pages}).
3. Use a nested "nodes" array for sub-sections.
4. Each node must have: title, node_id (e.g., "0001", "0001.1"), start_index, end_index, summary.
5. If a section is large (e.g., "Financial Statements"), break it down into sub-nodes (e.g., "Balance Sheet", "P&L").

Expected JSON Format:
{{
  "document_title": "Title",
  "total_pages": {total_pages},
  "nodes": [
    {{
      "title": "Main Section",
      "node_id": "0001",
      "start_index": 1,
      "end_index": 10,
      "summary": "Summary...",
      "nodes": [
        {{
          "title": "Sub Section",
          "node_id": "0001.1",
          "start_index": 1,
          "end_index": 5,
          "summary": "Sub-summary..."
        }}
      ]
    }}
  ]
}}

CRITICAL:
- Do not hallucinate pages.
- Ensure "nodes" is used for nesting.
- Return ONLY JSON."""

        response = self._call_llm(prompt, max_tokens=2500)

        try:
            # Use json_repair to fix and parse the response
            try:
                index_data = json.loads(repair_json(response))
            except Exception as e:
                logger.debug(f"JSON repair failed: {e}")
                # Fallback to manual fix
                fixed_json = self._fix_json(response)
                index_data = json.loads(fixed_json)

            # Use 'nodes' instead of 'sections' to match official PageIndex terminology
            if 'sections' in index_data and 'nodes' not in index_data:
                index_data['nodes'] = index_data.pop('sections')

            logger.info(f"Built hierarchical PageIndex with {len(index_data.get('nodes', []))} top-level nodes using {self.provider}")
            return index_data

        except Exception as e:
            logger.error(f"Failed to parse hierarchical LLM response: {e}")
            return {
                "document_title": Path(pdf_path).stem,
                "total_pages": total_pages,
                "nodes": []
            }

    def _get_all_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """Flatten hierarchical nodes for searching"""
        flat_list = []
        for node in nodes:
            flat_list.append(node)
            if 'nodes' in node and node['nodes']:
                flat_list.extend(self._get_all_nodes(node['nodes']))
        return flat_list

    def query_document(self, pdf_path: str, document_index: Dict, query: str) -> Dict[str, Any]:
        """
        Reasoning-based retrieval using PageIndex tree navigation.
        """
        logger.info(f"PageIndex hierarchical query: {query}")

        all_nodes = self._get_all_nodes(document_index.get('nodes', []))

        # Step 1: Navigate tree (Simplified for now - shows all nodes to LLM to pick)
        nodes_summary = "\n".join([
            f"- {n['title']} (ID: {n['node_id']}, pages {n['start_index']}-{n['end_index']}): {n.get('summary', '')[:100]}..."
            for n in all_nodes
        ])

        navigation_prompt = f"""Query: {query}

Document Structure:
{nodes_summary}

Based on the structure, which specific node_ids are most relevant?
Return ONLY a JSON array of node_ids: ["0001", "0002.1"]"""

        response = self._call_llm(navigation_prompt, max_tokens=200)

        relevant_node_ids = []
        try:
            # Use json_repair for navigation array
            relevant_node_ids = json.loads(repair_json(response))
        except:
            pass

        relevant_nodes = [n for n in all_nodes if n['node_id'] in relevant_node_ids]
        if not relevant_nodes:
            relevant_nodes = all_nodes[:3]  # Fallback to first few

        logger.info(f"Navigated to {len(relevant_nodes)} relevant nodes")

        # Step 2: Extract text and Answer
        pages_text = self.extract_text_from_pdf(pdf_path)
        relevant_text = ""
        page_refs = []

        for node in relevant_nodes:
            for page_num in range(node['start_index'], node['end_index'] + 1):
                if page_num in pages_text:
                    relevant_text += f"\n=== {node['title']} (Page {page_num}) ===\n"
                    relevant_text += pages_text[page_num]
                    page_refs.append(page_num)

        answer_prompt = f"""Query: {query}
Text:
{relevant_text[:4000]}

Answer as JSON: {{"answer": "...", "evidence": "...", "page": N, "confidence": "HIGH"}}"""

        response = self._call_llm(answer_prompt, max_tokens=800)

        try:
            # Use json_repair for the answer object
            result = json.loads(repair_json(response))
            result['nodes_searched'] = [n['title'] for n in relevant_nodes]
            return result
        except:
            pass

        return {"answer": "Error extracting answer", "confidence": "LOW"}

    def extract_financial_data(self, pdf_path: str, document_index: Dict, doc_type: str = "ANNUAL_REPORT") -> Dict[str, ProvenanceField]:
        """
        Extract financial figures using PageIndex reasoning-based retrieval.
        """
        logger.info(f"Extracting financial data from {doc_type} using PageIndex with {self.provider}")

        # Define base queries for financial metrics
        queries = {
            'revenue': "What is the total revenue or turnover?",
            'ebitda': "What is the EBITDA?",
            'pat': "What is the Profit After Tax (PAT) or net profit?",
            'total_debt': "What is the total debt or borrowings?",
            'tangible_net_worth': "What is the tangible net worth or shareholders' equity?",
            'contingent_liabilities': "What are the total contingent liabilities (guarantees, litigations, etc.)?",
            'capital_commitments': "What are the estimated capital commitments or unexecuted contracts?",
        }

        # Specialized queries for Sanction Letters
        if doc_type == "SANCTION_LETTER":
            queries.update({
                'sanctioned_limit': "What is the total sanctioned limit or loan amount?",
                'interest_rate': "What is the interest rate (ROI)?",
                'collateral_value': "What is the total value of collateral or security?",
                'repayment_tenure': "What is the repayment tenure or duration of the loan?",
            })

        extracted_data = {}

        for field_name, query in queries.items():
            try:
                result = self.query_document(pdf_path, document_index, query)

                if result.get('answer') and result['answer'] != "Could not extract answer":
                    # Try to extract number from answer
                    import re
                    answer_text = result['answer']

                    # Look for patterns like "Rs. 4,820 Lakhs" or "4820.00 Lakhs"
                    patterns = [
                        r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(Lakh|Crore|Cr)',
                        r'([\d,]+(?:\.\d+)?)\s*(Lakh|Crore|Cr)',
                        r'([\d,]+(?:\.\d+)?)',
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, answer_text, re.IGNORECASE)
                        if match:
                            value_str = match.group(1).replace(',', '')
                            try:
                                value = float(value_str)
                            except ValueError:
                                continue

                            # Convert to Lakhs if in Crores
                            unit = ""
                            if len(match.groups()) > 1 and match.group(2):
                                unit = match.group(2).lower()
                                if 'crore' in unit or 'cr' == unit:
                                    value = value * 100

                            extracted_data[field_name] = ProvenanceField(
                                value=value,
                                source_file=Path(pdf_path).name,
                                page=result.get('page'),
                                extraction_method='pageindex',
                                confidence=Confidence[result.get('confidence', 'MEDIUM')],
                                raw_text=result.get('evidence', answer_text)
                            )

                            logger.info(f"Extracted {field_name}: ₹{value:.2f}L from page {result.get('page')}")
                            break

            except Exception as e:
                logger.error(f"Failed to extract {field_name}: {e}")
                continue

        logger.info(f"Extracted {len(extracted_data)} financial metrics using PageIndex")
        return extracted_data

    def identify_risk_signals(self, pdf_path: str, document_index: Dict, doc_type: str = "ANNUAL_REPORT") -> List[IngestorRiskSignal]:
        """
        Identify risk signals using LLM.
        """
        logger.info(f"Identifying risk signals from {doc_type} using {self.provider}")

        pages_text = self.extract_text_from_pdf(pdf_path)
        risk_signals = []

        # Get full document text (limit to first 10k chars for risk scanning if very long)
        full_text = ""
        for p in range(1, min(15, len(pages_text) + 1)):
            full_text += pages_text.get(p, "") + "\n"

        # Query LLM for risk signals
        prompt = f"""Analyze this {doc_type} document for credit risk signals and financial commitments.

Document Type: {doc_type}
Content Snippet:
{full_text[:5000]}

Look for specific indicators based on document type:
- If ANNUAL REPORT: Legal proceedings (NCLT, litigation), contingent liabilities, related party loans, auditor qualifications, frequent change in auditors.
- If LEGAL NOTICE: Court cases, SARFAESI notices, default warnings, recovery actions.
- If SANCTION LETTER: Onerous conditions, high interest rates, restrictive covenants, insufficient collateral.

For each risk or significant commitment found, return ONLY a JSON array:
[
  {{
    "category": "LEGAL" or "REGULATORY" or "FINANCIAL" or "PROMOTER" or "OPERATIONAL",
    "subcategory": "NCLT_CASE" or "CONTINGENT_LIABILITY" or "DEFAULT_NOTICE" or "AUDITOR_QUALIFICATION",
    "description": "brief description of the risk or commitment",
    "severity": "RED" or "AMBER" or "GREEN",
    "evidence": "exact text snippet from document",
    "score_impact": -20 to 0
  }}
]

If no risks found, return []"""

        response = self._call_llm(prompt, max_tokens=1500)

        try:
            # Use json_repair for risk signal list
            risks = json.loads(repair_json(response))

            for risk in risks:
                signal = IngestorRiskSignal(
                    category=risk.get('category', 'FINANCIAL'),
                    subcategory=risk.get('subcategory', 'UNKNOWN'),
                    description=risk.get('description', ''),
                    severity=risk.get('severity', 'AMBER'),
                    source=f"pageindex_{doc_type.lower()}",
                    score_impact=float(risk.get('score_impact', 0)),
                    evidence_snippet=risk.get('evidence', '')
                )
                risk_signals.append(signal)
        except Exception as e:
            logger.error(f"Failed to identify risk signals: {e}")

        logger.info(f"Identified {len(risk_signals)} risk signals")
        return risk_signals

    def analyze_document(self, pdf_path: str, profile: BorrowerProfile, doc_type: str = "ANNUAL_REPORT") -> BorrowerProfile:
        """
        Full document analysis pipeline using LLM.

        Args:
            pdf_path: Path to PDF document
            profile: BorrowerProfile to update
            doc_type: Type of document (ANNUAL_REPORT, LEGAL_NOTICE, SANCTION_LETTER)

        Returns:
            Updated BorrowerProfile
        """
        logger.info(f"Starting {self.provider} PageIndex analysis for {pdf_path} (Type: {doc_type})")

        try:
            # Step 1: Build document index
            document_index = self.build_document_index(pdf_path)

            # Step 2: Extract financial data
            financial_data = self.extract_financial_data(pdf_path, document_index, doc_type)

            # Step 3: Identify risk signals
            risk_signals = self.identify_risk_signals(pdf_path, document_index, doc_type)

            # Update profile
            profile.document_analysis[Path(pdf_path).name] = {
                'doc_type': doc_type,
                'index': document_index,
                'financial_data': {k: str(v) for k, v in financial_data.items()},
                'risk_signals_count': len(risk_signals)
            }

            # Add risk signals to profile
            for signal in risk_signals:
                profile.add_risk_signal_from_ingestor(signal)

            logger.info(f"{self.provider} analysis complete: {len(financial_data)} metrics, {len(risk_signals)} risks")

        except Exception as e:
            logger.error(f"{self.provider} PageIndex analysis failed: {e}")
            profile.processing_errors.append(f"{self.provider} PageIndex error ({doc_type}): {str(e)}")

        return profile


class PDFParser(BaseParser):
    """
    PDF parser using PageIndex RAG (Ollama or OpenRouter).
    """

    def __init__(self, model_name: str = "llama3", provider: str = "ollama"):
        super().__init__()
        self.rag = PageIndexRAG(model_name=model_name, provider=provider)

    def parse(self, filepath: str, doc_type: str = "ANNUAL_REPORT") -> Dict[str, Any]:
        """Parse PDF using PageIndex RAG"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF not found: {filepath}")

        # Create temporary profile for parsing
        temp_profile = BorrowerProfile(company_name="temp")
        result_profile = self.rag.analyze_document(filepath, temp_profile, doc_type=doc_type)

        return {
            'document_analysis': result_profile.document_analysis,
            'risk_signals': [
                {
                    'category': s.category,
                    'subcategory': s.subcategory,
                    'description': s.description,
                    'severity': s.severity,
                    'score_impact': s.score_impact,
                    'evidence': s.evidence_snippet
                }
                for s in result_profile.ingestor_risk_signals
            ],
            'processing_errors': result_profile.processing_errors
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate parsed PDF data"""
        return 'document_analysis' in data
