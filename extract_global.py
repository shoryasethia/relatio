"""
Step 2A: Global Context Reference Extraction (Track A)

This module uses an LLM with File API to analyze the entire document,
leveraging the model's large context window to understand cross-references
and implicit relationships between regulations.

Uses Google's File API for efficient file uploads instead of sending
raw content in prompts.
"""

import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

from google import genai
from google.genai import types

from models import Reference, ExtractionSource
from utils import load_json, save_json, get_output_path, repair_json


logger = logging.getLogger("relatio.extract_global")


# Prompt template for global reference extraction
GLOBAL_EXTRACTION_PROMPT = """You are an expert regulatory compliance analyst specializing in SEBI (Securities and Exchange Board of India) circulars and regulations.

Your task is to extract ALL references to other regulatory documents from the provided SEBI circular document.

**Instructions:**
1. Identify EVERY reference to external documents including:
   - Other SEBI circulars (e.g., SEBI/HO/MIRSD/2024/120)
   - SEBI Acts (e.g., SEBI Act, 1992)
   - SEBI Regulations (e.g., SEBI (Portfolio Managers) Regulations, 2020)
   - Notifications, Guidelines, and other regulatory documents

2. For EACH reference found, extract:
   - The full title of the referenced document
   - The SEBI reference number or Act/Regulation name
   - The date of the referenced document (if mentioned)
   - The type of document (SEBI_CIRCULAR, ACT, REGULATION, GUIDELINE, NOTIFICATION, OTHER)
   - How it relates to the current circular (SUPERSEDES, AMENDS, REPEALS, REFERS_TO, CLARIFIES, DERIVES_FROM)
   - The exact citation text as it appears in the document
   - The surrounding context (full paragraph or sentence)
   - The section where it appears (e.g., "Preamble", "Section 4", "Annexure A")

3. Pay special attention to:
   - Tables and annexures (often contain multiple references)
   - Footnotes and endnotes
   - Preambles and legal basis sections
   - Sections titled "Repealed", "Superseded", "Related Circulars", etc.
   - Implicit references like "the aforementioned circular" or "as specified earlier"

**Output Format:**
Return a valid JSON array of references. Each reference must have this structure:
{{
  "referenced_document_title": "string",
  "referenced_sebi_number": "string",
  "referenced_date": "YYYY-MM-DD or null",
  "document_type": "SEBI_CIRCULAR|ACT|REGULATION|GUIDELINE|NOTIFICATION|OTHER",
  "relationship_type": "SUPERSEDES|AMENDS|REPEALS|REFERS_TO|CLARIFIES|DERIVES_FROM",
  "exact_citation_text": "string - verbatim quote",
  "context_paragraph": "string - full paragraph with context",
  "section_location": "string - where in document"
}}

**Important:**
- Be thorough - missing a reference could have compliance implications
- Extract verbatim quotes for exact_citation_text
- Provide enough context to understand the relationship
- Return ONLY valid JSON, no additional text

Now extract all references from the document:
"""


