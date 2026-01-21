# RELATIO

**Structured reference extraction for SEBI compliance**

Extract and map regulatory relationships from SEBI circular PDFs into structured JSON data for knowledge graph construction and compliance workflows.

---

## Problem Statement

The Head of Compliance for a major Indian bank must ensure compliance with SEBI circulars while being able to respond to SEBI, customers, and intermediaries about the bank's compliance posture. 

**The Challenge:** Most SEBI circulars reference other documentation (circulars, regulations, laws), and since they're all in PDF format, it's difficult to:
- Track which circular supersedes which
- Understand the full compliance context
- Map relationships across regulatory documents
- Respond quickly to compliance queries

**The Solution:** RELATIO uses a dual-track LLM pipeline to automatically extract these references into structured JSON, providing building blocks for knowledge graphs and downstream compliance applications.

---

## Architecture

RELATIO uses a **3-stage dual-track pipeline** for robust, high-recall reference extraction:

```mermaid
graph TB
    Start([PDF Circular]) --> Stage1
    
    subgraph Stage1[" Stage 1: PDF Conversion "]
        PDF[PDF Input] --> Choice{Conversion Provider}
        Choice -->|Docling| DoclingSys[Docling Converter]
        Choice -->|Gemini| GeminiAPI[Gemini Files API]
        DoclingSys --> MD[Markdown Output]
        GeminiAPI --> MD
        MD --> Meta[Metadata: Pages, Tables, Structure]
    end
    
    MD --> Split{Dual-Track Processing}
    
    subgraph Stage2A[" Track A: Global Context "]
        Split -->|Full Document| FileAPI[Google File API Upload]
        FileAPI --> LLM_A[LLM Model<br/>Large Context Window]
        LLM_A --> GlobalExtract[Extract All References<br/>Cross-page Analysis]
        GlobalExtract --> TrackA_JSON[track_a.json]
    end
    
    subgraph Stage2B[" Track B: Agentic Exploration "]
        Split -->|File Path| FSExplorer[fs-explorer Agent]
        FSExplorer --> Tools{Agentic Tools}
        Tools --> Parse[parse_file]
        Tools --> Grep[grep_search]
        Tools --> Read[read_section]
        Parse & Grep & Read --> LLM_B[LLM Model<br/>Multi-step Reasoning]
        LLM_B -->|Iterative Search| AgenticExtract[Tool-based Discovery<br/>Tables, Footnotes, Annexures]
        AgenticExtract --> TrackB_JSON[track_b.json]
    end
    
    TrackA_JSON --> Stage3
    TrackB_JSON --> Stage3
    MD --> Stage3
    
    subgraph Stage3[" Stage 3: AI Consensus "]
        Merge[AI-Powered Merger] --> LLM_C[LLM Model<br/>Consensus Engine]
        LLM_C --> Dedup[Deduplication]
        Dedup --> Validate[Conflict Resolution]
        Validate --> Confidence[Confidence Scoring]
        Confidence --> Final[final_references.json]
    end
    
    Final --> Output([Structured JSON Output<br/>Ready for Knowledge Graphs & APIs])
```




### Why Dual-Track?

- **Track A (Global):** Catches cross-document patterns and implicit references using full-context analysis
- **Track B (Agentic):** Finds hidden references in tables, footnotes, and annexures through iterative tool-based exploration
- **Consensus:** AI merger validates and deduplicates, assigning confidence scores based on agreement

