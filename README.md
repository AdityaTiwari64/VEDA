# IntelliCredit (VEDA Engine)

IntelliCredit is a modular, AI-powered credit risk assessment engine designed for Indian financial contexts. It consists of a complete pipeline spanning document ingestion, web research, and policy rule evaluation.

## Features

- **Document Ingestion (PageIndex RAG)**: Hierarchical PDF analysis using Ollama/OpenRouter to extract financial data and identify risk signals directly from documents like Annual Reports and Sanction Letters.
- **GST & Bank Statement Parsing**: Automatic parsing of GSTR-1, 2A, 3B JSON files and multi-format bank statement CSVs (HDFC, SBI, ICICI, AXIS).
- **GST-Bank Reconciliation**: Cross-references GST turnover with bank business credits to automatically flag revenue inflation, GST evasion, and circular trading patterns.
- **Web Research Agent**: Uses DuckDuckGo to automatically perform web searches on companies and promoters, classifying results (fraud, litigation, regulatory action) using LLMs.
- **Credit Rule Engine**: A rule engine that evaluates 10 comprehensive metrics including Debt-to-Equity, Current Ratio, NCLT insolvency checks, and composite risk scores to reach an APPROVE, REVIEW, or REJECT decision.

## Architecture

1. **Ingestor Module (`intellicredit/ingestor/`)**
   - `pageindex_rag.py`: AI-powered PDF parsing
   - `gst_parser.py`: GST portal JSON parser
   - `bank_parser.py`: Bank CSV parser
   - `reconciler.py`: GST vs Bank cross-referencing
2. **Research Agent (`intellicredit/research_agent.py`)**
   - Automated query generation and web scraping
3. **Rule Engine (`intellicredit/rule_engine.py`)**
   - Final evaluation against credit policies

## Installation

```bash
# Clone the repository
git clone https://github.com/AdityaTiwari64/VEDA.git
cd VEDA

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows

# Install dependencies
pip install -r intellicredit/requirements.txt
```

### Configuration (.env)
Create a `.env` file in the root directory:
```env
DEFAULT_PROVIDER=openrouter  # or 'ollama'
DEFAULT_MODEL=llama3
OPENROUTER_API_KEY=your_api_key_here
```

## Usage

### Using the full pipeline
You can run the full end-to-end pipeline (Ingestion + Rule Engine) using the provided script:
```bash
python run_navya_report.py
```

### Running the CLI
```bash
python intellicredit/main.py
```

### Testing the entire suite
```bash
python test_full_pipeline.py
```
