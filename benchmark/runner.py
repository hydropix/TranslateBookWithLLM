"""
Benchmark orchestrator.

Coordinates the complete benchmark workflow:
1. Load languages and reference texts
2. Run translations with specified Ollama models
3. Evaluate translations with OpenRouter
4. Track progress and handle resumption
5. Generate results
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Generator

import yaml

from benchmark.config import BenchmarkConfig
from benchmark.models import (
    Language, LanguageCategory, ReferenceText, TranslationResult,
    BenchmarkRun, EvaluationScores
)
from benchmark.translator import (
    BenchmarkTranslator, TranslationRequest,
    test_ollama_connection, get_available_ollama_models,
    test_openrouter_translation_connection, get_available_openrouter_models
)
from benchmark.evaluator import (
    TranslationEvaluator, test_openrouter_connection
)


class BenchmarkRunner:
    """
    Main orchestrator for benchmark runs.

    Handles:
    - Loading configuration and data
    - Running translation + evaluation pipeline
    - Progress tracking and callbacks
    - Error handling and resumption
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        log_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        Initialize the benchmark runner.

        Args:
            config: Benchmark configuration
            log_callback: Optional callback for logging (level, message)
            progress_callback: Optional callback for progress (stage, current, total)
        """
        self.config = config
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        self._languages: dict[str, Language] = {}
        self._texts: dict[str, ReferenceText] = {}
        self._translator: Optional[BenchmarkTranslator] = None
        self._evaluator: Optional[TranslationEvaluator] = None

    def _log(self, level: str, message: str) -> None:
        """Log a message."""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level.upper()}] {message}")

    def _progress(self, stage: str, current: int, total: int) -> None:
        """Report progress."""
        if self.progress_callback:
            self.progress_callback(stage, current, total)
        else:
            percent = (current / total * 100) if total > 0 else 0
            self._log("info", f"{stage}: {current}/{total} ({percent:.1f}%)")

    def load_languages(self) -> dict[str, Language]:
        """
        Load languages from YAML configuration.

        Returns:
            Dictionary of language code -> Language
        """
        yaml_path = self.config.paths.languages_file

        if not yaml_path.exists():
            raise FileNotFoundError(f"Languages file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        languages = {}

        # Map YAML category names to enum values
        category_map = {
            "european_major": LanguageCategory.EUROPEAN_MAJOR,
            "asian": LanguageCategory.ASIAN,
            "semitic": LanguageCategory.SEMITIC,
            "cyrillic": LanguageCategory.CYRILLIC,
            "classical": LanguageCategory.CLASSICAL,
            "minority": LanguageCategory.MINORITY,
        }

        for cat_key, cat_data in data.get("categories", {}).items():
            category = category_map.get(cat_key, LanguageCategory.EUROPEAN_MAJOR)

            for lang_data in cat_data.get("languages", []):
                code = str(lang_data["code"])  # Ensure string (YAML may parse "no" as boolean)
                languages[code] = Language(
                    code=code,
                    name=lang_data["name"],
                    category=category,
                    native_name=lang_data["native_name"],
                    is_rtl=lang_data.get("rtl", False),
                    script=lang_data.get("script", "Latin"),
                )

        self._languages = languages
        self._log("info", f"Loaded {len(languages)} languages")
        return languages

    def load_reference_texts(self) -> dict[str, ReferenceText]:
        """
        Load reference texts from YAML configuration.

        Returns:
            Dictionary of text id -> ReferenceText
        """
        yaml_path = self.config.paths.reference_texts_file

        if not yaml_path.exists():
            raise FileNotFoundError(f"Reference texts file not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        texts = {}

        for text_data in data.get("texts", []):
            text_id = text_data["id"]
            texts[text_id] = ReferenceText(
                id=text_id,
                title=text_data["title"],
                author=text_data["author"],
                year=text_data["year"],
                content=text_data["text"].strip(),
                style=text_data["style"],
            )

        self._texts = texts
        self._log("info", f"Loaded {len(texts)} reference texts")
        return texts

    def get_language(self, code: str) -> Optional[Language]:
        """Get a language by code."""
        return self._languages.get(code)

    def get_text(self, text_id: str) -> Optional[ReferenceText]:
        """Get a reference text by ID."""
        return self._texts.get(text_id)

    def filter_languages(self, codes: Optional[list[str]] = None) -> list[Language]:
        """
        Filter languages by codes.

        Args:
            codes: List of language codes to include. If None, returns all.

        Returns:
            List of Language objects
        """
        if codes is None:
            return list(self._languages.values())

        return [
            self._languages[code]
            for code in codes
            if code in self._languages
        ]

    async def validate_setup(self) -> tuple[bool, list[str]]:
        """
        Validate the benchmark setup.

        Returns:
            Tuple of (all_valid, list of error messages)
        """
        errors = []

        # Validate config
        config_errors = self.config.validate()
        errors.extend(config_errors)

        # Test translation provider connection
        if self.config.translation_provider == "openrouter":
            # Test OpenRouter for translation
            or_trans_ok, or_trans_msg = await test_openrouter_translation_connection(self.config)
            if not or_trans_ok:
                errors.append(f"OpenRouter (translation): {or_trans_msg}")
            else:
                self._log("info", f"OpenRouter (translation): {or_trans_msg}")
        else:
            # Test Ollama connection
            ollama_ok, ollama_msg = await test_ollama_connection(self.config)
            if not ollama_ok:
                errors.append(f"Ollama: {ollama_msg}")
            else:
                self._log("info", f"Ollama: {ollama_msg}")

        # Test OpenRouter connection (for evaluation - always required)
        openrouter_ok, openrouter_msg = await test_openrouter_connection(self.config)
        if not openrouter_ok:
            errors.append(f"OpenRouter (evaluation): {openrouter_msg}")
        else:
            self._log("info", f"OpenRouter (evaluation): {openrouter_msg}")

        return len(errors) == 0, errors

    def _generate_jobs(
        self,
        models: list[str],
        languages: list[Language],
        texts: list[ReferenceText],
        existing_results: Optional[list[TranslationResult]] = None
    ) -> Generator[TranslationRequest, None, None]:
        """
        Generate translation jobs, skipping already completed ones.

        Args:
            models: List of Ollama model names
            languages: List of target languages
            texts: List of reference texts
            existing_results: Results from a previous run (for resumption)

        Yields:
            TranslationRequest objects
        """
        # Build set of completed jobs for fast lookup
        completed = set()
        if existing_results:
            for result in existing_results:
                if result.success:
                    key = (result.source_text_id, result.target_language, result.model)
                    completed.add(key)

        # Generate jobs for all combinations
        for model in models:
            for language in languages:
                for text in texts:
                    key = (text.id, language.code, model)
                    if key not in completed:
                        yield TranslationRequest(
                            text=text,
                            target_language=language.code,
                            target_language_name=language.name,
                            model=model
                        )

    async def run(
        self,
        models: list[str],
        language_codes: Optional[list[str]] = None,
        resume_run: Optional[BenchmarkRun] = None
    ) -> BenchmarkRun:
        """
        Execute a complete benchmark run.

        Args:
            models: List of Ollama model names to benchmark
            language_codes: Language codes to test (None = quick test set)
            resume_run: Optional previous run to resume

        Returns:
            BenchmarkRun with all results
        """
        # Load data if not already loaded
        if not self._languages:
            self.load_languages()
        if not self._texts:
            self.load_reference_texts()

        # Determine languages to test
        if language_codes is None:
            language_codes = self.config.quick_languages

        languages = self.filter_languages(language_codes)
        texts = list(self._texts.values())

        if not languages:
            raise ValueError("No valid languages specified")
        if not models:
            raise ValueError("No models specified")

        # Create or resume run
        if resume_run:
            run = resume_run
            run.status = "running"
            self._log("info", f"Resuming run {run.run_id} ({run.total_completed}/{run.total_expected} completed)")
        else:
            run = BenchmarkRun(
                run_id=str(uuid.uuid4())[:8],
                started_at=datetime.now().isoformat(),
                models=models,
                languages=language_codes,
                evaluator_model=self.config.openrouter.default_model,
            )
            self._log("info", f"Starting new run {run.run_id}")

        # Log run parameters
        self._log("info", f"Models: {', '.join(models)}")
        self._log("info", f"Languages: {', '.join([l.name for l in languages])}")
        self._log("info", f"Texts: {len(texts)}")
        self._log("info", f"Total translations: {run.total_expected}")

        # Initialize translator and evaluator
        self._translator = BenchmarkTranslator(
            self.config,
            self.log_callback,
            provider_type=self.config.translation_provider
        )
        self._evaluator = TranslationEvaluator(self.config, self.log_callback)

        try:
            # Generate jobs
            jobs = list(self._generate_jobs(
                models=models,
                languages=languages,
                texts=texts,
                existing_results=run.results if resume_run else None
            ))

            self._log("info", f"Jobs to process: {len(jobs)}")

            # Process jobs
            for i, job in enumerate(jobs):
                self._progress("translation", i + 1, len(jobs))

                # Translate
                result = await self._translator.translate(job)

                # Evaluate if translation succeeded
                if result.success and result.translated_text:
                    source_text = self.get_text(result.source_text_id)
                    if source_text:
                        scores, eval_time = await self._evaluator.evaluate(
                            source_text=source_text,
                            translated_text=result.translated_text,
                            target_language=result.target_language,
                            target_language_name=job.target_language_name
                        )
                        result.scores = scores
                        result.evaluation_time_ms = eval_time

                        # Log score
                        self._log(
                            "info",
                            f"  Score: {scores.overall:.1f}/10 "
                            f"(acc={scores.accuracy:.1f}, flu={scores.fluency:.1f}, sty={scores.style:.1f})"
                        )

                # Add to run
                run.add_result(result)

                # Progress update
                self._progress("overall", run.total_completed, run.total_expected)

            # Complete run
            run.status = "completed"
            run.completed_at = datetime.now().isoformat()

            # Log summary
            self._log("info", "=" * 50)
            self._log("info", f"Run {run.run_id} completed")
            self._log("info", f"Total translations: {run.total_completed}")
            self._log("info", f"Success rate: {sum(1 for r in run.results if r.success) / len(run.results) * 100:.1f}%")

            # Evaluation cost summary
            cost_summary = self._evaluator.get_cost_summary()
            self._log("info", f"Evaluation cost: ${cost_summary['total_cost_usd']:.4f}")

            return run

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.now().isoformat()
            self._log("error", f"Run failed: {e}")
            raise

        finally:
            await self.close()

    async def close(self) -> None:
        """Clean up resources."""
        if self._translator:
            await self._translator.close()
        if self._evaluator:
            await self._evaluator.close()


async def quick_benchmark(
    config: BenchmarkConfig,
    models: Optional[list[str]] = None,
    log_callback: Optional[Callable[[str, str], None]] = None
) -> BenchmarkRun:
    """
    Run a quick benchmark with default settings.

    Args:
        config: Benchmark configuration
        models: Optional list of models (defaults to available Ollama models)
        log_callback: Optional logging callback

    Returns:
        BenchmarkRun with results
    """
    runner = BenchmarkRunner(config, log_callback)

    # Validate setup
    valid, errors = await runner.validate_setup()
    if not valid:
        raise RuntimeError(f"Setup validation failed: {'; '.join(errors)}")

    # Get models if not specified
    if models is None:
        models = await get_available_ollama_models(config)
        if not models:
            raise RuntimeError("No Ollama models available")
        # Limit to first 3 models for quick benchmark
        models = models[:3]

    return await runner.run(models=models)


async def full_benchmark(
    config: BenchmarkConfig,
    models: list[str],
    log_callback: Optional[Callable[[str, str], None]] = None
) -> BenchmarkRun:
    """
    Run a full benchmark with all languages.

    Args:
        config: Benchmark configuration
        models: List of Ollama models to benchmark
        log_callback: Optional logging callback

    Returns:
        BenchmarkRun with results
    """
    runner = BenchmarkRunner(config, log_callback)

    # Load all languages
    runner.load_languages()
    all_language_codes = list(runner._languages.keys())

    return await runner.run(models=models, language_codes=all_language_codes)
