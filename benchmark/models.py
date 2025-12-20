"""
Data models for the benchmark system.

Defines dataclasses for:
- Languages and categories
- Reference texts
- Translation and evaluation results
- Benchmark runs
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json


class LanguageCategory(Enum):
    """Categories for organizing languages."""

    EUROPEAN_MAJOR = "European Major"
    ASIAN = "Asian"
    SEMITIC = "Semitic"
    CYRILLIC = "Cyrillic"
    CLASSICAL = "Classical/Dead"
    MINORITY = "Minority/Rare"


@dataclass
class Language:
    """Represents a target language for translation."""

    code: str              # ISO 639-1 code (e.g., "fr", "zh")
    name: str              # Full name (e.g., "French", "Chinese (Simplified)")
    category: LanguageCategory
    native_name: str       # Name in the language itself (e.g., "Français", "简体中文")
    is_rtl: bool = False   # Right-to-left script
    script: str = "Latin"  # Writing system

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code,
            "name": self.name,
            "category": self.category.value,
            "native_name": self.native_name,
            "is_rtl": self.is_rtl,
            "script": self.script,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Language":
        """Create from dictionary."""
        return cls(
            code=data["code"],
            name=data["name"],
            category=LanguageCategory(data["category"]),
            native_name=data["native_name"],
            is_rtl=data.get("is_rtl", False),
            script=data.get("script", "Latin"),
        )


@dataclass
class ReferenceText:
    """A reference text for benchmark testing."""

    id: str                # Unique identifier (e.g., "pride_and_prejudice")
    title: str             # Book title
    author: str            # Author name
    year: int              # Publication year
    content: str           # The text excerpt (~500 chars)
    style: str             # Style description (e.g., "Prose narrative, irony")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "content": self.content,
            "style": self.style,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReferenceText":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            author=data["author"],
            year=data["year"],
            content=data["content"],
            style=data["style"],
        )


@dataclass
class EvaluationScores:
    """Scores from LLM evaluation of a translation."""

    accuracy: float        # 1-10: Preservation of meaning
    fluency: float         # 1-10: Natural expression
    style: float           # 1-10: Preservation of register/tone
    overall: float         # 1-10: Global score

    # Optional detailed feedback
    feedback: Optional[str] = None

    @property
    def average(self) -> float:
        """Calculate average of all scores."""
        return (self.accuracy + self.fluency + self.style + self.overall) / 4

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "accuracy": self.accuracy,
            "fluency": self.fluency,
            "style": self.style,
            "overall": self.overall,
            "feedback": self.feedback,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationScores":
        """Create from dictionary."""
        return cls(
            accuracy=data["accuracy"],
            fluency=data["fluency"],
            style=data["style"],
            overall=data["overall"],
            feedback=data.get("feedback"),
        )

    @classmethod
    def failed(cls, reason: str = "Evaluation failed") -> "EvaluationScores":
        """Create a failed evaluation with minimum scores."""
        return cls(
            accuracy=1.0,
            fluency=1.0,
            style=1.0,
            overall=1.0,
            feedback=reason,
        )


@dataclass
class TranslationResult:
    """Result of a single translation attempt."""

    source_text_id: str           # Reference to ReferenceText.id
    target_language: str          # Language code
    model: str                    # Ollama model name
    translated_text: str          # The translation output
    scores: Optional[EvaluationScores] = None

    # Metadata
    translation_time_ms: int = 0  # Time taken for translation
    evaluation_time_ms: int = 0   # Time taken for evaluation
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None   # Error message if failed

    @property
    def success(self) -> bool:
        """Check if translation succeeded."""
        return self.error is None and self.translated_text != ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_text_id": self.source_text_id,
            "target_language": self.target_language,
            "model": self.model,
            "translated_text": self.translated_text,
            "scores": self.scores.to_dict() if self.scores else None,
            "translation_time_ms": self.translation_time_ms,
            "evaluation_time_ms": self.evaluation_time_ms,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranslationResult":
        """Create from dictionary."""
        return cls(
            source_text_id=data["source_text_id"],
            target_language=data["target_language"],
            model=data["model"],
            translated_text=data["translated_text"],
            scores=EvaluationScores.from_dict(data["scores"]) if data.get("scores") else None,
            translation_time_ms=data.get("translation_time_ms", 0),
            evaluation_time_ms=data.get("evaluation_time_ms", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            error=data.get("error"),
        )


@dataclass
class ModelStats:
    """Aggregated statistics for a model across all languages."""

    model: str
    total_translations: int = 0
    successful_translations: int = 0
    avg_accuracy: float = 0.0
    avg_fluency: float = 0.0
    avg_style: float = 0.0
    avg_overall: float = 0.0
    best_language: Optional[str] = None
    worst_language: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "total_translations": self.total_translations,
            "successful_translations": self.successful_translations,
            "avg_accuracy": self.avg_accuracy,
            "avg_fluency": self.avg_fluency,
            "avg_style": self.avg_style,
            "avg_overall": self.avg_overall,
            "best_language": self.best_language,
            "worst_language": self.worst_language,
        }


@dataclass
class LanguageStats:
    """Aggregated statistics for a language across all models."""

    language_code: str
    language_name: str
    total_translations: int = 0
    successful_translations: int = 0
    avg_accuracy: float = 0.0
    avg_fluency: float = 0.0
    avg_style: float = 0.0
    avg_overall: float = 0.0
    best_model: Optional[str] = None
    worst_model: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "language_code": self.language_code,
            "language_name": self.language_name,
            "total_translations": self.total_translations,
            "successful_translations": self.successful_translations,
            "avg_accuracy": self.avg_accuracy,
            "avg_fluency": self.avg_fluency,
            "avg_style": self.avg_style,
            "avg_overall": self.avg_overall,
            "best_model": self.best_model,
            "worst_model": self.worst_model,
        }


@dataclass
class BenchmarkRun:
    """Represents a complete benchmark run."""

    run_id: str                           # Unique identifier
    started_at: str                       # ISO timestamp
    completed_at: Optional[str] = None    # ISO timestamp
    models: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    evaluator_model: str = ""
    results: list[TranslationResult] = field(default_factory=list)

    # Status
    status: str = "running"  # running, completed, failed
    error: Optional[str] = None

    @property
    def total_expected(self) -> int:
        """Total number of expected translations."""
        # 5 texts × N models × M languages
        return 5 * len(self.models) * len(self.languages)

    @property
    def total_completed(self) -> int:
        """Number of completed translations."""
        return len(self.results)

    @property
    def progress_percent(self) -> float:
        """Progress as percentage."""
        if self.total_expected == 0:
            return 0.0
        return (self.total_completed / self.total_expected) * 100

    def add_result(self, result: TranslationResult) -> None:
        """Add a translation result to the run."""
        self.results.append(result)

    def get_model_stats(self) -> list[ModelStats]:
        """Calculate statistics per model."""
        stats_by_model: dict[str, ModelStats] = {}

        for result in self.results:
            if result.model not in stats_by_model:
                stats_by_model[result.model] = ModelStats(model=result.model)

            stats = stats_by_model[result.model]
            stats.total_translations += 1

            if result.success and result.scores:
                stats.successful_translations += 1
                # Accumulate scores for averaging later
                stats.avg_accuracy += result.scores.accuracy
                stats.avg_fluency += result.scores.fluency
                stats.avg_style += result.scores.style
                stats.avg_overall += result.scores.overall

        # Calculate averages
        for stats in stats_by_model.values():
            if stats.successful_translations > 0:
                n = stats.successful_translations
                stats.avg_accuracy /= n
                stats.avg_fluency /= n
                stats.avg_style /= n
                stats.avg_overall /= n

        return list(stats_by_model.values())

    def get_language_stats(self) -> list[LanguageStats]:
        """Calculate statistics per language."""
        stats_by_lang: dict[str, LanguageStats] = {}
        # Track scores per model for each language to find best/worst
        scores_by_lang_model: dict[str, dict[str, list[float]]] = {}

        for result in self.results:
            lang = result.target_language
            if lang not in stats_by_lang:
                stats_by_lang[lang] = LanguageStats(
                    language_code=lang,
                    language_name=lang,  # Will be enriched later
                )
                scores_by_lang_model[lang] = {}

            stats = stats_by_lang[lang]
            stats.total_translations += 1

            if result.success and result.scores:
                stats.successful_translations += 1
                stats.avg_accuracy += result.scores.accuracy
                stats.avg_fluency += result.scores.fluency
                stats.avg_style += result.scores.style
                stats.avg_overall += result.scores.overall

                # Track scores per model
                if result.model not in scores_by_lang_model[lang]:
                    scores_by_lang_model[lang][result.model] = []
                scores_by_lang_model[lang][result.model].append(result.scores.overall)

        # Calculate averages and find best/worst models
        for lang, stats in stats_by_lang.items():
            if stats.successful_translations > 0:
                n = stats.successful_translations
                stats.avg_accuracy /= n
                stats.avg_fluency /= n
                stats.avg_style /= n
                stats.avg_overall /= n

                # Find best and worst model for this language
                model_avgs = {}
                for model, scores in scores_by_lang_model[lang].items():
                    if scores:
                        model_avgs[model] = sum(scores) / len(scores)

                if model_avgs:
                    stats.best_model = max(model_avgs, key=model_avgs.get)
                    stats.worst_model = min(model_avgs, key=model_avgs.get)

        return list(stats_by_lang.values())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "models": self.models,
            "languages": self.languages,
            "evaluator_model": self.evaluator_model,
            "results": [r.to_dict() for r in self.results],
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BenchmarkRun":
        """Create from dictionary."""
        run = cls(
            run_id=data["run_id"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            models=data.get("models", []),
            languages=data.get("languages", []),
            evaluator_model=data.get("evaluator_model", ""),
            status=data.get("status", "running"),
            error=data.get("error"),
        )
        run.results = [
            TranslationResult.from_dict(r) for r in data.get("results", [])
        ]
        return run

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "BenchmarkRun":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
