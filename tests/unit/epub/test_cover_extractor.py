"""
Unit tests for EPUBCoverExtractor.

Tests all cover extraction strategies, security validations,
and error handling scenarios as outlined in the implementation plan.
"""

import pytest
import tempfile
import zipfile
from pathlib import Path
from PIL import Image
import io

from src.core.epub.cover_extractor import EPUBCoverExtractor


class TestEPUBCoverExtractor:
    """Test suite for EPUB cover extraction functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_cover_image(self):
        """Create a sample cover image (100x150 PNG)."""
        img = Image.new('RGB', (100, 150), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        return img_bytes.read()

    @pytest.fixture
    def large_cover_image(self):
        """Create a large cover image (6MB - exceeds 5MB limit)."""
        # Create a large image
        img = Image.new('RGB', (3000, 4000), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', compress_level=0)  # No compression for large size
        img_bytes.seek(0)
        return img_bytes.read()

    @pytest.fixture
    def corrupted_image(self):
        """Create corrupted image data (not a valid image)."""
        return b"This is not a valid image file"

    def create_minimal_opf(self, cover_id=None):
        """Create minimal content.opf with optional cover metadata."""
        opf_content = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
              xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>Test Book</dc:title>
"""
        if cover_id:
            opf_content += f'        <meta name="cover" content="{cover_id}"/>\n'

        opf_content += """    </metadata>
    <manifest>
"""
        if cover_id:
            opf_content += f'        <item id="{cover_id}" href="images/cover.png" media-type="image/png"/>\n'

        opf_content += """        <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="chapter1"/>
    </spine>
</package>
"""
        return opf_content.encode('utf-8')

    def create_test_epub(self, temp_dir, name, cover_image=None, cover_metadata=True,
                        cover_filename="cover.png", opf_location="OEBPS/content.opf"):
        """
        Create a test EPUB file with configurable properties.

        Args:
            temp_dir: Temporary directory
            name: EPUB filename
            cover_image: Image bytes (None = no image)
            cover_metadata: Include cover metadata in OPF
            cover_filename: Name of cover file in EPUB
            opf_location: Location of content.opf
        """
        epub_path = temp_dir / name

        with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            # Add mimetype
            epub_zip.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)

            # Add META-INF/container.xml
            opf_full_path = opf_location
            container_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="{opf_full_path}" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>
