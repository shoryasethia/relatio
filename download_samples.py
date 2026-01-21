"""
Download Sample SEBI Circulars for Testing

Since SEBI PDFs require clicking through web pages, this script:
1. Shows you where to download circulars manually
2. Creates a test markdown file to verify the pipeline works
"""

import logging
from pathlib import Path

from utils import ensure_directory, load_config, setup_logging


logger = logging.getLogger("relatio.download_samples")


def show_download_instructions():
    """Show where to get SEBI circulars."""
    print("\nWhere to Download SEBI Circulars\n")
    
    print("SEBI Circulars Archive:")
    print("https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0\n")
    
    print("How to Download:")
    print("1. Click on any recent circular from the list")
    print("2. Click the PDF link that appears")
    print("3. Save the PDF to your samples/ folder\n")
    
    print("Tips:")
    print("  - Any circular works, pick something recent")
    print("  - Longer circulars = more references to extract")
    print("  - You can test with multiple PDFs\n")


def create_test_file():
    """Create a test markdown file to verify the pipeline."""
    test_content = """# Test SEBI Circular - Portfolio Management Guidelines

**SEBI/HO/MIRSD/TEST/2024/001**  
**Date: January 15, 2024**

## Preamble

In exercise of the powers conferred under Section 11(1) of the Securities and Exchange Board of India Act, 1992, to protect the interests of investors in securities and to promote the development of, and to regulate the securities market, this circular supersedes SEBI/HO/MIRSD/2023/105 dated March 20, 2023.

## Regulations Referenced

These guidelines are issued in terms of SEBI (Portfolio Managers) Regulations, 2020 to provide operational clarity.

## Previous Circulars

### Superseded Circulars

The following circulars stand superseded:
- SEBI/IMD/CIR No. 18/198647/2010 dated December 20, 2010
- SEBI/HO/MIRSD/2022/087 dated August 10, 2022

## Compliance Requirements

Portfolio managers shall maintain risk management systems as specified in SEBI/HO/MIRSD/2021/652 dated November 5, 2021.

## Annexure A - Table of References

| Reference Number | Title | Date | Status |
|-----------------|-------|------|--------|
| SEBI/HO/MIRSD/2023/078 | Disclosure Norms | 2023-06-15 | Active |
| SEBI Act, 1992 | SEBI Act | 1992-01-30 | Active |

---
**For and on behalf of the Board**  
**Securities and Exchange Board of India**
"""
    
    config = load_config()
    samples_dir = ensure_directory(config['samples_dir'])
    
    test_path = samples_dir / "test_circular.md"
    
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"Created test file: {test_path}\n")
    
    return test_path


def main():
    """Main entry point."""
    setup_logging(debug=False)
    
    print("\nSEBI Circular Downloader\n")
    
    # Load config
    try:
        config = load_config()
    except RuntimeError as e:
        print(f"Note: {e}\n")
        config = {'samples_dir': 'samples'}
    
    # Ensure samples directory
    samples_dir = ensure_directory(config['samples_dir'])
    print(f"Samples folder: {samples_dir}\n")
    
    # Show download instructions
    show_download_instructions()
    
    # Create test file
    print("Creating test markdown file for pipeline verification...\n")
    test_path = create_test_file()
    
    print("Next Steps:\n")
    print("1. Download a SEBI circular PDF from the link above")
    print(f"2. Save it to: {samples_dir}")
    print("3. Run: python main.py samples/your_circular.pdf\n")
    
    print("Or test with the generated file:")
    print(f"   python extract_global.py {test_path}\n")


if __name__ == "__main__":
    main()