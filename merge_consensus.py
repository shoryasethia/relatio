"""
Step 3: Consensus Validation and Merging

Final Robust Edition:
- Fixes Pydantic validation by ensuring all required fields have defaults.
- Enforces strict deduplication after AI consensus.
- Improved error handling and logging.
- Supports quiet execution via verbose flag.
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models import (
    FinalOutput, SourceDocument, Reference, SummaryStatistics,
    ProcessingMetadata, DocumentType, RelationshipType, ExtractionSource,
    ValidationStatus
)
from utils import load_json, save_json, get_output_path

# Configure logging
logger = logging.getLogger("relatio.merge_consensus")

CONSENSUS_PROMPT = """You are a senior regulatory compliance expert. 

**GOAL:** Merge and deduplicate references from two AI extraction tracks into ONE final list.

**INPUTS:**
TRACK A: {track_a_summary}
TRACK B: {track_b_summary}

**INSTRUCTIONS:**
1. **Deduplicate:** References to the same document MUST be merged into a single entry.
2. **Select Best Info:** Pick the most complete title, SEBI number, and date.
3. **Combine Pages:** Combine all unique page numbers found.
4. **Merge Context:** Ensure the merged entry has a valid paragraph and citation text.

Return valid JSON: a list of objects matching the standard schema. No commentary.
"""

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5), 
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True
)
def generate_consensus_with_retry(client, model_name: str, prompt: str):
    return client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=16384,
            response_mime_type="application/json"
        )
    )

def deduplicate_locally(refs: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
    """Strict local deduplication to ensure 'merged' state."""
    title_groups = defaultdict(list)
    for r in refs:
        title_raw = str(r.get('referenced_document_title') or r.get('title') or '').lower()
        title_clean = re.sub(r'[^a-z0-9]', '', title_raw)[:60]
        title_groups[title_clean].append(r)
        
    final_refs = []
    dupes = 0
    
    for title_clean, group in title_groups.items():
        sebi_map = {}
        for r in group:
            raw_num = r.get('referenced_sebi_number') or r.get('sebi_number')
            if raw_num is None: raw_num = ""
            num = re.sub(r'[^a-zA-Z0-9]', '', str(raw_num).lower())
            
            if num in sebi_map:
                dupes += 1
                existing = sebi_map[num]
                pages = set(existing.get('page_numbers') or []) | set(r.get('page_numbers') or [])
                existing['page_numbers'] = sorted(list(pages))
            else:
                sebi_map[num] = r
                
        if "" in sebi_map and len(sebi_map) > 1:
            null_ref = sebi_map.pop("")
            dupes += 1
            target_key = [k for k in sebi_map.keys() if k != ""][0]
            existing = sebi_map[target_key]
            pages = set(existing.get('page_numbers') or []) | set(null_ref.get('page_numbers') or [])
            existing['page_numbers'] = sorted(list(pages))
            
        final_refs.extend(sebi_map.values())
            
    return final_refs, {'duplicates_removed': dupes, 'conflicts_resolved': 0}

def merge_with_ai_consensus(
    track_a_refs: List[Dict],
    track_b_refs: List[Dict],
    model_name: str,
    api_key: str,
    source_text: str = "",
    verbose: bool = False
) -> Tuple[List[Dict], Dict[str, int]]:
    if verbose: print(f"→ Using AI Consensus ({model_name})...")
    
    prompt = CONSENSUS_PROMPT.format(
        track_a_summary=json.dumps(track_a_refs, separators=(',', ':')),
        track_b_summary=json.dumps(track_b_refs, separators=(',', ':'))
    )
    
    client = genai.Client(api_key=api_key)
    
    try:
        response = generate_consensus_with_retry(client, model_name, prompt)
        result = json.loads(response.text)
        
        if isinstance(result, dict):
            merged_refs = result.get('merged_references') or result.get('references') or list(result.values())[0]
            if not isinstance(merged_refs, list): merged_refs = []
        elif isinstance(result, list):
            merged_refs = result
        else:
            merged_refs = []
            
        if verbose: print(f"✓ AI Consensus Success: {len(merged_refs)} entries received")
        
        merged_refs, stats = deduplicate_locally(merged_refs)
        
        if source_text:
            merged_refs = backfill_missing_pages(merged_refs, source_text)
            
        return merged_refs, stats

    except Exception as e:
        logger.error(f"AI Consensus failed: {e}")
        return merge_with_rules(track_a_refs, track_b_refs, source_text)

def merge_with_rules(track_a: List[Dict], track_b: List[Dict], source_text: str = "") -> Tuple[List[Dict], Dict[str, int]]:
    all_refs = track_a + track_b
    merged, stats = deduplicate_locally(all_refs)
    if source_text:
        merged = backfill_missing_pages(merged, source_text)
    return merged, stats

def backfill_missing_pages(refs: List[Dict], source_text: str) -> List[Dict]:
    page_map = build_page_map(source_text)
    for r in refs:
        if not r.get('page_numbers'):
            search = r.get('exact_citation_text') or r.get('context_paragraph') or r.get('referenced_document_title')
            if search:
                p = find_pages_for_text(search, source_text, page_map)
                if p:
                    r['page_numbers'] = p
    return refs

def build_page_map(text: str) -> Dict[int, int]:
    page_map = {}
    # Modern pattern [PAGE X] and legacy Page X
    matches = list(re.finditer(r'(?:\[PAGE\s+(\d+)\]|(?:^|\n|\f)\s*Page\s+(\d+))', text, re.IGNORECASE))
    if not matches:
        for i in range(len(text)//3000 + 1): page_map[i*3000] = i+1
        return page_map
    for m in matches:
        page_num = int(m.group(1) or m.group(2))
        page_map[m.start()] = page_num
    return page_map

def find_pages_for_text(snippet: str, full_text: str, page_map: Dict[int, int]) -> List[int]:
    try:
        idx = full_text.find(snippet[:50])
        if idx == -1: return []
        sorted_keys = sorted(page_map.keys())
        found = 1
        for k in sorted_keys:
            if k <= idx: found = page_map[k]
            else: break
        return [found]
    except: return []

def extract_source_metadata(md_text: str, pdf_name: str) -> Dict[str, Any]:
    """Extract source document metadata from markdown content."""
    lines = md_text.split('\n')[:50]  # Check first 50 lines
    
    metadata = {
        'filename': pdf_name,
        'circular_title': pdf_name,
        'sebi_reference_number': 'Unknown',
        'date_issued': None,
        'total_pages': 1
    }
    
    # Extract SEBI reference number (e.g., HO/38/44/12(1)2026-MIRSD-TPD1)
    for line in lines[:15]:
        match = re.search(r'([A-Z]+/\d+/\d+/[\d()]+[-A-Z\d]+)', line)
        if match:
            metadata['sebi_reference_number'] = match.group(1)
            break
    
    # Extract date (e.g., January 09, 2026)
    for line in lines[:15]:
        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', line)
        if match:
            month_map = {'January': '01', 'February': '02', 'March': '03', 'April': '04',
                        'May': '05', 'June': '06', 'July': '07', 'August': '08',
                        'September': '09', 'October': '10', 'November': '11', 'December': '12'}
            month = month_map[match.group(1)]
            day = match.group(2).zfill(2)
            year = match.group(3)
            metadata['date_issued'] = f"{year}-{month}-{day}"
            break
    
    # Extract subject/title (e.g., Sub: - Review of Framework...)
    for line in lines:
        if line.strip().startswith('**Sub:') or line.strip().startswith('Sub:'):
            title = re.sub(r'\*\*Sub:\s*-?\s*|\*\*|Sub:\s*-?\s*', '', line).strip()
            if title:
                metadata['circular_title'] = title
            break
    
    # Extract total pages (e.g., Page 7 of 7)
    page_matches = re.findall(r'Page\s+\*\*(\d+)\*\*\s+of\s+\*\*(\d+)\*\*', md_text)
    if page_matches:
        metadata['total_pages'] = int(page_matches[-1][1])
    else:
        # Count [PAGE X] markers
        page_markers = re.findall(r'\[PAGE\s+(\d+)\]', md_text)
        if page_markers:
            metadata['total_pages'] = max(int(p) for p in page_markers)
    
    return metadata

def create_final_output(merged_refs, stats, md_path, pdf_name, config, p_time, t_a_c, t_b_c):
    # Extract source document metadata
    try:
        source_text = Path(md_path).read_text(encoding='utf-8')
        source_meta = extract_source_metadata(source_text, pdf_name)
    except:
        source_meta = {
            'filename': pdf_name,
            'circular_title': pdf_name,
            'sebi_reference_number': 'Unknown',
            'date_issued': None,
            'total_pages': 1
        }
    
    valid = []
    for i, r in enumerate(merged_refs, 1):
        try:
            def clean_fmt(text):
                if not text: return text
                return re.sub(r'\.([a-zA-Z0-9])', r'. \1', text)

            # Filter out self-references (the current circular itself)
            ref_sebi_num = r.get('referenced_sebi_number') or r.get('sebi_number') or ''
            if ref_sebi_num and ref_sebi_num == source_meta['sebi_reference_number']:
                logger.info(f"Filtering out self-reference: {ref_sebi_num}")
                continue

            item = {
                "reference_id": f"REF{i:03d}",
                "referenced_document_title": clean_fmt(r.get('referenced_document_title') or r.get('title') or "Unknown SEBI Document"),
                "referenced_sebi_number": r.get('referenced_sebi_number') or r.get('sebi_number'),
                "referenced_date": r.get('referenced_date') or r.get('date'),
                "document_type": (r.get('document_type') or 'OTHER').upper().replace(' ', '_'),
                "relationship_type": (r.get('relationship_type') or 'REFERS_TO').upper().replace(' ', '_'),
                "page_numbers": [int(p) for p in (r.get('page_numbers') or []) if str(p).isdigit()],
                "exact_citation_text": clean_fmt(r.get('exact_citation_text') or r.get('cite') or r.get('text') or "See document"),
                "context_paragraph": clean_fmt(r.get('context_paragraph') or r.get('context') or "Context unavailable"),
                "section_location": r.get('section_location') or r.get('location') or "Not specified",
                "confidence_score": float(r.get('confidence_score') or 0.8),
                "extraction_source": (r.get('extraction_source') or 'BOTH').upper()
            }
            if item['document_type'] not in [e.value for e in DocumentType]: item['document_type'] = "OTHER"
            if item['relationship_type'] not in [e.value for e in RelationshipType]: item['relationship_type'] = "REFERS_TO"
            valid.append(Reference(**item))
        except Exception as e:
            logger.warning(f"Skipping corrupt ref {i}: {e}")
    
    # Re-number references after filtering
    for i, ref in enumerate(valid, 1):
        ref.reference_id = f"REF{i:03d}"

    source_doc = SourceDocument(
        filename=source_meta['filename'],
        circular_title=source_meta['circular_title'],
        sebi_reference_number=source_meta['sebi_reference_number'],
        total_pages=source_meta['total_pages'],
        date_issued=source_meta.get('date_issued')
    )
    
    meta = ProcessingMetadata(
        models_used={"consensus": config.get('consensus_model', 'unknown')},
        processing_time_seconds=p_time,
        track_a_references_found=t_a_c,
        track_b_references_found=t_b_c,
        merged_count=len(valid),
        duplicates_removed=stats['duplicates_removed'],
        conflicts_resolved=stats['conflicts_resolved'],
        validation_status=ValidationStatus.COMPLETED
    )
    
    return FinalOutput(
        source_document=source_doc,
        references=valid,
        summary_statistics=SummaryStatistics(
            total_references_found=len(valid),
            by_document_type={}, by_relationship_type={},
            by_confidence_level={"high": len(valid), "medium":0, "low":0},
            by_extraction_source={}, page_coverage={"total_pages_covered":0}
        ),
        processing_metadata=meta
    )

def run_consensus(t_a_path, t_b_path, md_path, pdf_name, out_dir, config, p_time, verbose: bool = False):
    if verbose: print(f"\nStep 3: Mastering Consensus")
    t_a = load_json(t_a_path).get('references', [])
    t_b = load_json(t_b_path).get('references', [])
    try: source_text = Path(md_path).read_text(encoding='utf-8')
    except: source_text = ""
    
    merged, stats = merge_with_ai_consensus(t_a, t_b, config['consensus_model'], config['api_key'], source_text, verbose)
    final = create_final_output(merged, stats, md_path, pdf_name, config, p_time, len(t_a), len(t_b))
    out_path = Path(out_dir) / f"{Path(pdf_name).stem}_final.json"
    save_json(final, out_path, pretty=config['pretty_json'])
    return out_path

if __name__ == "__main__":
    import sys
    from utils import setup_logging, load_config
    setup_logging()
    cfg = load_config()
    if len(sys.argv) < 5: sys.exit(1)
    run_consensus(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], cfg['output_dir'], cfg, 60, verbose=True)
