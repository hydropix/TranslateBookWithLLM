"""
Test script for hierarchical HTML chunking
"""
from src.core.epub.tag_preservation import TagPreserver
from src.core.epub.html_chunker import HtmlChunker
from lxml import etree

# Read the test HTML file
html_file = r"c:\Users\Bruno\Documents\GitHub\TestFileToTranslate\Fake Romance (Andy Wayne.) (Z-Library) - Copie\index_split_000.html"

with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Parse the HTML
parser = etree.XMLParser(recover=True, remove_blank_text=False)
tree = etree.fromstring(html_content.encode('utf-8'), parser)

# Find body
body = tree.find('.//{http://www.w3.org/1999/xhtml}body')
if body is None:
    print("No body found!")
    exit(1)

# Extract body HTML
body_html = etree.tostring(body, encoding='unicode', method='html')

print(f"Original body HTML length: {len(body_html)} chars")
print(f"Original body HTML tokens: ~{len(body_html) // 4} (rough estimate)")
print("\n" + "="*80 + "\n")

# Preserve tags
tag_preserver = TagPreserver()
text_with_placeholders, global_tag_map = tag_preserver.preserve_tags(body_html)

internal_placeholder_count = len([k for k in global_tag_map.keys() if not k.startswith("__")])
print(f"Preserved {internal_placeholder_count} internal tag groups")
print(f"Text with placeholders length: {len(text_with_placeholders)} chars")
print("\n" + "="*80 + "\n")

# Chunk with different max_tokens values
for max_tokens in [450, 700, 1000]:
    print(f"\n{'='*80}")
    print(f"Testing with max_tokens={max_tokens}")
    print(f"{'='*80}\n")

    chunker = HtmlChunker(max_tokens=max_tokens)
    chunks = chunker.chunk_html_with_placeholders(text_with_placeholders, global_tag_map)

    print(f"Created {len(chunks)} chunks")

    for i, chunk in enumerate(chunks):
        chunk_tokens = chunker.token_chunker.count_tokens(chunk['text'])
        chunk_chars = len(chunk['text'])
        placeholder_count = len([k for k in chunk['local_tag_map'].keys() if not k.startswith("__")])

        # Show first 100 chars of chunk text (without placeholders for readability)
        import re
        text_preview = re.sub(r'\[\[\d+\]\]', '', chunk['text'])[:150]

        print(f"\nChunk {i+1}:")
        print(f"  Tokens: {chunk_tokens} / {max_tokens}")
        print(f"  Chars: {chunk_chars}")
        print(f"  Placeholders: {placeholder_count}")
        print(f"  Preview: {text_preview}...")

        if chunk_tokens > max_tokens:
            print(f"  ⚠️  WARNING: Chunk exceeds max_tokens!")

print("\n" + "="*80)
print("Test complete!")
