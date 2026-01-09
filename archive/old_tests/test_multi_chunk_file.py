"""Test multi-chunk file scenario to identify the renumbering issue"""
import re

def simulate_create_chunk(segments, global_tag_map, global_offset):
    """Simulate the _create_chunk() method"""
    merged_text = "".join(segments)

    # Find all global placeholders in this chunk
    global_placeholders = re.findall(r'\[\[\d+\]\]', merged_text)
    global_placeholders = list(dict.fromkeys(global_placeholders))

    # Create local mapping
    local_tag_map = {}
    global_indices = []
    renumbered_text = merged_text

    for local_idx, global_placeholder in enumerate(global_placeholders):
        local_placeholder = f"[[{local_idx}]]"
        local_tag_map[local_placeholder] = global_tag_map.get(global_placeholder, "")

        # Extract global index
        global_idx = int(global_placeholder[2:-2])
        global_indices.append(global_idx)

        # Renumber in text
        renumbered_text = renumbered_text.replace(global_placeholder, local_placeholder)

    return {
        'text': renumbered_text,
        'local_tag_map': local_tag_map,
        'global_offset': global_offset,
        'global_indices': global_indices
    }

def test_multi_chunk_scenario():
    """
    Simulate a file like part0000_split_002.html that has many placeholders
    and gets split into multiple chunks
    """

    print("=" * 70)
    print("SCENARIO: Large file split into 3 chunks")
    print("=" * 70)
    print()

    # After TagPreserver, the entire file has placeholders [[0]] to [[20]]
    full_text_with_placeholders = (
        "[[0]]Text1[[1]][[2]]Text2[[3]][[4]]Text3[[5]][[6]]Text4[[7]]"
        "[[8]]Text5[[9]][[10]]Text6[[11]][[12]]Text7[[13]][[14]]Text8[[15]]"
        "[[16]]Text9[[17]][[18]]Text10[[19]][[20]]"
    )

    global_tag_map = {f"[[{i}]]": f"<tag{i}>" for i in range(21)}

    print(f"Full text after TagPreserver (with global indices):")
    print(f"  {full_text_with_placeholders[:80]}...")
    print()

    # HtmlChunker splits this into 3 chunks based on token limits
    # Chunk 1: [[0]] to [[6]]
    # Chunk 2: [[7]] to [[13]]
    # Chunk 3: [[14]] to [[20]]

    chunks_data = [
        {
            'segments': ["[[0]]Text1[[1]][[2]]Text2[[3]][[4]]Text3[[5]][[6]]"],
            'global_offset': 0,
            'name': 'Chunk 1'
        },
        {
            'segments': ["Text4[[7]][[8]]Text5[[9]][[10]]Text6[[11]][[12]]"],
            'global_offset': 7,  # This is where the bug might be
            'name': 'Chunk 2'
        },
        {
            'segments': ["Text7[[13]][[14]]Text8[[15]][[16]]Text9[[17]][[18]]Text10[[19]][[20]]"],
            'global_offset': 13,  # This is where the bug might be
            'name': 'Chunk 3'
        }
    ]

    for chunk_data in chunks_data:
        print(f"{chunk_data['name']} (global_offset={chunk_data['global_offset']}):")
        print(f"  Segments: {chunk_data['segments']}")

        chunk = simulate_create_chunk(
            chunk_data['segments'],
            global_tag_map,
            chunk_data['global_offset']
        )

        print(f"  Text sent to LLM: {chunk['text']}")
        print(f"  Global indices: {chunk['global_indices']}")

        # Check if local indices start at 0
        if chunk['text'].startswith("[[0]]") or "[[0]]" in chunk['text']:
            print(f"  Result: OK - Contains [[0]]")
        else:
            # Extract first placeholder index
            match = re.search(r'\[\[(\d+)\]\]', chunk['text'])
            if match:
                first_idx = match.group(1)
                print(f"  Result: BUG - First placeholder is [[{first_idx}]], should be [[0]]!")
        print()

if __name__ == "__main__":
    test_multi_chunk_scenario()
