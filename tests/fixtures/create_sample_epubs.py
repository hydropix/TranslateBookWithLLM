#!/usr/bin/env python3
"""
Generate sample EPUB files for testing.

Creates various EPUB test fixtures:
- simple.epub: Basic single-chapter EPUB
- multi_chapter.epub: Multiple chapters with varying sizes
- long_sentences.epub: Tests boundary detection with long sentences
- mixed_content.epub: Headers, quotes, abbreviations

Usage:
    python create_sample_epubs.py
"""

import os
import zipfile
import tempfile
from datetime import datetime


def create_mimetype():
    """Return mimetype file content."""
    return 'application/epub+zip'


def create_container_xml():
    """Create META-INF/container.xml content."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>'''


def create_opf(title, author, chapters):
    """Create content.opf package document."""
    manifest_items = ['<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                      '<item id="css" href="stylesheet.css" media-type="text/css"/>']
    spine_items = []

    for i in range(len(chapters)):
        item_id = f'chapter{i+1}'
        href = f'chapter_{i+1:03d}.xhtml'
        manifest_items.append(f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'<itemref idref="{item_id}"/>')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    <dc:creator opf:role="aut">{author}</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="BookId">test-{title.lower().replace(' ', '-')}</dc:identifier>
    <dc:date>{datetime.now().strftime('%Y-%m-%d')}</dc:date>
  </metadata>
  <manifest>
    {chr(10).join('    ' + item for item in manifest_items)}
  </manifest>
  <spine toc="ncx">
    {chr(10).join('    ' + item for item in spine_items)}
  </spine>
</package>'''


def create_ncx(title, chapters):
    """Create toc.ncx navigation document."""
    nav_points = []
    for i, chapter in enumerate(chapters):
        nav_points.append(f'''    <navPoint id="navPoint-{i+1}" playOrder="{i+1}">
      <navLabel>
        <text>Chapter {i+1}</text>
      </navLabel>
      <content src="chapter_{i+1:03d}.xhtml"/>
    </navPoint>''')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="test-{title.lower().replace(' ', '-')}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{title}</text>
  </docTitle>
  <navMap>
{chr(10).join(nav_points)}
  </navMap>
</ncx>'''


def create_chapter_xhtml(title, content, language='en'):
    """Create chapter XHTML file."""
    # Convert text to HTML paragraphs
    paragraphs = content.strip().split('\n\n')
    html_content = '\n'.join(f'    <p>{p.strip()}</p>' for p in paragraphs if p.strip())

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{language}">
<head>
  <title>{title}</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <h1>{title}</h1>
{html_content}
</body>
</html>'''


def create_stylesheet():
    """Create basic CSS stylesheet."""
    return '''body {
  font-family: serif;
  margin: 1em;
  line-height: 1.6;
}

h1 {
  font-size: 1.5em;
  margin-bottom: 1em;
}

p {
  margin-bottom: 0.5em;
  text-indent: 1em;
}
'''


def create_epub(output_path, title, author, chapters):
    """
    Create a valid EPUB 2.0 file.

    Args:
        output_path: Path for output EPUB file
        title: Book title
        author: Author name
        chapters: List of chapter text content strings
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create directory structure
        meta_inf_dir = os.path.join(temp_dir, 'META-INF')
        os.makedirs(meta_inf_dir)

        # Create files
        files_to_add = []

        # 1. mimetype (MUST be first)
        mimetype_path = os.path.join(temp_dir, 'mimetype')
        with open(mimetype_path, 'w', encoding='utf-8', newline='') as f:
            f.write(create_mimetype())
        files_to_add.append(('mimetype', mimetype_path, zipfile.ZIP_STORED))

        # 2. META-INF/container.xml
        container_path = os.path.join(meta_inf_dir, 'container.xml')
        with open(container_path, 'w', encoding='utf-8', newline='') as f:
            f.write(create_container_xml())
        files_to_add.append(('META-INF/container.xml', container_path, zipfile.ZIP_DEFLATED))

        # 3. content.opf
        opf_path = os.path.join(temp_dir, 'content.opf')
        with open(opf_path, 'w', encoding='utf-8', newline='') as f:
            f.write(create_opf(title, author, chapters))
        files_to_add.append(('content.opf', opf_path, zipfile.ZIP_DEFLATED))

        # 4. toc.ncx
        ncx_path = os.path.join(temp_dir, 'toc.ncx')
        with open(ncx_path, 'w', encoding='utf-8', newline='') as f:
            f.write(create_ncx(title, chapters))
        files_to_add.append(('toc.ncx', ncx_path, zipfile.ZIP_DEFLATED))

        # 5. stylesheet.css
        css_path = os.path.join(temp_dir, 'stylesheet.css')
        with open(css_path, 'w', encoding='utf-8', newline='') as f:
            f.write(create_stylesheet())
        files_to_add.append(('stylesheet.css', css_path, zipfile.ZIP_DEFLATED))

        # 6. Chapter files
        for i, content in enumerate(chapters):
            chapter_title = f'Chapter {i+1}'
            filename = f'chapter_{i+1:03d}.xhtml'
            chapter_path = os.path.join(temp_dir, filename)
            with open(chapter_path, 'w', encoding='utf-8', newline='') as f:
                f.write(create_chapter_xhtml(chapter_title, content))
            files_to_add.append((filename, chapter_path, zipfile.ZIP_DEFLATED))

        # Create EPUB ZIP file
        with zipfile.ZipFile(output_path, 'w') as epub_zip:
            for arcname, filepath, compress_type in files_to_add:
                epub_zip.write(filepath, arcname, compress_type=compress_type)

    print(f"Created: {output_path}")


