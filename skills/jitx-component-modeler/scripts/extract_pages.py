#!/usr/bin/env python3
"""Extract specific pages from a datasheet PDF.

Usage:
    # Find pages containing keywords
    python extract_pages.py da1470x.pdf --find "vfbga" "dimension" "pinout"

    # Extract specific pages to a smaller PDF
    python extract_pages.py da1470x.pdf --pages 142 143 144 -o da1470x_package.pdf

    # Extract and show text content (for verification)
    python extract_pages.py da1470x.pdf --pages 142 --text
"""

import argparse
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)


def find_pages_with_keywords(input_pdf: str, keywords: list[str]) -> dict[int, list[str]]:
    """Find pages containing specific keywords.

    Args:
        input_pdf: Source PDF path
        keywords: Keywords to search for (case-insensitive)

    Returns:
        Dict mapping page numbers (1-indexed) to list of matched keywords
    """
    doc = fitz.open(input_pdf)
    results = {}

    for page_num, page in enumerate(doc, 1):
        text = page.get_text().lower()
        matches = [kw for kw in keywords if kw.lower() in text]
        if matches:
            results[page_num] = matches

    doc.close()
    return results


def extract_pages(input_pdf: str, pages: list[int], output_pdf: str) -> int:
    """Extract specified pages from a PDF.

    Args:
        input_pdf: Source PDF path
        pages: List of page numbers (1-indexed)
        output_pdf: Output PDF path

    Returns:
        Number of pages extracted
    """
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()

    extracted = 0
    for page_num in pages:
        idx = page_num - 1  # Convert to 0-indexed
        if 0 <= idx < len(doc):
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)
            extracted += 1
        else:
            print(f"Warning: Page {page_num} out of range (1-{len(doc)})", file=sys.stderr)

    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()

    return extracted


def get_page_text(input_pdf: str, pages: list[int]) -> dict[int, str]:
    """Extract text content from specific pages.

    Args:
        input_pdf: Source PDF path
        pages: List of page numbers (1-indexed)

    Returns:
        Dict mapping page numbers to text content
    """
    doc = fitz.open(input_pdf)
    results = {}

    for page_num in pages:
        idx = page_num - 1
        if 0 <= idx < len(doc):
            results[page_num] = doc[idx].get_text()
        else:
            print(f"Warning: Page {page_num} out of range (1-{len(doc)})", file=sys.stderr)

    doc.close()
    return results


def get_pdf_info(input_pdf: str) -> dict:
    """Get basic PDF information."""
    doc = fitz.open(input_pdf)
    info = {
        "pages": len(doc),
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
        "file_size_mb": Path(input_pdf).stat().st_size / (1024 * 1024),
    }
    doc.close()
    return info


def main():
    parser = argparse.ArgumentParser(
        description="Extract pages from datasheet PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show PDF info
  %(prog)s da1470x.pdf --info

  # Find pages with package info
  %(prog)s da1470x.pdf --find "vfbga" "dimension" "pinout" "ball map"

  # Extract pages 142-144 to a new PDF
  %(prog)s da1470x.pdf --pages 142 143 144 -o package_info.pdf

  # Extract and print text content
  %(prog)s da1470x.pdf --pages 142 --text
"""
    )

    parser.add_argument("input_pdf", help="Input PDF file")
    parser.add_argument("--info", action="store_true", help="Show PDF information")
    parser.add_argument("--find", nargs="+", metavar="KEYWORD", help="Find pages containing keywords")
    parser.add_argument("--pages", nargs="+", type=int, metavar="N", help="Page numbers to extract (1-indexed)")
    parser.add_argument("-o", "--output", metavar="FILE", help="Output PDF file (required with --pages)")
    parser.add_argument("--text", action="store_true", help="Print text content of pages")

    args = parser.parse_args()

    if not Path(args.input_pdf).exists():
        print(f"Error: File not found: {args.input_pdf}", file=sys.stderr)
        sys.exit(1)

    # Show PDF info
    if args.info:
        info = get_pdf_info(args.input_pdf)
        print(f"File: {args.input_pdf}")
        print(f"Pages: {info['pages']}")
        print(f"Size: {info['file_size_mb']:.1f} MB")
        if info['title']:
            print(f"Title: {info['title']}")
        return

    # Find pages with keywords
    if args.find:
        results = find_pages_with_keywords(args.input_pdf, args.find)
        if results:
            print(f"Found matches in {len(results)} pages:")
            for page_num, keywords in sorted(results.items()):
                print(f"  Page {page_num}: {', '.join(keywords)}")
        else:
            print("No pages found matching keywords")
        return

    # Extract pages
    if args.pages:
        if args.text:
            # Print text content
            texts = get_page_text(args.input_pdf, args.pages)
            for page_num, text in texts.items():
                print(f"\n{'='*60}")
                print(f"PAGE {page_num}")
                print('='*60)
                print(text)
        elif args.output:
            # Extract to new PDF
            count = extract_pages(args.input_pdf, args.pages, args.output)
            print(f"Extracted {count} pages to {args.output}")

            # Show new file size
            new_size = Path(args.output).stat().st_size / 1024
            print(f"New file size: {new_size:.1f} KB")
        else:
            print("Error: --output required when extracting pages (or use --text)", file=sys.stderr)
            sys.exit(1)
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