**Key Design:** Docling runs only once (Stage 1). Track B uses fs-explorer which has its own document parsing, avoiding redundant PDF processing.

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Google Gemini API Key** - Get one free at [Google AI Studio](https://aistudio.google.com/welcome)

### Installation

**Step 1: Clone and Navigate**

```powershell
# If cloning from repository
git clone https://github.com/shoryasethia/relatio
cd relatio
```

**Step 2: Create Virtual Environment**

```powershell
# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# On Linux/Mac:
# source .venv/bin/activate
```

**Step 3: Install Dependencies**

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt
```

**Step 4: Configure API Key and Models**

```powershell
# Copy the example environment file
copy .env.example .env

# Edit .env and configure your settings
notepad .env
```

**Required configuration in `.env`:**
```env
# Your Gemini API key (REQUIRED)
GOOGLE_API_KEY=your_actual_api_key_here

# Choose your Gemini models (defaults shown, you can change)
TRACK_A_MODEL=gemini-3-flash-preview
TRACK_B_MODEL=gemini-3-flash-preview
CONSENSUS_MODEL=gemini-3-flash-preview
```

---

## Usage

### Basic Extraction

```powershell
# Ensure virtual environment is activated
.venv\Scripts\activate

# Run on a SEBI circular PDF
python main.py path\to\sebi_circular.pdf

# Example with sample file
python main.py samples\1767957683485.pdf
```

### Advanced Options

```powershell
# Custom output directory
python main.py circular.pdf --output results\

# Enable debug logging for troubleshooting
python main.py circular.pdf --debug

# Combine options
python main.py circular.pdf --output custom_folder\ --debug
```

### Output Structure

After running, you'll find results organized in subdirectories:

```
output\
└── <pdf_name>\
    ├── <pdf_name>.md                # Stage 1: Markdown conversion
    ├── <pdf_name>_track_a.json      # Stage 2A: Global context results
    ├── <pdf_name>_track_b.json      # Stage 2B: Agentic search results
    └── <pdf_name>_final.json        # Stage 3: FINAL MERGED OUTPUT ⭐
```

The `*_final.json` file contains the complete, validated reference extraction.

---

## Configuration

All settings are managed via the `.env` file:

### Required Configuration

```env
# Your Google Gemini API key (REQUIRED)
GOOGLE_API_KEY=your_api_key_here
```

### Model Selection

Choose any Gemini models available in your API tier:

```env
# You can use different models for each stage
TRACK_A_MODEL=gemini-2.0-flash-exp      # Global context extraction
TRACK_B_MODEL=gemini-2.0-flash-exp      # Agentic search
CONSENSUS_MODEL=gemini-2.0-flash-exp    # Consensus validation
```

See [.env.example](https://github.com/shoryasethia/relatio/blob/main/.env.example) for all available options.

---

## Output Schema

The final JSON output follows a structured schema designed for easy integration with knowledge graphs, databases, and compliance APIs.

### Source Document Metadata

```json
{
  "source_document": {
    "filename": "sebi_circular_2024_120.pdf",
    "circular_title": "Master Circular on Portfolio Management Services",
    "sebi_reference_number": "SEBI/HO/MIRSD/2024/120",
    "date_issued": "2024-09-15",
    "total_pages": 47,
    "processing_timestamp": "2026-01-21T12:53:00Z"
  }
}
```

### Extracted References

Each reference includes rich metadata for knowledge graph construction:

```json
{
  "references": [
    {
      "reference_id": "REF001",
      "referenced_document_title": "Guidelines on Portfolio Management Services",
      "referenced_sebi_number": "SEBI/HO/MIRSD/2023/105",
      "referenced_date": "2023-03-20",
      "document_type": "SEBI_CIRCULAR",
      "relationship_type": "SUPERSEDES",
      "page_numbers": [1, 2],
      "exact_citation_text": "This circular supersedes SEBI/HO/MIRSD/2023/105...",
      "context_paragraph": "Full paragraph providing context...",
      "section_location": "Preamble - Section 1.1",
      "confidence_score": 0.98,
      "extraction_source": "BOTH"
    }
  ]
}
```

**Document Types:**
- `SEBI_CIRCULAR` - SEBI circulars
- `ACT` - Legislative acts (e.g., SEBI Act 1992)
- `REGULATION` - SEBI regulations
- `GUIDELINE` - Guidelines and master circulars
- `NOTIFICATION` - Official notifications
- `OTHER` - Other regulatory documents

**Relationship Types:**
- `SUPERSEDES` - Replaces the referenced document entirely
- `AMENDS` - Modifies specific parts
- `REPEALS` - Cancels/invalidates
- `REFERS_TO` - General reference
- `CLARIFIES` - Provides additional explanation
- `DERIVES_FROM` - Based on/authorized by

**Confidence Scores:**
- **High (0.90-1.0):** Found by both tracks, validated
- **Medium (0.70-0.89):** Found by one track, reliable
- **Low (0.50-0.69):** Needs manual review

**Extraction Source:**
- `BOTH` - Found by Track A and Track B (highest confidence)
- `TRACK_A` - Found only by global context analysis
- `TRACK_B` - Found only by agentic exploration

### Summary Statistics

```json
{
  "summary_statistics": {
    "total_references_found": 7,
    "by_document_type": {
      "SEBI_CIRCULAR": 5,
      "ACT": 1,
      "REGULATION": 1
    },
    "by_relationship_type": {
      "SUPERSEDES": 1,
      "REFERS_TO": 4,
      "AMENDS": 2
    },
    "by_confidence_level": {
      "high": 6,
      "medium": 1,
      "low": 0
    }
  }
}
```

### Processing Metadata

```json
{
  "processing_metadata": {
    "pipeline_version": "1.0.0",
    "models_used": {
      "track_a": "gemini-2.0-flash-exp",
      "track_b": "gemini-2.0-flash-exp",
      "consensus": "gemini-2.0-flash-exp"
    },
    "processing_time_seconds": 245,
    "track_a_references_found": 6,
    "track_b_references_found": 5,
    "merged_count": 7,
    "duplicates_removed": 4,
    "validation_status": "COMPLETED"
  }
}
```

---

## How It Works

### Stage 1: PDF to Markdown

You can choose between two conversion providers via `.env` configuration:

**Option A: Docling (Local)**
- **Tool:** Docling library from IBM Research
- **Process:** Converts PDF locally on your machine
- **Pros:** High-quality table preservation, works offline, no API costs
- **Cons:** Slower on CPU without GPU acceleration
- **Use when:** You need maximum table accuracy or want offline processing

**Option B: Gemini Files API (Cloud)**
- **Tool:** Google Gemini Files API with LLM-powered conversion
- **Process:** Uploads PDF to Gemini, uses AI to convert to markdown
- **Pros:** Fast, good structure preservation, cloud processing
- **Cons:** Requires API key, uses API quota, needs internet
- **Use when:** You want faster processing and have API access

**Both methods:**
- Preserve page numbers and document hierarchy
- Output clean markdown for LLM processing
- Maintain metadata (pages, tables, structure)

**Configuration:** Set `CONVERSION_PROVIDER=docling` or `CONVERSION_PROVIDER=gemini` in `.env`

### Stage 2A: Global Context (Track A)

- **Method:** Full-document analysis with Google File API
- **Approach:** Uploads markdown to LLM for single-pass comprehensive extraction
- **Strengths:** Cross-page references, implicit relationships, document-wide context, **ideal for shorter documents**
- **Strategy:** Leverages large context windows to understand the entire circular

### Stage 2B: Agentic Search (Track B)

- **Tool:** fs-explorer (agentic file search framework)
- **Approach:** Multi-step reasoning with tool use
- **Tools Available:**
  - `parse_file` - Read document sections
  - `grep_search` - Pattern matching
  - `read_section` - Targeted content extraction
- **Strengths:** Tables, footnotes, annexures, iterative discovery, **document size independent**
- **Strategy:** Agent decides where to look next based on findings

### Stage 3: Consensus Validation

- **Process:** AI-powered merger and deduplication
- **Steps:**
  1. Merge results from both tracks
  2. Deduplicate identical references
  3. Resolve conflicts (pick best metadata)
  4. Assign confidence scores based on track agreement
  5. Validate against source document

**Smart Optimization:** Docling runs only once in Stage 1. Track B's fs-explorer has built-in document parsing, avoiding redundant processing.

---

## Why This Approach? (Not Traditional RAG)

### Limitations of Traditional RAG

Traditional RAG (Retrieval-Augmented Generation) has fundamental limitations for regulatory document analysis:

1. **Chunks lose context** - Splitting circulars destroys relationships between sections. A reference on page 5 to "Annexure B on page 23" becomes meaningless when chunked.

2. **Cross-references are invisible** - "See Exhibit B" or "as mentioned in Section 3.2" mean nothing to embeddings since the context is fragmented.

3. **Similarity ≠ Relevance** - Semantic matching finds similar text, not logical connections. Two sections might be semantically similar but reference completely different regulations.

4. **Table structure is lost** - RAG chunking breaks tables apart, making it impossible to extract tabular references accurately.

### My Solution: Dual-Track Agentic Extraction

Inspired by **[agentic-file-search](https://github.com/PromtEngineer/agentic-file-search)** and **[LLM council](https://github.com/karpathy/llm-council)** , I use:

**Track A (Global Context):**
- Analyzes the **entire document** without chunking
- Leverages Gemini's large context window (up to 1M tokens)
- Understands cross-page relationships and document structure
- Similar to having an expert read the full circular once

**Track B (Agentic Exploration):**
- Uses **fs-explorer** framework with 6 specialized tools
- Agent iteratively explores: `scan_folder` → `parse_file` → `grep` → `read`
- Follows cross-references dynamically (e.g., "see page 23" → agent reads page 23)
- Focuses on tables, footnotes, and annexures that Track A might miss

**Consensus Stage (LLM Council):**
- Merges both perspectives using AI consensus
- Deduplicates and resolves conflicts
- Assigns confidence based on agreement (both tracks found = high confidence)
- Similar to expert panel reviewing findings

### Why It Works Better

| Aspect | Traditional RAG | My Agentic Approach |
|--------|----------------|---------------------|
| Context preservation | ❌ Lost in chunking | ✅ Full document analysis |
| Cross-references | ❌ Invisible | ✅ Agent follows them |
| Table handling | ❌ Structure destroyed | ✅ Parsed intact |
| Iterative search | ❌ Static retrieval | ✅ Dynamic exploration |
| Confidence scoring | ❌ Single source | ✅ Dual-track validation |

---

## Example Execution

Here's a real extraction run on a 7-page SEBI circular using `gemini-2.5-flash`:

**View the complete example output:** [output/1767957683485](https://github.com/shoryasethia/relatio/tree/main/output/1767957683485)

```powershell
(.venv) PS C:\Users\shory\Desktop\relatio> python main.py .\samples\1767957683485.pdf

======================================================================
            RELATIO: MAPPING THE DNA OF REGULATORY EVOLUTION
======================================================================

  SOURCE PDF:  1767957683485.pdf
  OUTPUT DIR:  output\1767957683485

[1/4] PDF Conversion (Gemini)...
2026-01-21 18:48:01,605 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
      [  DONE  ] Markdown Generated: 1767957683485.md

[2/4] Global Extraction (Track A)...
2026-01-21 18:48:25,415 - relatio.extract_global - INFO - Starting Track A: Global Context Analysis
2026-01-21 18:48:27,869 - relatio.extract_global - INFO - Uploaded file: files/5ts5e5fxpsmw
2026-01-21 18:48:27,870 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2026-01-21 18:48:51,466 - relatio.extract_global - INFO - Deleted uploaded file
2026-01-21 18:48:51,467 - relatio.extract_global - INFO - Track A extracted 5 references
✓ Saved: output\1767957683485\1767957683485_track_a.json
      [  DONE  ] Track A Result: 1767957683485_track_a.json

[3/4] Agentic Extraction (Track B)...
2026-01-21 18:48:51,471 - relatio.extract_agentic - INFO - Starting Track B: Agentic Exploration
2026-01-21 18:48:51,474 - relatio.extract_agentic - INFO - Agent working directory: output\1767957683485
2026-01-21 18:48:51,510 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2026-01-21 18:48:55,284 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2026-01-21 18:49:16,978 - relatio.extract_agentic - INFO - Agent completed successfully
2026-01-21 18:49:16,980 - relatio.extract_agentic - INFO - Track B extracted 5 references
✓ Saved: output\1767957683485\1767957683485_track_b.json
      [  DONE  ] Track B Result: 1767957683485_track_b.json

[4/4] Final Consensus & Merging...
2026-01-21 18:49:17,081 - google_genai.models - INFO - AFC is enabled with max remote calls: 10.
2026-01-21 18:50:31,127 - relatio.merge_consensus - ERROR - AI Consensus failed: Expecting value: line 40 column 25 (char 1857)
2026-01-21 18:50:31,130 - relatio.merge_consensus - INFO - Filtering out self-reference: HO/38/44/12(1)2026-MIRSD-TPD1
✓ Saved: output\1767957683485\1767957683485_final.json
      [  DONE  ] Final Output: 1767957683485_final.json

----------------------------------------------------------------------

======================================================================
                           EXECUTION SUMMARY
======================================================================

  STAGE           DURATION   STATUS
  --------------  ---------  -------
  1. Conversion   27.47s     DONE
  2. Track A      26.06s     DONE
  3. Track B      25.51s     DONE
  4. Consensus    74.15s     DONE

      [ TOTAL TIME ]   : 153.19s (2.5 minutes)
      [ FINAL JSON ]   : output\1767957683485\1767957683485_final.json

======================================================================
```

### Performance Notes

- **Document:** 7 pages ([sample PDF](https://github.com/shoryasethia/relatio/blob/main/samples/1767957683485.pdf))
- **Total Time:** ~2.5 minutes
- **Model:** gemini-2.5-flash
- **References Found:** 8 unique references
- **Rate Limits:** 2 RPM, 5.2K TPM / 250K daily, 3 RPD / 20 ([view limits](https://ai.google.dev/pricing))

---

## Testing

Run extraction on a SEBI circular PDF:

```powershell
# Basic usage
python main.py path\to\sebi_circular.pdf

# With debug logging
python main.py path\to\sebi_circular.pdf --debug

# Custom output directory
python main.py path\to\sebi_circular.pdf --output results\
```

---

## Evaluation

### Manual Verification Process

1. **Open Side-by-Side:** Source PDF and `*_final.json`
2. **Count References:** Manually identify all regulatory references in the PDF
3. **Compare:** Check extraction accuracy, page numbers, citation text
4. **Review Low-Confidence:** Manually verify references with confidence < 0.7

### Metrics

- **Recall:** References Found / Total Actual References (Target: **>90%**)
- **Precision:** Correct References / Total Extracted (Target: **>85%**)
- **F1 Score:** Harmonic mean of precision and recall (Target: **>87%**)

### Confidence-Based Review

- **High (>0.9):** Spot-check only (~5% sample)
- **Medium (0.7-0.9):** Review carefully (~25% sample)
- **Low (<0.7):** Manual verification required (100%)

---

## Limitations

### Current Known Issues (v1.0)

1. **Implicit References** (~5-10% miss rate)
   - Phrases like "aforementioned circular" without explicit citation
   - **Mitigation:** Track B specifically searches for these patterns

2. **Old Citation Formats** (~10-15% degradation on pre-2010 circulars)
   - Pre-2010 SEBI circulars use different reference patterns
   - **Mitigation:** Extend regex patterns in [utils.py](https://github.com/shoryasethia/relatio/blob/main/utils.py)

3. **Scanned PDFs** (OCR-dependent accuracy)
   - Requires `ENABLE_OCR=true` in `.env`
   - Processing time increases 3-5x
   - **Mitigation:** Use high-quality PDFs when available

4. **Processing Time** (~2.5 minutes per document)
   - Single-PDF processing focus per assignment requirements

5. **API Rate Limits** (Free tier: 2 RPM, 5.2K TPM)
   - With rate limits: 2 requests/min, 3 requests/day for free tier
   - **Mitigation:** Upgrade to paid tier for higher quotas

---

## Project Structure

```
relatio/
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── requirements-lock.txt     # Locked dependency versions
├── main.py                   # End to end pipeline
├── convert_pdf.py            # Stage 1: PDF → Markdown
├── extract_global.py         # Stage 2A: Global context (Track A)
├── extract_agentic.py        # Stage 2B: Agentic search (Track B)
├── merge_consensus.py        # Stage 3: Consensus validation
├── models.py                 # Pydantic data models (output schema)
├── utils.py                  # Shared utilities (logging, JSON, etc.)
├── samples/                  # Test PDFs
│   └── 1767957683485.pdf     # Example SEBI circular
└── output/                   # Extraction results (auto-created)
    └── 1767957683485/
        ├── 1767957683485.md
        ├── 1767957683485_track_a.json
        ├── 1767957683485_track_b.json
        └── 1767957683485_final.json  ⭐
```

## Dependencies

### Core Requirements

- **docling** ≥2.55.0 - PDF parsing and conversion
- **google-generativeai** ≥0.8.0 - Gemini API (legacy SDK)
- **google-genai** ≥1.55.0 - Gemini API (new SDK)
- **pydantic** ≥2.0.0 - Data validation and schema
- **python-dotenv** ≥1.0.0 - Environment configuration

### Agentic Search (Track B)

- **fs-explorer** - Agentic file search framework (from GitHub)
- **llama-index-workflows** ≥2.11.5 - Agentic orchestration
- **fastapi** ≥0.115.0 - Web server for fs-explorer
- **uvicorn** ≥0.34.0 - ASGI server
- **websockets** ≥14.0 - WebSocket support

### Utilities

- **requests** ≥2.31.0 - HTTP client
- **tqdm** ≥4.66.0 - Progress bars
- **reportlab** ≥4.4.7 - PDF utilities

See [requirements.txt](https://github.com/shoryasethia/relatio/blob/main/requirements.txt) for complete list.

---

## License

GPL-3.0 License - See [LICENSE](https://github.com/shoryasethia/relatio/blob/main/LICENSE) file for details