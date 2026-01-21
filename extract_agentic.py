"""
Step 2B: Agentic Deep Search Reference Extraction (Track B)

This module uses fs-explorer's agentic workflow to explore documents
through multi-step reasoning and tool usage. 

Unlike Track A's single-pass approach, this agent: 
- Strategically explores different sections
- Uses tools (grep, read, parse) to navigate
- Makes decisions about where to look next
- May find references Track A missed through iterative exploration

Docling is only used internally by fs-explorer for PDF→Markdown conversion.
Since we already have Markdown files, the agent uses read/grep tools directly.
"""

import json
import logging
import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any

from utils import save_json, get_output_path, setup_logging, load_config

# Setup logger first before any usage
logger = logging.getLogger("relatio.extract_agentic")

# fs-explorer imports
try:
    from fs_explorer import workflow, InputEvent, reset_agent # pyright: ignore[reportMissingImports]
    FS_EXPLORER_AVAILABLE = True
except ImportError as e:
    logger.error(f"fs-explorer not available: {e}")
    logger.error("Install with: uv pip install git+https://github.com/PromtEngineer/agentic-file-search.git")
    FS_EXPLORER_AVAILABLE = False


async def run_agent_workflow(task: str, markdown_parent: Path) -> str:
    """
    Run the agentic workflow. 
    """
    original_cwd = os.getcwd()
    
    try:
        os.chdir(markdown_parent)
        logger.info(f"Agent working directory: {markdown_parent}")
        
        # Reset agent for fresh state
        reset_agent()
        
        # Run workflow
        handler = workflow.run(start_event=InputEvent(task=task))
        result = await handler
        
        if result.error:
            logger.error(f"Agent error: {result.error}")
            return ""
        
        if result.final_result:
            logger.info("Agent completed successfully")
            return result.final_result
        else:
            logger.warning("Agent completed but returned no result")
            return ""
            
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        return ""
    finally:
        os.chdir(original_cwd)


def run_track_b(
    markdown_path: Path,
    output_dir: str,
    config: Dict[str, Any],
    verbose: bool = False
) -> Path:
    """
    Run Track B: Agentic exploration with tools and reasoning.
    """
    if not FS_EXPLORER_AVAILABLE:
        logger.error("fs-explorer not installed. Skipping Track B.")
        if verbose:
            print("✗ Track B skipped: fs-explorer not available")
            print("  Install with: uv pip install git+https://github.com/PromtEngineer/agentic-file-search.git")
        
        output_data = {
            "track": "B",
            "method": "agentic_exploration_skipped",
            "model": config['track_b_model'],
            "source": str(markdown_path),
            "error": "fs-explorer not installed",
            "references_found": 0,
            "references": []
        }
        output_path = get_output_path(str(markdown_path), output_dir, "_track_b.json")
        save_json(output_data, output_path, pretty=config['pretty_json'])
        return output_path
    
    logger.info("Starting Track B: Agentic Exploration")
    if verbose:
        print(f"\nStep 2B: Agentic Deep Search (Track B)")
        print(f"Model: {config['track_b_model']}")
    
    # Build agentic task - simplified and more prescriptive
    task = f"""Analyze the file '{markdown_path.name}' and extract ALL regulatory references into a JSON array.

REQUIRED STEPS:
1. Use 'parse_file' to read the document.
2. If the document is large, use 'grep' to find patterns like 'circular', 'regulation', or 'SEBI/'.
3. Extract ALL references found.

Target references:
- SEBI circulars (e.g., SEBI/HO/MIRSD/2024/120)
- SEBI Acts or Regulations
- Notifications and Guidelines

Return ONLY a JSON array of objects with fields:
referenced_document_title, referenced_sebi_number, referenced_date, document_type, relationship_type, exact_citation_text, context_paragraph, section_location
"""

    references = []
    
    try:
        if verbose: print(f"→ Starting agentic exploration (this may take a few steps)...")
        result_text = asyncio.run(run_agent_workflow(task, markdown_path.parent))
        
        if result_text:
            logger.debug(f"Agent output preview: {result_text[:500]}")
            references = parse_references_from_output(result_text)
        else:
            logger.warning("Agent returned no output")
            
        logger.info(f"Track B extracted {len(references)} references")
        
    except Exception as e:
        logger.error(f"Track B extraction failed: {e}", exc_info=True)
        if verbose: print(f"✗ Track B failed: {e}")
        references = []

    # Save results
    output_data = {
        "track": "B",
        "method": "agentic_exploration_with_tools",
        "model": config['track_b_model'],
        "source": str(markdown_path),
        "strategy": "multi_step_tool_based_exploration",
        "references_found": len(references),
        "references": references
    }
    
    output_path = get_output_path(str(markdown_path), output_dir, "_track_b.json")
    save_json(output_data, output_path, pretty=config['pretty_json'])
    
    return output_path


def parse_references_from_output(output_text: str) -> List[Dict[str, Any]]: 
    """Parse JSON from agent output."""
    import re
    
    # Strategy 1: Markdown code block
    code_block_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', output_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except: pass
    
    # Strategy 2: Inline JSON array
    json_match = re.search(r'\[\s*\{.*?\}\s*\]', output_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except: pass
    
    return []


if __name__ == "__main__": 
    import sys
    setup_logging(debug=True)
    if len(sys.argv) < 2:
        print("Usage: python extract_agentic.py <markdown_file>")
        sys.exit(1)
    
    config = load_config()
    output_path = run_track_b(Path(sys.argv[1]), config['output_dir'], config, verbose=True)
    print(f"\n✓ Track B complete! Results saved to: {output_path}")