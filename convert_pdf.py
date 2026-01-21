"""
Step 1: PDF to Markdown Conversion

Supports two modes configured via .env:
1. 'docling' - Local processing (high quality tables, slow on CPU without GPU)
2. 'gemini'  - Cloud processing (fast, good structure, requires API key)
"""

import logging
import time
import argparse
from pathlib import Path
from typing import Dict, Tuple, Any

from tqdm import tqdm
from utils import get_output_path, setup_logging, load_config

# Provider-specific imports (lazy loaded in functions to avoid startup cost/errors)
# from docling.document_converter import ...
# from google import genai ...

logger = logging.getLogger("relatio.convert_pdf")


def convert_pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    verbose: bool = False,
    **kwargs
) -> Tuple[Path, Dict[str, Any]]:
    """
    Dispatcher function to select conversion strategy based on config.
    """
    config = load_config()
    provider = config.get('conversion_provider', 'docling').lower()
    
    if provider == 'gemini':
        return _convert_with_gemini(pdf_path, output_dir, config, verbose)
    else:
        return _convert_with_docling(pdf_path, output_dir, config, verbose)


def _convert_with_gemini(pdf_path: str, output_dir: str, config: dict, verbose: bool = False):
    """Convert using Google Gemini File API (Fast, Cloud)."""
    from google import genai
    from google.genai import types
    
    start_time = time.time()
    pdf_file = Path(pdf_path)
    
    api_key = config.get('api_key')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY required for Gemini conversion")
        
    client = genai.Client(api_key=api_key)
    model_name = config.get('track_a_model', 'gemini-3.0-flash-preview')
    
    # 1. Upload
    if verbose: print("Step 1/3: Uploading PDF to Gemini...")
    upload_start = time.time()
    
    try:
        uploaded_file = client.files.upload(file=str(pdf_file))
        
        # Wait for processing
        with tqdm(total=100, desc="   Processing", bar_format="{desc}: {bar} {elapsed}s", colour="cyan", disable=not verbose) as pbar:
            while uploaded_file.state == "PROCESSING":
                time.sleep(1)
                uploaded_file = client.files.get(name=uploaded_file.name)
                if pbar.n < 90: pbar.update(10)
            pbar.n = 100
            pbar.refresh()
            
        if uploaded_file.state == "FAILED":
            raise RuntimeError(f"File processing failed: {uploaded_file.error}")
            
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise
        
    if verbose: print(f"   Uploaded in {time.time() - upload_start:.2f}s\n")
    
    # 2. Generate
    if verbose: print(f"Step 2/3: Converting with {model_name}...")
    generate_start = time.time()
    
    prompt = """
    Convert this PDF document into accurate as it is, structured Markdown.
    
    IMPORTANT REQUIREMENTS:
    1. Preserve text-for-text content (no summarizing).
    2. Convert tables to Markdown tables.
    3. Keep headers and structure matching original.
    4. Provide EXPLICIT page markers in the format '[PAGE X]' (e.g., [PAGE 1], [PAGE 2]) at the start of every page's content.
    5. Output ONLY Markdown.
    """
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                prompt
            ]
        )
        
        # Extract content with proper error handling
        if not response or not response.text:
            logger.error(f"API returned empty response. Response object: {response}")
            raise ValueError("Gemini API returned empty content. The model may have refused to process the PDF or encountered an error.")
            
        content = response.text
        
        # Clean up uploaded file
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception as cleanup_error:
            logger.warning(f"Failed to delete uploaded file: {cleanup_error}")
            
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        # Try to clean up file even if generation failed
        try:
            client.files.delete(name=uploaded_file.name)
        except:
            pass
        raise
        
    if verbose: print(f"   Converted in {time.time() - generate_start:.2f}s\n")
    
    # 3. Save
    if verbose: print("Step 3/3: Saving Output...")
    markdown_path = get_output_path(pdf_path, output_dir, ".md")
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return _finish(markdown_path, start_time, page_count=0, verbose=verbose)


def _convert_with_docling(pdf_path: str, output_dir: str, config: dict, verbose: bool = False):
    """Convert using Docling (Local, High Quality Tables)."""
    from docling.document_converter import DocumentConverter
    
    start_time = time.time()
    
    if verbose: print("Step 1/3: Initializing Docling (Tables=True, OCR=False)...")
    converter = DocumentConverter() # Default config is what user validated
    
    if verbose: print("Step 2/3: Converting PDF (Local)...")
    convert_start = time.time()
    result = converter.convert(pdf_path)
    if verbose: print(f"   Converted in {time.time() - convert_start:.2f}s\n")
    
    if verbose: print("Step 3/3: Saving Output...")
    markdown_path = get_output_path(pdf_path, output_dir, ".md")
    
    # Export to markdown
    content = result.document.export_to_markdown()
    
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    page_count = 0
    if hasattr(result.document, 'num_pages'):
        page_count = result.document.num_pages
        
    return _finish(markdown_path, start_time, page_count, verbose=verbose)


def _finish(path, start_time, page_count, verbose: bool = False):
    total_time = time.time() - start_time
    if verbose: 
        print(f"   Saved to: {path.name}\n")
        
        print(f"{'='*60}")
        print("EXTRACTION COMPLETED")
        print(f"{'='*60}")
        print(f"PDF:              {path.name}")
        print(f"Time:             {total_time:.2f}s")
        if page_count:
            print(f"Pages:            {page_count}")
        print(f"{'='*60}\n")
    
    metadata = {
        'filename': path.name,
        'total_pages': page_count,
        'output_dir': str(path.parent),
        'markdown_size_kb': path.stat().st_size / 1024
    }
    return path, metadata


if __name__ == "__main__":
    setup_logging(debug=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--provider", help="Override provider (docling/gemini)")
    args = parser.parse_args()
    
    config = load_config()
    if args.provider:
        config['conversion_provider'] = args.provider
        
    convert_pdf_to_markdown(args.pdf_path, config['output_dir'], verbose=True)