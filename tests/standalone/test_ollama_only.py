"""
Test simple du benchmark - traduction Ollama uniquement (sans evaluation OpenRouter).
"""

import asyncio
import sys
sys.path.insert(0, '.')

from benchmark.config import BenchmarkConfig
from benchmark.runner import BenchmarkRunner
from benchmark.translator import BenchmarkTranslator, TranslationRequest, get_available_ollama_models, test_ollama_connection


async def main():
    config = BenchmarkConfig()

    print(f"Endpoint Ollama: {config.ollama.endpoint}")
    print(f"Modele par defaut: {config.ollama.default_model}")
    print()

    # Test 1: Connexion Ollama
    print("[1] Test connexion Ollama...")
    ok, msg = await test_ollama_connection(config)
    print(f"    {msg}")
    if not ok:
        print("ECHEC: Ollama non accessible")
        return 1
    print()

    # Test 2: Liste des modeles
    print("[2] Modeles disponibles...")
    models = await get_available_ollama_models(config)
    if not models:
        print("ECHEC: Aucun modele trouve")
        return 1
    for m in models[:5]:
        print(f"    - {m}")
    if len(models) > 5:
        print(f"    ... et {len(models) - 5} autres")
    print()

    # Test 3: Charger les textes de reference
    print("[3] Chargement des textes de reference...")
    runner = BenchmarkRunner(config)
    runner.load_reference_texts()
    text = list(runner._texts.values())[0]
    print(f"    Texte: {text.title} ({text.author})")
    print(f"    Extrait: {text.content[:80]}...")
    print()

    # Test 4: Traduction simple
    model = models[0]
    print(f"[4] Test traduction vers French avec {model}...")
    translator = BenchmarkTranslator(config)

    request = TranslationRequest(
        text=text,
        target_language='fr',
        target_language_name='French',
        model=model
    )

    result = await translator.translate(request)
    await translator.close()

    if result.success:
        print(f"    OK - Traduction reussie ({result.translation_time_ms}ms)")
        print(f"    Resultat: {result.translated_text[:150]}...")
        print()
        print("=== TOUS LES TESTS PASSES ===")
        return 0
    else:
        print(f"    ECHEC: {result.error}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