def extract_global_references(
    markdown_path: Path,
    model_name: str,
    api_key: str,
    temperature: float = 0.1,
    max_output_tokens: int = 8192,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Extract references using LLM global context analysis with File API.
    
    This track uploads the markdown file using Google's File API,
    then processes it with the LLM for efficient handling of large documents.
    
    Args:
        markdown_path: Path to markdown file from Step 1
        model_name: LLM model to use
        api_key: API key for the LLM service
        temperature: Model temperature (lower = more deterministic)
        max_output_tokens: Maximum tokens in response
        verbose: Print progress to terminal
        
    Returns:
        List of extracted reference dictionaries
    """
    logger.info(f"Starting Track A: Global Context Analysis")
    if verbose:
        print(f"\nStep 2A: Global Context Analysis (Track A)")
        print(f"Model: {model_name}")
    
    # Initialize genai client
    client = genai.Client(api_key=api_key)
    
    try:
        # Upload the markdown file
        if verbose: print(f"→ Uploading markdown file to Google File API...")
        uploaded_file = client.files.upload(file=str(markdown_path))
        
        # Wait for file to be processed
        if verbose: print(f"→ Processing file...")
        while uploaded_file.state == "PROCESSING":
            time.sleep(1)
            uploaded_file = client.files.get(name=uploaded_file.name)
        
        if uploaded_file.state == "FAILED":
            raise ValueError(f"File processing failed: {uploaded_file.error}")
        
        if verbose: print(f"→ File uploaded successfully: {uploaded_file.display_name}")
        logger.info(f"Uploaded file: {uploaded_file.name}")
        
        # Generate content with the uploaded file
        if verbose: print("→ Sending to LLM for analysis...")
        
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type=uploaded_file.mime_type
                ),
                GLOBAL_EXTRACTION_PROMPT
            ],
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE"
                    )
                ]
            )
        )
        
        # Clean up - delete the uploaded file
        client.files.delete(name=uploaded_file.name)
        logger.info("Deleted uploaded file")
        
        # Extract text from response
        response_text = response.text
        
        if not response_text:
            logger.error("LLM returned empty response or was blocked by safety filters.")
            if verbose: print("✗ Track A received empty response (check safety filters).")
            return []
            
        logger.debug(f"Raw response: {response_text[:500]}...")
        
        # Parse JSON response with repair logic
        try:
            references = json.loads(response_text)
        except json.JSONDecodeError:
            logger.info("Standard JSON parse failed, attempting repair...")
            repaired_text = repair_json(response_text)
            try:
                references = json.loads(repaired_text)
                logger.info("Successfully repaired JSON.")
            except json.JSONDecodeError as e2:
                logger.error(f"Failed to parse even after repair: {e2}")
                logger.error(f"Repaired text was: {repaired_text}")
                return []
        
        # Ensure it's a list
        if not isinstance(references, list):
            logger.warning(f"Expected list, got {type(references)}. Wrapping in list.")
            references = [references] if references else []
        
        logger.info(f"Track A extracted {len(references)} references")
        
        return references
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response was: {response_text}")
        if verbose: print(f"✗ JSON parsing error. See logs for details.")
        return []
    
    except Exception as e:
        logger.error(f"Track A extraction failed: {e}")
        if verbose: print(f"✗ Extraction failed: {e}")
        return []


def run_track_a(
    markdown_path: Path,
    output_dir: str,
    config: Dict[str, Any],
    verbose: bool = False
) -> Path:
    """
    Run Track A extraction and save results.
    
    Args:
        markdown_path: Path to markdown from Step 1
        output_dir: Where to save Track A results
        config: Configuration dictionary
        verbose: Print progress to terminal
        
    Returns:
        Path to Track A JSON output
    """
    # Extract references
    references = extract_global_references(
        markdown_path=markdown_path,
        model_name=config['track_a_model'],
        api_key=config['api_key'],
        temperature=config['model_temperature'],
        max_output_tokens=config['max_output_tokens'],
        verbose=verbose
    )
    
    # Prepare output with metadata
    output_data = {
        "track": "A",
        "method": "global_context_analysis_file_api",
        "model": config['track_a_model'],
        "markdown_source": str(markdown_path),
        "references_found": len(references),
        "references": references
    }
    
    # Save to JSON
    output_path = get_output_path(str(markdown_path), output_dir, "_track_a.json")
    save_json(output_data, output_path, pretty=config['pretty_json'])
    
    return output_path


if __name__ == "__main__":
    """
    Standalone testing mode.
    
    Usage:
        python extract_global.py path/to/circular.md
    """
    import sys
    from utils import setup_logging, load_config
    
    # Setup logging
    setup_logging(debug=True)
    
    # Check arguments
    if len(sys.argv) < 2:
        print("Usage: python extract_global.py <markdown_file>")
        sys.exit(1)
    
    # Load configuration
    config = load_config()
    
    # Run Track A
    markdown_path = Path(sys.argv[1])
    output_path = run_track_a(markdown_path, config['output_dir'], config, verbose=True)
    
    print(f"\n✓ Track A complete! Results saved to: {output_path}")
