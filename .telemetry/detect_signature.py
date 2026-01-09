#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Watermark Detection Tool for TranslateBookWithLLM

This tool detects metadatas in translated files to help identify
unauthorized commercial use of this AGPL-3.0 licensed software.

Usage:
    python detect_metadata.py <file.txt|file.epub|file.srt>
    python detect_metadata.py --text "Your translated text here"
"""

import sys
import os
import io
import argparse
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.text_encoding import detect_metadata_in_text


def detect_in_text(text: str) -> dict:
    """
    Detect metadata in text.

    Args:
        text: Text to analyze

    Returns:
        Detection result dictionary
    """
    metadata = detect_metadata_in_text(text)

    return {
        'detected': metadata is not None,
        'metadata': metadata,
        'method': 'zero-width-characters' if metadata else None
    }


def detect_in_txt_file(file_path: Path) -> dict:
    """Detect metadata in TXT file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Check for visible signature
        visible_signature = None
        if 'TranslateBookWithLLM' in text or 'TBL' in text:
            visible_signature = 'Found visible attribution in text'

        # Check for steganographic metadata
        stego_result = detect_in_text(text)

        return {
            'file': str(file_path),
            'type': 'txt',
            'detected': stego_result['detected'] or visible_signature is not None,
            'steganographic': stego_result['metadata'],
            'visible': visible_signature
        }
    except Exception as e:
        return {
            'file': str(file_path),
            'type': 'txt',
            'error': str(e)
        }


def detect_in_epub_file(file_path: Path) -> dict:
    """Detect metadata in EPUB file."""
    import zipfile
    import xml.etree.ElementTree as ET

    try:
        results = {
            'file': str(file_path),
            'type': 'epub',
            'detected': False,
            'metadata': None,
            'steganographic': None,
            'files_checked': 0
        }

        with zipfile.ZipFile(file_path, 'r') as epub:
            # Check metadata in content.opf
            opf_files = [f for f in epub.namelist() if f.endswith('.opf')]

            for opf_file in opf_files:
                try:
                    opf_content = epub.read(opf_file).decode('utf-8')

                    # Check for visible metadata
                    if 'TranslateBookWithLLM' in opf_content or 'TBL' in opf_content:
                        results['metadata'] = 'Found in EPUB metadata'
                        results['detected'] = True

                except Exception:
                    pass

            # Check content files for steganographic metadatas
            html_files = [f for f in epub.namelist() if f.endswith(('.html', '.xhtml'))]

            for html_file in html_files[:5]:  # Check first 5 files
                try:
                    content = epub.read(html_file).decode('utf-8')
                    results['files_checked'] += 1

                    # Strip HTML tags for text analysis
                    import re
                    text = re.sub(r'<[^>]+>', ' ', content)

                    # Check for steganographic metadata
                    metadata = detect_metadata_in_text(text)
                    if metadata:
                        results['steganographic'] = metadata
                        results['detected'] = True
                        break  # Found one, no need to check more

                except Exception:
                    pass

        return results

    except Exception as e:
        return {
            'file': str(file_path),
            'type': 'epub',
            'error': str(e)
        }


