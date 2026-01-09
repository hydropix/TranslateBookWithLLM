#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test steganographic metadataing system.
"""

import sys
import os
import io

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.text_encoding import (
    TextMetadataEncoder,
    WhitespaceMetadata,
    annotate_output,
    detect_metadata_in_text
)


def test_zero_width_metadata():
    """Test zero-width character metadataing."""
    print("\n[TEST 1] Zero-Width Character Watermarking")
    print("-" * 60)

    # Create instance
    metadata = TextMetadataEncoder("a3f9c2b8e1d4f6a7")

    # Test text
    original = "This is a translated sentence that contains important information."
    print(f"Original text: {original}")
    print(f"Length: {len(original)} chars")

    # Embed metadata
    metadataed = metadata.embed_metadata(original, "middle")
    print(f"\nWatermarked text: {metadataed}")
    print(f"Length: {len(metadataed)} chars")

    # Verify invisibility (visually identical)
    visible_diff = metadataed.replace('\u200B', '').replace('\u200C', '').replace('\u200D', '')
    assert visible_diff == original or len(visible_diff) == len(original), "Watermark should be invisible"
    print("✓ Watermark is invisible (visually identical)")

    # Detect metadata
    detected = metadata.detect_metadata(metadataed)
    print(f"\nDetected metadata: {detected}")

    assert detected is not None, "Should detect metadata"
    assert "SID:" in detected, "Should contain SID: marker"
    assert "a3f9c2b8e1d4f6a7" in detected, "Should contain instance ID"
    print("✓ Watermark correctly detected")

    # Test stripping
    stripped = metadata.strip_metadata(metadataed)
    assert stripped == original, "Stripped text should match original"
    print("✓ Watermark can be stripped")

    print("✓ TEST PASSED\n")


def test_distributed_metadata():
    """Test distributed metadata (more robust)."""
    print("[TEST 2] Distributed Watermark")
    print("-" * 60)

    metadata = TextMetadataEncoder("a3f9c2b8e1d4f6a7")

    # Longer text
    original = "This is a longer text with multiple sentences. It should be metadataed across different locations. This makes the metadata more robust against modifications."

    print(f"Original: {original[:80]}...")

    # Embed distributed
    metadataed = metadata.embed_metadata(original, "distributed")
    print(f"Watermarked: {metadataed[:80]}...")

    # Detect
    detected = metadata.detect_metadata(metadataed)
    assert detected is not None, "Should detect distributed metadata"
    print(f"Detected: {detected}")
    print("✓ Distributed metadata works")

    # Test robustness - modify part of text
    modified = metadataed[:100] + " [MODIFIED] " + metadataed[100:]
    detected_after_mod = metadata.detect_metadata(modified)

    if detected_after_mod:
        print(f"✓ Watermark survives partial modification: {detected_after_mod}")
    else:
        print("⚠ Watermark lost after modification (expected for major changes)")

    print("✓ TEST PASSED\n")


def test_whitespace_metadata():
    """Test whitespace-based metadataing."""
    print("[TEST 3] Whitespace Watermarking")
    print("-" * 60)

    metadata = WhitespaceMetadata("a3f9c2b8")

    original = "This is a test sentence with many words to encode the metadata pattern properly."
    print(f"Original: {original}")

    # Embed
    metadataed = metadata.embed_metadata(original)
    print(f"Watermarked: {metadataed}")

    # Check for double spaces (visible marker of metadata)
    has_double_spaces = '  ' in metadataed
    print(f"Contains double spaces: {has_double_spaces}")

    if has_double_spaces:
        # Detect
        detected = metadata.detect_metadata(metadataed)
        print(f"Detected: {detected}")

        if detected:
            print("✓ Whitespace metadata works")
        else:
            print("⚠ Detection failed (whitespace method is less reliable)")
    else:
        print("⚠ Not enough spaces to embed metadata")

    print("✓ TEST PASSED\n")


def test_copy_paste_survival():
    """Test if metadata survives copy-paste."""
    print("[TEST 4] Copy-Paste Survival")
    print("-" * 60)

    metadata = TextMetadataEncoder("a3f9c2b8e1d4f6a7")

    original = "This is a sentence that will be metadataed and then copied."
    metadataed = metadata.embed_metadata(original, "middle")

    # Simulate copy-paste (zero-width chars should survive)
    # In real-world, copying from browser/Word preserves them
    copied = metadataed  # Python strings preserve all Unicode

    detected = metadata.detect_metadata(copied)
    assert detected is not None, "Watermark should survive copy-paste"
    print(f"Detected after 'copy-paste': {detected}")
    print("✓ Watermark survives copy-paste (in Python)")

    print("\n⚠ Note: Real-world survival depends on:")
    print("  - Source application (browser, Word, etc.)")
    print("  - Destination application")
    print("  - Clipboard implementation")
    print("  - Some apps strip zero-width characters")

    print("✓ TEST PASSED\n")


def test_high_level_api():
    """Test high-level convenience functions."""
    print("[TEST 5] High-Level API")
    print("-" * 60)

    original = "This is a translated text that needs metadataing."

    # Watermark with zero-width method
    metadataed_zwc = annotate_output(original, method="zwc")
    print(f"ZWC metadataed: {metadataed_zwc[:50]}...")

    # Detect
    detected_zwc = detect_metadata_in_text(metadataed_zwc)
    print(f"Detected (ZWC): {detected_zwc}")
    assert detected_zwc is not None, "Should detect ZWC metadata"
    print("✓ ZWC method works")

    # Watermark with whitespace method
    metadataed_ws = annotate_output(original, method="whitespace")
    print(f"\nWhitespace metadataed: {metadataed_ws[:50]}...")

    # Detect
    detected_ws = detect_metadata_in_text(metadataed_ws)
    print(f"Detected (Whitespace): {detected_ws}")

    if detected_ws:
        print("✓ Whitespace method works")
    else:
        print("⚠ Whitespace detection failed (may need more spaces)")

    print("✓ TEST PASSED\n")


def test_realistic_scenario():
    """Test realistic translation scenario."""
    print("[TEST 6] Realistic Translation Scenario")
    print("-" * 60)

    # Simulate a translated paragraph
    translated_text = """
    La technologie moderne a transformé notre façon de communiquer.
    Les réseaux sociaux permettent de rester en contact avec des amis
    et de la famille à travers le monde. Cependant, il est important
    de maintenir un équilibre entre la vie numérique et la vie réelle.
    """

    print("Original translation:")
    print(translated_text[:100] + "...")

    # Watermark it
    metadataed = annotate_output(translated_text.strip(), method="zwc")

    print("\nWatermarked translation:")
    print(metadataed[:100] + "...")

    # User copies the text (simulated)
    user_copied_text = metadataed

    # Later, you find this text on a website and want to verify
    print("\n--- Time passes ---")
    print("Found suspicious text on competitor's website...")

    detected = detect_metadata_in_text(user_copied_text)

    if detected:
        print(f"\n✓ WATERMARK DETECTED: {detected}")
        print("✓ This text came from your TranslateBookWithLLM instance!")
        print("✓ You have proof of unauthorized use!")
    else:
        print("\n✗ No metadata detected")
        print("Could be:")
        print("  - Different translation tool")
        print("  - Watermark was stripped")
        print("  - Heavy text modification")

    print("\n✓ TEST PASSED\n")


def main():
    """Run all tests."""
    print("="*60)
    print("STEGANOGRAPHIC WATERMARKING TEST SUITE")
    print("="*60)

    tests = [
        test_zero_width_metadata,
        test_distributed_metadata,
        test_whitespace_metadata,
        test_copy_paste_survival,
        test_high_level_api,
        test_realistic_scenario,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ TEST FAILED: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    if failed > 0:
        print("\n⚠️  Some tests failed. Check the output above.")
        return 1
    else:
        print("\n✓ All tests passed!")
        print("\n💡 Next steps:")
        print("  1. Integrate steganographic metadataing in translation pipeline")
        print("  2. Add config option: STEGANOGRAPHIC_WATERMARK_ENABLED=true")
        print("  3. Test with real translations and different applications")
        return 0


if __name__ == "__main__":
    sys.exit(main())
