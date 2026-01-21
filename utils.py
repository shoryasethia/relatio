"""
Shared utility functions for the SEBI circular extraction pipeline.

This module provides common functionality used across all pipeline stages,
including configuration loading, logging setup, file operations, and helpers.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

import requests
from dotenv import load_dotenv
import shutil


def load_config() -> Dict[str, Any]:
    """
    Load configuration from .env file and environment variables.
    
    Returns:
        Dict containing all configuration settings
        
    Raises:
        RuntimeError: If required API key is missing
    """
    # Load .env file from project root
    load_dotenv()
    
    # Get required API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise RuntimeError(
            "GOOGLE_API_KEY not found or not configured!\n"
            "Please copy .env.example to .env and add your API key.\n"
            "Get one at: https://aistudio.google.com/welcome"
        )
    
    # Build comprehensive configuration dictionary
    config = {
        # API Configuration
        "api_key": api_key,
        "track_a_model": os.getenv("TRACK_A_MODEL", "gemini-2.0-flash-exp"),
        'track_b_model': os.getenv('TRACK_B_MODEL', 'gemini-2.0-flash-exp'),
        'consensus_model': os.getenv('CONSENSUS_MODEL', 'gemini-2.0-flash-exp'),
        'consensus_fallback_model': os.getenv('CONSENSUS_FALLBACK_MODEL', 'gemini-2.0-flash'),
        'conversion_provider': os.getenv('CONVERSION_PROVIDER', 'docling').lower(),  # docling or gemini
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "api_timeout": int(os.getenv("API_TIMEOUT", "120")),
        "model_temperature": float(os.getenv("MODEL_TEMPERATURE", "0.1")),
        "max_output_tokens": int(os.getenv("MAX_OUTPUT_TOKENS", "8192")),
        
        # Pipeline Configuration
        "output_dir": os.getenv("OUTPUT_DIR", "output"),
        "samples_dir": os.getenv("SAMPLES_DIR", "samples"),
        "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true",
        "log_file": os.getenv("LOG_FILE", ""),
        
        # Docling Configuration
        "enable_ocr": os.getenv("ENABLE_OCR", "false").lower() == "true",
        "preserve_tables": os.getenv("PRESERVE_TABLES", "true").lower() == "true",
        "extract_images": os.getenv("EXTRACT_IMAGES", "false").lower() == "true",
        
        # Agentic Search Configuration
        "max_search_iterations": int(os.getenv("MAX_SEARCH_ITERATIONS", "10")),
        "agentic_verbose": os.getenv("AGENTIC_VERBOSE", "false").lower() == "true",
        
        # Validation Configuration
        "min_confidence_threshold": float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.5")),
        "strict_validation": os.getenv("STRICT_VALIDATION", "false").lower() == "true",
        
        # Output Configuration
        "pretty_json": os.getenv("PRETTY_JSON", "true").lower() == "true",
        "include_metadata": os.getenv("INCLUDE_METADATA", "true").lower() == "true",
        "save_intermediate": os.getenv("SAVE_INTERMEDIATE", "true").lower() == "true",
    }
    
    return config


def setup_logging(debug: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """
    Configure logging for the pipeline.
    
    Args:
        debug: Enable DEBUG level logging
        log_file: Optional file path to write logs
        
    Returns:
        Configured logger instance
    """
    # Set logging level
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers
    )
    
    # Suppress verbose third-party logs
    logging.getLogger("docling").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("filelock").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("docling_ibm_models").setLevel(logging.WARNING)
    
    # Suppress Pydantic V2 warnings if feasible or via filter
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
    warnings.filterwarnings("ignore", category=FutureWarning)
    
    return logging.getLogger("relatio")


def ensure_directory(path: str) -> Path:
    """
    Create directory if it doesn't exist and return Path object.
    
    Args:
        path: Directory path to create
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_output_path(input_pdf: str, output_dir: str, suffix: str) -> Path:
    """
    Generate output file path based on input PDF name.
    
    Args:
        input_pdf: Path to input PDF file
        output_dir: Output directory
        suffix: File suffix/extension (e.g., '.md', '.json')
        
    Returns:
        Path object for output file
    """
    # Get base name without extension
    base_name = Path(input_pdf).stem
    
    # Create output directory
    output_path = ensure_directory(output_dir)
    
    # Return full path with suffix
    return output_path / f"{base_name}{suffix}"


def repair_json(text: str) -> str:
    """Attempt to repair common LLM JSON issues like truncation or missing brackets."""
    if not text: return ""
    
    # 1. Find start
    first_bracket = text.find('[')
    first_brace = text.find('{')
    
    start = -1
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        start = first_bracket
    elif first_brace != -1:
        start = first_brace
        
    if start == -1: return text
    
    # 2. Extract and balance
    target = text[start:].strip()
    braces = 0
    brackets = 0
    in_string = False
    escape = False
    
    clean_text = ""
    for char in target:
        clean_text += char
        if char == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if char == '{': braces += 1
            elif char == '}': braces -= 1
            elif char == '[': brackets += 1
            elif char == ']': brackets -= 1
        escape = (char == '\\' and not escape)

    # 3. Clean trailing mess and close
    clean_text = clean_text.strip()
    # Remove trailing commas or partial property names
    while clean_text and (clean_text.endswith(',') or clean_text[-1].isalnum() or clean_text.endswith('"') or clean_text.endswith(':')):
        if clean_text.endswith('}') or clean_text.endswith(']'): break
        clean_text = clean_text[:-1].strip()
        
    while braces > 0:
        clean_text += '}'
        braces -= 1
    while brackets > 0:
        clean_text += ']'
        brackets -= 1
        
    return clean_text


