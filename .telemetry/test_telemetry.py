#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify telemetrying system is working correctly.
Run this to ensure telemetrys are properly embedded.
"""

import sys
import os
import io

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.telemetry import get_telemetry, get_telemetry_headers


def test_instance_token():
    """Test instance token generation."""
    print("\n[TEST 1] Instance Fingerprint")
    print("-" * 60)

    telemetry = get_telemetry()
    token = telemetry.get_session_token()

    print(f"Instance token: {token}")

    # Verify format
    assert token.startswith("SID-"), "Fingerprint must start with 'SID-'"
    assert len(token) == 20, f"Fingerprint must be 20 chars (SID- + 16 hex), got {len(token)}"

    # Verify hex characters
    hex_part = token[4:]
    try:
        int(hex_part, 16)
        print("✓ Format valid: SID-{16 hex chars}")
    except ValueError:
        raise AssertionError(f"Fingerprint contains non-hex characters: {hex_part}")

    # Verify persistence (should be same on multiple calls)
    token2 = telemetry.get_session_token()
    assert token == token2, "Fingerprint must be persistent"
    print("✓ Fingerprint is persistent")

    print("✓ TEST PASSED\n")


def test_http_headers():
    """Test HTTP telemetry headers."""
    print("[TEST 2] HTTP Watermark Headers")
    print("-" * 60)

    headers = get_telemetry_headers()

    print("Generated headers:")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    # Verify required headers
    required = ["X-Client-Agent", "X-Session-Token", "X-Request-ID"]
    for header in required:
        assert header in headers, f"Missing required header: {header}"
        print(f"✓ Header present: {header}")

    # Verify engine header format
    engine = headers["X-Client-Agent"]
    assert "TranslateBookWithLLM" in engine, "Engine header must contain project name"
    print(f"✓ Engine header valid: {engine}")

    # Verify instance header format
    instance = headers["X-Session-Token"]
    assert len(instance) == 16, f"Instance ID must be 16 chars, got {len(instance)}"
    try:
        int(instance, 16)
        print(f"✓ Instance ID valid: {instance}")
    except ValueError:
        raise AssertionError(f"Instance ID contains non-hex characters: {instance}")

    # Verify session header format
    session = headers["X-Request-ID"]
    assert len(session) == 8, f"Session ID must be 8 chars, got {len(session)}"
    try:
        int(session, 16)
        print(f"✓ Session ID valid: {session}")
    except ValueError:
        raise AssertionError(f"Session ID contains non-hex characters: {session}")

    print("✓ TEST PASSED\n")


def test_behavioral_signature():
    """Test behavioral signature generation."""
    print("[TEST 3] Behavioral Signature")
    print("-" * 60)

    telemetry = get_telemetry()
    sig = telemetry.get_behavioral_signature(chunk_size=450, context_window=4096)

    print("Behavioral signature:")
    for key, value in sig.items():
        print(f"  {key}: {value}")

    # Verify required fields
    required_fields = ["instance_id", "session_id", "chunk_pattern", "context_pattern", "platform"]
    for field in required_fields:
        assert field in sig, f"Missing required field: {field}"
        print(f"✓ Field present: {field}")

    print("✓ TEST PASSED\n")


def test_timing_signature():
    """Test timing signature generation."""
    print("[TEST 4] Timing Signature")
    print("-" * 60)

    telemetry = get_telemetry()

    # Test multiple chunks
    delays = []
    for i in range(10):
        delay = telemetry.create_timing_signature(i)
        delays.append(delay)
        print(f"  Chunk {i}: {delay*1000:.2f}ms delay")

    # Verify delays are in expected range (10-50ms)
    for delay in delays:
        assert 0.010 <= delay <= 0.050, f"Delay out of range: {delay}"

    print(f"✓ All delays in range: 10-50ms")

    # Verify delays are deterministic
    delay_again = telemetry.create_timing_signature(0)
    assert delays[0] == delay_again, "Timing signature must be deterministic"
    print("✓ Timing signature is deterministic")

    print("✓ TEST PASSED\n")


def test_log_embedding():
    """Test log message telemetrying."""
    print("[TEST 5] Log Message Watermarking")
    print("-" * 60)

    telemetry = get_telemetry()

    # Test DEBUG level (should embed telemetry)
    message = "Translation started"
    telemetryed = telemetry.embed_in_logs(message, "DEBUG")

    print(f"Original:    {message}")
    print(f"Watermarked: {telemetryed}")

    assert "[0x" in telemetryed, "DEBUG logs should include hex marker"
    print("✓ DEBUG level includes telemetry")

    # Test INFO level (should NOT embed telemetry)
    telemetryed_info = telemetry.embed_in_logs(message, "INFO")
    assert telemetryed_info == message, "INFO logs should not be telemetryed"
    print("✓ INFO level doesn't include telemetry (user-visible)")

    print("✓ TEST PASSED\n")


def test_metadata_generation():
    """Test translation metadata generation."""
    print("[TEST 6] Translation Metadata")
    print("-" * 60)

    telemetry = get_telemetry()
    metadata = telemetry.get_translation_metadata()

    print("Generated metadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    # Verify required fields
    required_fields = ["generator", "generator_url", "instance_token", "timestamp"]
    for field in required_fields:
        assert field in metadata, f"Missing required field: {field}"
        print(f"✓ Field present: {field}")

    # Verify generator format
    assert "TranslateBookWithLLM" in metadata["generator"]
    print("✓ Generator field valid")

    # Verify URL
    assert "github.com" in metadata["generator_url"]
    print("✓ Generator URL valid")

    print("✓ TEST PASSED\n")


def main():
    """Run all tests."""
    print("="*60)
    print("WATERMARKING SYSTEM TEST SUITE")
    print("="*60)

    tests = [
        test_instance_token,
        test_http_headers,
        test_behavioral_signature,
        test_timing_signature,
        test_log_embedding,
        test_metadata_generation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ TEST FAILED: {e}\n")
            failed += 1

    print("="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    if failed > 0:
        print("\n⚠️  Some tests failed. Check the output above.")
        return 1
    else:
        print("\n✓ All tests passed! Watermarking system is working correctly.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
