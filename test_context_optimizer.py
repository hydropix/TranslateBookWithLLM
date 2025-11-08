"""
Test script for context optimization features (Phase 1)
"""
import sys
import asyncio
import os

# Fix encoding for Windows console
if os.name == 'nt':
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
from src.core.context_optimizer import (
    estimate_tokens_with_margin,
    calculate_optimal_chunk_size,
    get_max_model_context,
    adjust_parameters_for_context,
    validate_configuration,
    format_estimation_info
)


def test_token_estimation():
    """Test token estimation with different languages and texts"""
    print("\n" + "="*70)
    print("TEST 1: Token Estimation")
    print("="*70)

    test_cases = [
        ("Hello world", "english"),
        ("Bonjour le monde", "french"),
        ("This is a longer text with multiple sentences. It should estimate more tokens.", "english"),
        ("Ceci est un texte plus long avec plusieurs phrases. Il devrait estimer plus de tokens.", "french"),
    ]

    for text, language in test_cases:
        estimation = estimate_tokens_with_margin(text, language, apply_margin=True)
        print(f"\nText: {text[:50]}...")
        print(f"  {format_estimation_info(estimation)}")


def test_chunk_size_calculation():
    """Test optimal chunk size calculation"""
    print("\n" + "="*70)
    print("TEST 2: Optimal Chunk Size Calculation")
    print("="*70)

    context_sizes = [2048, 4096, 8192, 16384, 32768]

    for ctx_size in context_sizes:
        optimal = calculate_optimal_chunk_size(ctx_size)
        print(f"\nContext: {ctx_size} tokens -> Optimal chunk: {optimal} lines")


def test_model_max_context():
    """Test model family context detection"""
    print("\n" + "="*70)
    print("TEST 3: Model Family Context Detection")
    print("="*70)

    models = [
        "mistral-small:24b",
        "llama3:8b",
        "gemma:7b",
        "phi3:mini",
        "qwen2:7b",
        "unknown-model:1b"
    ]

    for model in models:
        max_ctx = get_max_model_context(model)
        print(f"\nModel: {model:<25} -> Max context: {max_ctx:>6} tokens")


def test_parameter_adjustment():
    """Test automatic parameter adjustment"""
    print("\n" + "="*70)
    print("TEST 4: Parameter Adjustment")
    print("="*70)

    test_cases = [
        {
            "name": "Prompt fits in current context",
            "estimated_tokens": 1000,
            "current_num_ctx": 4096,
            "current_chunk_size": 25,
            "model_name": "mistral-small:24b"
        },
        {
            "name": "Need to increase context",
            "estimated_tokens": 3000,
            "current_num_ctx": 2048,
            "current_chunk_size": 25,
            "model_name": "mistral-small:24b"
        },
        {
            "name": "Prompt too large even for max context",
            "estimated_tokens": 20000,
            "current_num_ctx": 2048,
            "current_chunk_size": 100,
            "model_name": "mistral-small:24b"
        }
    ]

    for case in test_cases:
        print(f"\n{case['name']}:")
        print(f"  Input: estimated={case['estimated_tokens']}, num_ctx={case['current_num_ctx']}, chunk={case['current_chunk_size']}")

        adj_ctx, adj_chunk, warnings = adjust_parameters_for_context(
            estimated_tokens=case['estimated_tokens'],
            current_num_ctx=case['current_num_ctx'],
            current_chunk_size=case['current_chunk_size'],
            model_name=case['model_name']
        )

        print(f"  Output: num_ctx={adj_ctx}, chunk={adj_chunk}")
        if warnings:
            for warning in warnings:
                print(f"  ⚠️  {warning}")


