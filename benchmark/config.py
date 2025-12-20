"""
Benchmark configuration module.

Defines configuration settings for the benchmark system including:
- Ollama settings for translation
- OpenRouter settings for evaluation
- File paths and defaults
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# Default languages for quick benchmark (representative sample)
DEFAULT_QUICK_LANGUAGES = [
    # European
    "fr",       # French
    "de",       # German
    "es",       # Spanish
    "it",       # Italian
    "pt",       # Portuguese
    "pl",       # Polish
    # Asian
    "zh-Hans",  # Chinese (Simplified)
    "zh-Hant",  # Chinese (Traditional)
    "ja",       # Japanese
    "ko",       # Korean
    "vi",       # Vietnamese
    "th",       # Thai
    # South Asian
    "hi",       # Hindi
    "bn",       # Bengali
    "ta",       # Tamil
    # Cyrillic
    "ru",       # Russian
    "uk",       # Ukrainian
    # Semitic (RTL)
    "ar",       # Arabic
    "he",       # Hebrew
]

# Default evaluator model
DEFAULT_EVALUATOR_MODEL = "anthropic/claude-haiku-4.5"

# Score thresholds for visual indicators
SCORE_THRESHOLDS = {
    "excellent": 9,   # 🟢 9-10
    "good": 7,        # 🟡 7-8
    "acceptable": 5,  # 🟠 5-6
    "poor": 3,        # 🔴 3-4
    # Below 3: ⚫ Failed (1-2)
}


@dataclass
class OllamaConfig:
    """Configuration for Ollama translation provider."""

    endpoint: str = field(
        default_factory=lambda: os.getenv("API_ENDPOINT", "http://ai_server.mds.com:11434/api/generate")
    )
    default_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "mistral-small:24b")
    )
    num_ctx: int = field(
        default_factory=lambda: int(os.getenv("OLLAMA_NUM_CTX", "2048"))
    )
    timeout: int = field(
        default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "900"))
    )


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter evaluation provider."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY")
    )
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"
    default_model: str = DEFAULT_EVALUATOR_MODEL
    timeout: int = 120

    # Request headers
    site_url: str = "https://github.com/yourusername/TranslateBookWithLLM"
    site_name: str = "TranslateBookWithLLM Benchmark"


@dataclass
class PathConfig:
    """Configuration for file paths."""

    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)

    @property
    def languages_file(self) -> Path:
        return self.base_dir / "languages.yaml"

    @property
    def reference_texts_file(self) -> Path:
        return self.base_dir / "reference_texts.yaml"

    @property
    def results_dir(self) -> Path:
        return self.base_dir.parent / "benchmark_results"

    @property
    def wiki_output_dir(self) -> Path:
        return self.base_dir.parent / "wiki"

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "wiki" / "templates"


@dataclass
class BenchmarkConfig:
    """Main benchmark configuration aggregating all sub-configs."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openrouter: OpenRouterConfig = field(default_factory=OpenRouterConfig)
    paths: PathConfig = field(default_factory=PathConfig)

    # Benchmark settings
    source_language: str = "English"
    quick_languages: list = field(default_factory=lambda: DEFAULT_QUICK_LANGUAGES.copy())

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 2.0

    @classmethod
    def from_env(cls) -> "BenchmarkConfig":
        """Create configuration from environment variables."""
        return cls()

    @classmethod
    def from_cli_args(
        cls,
        openrouter_key: Optional[str] = None,
        evaluator_model: Optional[str] = None,
        ollama_endpoint: Optional[str] = None,
        **kwargs
    ) -> "BenchmarkConfig":
        """Create configuration from CLI arguments with env fallbacks."""
        config = cls()

        if openrouter_key:
            config.openrouter.api_key = openrouter_key

        if evaluator_model:
            config.openrouter.default_model = evaluator_model

        if ollama_endpoint:
            config.ollama.endpoint = ollama_endpoint

        return config

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.openrouter.api_key:
            errors.append(
                "OpenRouter API key not configured. "
                "Set OPENROUTER_API_KEY in .env or use --openrouter-key"
            )

        if not self.paths.languages_file.exists():
            errors.append(f"Languages file not found: {self.paths.languages_file}")

        if not self.paths.reference_texts_file.exists():
            errors.append(f"Reference texts file not found: {self.paths.reference_texts_file}")

        return errors


def get_score_indicator(score: float) -> str:
    """Get visual indicator emoji for a score."""
    if score >= SCORE_THRESHOLDS["excellent"]:
        return "🟢"
    elif score >= SCORE_THRESHOLDS["good"]:
        return "🟡"
    elif score >= SCORE_THRESHOLDS["acceptable"]:
        return "🟠"
    elif score >= SCORE_THRESHOLDS["poor"]:
        return "🔴"
    else:
        return "⚫"


def get_score_label(score: float) -> str:
    """Get text label for a score."""
    if score >= SCORE_THRESHOLDS["excellent"]:
        return "Excellent"
    elif score >= SCORE_THRESHOLDS["good"]:
        return "Good"
    elif score >= SCORE_THRESHOLDS["acceptable"]:
        return "Acceptable"
    elif score >= SCORE_THRESHOLDS["poor"]:
        return "Poor"
    else:
        return "Failed"