def create_simple_epub(output_dir):
    """Create a simple single-chapter EPUB."""
    chapters = [
        '''This is a simple test EPUB with a single chapter. It contains multiple paragraphs of text that can be used for testing the translation pipeline.

The first paragraph introduces the content. This second paragraph provides more details about the testing scenario.

Finally, this third paragraph wraps up the chapter content. The entire chapter should be processed as a single unit with consistent chunking behavior.'''
    ]

    create_epub(
        os.path.join(output_dir, 'simple.epub'),
        'Simple Test Book',
        'Test Author',
        chapters
    )


def create_multi_chapter_epub(output_dir):
    """Create a multi-chapter EPUB with varying chapter sizes."""
    chapters = [
        # Chapter 1: Short
        '''Chapter one is intentionally short. It tests how the chunking algorithm handles small content blocks.

This paragraph adds a bit more text to the chapter.''',

        # Chapter 2: Medium
        '''Chapter two has a medium amount of content. This chapter tests the standard chunking behavior with normal text flow.

The second paragraph adds more content to reach a reasonable size. We want to ensure that chunks respect chapter boundaries.

A third paragraph provides additional testing material. This helps verify that statistics are calculated correctly across chapters.

The fourth paragraph continues the narrative. Each sentence contributes to the overall character count for chunking purposes.''',

        # Chapter 3: Long
        '''Chapter three is the longest chapter in this test book. It contains many paragraphs to test how the chunking algorithm handles larger content blocks. The goal is to generate multiple chunks from a single chapter while respecting semantic boundaries.

The second paragraph continues the narrative with additional content. We need enough text to trigger multiple chunk creation within this single chapter. Each paragraph should be considered as a potential boundary point.

Here we have the third paragraph with even more content to process. The chunking algorithm should identify sentence boundaries and create appropriately sized chunks. This paragraph adds more characters to reach our target chunk size.

The fourth paragraph provides more testing material. We want to ensure that the chunks are evenly distributed and that no chunk breaks in the middle of a sentence. Semantic coherence is important for translation quality.

This fifth paragraph approaches the end of the chapter. The final chunks should maintain proper context for accurate translation. We test both boundary detection and size conformance with this extended content.

Finally, the sixth paragraph concludes this long chapter. The entire chapter should produce multiple chunks, each respecting sentence boundaries. Statistics should show high conformance to the target size range.'''
    ]

    create_epub(
        os.path.join(output_dir, 'multi_chapter.epub'),
        'Multi-Chapter Test Book',
        'Test Author',
        chapters
    )


