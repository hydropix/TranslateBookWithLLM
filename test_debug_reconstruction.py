"""
Debug test to understand the reconstruction issue
"""
import re


def simulate_epub_chunk_workflow():
    """
    Simulate the actual EPUB translation workflow to find the bug
    """
    print("=" * 70)
    print("Simulating EPUB translation workflow")
    print("=" * 70)
    print()

    # Step 1: Original HTML body
    original_body = """<p>Paragraph 1 text here.</p>
<p>Paragraph 2 text here.</p>
<p>Paragraph 3 text here.</p>"""

    print("Step 1: Original HTML body")
    print(original_body)
    print()

    # Step 2: TagPreserver preserves tags (simplified - no boundary stripping for clarity)
    # Creates global_tag_map: {"[[0]]": "<p>", "[[1]]": "</p>", ...}
    text_with_placeholders = "[[0]]Paragraph 1 text here.[[1]][[2]]Paragraph 2 text here.[[3]][[4]]Paragraph 3 text here.[[5]]"
    global_tag_map = {
        "[[0]]": "<p>",
        "[[1]]": "</p>",
        "[[2]]": "<p>",
        "[[3]]": "</p>",
        "[[4]]": "<p>",
        "[[5]]": "</p>"
    }

    print("Step 2: After TagPreserver.preserve_tags()")
    print(f"  Text with placeholders: {text_with_placeholders}")
    print(f"  Global tag map: {global_tag_map}")
    print()

    # Step 3: HtmlChunker splits into chunks with LOCAL indices
    # Chunk 0: [[0]]Paragraph 1 text here.[[1]]
    # Chunk 1: [[0]]Paragraph 2 text here.[[1]]
    # Chunk 2: [[0]]Paragraph 3 text here.[[1]]

    chunks = [
        {
            'text': '[[0]]Paragraph 1 text here.[[1]]',
            'local_tag_map': {'[[0]]': '<p>', '[[1]]': '</p>'},
            'global_indices': [0, 1]
        },
        {
            'text': '[[0]]Paragraph 2 text here.[[1]]',
            'local_tag_map': {'[[0]]': '<p>', '[[1]]': '</p>'},
            'global_indices': [2, 3]
        },
        {
            'text': '[[0]]Paragraph 3 text here.[[1]]',
            'local_tag_map': {'[[0]]': '<p>', '[[1]]': '</p>'},
            'global_indices': [4, 5]
        }
    ]

    print("Step 3: After HtmlChunker.chunk_html_with_placeholders()")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {chunk['text']}")
        print(f"    Local map: {chunk['local_tag_map']}")
        print(f"    Global indices: {chunk['global_indices']}")
    print()

    # Step 4: Translate each chunk
    # For this test, assume translation succeeds and we get:
    # Chunk 0: [[0]]Texte paragraphe 1 ici.[[1]]  (still local indices!)
    # Chunk 1: [[0]]Texte paragraphe 2 ici.[[1]]  (still local indices!)
    # Chunk 2: [[0]]Texte paragraphe 3 ici.[[1]]  (still local indices!)

    translated_chunks_local = [
        '[[0]]Texte paragraphe 1 ici.[[1]]',
        '[[0]]Texte paragraphe 2 ici.[[1]]',
        '[[0]]Texte paragraphe 3 ici.[[1]]'
    ]

    print("Step 4: After translation (still with LOCAL indices)")
    for i, chunk in enumerate(translated_chunks_local):
        print(f"  Chunk {i}: {chunk}")
    print()

    # Step 5: PlaceholderManager.restore_to_global() for each chunk
    def restore_to_global(text, global_indices):
        result = text
        for local_idx in range(len(global_indices)):
            result = result.replace(f"[[{local_idx}]]", f"__RESTORE_{local_idx}__")
        for local_idx, global_idx in enumerate(global_indices):
            result = result.replace(f"__RESTORE_{local_idx}__", f"[[{global_idx}]]")
        return result

    translated_chunks_global = [
        restore_to_global(translated_chunks_local[0], chunks[0]['global_indices']),
        restore_to_global(translated_chunks_local[1], chunks[1]['global_indices']),
        restore_to_global(translated_chunks_local[2], chunks[2]['global_indices'])
    ]

    print("Step 5: After PlaceholderManager.restore_to_global()")
    for i, chunk in enumerate(translated_chunks_global):
        print(f"  Chunk {i}: {chunk}")
    print()

    # Step 6: Join chunks
    full_translated = "".join(translated_chunks_global)

    print("Step 6: After joining chunks")
    print(f"  Full text: {full_translated}")
    print()

    # Step 7: TagPreserver.restore_tags()
    # This should replace ALL placeholders with their tags from global_tag_map

    def restore_tags(text, tag_map):
        """Simplified version of restore_tags"""
        restored = text
        # Sort by number (reverse) to avoid partial replacements
        placeholders = sorted(tag_map.keys(),
                            key=lambda p: int(p[2:-2]),
                            reverse=True)
        for placeholder in placeholders:
            if placeholder in restored:
                restored = restored.replace(placeholder, tag_map[placeholder])
        return restored

    final_html = restore_tags(full_translated, global_tag_map)

    print("Step 7: After TagPreserver.restore_tags()")
    print(f"  Final HTML: {final_html}")
    print()

    # Check result
    expected = """<p>Texte paragraphe 1 ici.</p><p>Texte paragraphe 2 ici.</p><p>Texte paragraphe 3 ici.</p>"""

    print("=" * 70)
    print(f"Expected: {expected}")
    print(f"Got:      {final_html}")
    print(f"Match: {final_html == expected}")
    print("=" * 70)

    # This should work! So where's the actual bug?
    # Let me add some debug to see what might be wrong...


if __name__ == "__main__":
    simulate_epub_chunk_workflow()
