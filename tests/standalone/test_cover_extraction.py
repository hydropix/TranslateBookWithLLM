"""
Standalone test for EPUB cover extraction.

Usage:
    python tests/standalone/test_cover_extraction.py path/to/book.epub

This script tests the EPUBCoverExtractor module by:
1. Extracting cover from the provided EPUB file
2. Saving thumbnail to data/thumbnails/
3. Displaying result information

NOTE: This is a standalone script, not a pytest test.
      Run it directly with an EPUB file path as argument.
"""
import sys

# Skip this file when running pytest
if 'pytest' in sys.modules:
    import pytest
    pytest.skip("Standalone script, not a pytest test", allow_module_level=True)
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.epub.cover_extractor import EPUBCoverExtractor


def test_cover_extraction(epub_path: str):
    """Test cover extraction from an EPUB file."""
    epub_file = Path(epub_path)

    # Validate file exists
    if not epub_file.exists():
        print(f"❌ Error: File not found: {epub_path}")
        return False

    if epub_file.suffix.lower() != '.epub':
        print(f"❌ Error: Not an EPUB file: {epub_path}")
        return False

    print(f"📚 Testing EPUB cover extraction")
    print(f"   File: {epub_file.name}")
    print(f"   Path: {epub_file.absolute()}")
    print()

    # Create output directory
    output_dir = project_root / 'data' / 'thumbnails'
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🔍 Extracting cover...")

    # Extract cover
    thumbnail_filename = EPUBCoverExtractor.extract_cover(
        str(epub_file.absolute()),
        output_dir
    )

    print()

    if thumbnail_filename:
        thumbnail_path = output_dir / thumbnail_filename
        print(f"✅ Success!")
        print(f"   Thumbnail: {thumbnail_filename}")
        print(f"   Location: {thumbnail_path.absolute()}")
        print(f"   Size: {thumbnail_path.stat().st_size} bytes")

        # Display image info
        try:
            from PIL import Image
            img = Image.open(thumbnail_path)
            print(f"   Dimensions: {img.width}x{img.height}")
            print(f"   Format: {img.format}")
            print(f"   Mode: {img.mode}")
        except Exception as e:
            print(f"   (Could not read image info: {e})")

        return True
    else:
        print(f"⚠️  No cover found")
        print(f"   The EPUB may not contain a cover image,")
        print(f"   or the cover could not be extracted.")
        print(f"   This is normal for some EPUB files.")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python tests/standalone/test_cover_extraction.py <epub_file>")
        print()
        print("Example:")
        print("  python tests/standalone/test_cover_extraction.py book.epub")
        print("  python tests/standalone/test_cover_extraction.py data/uploads/abc123_book.epub")
        sys.exit(1)

    epub_path = sys.argv[1]
    success = test_cover_extraction(epub_path)

    print()
    if success:
        print("✨ Test completed successfully!")
    else:
        print("💡 Test completed (no cover extracted)")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