def create_long_sentences_epub(output_dir):
    """Create an EPUB with very long sentences to test boundary detection."""
    chapters = [
        '''This chapter contains unusually long sentences that test the boundary detection algorithm's ability to handle edge cases where a single sentence might exceed the target chunk size, which could potentially cause issues if the algorithm tries to force a break in the middle of the sentence rather than allowing an oversized chunk that preserves semantic integrity.

Another extremely long sentence follows here, containing multiple clauses separated by commas, conjunctions, and other punctuation marks that are not sentence terminators, which means the algorithm must correctly identify that this is still one continuous sentence despite its considerable length and should not break it apart.

Here we have Dr. Smith and Mr. Jones discussing the implications of the new policy announced by Corp. Inc. at their meeting on Jan. 15th, where they determined that the changes would affect approximately 50.5% of their user base based on data from Q4 2024.

The final paragraph contains normal-length sentences. These provide contrast to the long sentences above. The chunking algorithm should handle both cases appropriately.'''
    ]

    create_epub(
        os.path.join(output_dir, 'long_sentences.epub'),
        'Long Sentences Test',
        'Test Author',
        chapters
    )


def create_mixed_content_epub(output_dir):
    """Create an EPUB with mixed content types: headers, quotes, abbreviations."""
    chapters = [
        '''Introduction to Mixed Content

This chapter tests various content types that the chunking algorithm must handle correctly.

Section 1: Quotations

"This is a quoted passage," said the professor. "It should remain intact during chunking." He continued, "Breaking quotes in the middle would harm translation quality."

The student replied, "I understand the importance of preserving semantic units. This is crucial for accurate translation."

Section 2: Abbreviations and Numbers

Dr. Johnson from the U.S.A. met with Prof. Williams on Dec. 25th to discuss the findings. The data showed 99.9% accuracy with results ranging from 0.1 to 100.0 units.

Mr. Smith reported to Mrs. Davis that Corp. Ltd. had achieved their Q3 targets. The P.O. box number was 12345.

Section 3: Technical Terms

The API endpoint https://example.com/api/v1/translate accepts POST requests. Version 2.0.1 introduced breaking changes.

URLs like https://docs.example.org/guide/installation.html should remain unbroken during chunking.

Conclusion

This chapter demonstrates the complexity of boundary detection in real-world text content.''',

        '''Chapter 2: Edge Cases

This chapter focuses on additional edge cases.

Consecutive breaks test:



Multiple blank lines above should be handled gracefully.

Very short paragraph.

Followed by another short one.

And another.

This tests how consecutive small blocks are handled during chunking operations.

The final paragraph provides a longer block of text to ensure proper statistics calculation across varied content sizes and structures.'''
    ]

    create_epub(
        os.path.join(output_dir, 'mixed_content.epub'),
        'Mixed Content Test Book',
        'Test Author',
        chapters
    )


def main():
    """Generate all sample EPUB files."""
    # Get the fixtures directory (same as this script)
    fixtures_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"Creating sample EPUB files in: {fixtures_dir}")
    print()

    # Create all sample EPUBs
    create_simple_epub(fixtures_dir)
    create_multi_chapter_epub(fixtures_dir)
    create_long_sentences_epub(fixtures_dir)
    create_mixed_content_epub(fixtures_dir)

    print()
    print("All sample EPUB files created successfully!")
    print()
    print("Usage in tests:")
    print('  epub_path = os.path.join(fixtures_dir, "simple.epub")')
    print()
    print("Available fixtures:")
    for name in ['simple.epub', 'multi_chapter.epub', 'long_sentences.epub', 'mixed_content.epub']:
        path = os.path.join(fixtures_dir, name)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  - {name} ({size} bytes)")


if __name__ == "__main__":
    main()
