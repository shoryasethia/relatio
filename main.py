"""
RELATIO - Regulatory Relationship Intelligence and Optimization
End to End Pipeline

Coordinates the 3-stage extraction pipeline:
1. PDF -> Markdown
2. Dual-track extraction (Track A: Global, Track B: Agentic)
3. Consensus & Merging
"""

import sys
import time
import argparse
import logging
from pathlib import Path
from typing import Optional

from utils import (
    load_config,
    setup_logging,
    ensure_directory,
    format_duration,
    print_banner,
    print_step,
    print_status,
    print_table
)
from convert_pdf import convert_pdf_to_markdown
from extract_global import run_track_a
from extract_agentic import run_track_b
from merge_consensus import run_consensus

logger = logging.getLogger("relatio.main")

def run_pipeline(
    input_pdf: Path,
    output_dir: Optional[Path] = None,
    config: Optional[dict] = None
) -> Path:
    # 1. Setup
    if not input_pdf.exists(): raise FileNotFoundError(f"PDF not found: {input_pdf}")
    if config is None: config = load_config()
    
    # Create sub-directory for this specific PDF inside the base output dir
    base_out = Path(output_dir or config['output_dir'])
    pdf_out = base_out / input_pdf.stem
    ensure_directory(str(pdf_out))
    
    start_time = time.time()
    results = [] # To store [Stage, Time, Status] for the final table
    
    print_banner("Relatio: Mapping the DNA of regulatory evolution")
    print(f"  SOURCE PDF:  {input_pdf.name}")
    print(f"  OUTPUT DIR:  {pdf_out}\n")
    
    try:
        # Stage 1: PDF to Markdown
        provider = config.get('conversion_provider', 'docling').capitalize()
        print_step(1, 4, f"PDF Conversion ({provider})")
        s1_start = time.time()
        try:
            markdown_path, _ = convert_pdf_to_markdown(str(input_pdf), str(pdf_out), verbose=False)
            s1_time = time.time() - s1_start
            print_status("Markdown Generated", f"{markdown_path.name}", "DONE")
            results.append(["1. Conversion", f"{s1_time:.2f}s", "DONE"])
        except Exception as e:
            results.append(["1. Conversion", "0.00s", "FAIL"])
            raise e
        
        print()  # Add spacing after Stage 1
        
        # Stage 2A: Track A (Global)
        print_step(2, 4, "Global Extraction (Track A)")
        s2a_start = time.time()
        try:
            track_a_path = run_track_a(markdown_path, str(pdf_out), config, verbose=False)
            s2a_time = time.time() - s2a_start
            print_status("Track A Result", f"{track_a_path.name}", "DONE")
            results.append(["2. Track A", f"{s2a_time:.2f}s", "DONE"])
        except Exception as e:
            results.append(["2. Track A", "0.00s", "FAIL"])
            raise e
        
        print()  # Add spacing after Stage 2A
        
        # Stage 2B: Track B (Agentic)
        print_step(3, 4, "Agentic Extraction (Track B)")
        s2b_start = time.time()
        try:
            track_b_path = run_track_b(markdown_path, str(pdf_out), config, verbose=False)
            s2b_time = time.time() - s2b_start
            if "skipped" in str(track_b_path):
                print_status("Track B Result", "Explorer not available", "SKIP")
                results.append(["3. Track B", "0.00s", "SKIP"])
            else:
                print_status("Track B Result", f"{track_b_path.name}", "DONE")
                results.append(["3. Track B", f"{s2b_time:.2f}s", "DONE"])
        except Exception as e:
            print_status("Track B Result", str(e), "WARN")
            results.append(["3. Track B", "0.00s", "FAIL"])
        
        print()  # Add spacing after Stage 2B
        
        # Stage 3: Consensus & Merging
        print_step(4, 4, "Final Consensus & Merging")
        s3_start = time.time()
        try:
            total_p_time = int(time.time() - start_time)
            final_path = run_consensus(
                t_a_path=track_a_path,
                t_b_path=track_b_path,
                md_path=markdown_path,
                pdf_name=input_pdf.name,
                out_dir=str(pdf_out),
                config=config,
                p_time=total_p_time,
                verbose=False
            )
            s3_time = time.time() - s3_start
            print_status("Final Output", f"{final_path.name}", "DONE")
            results.append(["4. Consensus", f"{s3_time:.2f}s", "DONE"])
        except Exception as e:
            results.append(["4. Consensus", "0.00s", "FAIL"])
            raise e
        
        # Final Summary Table
        total_time = time.time() - start_time
        print("\n" + "-" * 70)
        print_banner("Execution Summary")
        print_table(["STAGE", "DURATION", "STATUS"], results)
        
        print(f"      [ TOTAL TIME ]   : {total_time:.2f}s")
        print(f"      [ FINAL JSON ]   : {final_path}\n")
        print("=" * 70 + "\n")
        
        return final_path
        
    except Exception as e:
        print_banner("PIPELINE FAILED")
        print(f"      [ ERROR ] : {e}")
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise

def main():
    parser = argparse.ArgumentParser(description="RELATIO master pipeline")
    parser.add_argument('pdf', type=Path, help="Path to SEBI circular")
    parser.add_argument('--output', '-o', type=Path, help="Custom output directory")
    parser.add_argument('--debug', '-d', action='store_true', help="Verbose logging")
    
    args = parser.parse_args()
    
    config = load_config()
    setup_logging(debug=args.debug or config.get('debug_mode', False))
    
    try:
        run_pipeline(args.pdf, args.output, config)
        sys.exit(0)
    except Exception:
        sys.exit(1)

if __name__ == "__main__":
    main()
