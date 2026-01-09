#!/usr/bin/env python3
"""Test placeholder offset logic"""
import re

def test():
    # Test 1: Renumbering from global to local
    global_text = '[[5]]Hello [[6]]world[[7]]'
    print('Global:', global_text)
    
    # Find placeholders
    phs = re.findall(r'\[\[\d+\]\]', global_text)
    global_indices = [int(p[2:-2]) for p in phs]
    print('Global indices:', global_indices)
    
    # Renumber locally (0, 1, 2...)
    local_text = global_text
    for i, ph in enumerate(phs):
        local_text = local_text.replace(ph, f'__T{i}__')
    for i in range(len(phs)):
        local_text = local_text.replace(f'__T{i}__', f'[[{i}]]')
    
    print('Local:', local_text)
    
    # Simulate translation
    translated = 'Bonjour [[0]]monde[[1]]'
    print('Translated:', translated)
    
    # Restore global indices
    restored = translated
    for local_idx, global_idx in enumerate(global_indices):
        restored = restored.replace(f'[[{local_idx}]]', f'__R{local_idx}__')
    for local_idx, global_idx in enumerate(global_indices):
        restored = restored.replace(f'__R{local_idx}__', f'[[{global_idx}]]')
    
    print('Restored:', restored)
    expected = 'Bonjour [[6]]monde[[7]]'
    print('Expected:', expected)
    print('SUCCESS' if restored == expected else 'FAIL')

if __name__ == '__main__':
    test()