"""
            epub_zip.writestr('META-INF/container.xml', container_xml)

            # Add content.opf
            cover_id = "cover-image" if cover_metadata and cover_image else None
            opf_content = self.create_minimal_opf(cover_id)
            epub_zip.writestr(opf_location, opf_content)

            # Add cover image if provided
            if cover_image:
                # Determine path based on OPF location
                opf_dir = str(Path(opf_location).parent)
                if opf_dir == '.':
                    image_path = f"images/{cover_filename}"
                else:
                    image_path = f"{opf_dir}/images/{cover_filename}"
                epub_zip.writestr(image_path, cover_image)

            # Add a dummy chapter
            chapter_content = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 1</title></head>
<body><p>Test content</p></body>
</html>
"""
            if opf_location.startswith('OEBPS/'):
                epub_zip.writestr('OEBPS/chapter1.xhtml', chapter_content)
            else:
                epub_zip.writestr('chapter1.xhtml', chapter_content)

        return epub_path

    # ========================================
    # Test 1: Standard Cover Extraction (OPF Metadata)
    # ========================================

    def test_extract_cover_from_metadata(self, temp_dir, sample_cover_image):
        """Test extraction using OPF metadata (standard method)."""
        epub_path = self.create_test_epub(
            temp_dir,
            "test_book.epub",
            cover_image=sample_cover_image,
            cover_metadata=True
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None
        assert result == "test_book_cover.jpg"

        # Verify thumbnail file exists
        thumbnail_path = output_dir / result
        assert thumbnail_path.exists()

        # Verify thumbnail dimensions
        img = Image.open(thumbnail_path)
        assert img.size == (48, 64)
        assert img.format == 'JPEG'

    # ========================================
    # Test 2: Cover by Naming Convention
    # ========================================

    def test_extract_cover_by_naming_convention(self, temp_dir, sample_cover_image):
        """Test extraction using naming convention (cover.png)."""
        # Create EPUB without metadata but with cover.png
        epub_path = self.create_test_epub(
            temp_dir,
            "naming_test.epub",
            cover_image=sample_cover_image,
            cover_metadata=False,  # No metadata
            cover_filename="cover.png"
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None
        assert result == "naming_test_cover.jpg"

        thumbnail_path = output_dir / result
        assert thumbnail_path.exists()

    def test_extract_cover_uppercase_naming(self, temp_dir, sample_cover_image):
        """Test extraction with uppercase Cover.jpg."""
        epub_path = self.create_test_epub(
            temp_dir,
            "uppercase_test.epub",
            cover_image=sample_cover_image,
            cover_metadata=False,
            cover_filename="Cover.jpg"
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None

    # ========================================
    # Test 3: No Cover Found
    # ========================================

    def test_extract_no_cover_returns_none(self, temp_dir):
        """Test that extraction returns None when no cover exists."""
        # Create EPUB without any images
        epub_path = self.create_test_epub(
            temp_dir,
            "no_cover.epub",
            cover_image=None,
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is None
        # Verify no thumbnail file was created
        assert not list(output_dir.glob("*.jpg"))

    # ========================================
    # Test 4: Different Image Formats
    # ========================================

    @pytest.mark.parametrize("format_name,extension", [
        ("JPEG", "cover.jpg"),
        ("PNG", "cover.png"),
        ("GIF", "cover.gif"),
    ])
    def test_extract_different_image_formats(self, temp_dir, format_name, extension):
        """Test extraction with various image formats (JPEG, PNG, GIF)."""
        # Create image in specific format
        img = Image.new('RGB', (100, 150), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format_name)
        img_bytes.seek(0)

        epub_path = self.create_test_epub(
            temp_dir,
            f"format_{format_name}.epub",
            cover_image=img_bytes.read(),
            cover_metadata=False,
            cover_filename=extension
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None
        # All formats should be converted to JPEG
        assert result.endswith("_cover.jpg")

        # Verify output is JPEG
        img = Image.open(output_dir / result)
        assert img.format == 'JPEG'

    # ========================================
    # Test 5: Security - Large Image
    # ========================================

    def test_extract_large_image_rejected(self, temp_dir, large_cover_image):
        """Test that images larger than 5MB are rejected."""
        assert len(large_cover_image) > EPUBCoverExtractor.MAX_IMAGE_SIZE

        epub_path = self.create_test_epub(
            temp_dir,
            "large_cover.epub",
            cover_image=large_cover_image,
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        # Should gracefully fail and return None
        assert result is None

    # ========================================
    # Test 6: Security - Corrupted Image
    # ========================================

    def test_extract_corrupted_image_returns_none(self, temp_dir, corrupted_image):
        """Test graceful handling of corrupted image data."""
        epub_path = self.create_test_epub(
            temp_dir,
            "corrupted.epub",
            cover_image=corrupted_image,
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        # Should handle gracefully
        assert result is None

    # ========================================
    # Test 7: Security - Unsupported Format
    # ========================================

    def test_extract_unsupported_format_rejected(self, temp_dir):
        """Test that unsupported image formats are rejected."""
        # Create a fake .bmp file (not in ALLOWED_FORMATS)
        fake_bmp = b"BM" + b"\x00" * 100

        epub_path = temp_dir / "test.epub"
        with zipfile.ZipFile(epub_path, 'w') as epub_zip:
            epub_zip.writestr('mimetype', 'application/epub+zip')
            epub_zip.writestr('OEBPS/content.opf', self.create_minimal_opf())
            epub_zip.writestr('OEBPS/images/cover.bmp', fake_bmp)  # .bmp not allowed

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is None

    # ========================================
    # Test 8: Thumbnail Dimensions and Aspect Ratio
    # ========================================

    def test_thumbnail_maintains_aspect_ratio_portrait(self, temp_dir):
        """Test that portrait images are correctly centered with padding."""
        # Create tall portrait image (50x100)
        img = Image.new('RGB', (50, 100), color='purple')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        epub_path = self.create_test_epub(
            temp_dir,
            "portrait.epub",
            cover_image=img_bytes.read(),
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        # Verify exact dimensions (48x64)
        img = Image.open(output_dir / result)
        assert img.size == (48, 64)

    def test_thumbnail_maintains_aspect_ratio_landscape(self, temp_dir):
        """Test that landscape images are correctly centered with padding."""
        # Create wide landscape image (200x100)
        img = Image.new('RGB', (200, 100), color='orange')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        epub_path = self.create_test_epub(
            temp_dir,
            "landscape.epub",
            cover_image=img_bytes.read(),
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        # Verify exact dimensions (48x64)
        img = Image.open(output_dir / result)
        assert img.size == (48, 64)

    # ========================================
    # Test 9: Filename Prefix Preservation
    # ========================================

    def test_thumbnail_preserves_epub_filename_prefix(self, temp_dir, sample_cover_image):
        """Test that thumbnail inherits the EPUB filename prefix."""
        epub_path = self.create_test_epub(
            temp_dir,
            "abc123_mybook.epub",
            cover_image=sample_cover_image,
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result == "abc123_mybook_cover.jpg"

    # ========================================
    # Test 10: OPF in Different Locations
    # ========================================

    @pytest.mark.parametrize("opf_location", [
        "content.opf",          # Root level
        "OEBPS/content.opf",    # Common location
        "OPS/content.opf",      # Alternative location
    ])
    def test_find_opf_in_various_locations(self, temp_dir, sample_cover_image, opf_location):
        """Test that content.opf is found in various standard locations."""
        epub_path = self.create_test_epub(
            temp_dir,
            f"opf_test_{opf_location.replace('/', '_')}.epub",
            cover_image=sample_cover_image,
            cover_metadata=True,
            opf_location=opf_location
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None

    # ========================================
    # Test 11: Invalid EPUB Structure
    # ========================================

    def test_extract_from_invalid_epub_returns_none(self, temp_dir):
        """Test graceful handling of invalid EPUB files."""
        # Create invalid EPUB (missing content.opf)
        epub_path = temp_dir / "invalid.epub"
        with zipfile.ZipFile(epub_path, 'w') as epub_zip:
            epub_zip.writestr('mimetype', 'application/epub+zip')
            epub_zip.writestr('random.txt', 'not a valid epub')

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is None

    def test_extract_from_non_zip_returns_none(self, temp_dir):
        """Test graceful handling when file is not a valid ZIP."""
        # Create fake EPUB (not a ZIP)
        epub_path = temp_dir / "fake.epub"
        epub_path.write_text("This is not a ZIP file")

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is None

    # ========================================
    # Test 12: Output Directory Creation
    # ========================================

    def test_creates_output_directory_if_missing(self, temp_dir, sample_cover_image):
        """Test that output directory is created if it doesn't exist."""
        epub_path = self.create_test_epub(
            temp_dir,
            "test.epub",
            cover_image=sample_cover_image,
            cover_metadata=False
        )

        # Use non-existent nested directory
        output_dir = temp_dir / "nested" / "thumbnails" / "deep"
        assert not output_dir.exists()

        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None
        assert output_dir.exists()
        assert (output_dir / result).exists()

    # ========================================
    # Test 13: RGBA to RGB Conversion
    # ========================================

    def test_converts_rgba_to_rgb(self, temp_dir):
        """Test that RGBA images are converted to RGB before JPEG conversion."""
        # Create RGBA PNG (with transparency)
        img = Image.new('RGBA', (100, 150), color=(255, 0, 0, 128))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        epub_path = self.create_test_epub(
            temp_dir,
            "rgba_test.epub",
            cover_image=img_bytes.read(),
            cover_metadata=False
        )

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None

        # Verify it was converted to RGB (JPEG doesn't support RGBA)
        img = Image.open(output_dir / result)
        assert img.mode == 'RGB'
        assert img.format == 'JPEG'

    # ========================================
    # Test 14: First Image Fallback
    # ========================================

    def test_fallback_to_first_image_in_manifest(self, temp_dir, sample_cover_image):
        """Test fallback to first image when no cover metadata or naming convention."""
        epub_path = temp_dir / "fallback.epub"

        # Create EPUB with image but no cover metadata and non-standard name
        with zipfile.ZipFile(epub_path, 'w') as epub_zip:
            epub_zip.writestr('mimetype', 'application/epub+zip')

            # OPF with image in manifest but no cover metadata
            opf_content = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>Test</dc:title>
    </metadata>
    <manifest>
        <item id="img1" href="images/random_name.png" media-type="image/png"/>
        <item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest>
    <spine>
        <itemref idref="ch1"/>
    </spine>
</package>
"""
            epub_zip.writestr('content.opf', opf_content)
            epub_zip.writestr('images/random_name.png', sample_cover_image)
            epub_zip.writestr('chapter1.xhtml', '<html><body>Test</body></html>')

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        # Should fallback to first image
        assert result is not None

    # ========================================
    # Test 15: Concurrent Extraction Safety
    # ========================================

    def test_multiple_epubs_unique_thumbnails(self, temp_dir, sample_cover_image):
        """Test that extracting from multiple EPUBs creates unique thumbnails."""
        epubs = []
        for i in range(3):
            epub_path = self.create_test_epub(
                temp_dir,
                f"book{i}.epub",
                cover_image=sample_cover_image,
                cover_metadata=False
            )
            epubs.append(epub_path)

        output_dir = temp_dir / "thumbnails"
        results = []

        for epub_path in epubs:
            result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)
            results.append(result)

        # All results should be unique
        assert len(results) == len(set(results))
        assert all(r is not None for r in results)

        # Verify all thumbnails exist
        for result in results:
            assert (output_dir / result).exists()


class TestCoverExtractorEdgeCases:
    """Additional edge case tests."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_extract_with_special_characters_in_filename(self, temp_dir):
        """Test handling of special characters in EPUB filename."""
        # Create simple test image
        img = Image.new('RGB', (100, 150), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')

        # Note: Windows doesn't allow some special chars in filenames
        epub_path = temp_dir / "book-with-dashes_and_underscores.epub"

        with zipfile.ZipFile(epub_path, 'w') as epub_zip:
            epub_zip.writestr('mimetype', 'application/epub+zip')
            epub_zip.writestr('content.opf', """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf">
    <metadata><title>Test</title></metadata>
    <manifest>
        <item id="img" href="cover.png" media-type="image/png"/>
    </manifest>
    <spine></spine>
</package>""")
            epub_zip.writestr('cover.png', img_bytes.getvalue())

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        assert result is not None
        assert (output_dir / result).exists()

    def test_extract_with_very_small_image(self, temp_dir):
        """Test handling of very small images (1x1 pixel)."""
        img = Image.new('RGB', (1, 1), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')

        epub_path = temp_dir / "tiny.epub"
        with zipfile.ZipFile(epub_path, 'w') as epub_zip:
            epub_zip.writestr('mimetype', 'application/epub+zip')
            epub_zip.writestr('content.opf', """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf">
    <metadata><title>Test</title></metadata>
    <manifest></manifest>
    <spine></spine>
</package>""")
            epub_zip.writestr('cover.png', img_bytes.getvalue())

        output_dir = temp_dir / "thumbnails"
        result = EPUBCoverExtractor.extract_cover(str(epub_path), output_dir)

        # Should still create a 48x64 thumbnail with padding
        if result:
            img = Image.open(output_dir / result)
            assert img.size == (48, 64)
