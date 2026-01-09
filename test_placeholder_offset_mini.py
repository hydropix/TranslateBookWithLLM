"""
Test script to validate placeholder offset logic for EPUB chunks.
"""
import re
from typing import Dict, List, Tuple

print('Test placeholder offset logic')
print('=' * 80)

# Test 1: Simple renumbering
full_text = '[[5]]Hello [[6]]beautiful[[7]] world[[8]]'
print(f'Original: {full_text}')

# Simulate chunking - renumber locally
global_placeholders = re.findall(r'\[\[\d+\]\]', full_text)
local_text = full_text
for i, gp in enumerate(global_placeholders):
    local_text = local_text.replace(gp, f'__TEMP_{i}__')
for i in range(len(global_placeholders)):
    local_text = local_text.replace(f'__TEMP_{i}__', f'[[{i}]]')

print(f'Chunked (local): {local_text}')
print(f'Global indices: {[int(p[2:-2]) for p in global_placeholders]}')