def detect_in_srt_file(file_path: Path) -> dict:
    """Detect metadata in SRT file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for visible signature in comments
        visible_signature = None
        if 'TranslateBookWithLLM' in content or 'TBL' in content:
            visible_signature = 'Found in SRT comments or subtitles'

        # Extract subtitle text (skip timestamps and numbers)
        import re
        subtitle_text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', content)
        subtitle_text = re.sub(r'^\d+$', '', subtitle_text, flags=re.MULTILINE)

        # Check for steganographic metadata
        stego_result = detect_in_text(subtitle_text)

        return {
            'file': str(file_path),
            'type': 'srt',
            'detected': stego_result['detected'] or visible_signature is not None,
            'steganographic': stego_result['metadata'],
            'visible': visible_signature
        }

    except Exception as e:
        return {
            'file': str(file_path),
            'type': 'srt',
            'error': str(e)
        }


def print_result(result: dict):
    """Print detection result in user-friendly format."""
    print("\n" + "="*70)
    print("WATERMARK DETECTION RESULT")
    print("="*70)

    if 'error' in result:
        print(f"\n❌ ERROR: {result['error']}")
        return

    print(f"\nFile: {result.get('file', 'N/A')}")
    print(f"Type: {result.get('type', 'N/A').upper()}")

    print("\n" + "-"*70)

    if result['detected']:
        print("✅ WATERMARK DETECTED - This file was likely created by TranslateBookWithLLM")
        print("-"*70)

        if result.get('steganographic'):
            print(f"\n🔍 Steganographic Watermark: {result['steganographic']}")
            print("   Type: Zero-width characters (invisible)")
            print("   Reliability: HIGH - This is strong evidence")

        if result.get('metadata'):
            print(f"\n📝 Metadata: {result['metadata']}")
            print("   Type: EPUB metadata field")
            print("   Reliability: MEDIUM - Can be easily modified")

        if result.get('visible'):
            print(f"\n👁️  Visible Signature: {result['visible']}")
            print("   Type: Text attribution")
            print("   Reliability: LOW - Can be easily removed")

        if result.get('files_checked'):
            print(f"\n📄 EPUB Files Checked: {result['files_checked']}")

        print("\n" + "="*70)
        print("CONCLUSION")
        print("="*70)
        print("\nThis file appears to be created by TranslateBookWithLLM.")
        print("\n⚖️  If this is from an unauthorized SaaS service:")
        print("   1. Document this finding (screenshot)")
        print("   2. Check their license compliance")
        print("   3. See PROTECTION_STRATEGY.md for next steps")

    else:
        print("❌ NO WATERMARK DETECTED")
        print("-"*70)
        print("\nNo TranslateBookWithLLM metadatas found in this file.")
        print("\nPossible reasons:")
        print("  • File was not created by TranslateBookWithLLM")
        print("  • Watermarks were intentionally removed")
        print("  • File was heavily edited after translation")
        print("  • Watermarking was disabled (SIGNATURE_ENABLED=false)")

        if result.get('files_checked'):
            print(f"\n📄 EPUB Files Checked: {result['files_checked']}")

    print("\n" + "="*70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Detect TranslateBookWithLLM metadatas in translated files',
        epilog='For more information, see PROTECTION_STRATEGY.md'
    )

    parser.add_argument(
        'file',
        nargs='?',
        help='File to analyze (.txt, .epub, .srt)'
    )

    parser.add_argument(
        '--text',
        help='Analyze text directly instead of a file'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed analysis'
    )

    args = parser.parse_args()

    # Show usage if no arguments
    if not args.file and not args.text:
        parser.print_help()
        print("\nExamples:")
        print('  python detect_metadata.py translated.txt')
        print('  python detect_metadata.py book.epub')
        print('  python detect_metadata.py subtitle.srt')
        print('  python detect_metadata.py --text "Your translated text"')
        sys.exit(1)

    # Analyze text directly
    if args.text:
        result = detect_in_text(args.text)
        result['type'] = 'text'
        result['file'] = '<direct text input>'

        if result['detected']:
            result['steganographic'] = result['metadata']
        else:
            result['steganographic'] = None

        print_result(result)
        sys.exit(0 if result['detected'] else 1)

    # Analyze file
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    # Detect based on file type
    suffix = file_path.suffix.lower()

    if suffix == '.txt':
        result = detect_in_txt_file(file_path)
    elif suffix == '.epub':
        result = detect_in_epub_file(file_path)
    elif suffix == '.srt':
        result = detect_in_srt_file(file_path)
    else:
        print(f"❌ Error: Unsupported file type: {suffix}")
        print("Supported types: .txt, .epub, .srt")
        sys.exit(1)

    print_result(result)

    # Exit code: 0 if detected, 1 if not
    sys.exit(0 if result.get('detected') else 1)


if __name__ == '__main__':
    main()