def save_json(data: Any, filepath: Path, pretty: bool = True) -> None:
    """
    Save data as JSON file with optional pretty printing.
    
    Args:
        data: Data to serialize (dict, list, or Pydantic model)
        filepath: Where to save the JSON file
        pretty: Whether to pretty-print with indentation
    """
    # Ensure parent directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert Pydantic models to dict
    if hasattr(data, 'model_dump'):
        data = data.model_dump()
    
    # Write JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, ensure_ascii=False)
    
    print(f"✓ Saved: {filepath}")


def load_json(filepath: Path) -> Dict[str, Any]:
    """
    Load JSON file and return as dictionary.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Parsed JSON as dictionary
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def download_pdf(url: str, output_path: Path) -> Path:
    """
    Download PDF from URL to specified path.
    
    Args:
        url: URL of the PDF to download
        output_path: Where to save the downloaded file
        
    Returns:
        Path to downloaded file
        
    Raises:
        requests.RequestException: If download fails
    """
    print(f"Downloading: {url}")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Download with progress
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    
    # Write to file
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✓ Downloaded: {output_path}")
    return output_path


def extract_sebi_reference(text: str) -> Optional[str]:
    """
    Extract SEBI reference number from text using regex patterns.
    
    Common patterns:
    - SEBI/HO/MIRSD/2024/120
    - SEBI/IMD/CIR No. 18/198647/2010
    - SEBI (Portfolio Managers) Regulations, 2020
    
    Args:
        text: Text to search for SEBI reference
        
    Returns:
        Extracted reference or None if not found
    """
    patterns = [
        r'SEBI/[A-Z]+/[A-Z\-]+/\d+/\d+',  # SEBI/HO/MIRSD/2024/120
        r'SEBI/[A-Z]+/CIR\s+No\.\s+\d+/\d+/\d+',  # SEBI/IMD/CIR No. 18/198647/2010
        r'SEBI\s*\([^)]+\)\s*Regulations,?\s*\d{4}',  # SEBI (Portfolio Managers) Regulations, 2020
        r'SEBI\s*Act,?\s*\d{4}',  # SEBI Act, 1992
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    return None


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2m 30s", "45s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}m {remaining_seconds}s"


def calculate_confidence(
    found_by_both: bool,
    validated_in_source: bool,
    has_page_numbers: bool
) -> float:
    """
    Calculate confidence score based on extraction agreement and validation.
    
    Args:
        found_by_both: Whether both tracks found this reference
        validated_in_source: Whether reference text was validated in source
        has_page_numbers: Whether page numbers are available
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    base_score = 0.7  # Base confidence for any extraction
    
    # Boost for agreement between tracks
    if found_by_both:
        base_score += 0.2
    
    # Boost for validation in source document
    if validated_in_source:
        base_score += 0.1
    
    # Small boost for having page numbers
    if has_page_numbers:
        base_score += 0.05
    
    # Cap at 0.99 (never 100% certainty with AI)
    return min(base_score, 0.99)


def normalize_citation_text(text: str) -> str:
    """
    Normalize citation text by removing extra whitespace and standardizing format.
    
    Args:
        text: Raw citation text
        
    Returns:
        Normalized citation text
    """
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Normalize common patterns
    text = text.replace("Circular No.", "Circular")
    text = text.replace("circular no.", "circular")
    
    return text


# --- Terminal UI Helpers ---

def print_banner(text: str):
    """Print a clean, visually appealing banner."""
    width = 70
    print("\n" + "=" * width)
    print(f"  {text.upper()}".center(width))
    print("=" * width + "\n")

def print_step(current: int, total: int, description: str):
    """Print a standardized step indicator."""
    print(f"[{current}/{total}] {description}...")

def print_status(label: str, message: str, status: str = "DONE"):
    """
    Print a status line with a visual indicator.
    Status can be: DONE, FAIL, SKIP, OK, WARN
    """
    indicators = {
        "DONE": "[  DONE  ]",
        "FAIL": "[  FAIL  ]",
        "SKIP": "[  SKIP  ]",
        "OK":   "[   OK   ]",
        "WARN": "[  WARN  ]"
    }
    ind = indicators.get(status, f"[ {status} ]")
    print(f"      {ind} {label}: {message}")

def print_table(headers: List[str], rows: List[List[Any]]):
    """Print data in a clean ASCII table."""
    if not rows:
        return
        
    # Find column widths
    cols = len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(row[i])))
            
    # Print header
    header_line = "  "
    sep_line = "  "
    for i in range(cols):
        header_line += headers[i].ljust(widths[i] + 3)
        sep_line += "-" * (widths[i] + 1) + "  "
        
    print("\n" + header_line)
    print(sep_line)
    
    # Print rows
    for row in rows:
        row_line = "  "
        for i in range(cols):
            row_line += str(row[i]).ljust(widths[i] + 3)
        print(row_line)
    print("")