def test_configuration_validation():
    """Test configuration validation"""
    print("\n" + "="*70)
    print("TEST 5: Configuration Validation")
    print("="*70)

    configs = [
        {"chunk_size": 25, "num_ctx": 2048, "model": "mistral-small:24b"},
        {"chunk_size": 25, "num_ctx": 8192, "model": "mistral-small:24b"},
        {"chunk_size": 50, "num_ctx": 8192, "model": "mistral-small:24b"},
        {"chunk_size": 100, "num_ctx": 16384, "model": "llama3:8b"},
    ]

    for config in configs:
        print(f"\nConfig: chunk_size={config['chunk_size']}, num_ctx={config['num_ctx']}, model={config['model']}")
        warnings = validate_configuration(
            chunk_size=config['chunk_size'],
            num_ctx=config['num_ctx'],
            model_name=config['model']
        )

        if warnings:
            for warning in warnings:
                print(f"  {warning}")
        else:
            print("  ✅ Configuration looks good!")


def test_realistic_prompt():
    """Test with a realistic translation prompt"""
    print("\n" + "="*70)
    print("TEST 6: Realistic Translation Prompt")
    print("="*70)

    # Simulate a realistic translation prompt
    system_instructions = """You are a professional translator. Your task is to translate the following text from English to French.

IMPORTANT RULES:
1. Preserve the original meaning and tone
2. Adapt cultural references appropriately
3. Maintain formatting and structure
4. Do not translate technical terms, URLs, or code snippets
5. Use natural, fluent French

Previous translation context:
[Previous translation here...]

Text to translate:
"""

    # Simulate chunk content (25 lines)
    chunk_content = "\n".join([f"This is line {i} of the content to translate." for i in range(1, 26)])

    full_prompt = system_instructions + chunk_content + "\n\nPlease provide the translation within <COMPLETED></COMPLETED> tags."

    estimation = estimate_tokens_with_margin(full_prompt, "english", apply_margin=True)
    print(f"\nPrompt length: {len(full_prompt)} characters")
    print(f"{format_estimation_info(estimation)}")

    # Test if it fits in different context sizes
    print("\nCompatibility with different context sizes:")
    for ctx_size in [2048, 4096, 8192]:
        required_ctx = estimation.estimated_tokens * 2  # Need 50% for output
        fits = required_ctx <= ctx_size
        status = "✅" if fits else "❌"
        print(f"  {status} num_ctx={ctx_size}: {'OK' if fits else f'Too small (need ~{required_ctx})'}")


async def test_ollama_integration():
    """Test integration with OllamaProvider (requires Ollama running)"""
    print("\n" + "="*70)
    print("TEST 7: Ollama Integration (Optional - requires Ollama running)")
    print("="*70)

    try:
        from src.core.llm_providers import OllamaProvider
        from src.config import API_ENDPOINT, DEFAULT_MODEL

        print(f"\nTrying to connect to Ollama at {API_ENDPOINT}")
        print(f"Model: {DEFAULT_MODEL}")

        # Create provider with log callback
        def log_callback(level, message):
            print(f"  [{level.upper()}] {message}")

        provider = OllamaProvider(
            api_endpoint=API_ENDPOINT,
            model=DEFAULT_MODEL,
            context_window=8192,
            log_callback=log_callback
        )

        # Try to get model context size
        print("\nQuerying model context size...")
        max_ctx = await provider.get_model_context_size()
        print(f"✅ Model maximum context: {max_ctx} tokens")

        await provider.close()

    except Exception as e:
        print(f"\n⚠️  Could not connect to Ollama: {e}")
        print("This is normal if Ollama is not running. Skipping integration test.")


def main():
    """Run all tests"""
    print("="*70)
    print("CONTEXT OPTIMIZER - PHASE 1 TESTS")
    print("="*70)

    # Run synchronous tests
    test_token_estimation()
    test_chunk_size_calculation()
    test_model_max_context()
    test_parameter_adjustment()
    test_configuration_validation()
    test_realistic_prompt()

    # Run async test
    print("\n")
    asyncio.run(test_ollama_integration())

    print("\n" + "="*70)
    print("ALL TESTS COMPLETED")
    print("="*70)
    print("\nNote: These are functional tests. For production use, consider:")
    print("  1. Installing tiktoken for better accuracy: pip install tiktoken")
    print("  2. Testing with actual translation workloads")
    print("  3. Monitoring token usage in production")


if __name__ == "__main__":
    main()
