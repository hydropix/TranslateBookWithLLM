"""
Prompt Optimizer - Automatic prompt optimization for translation via reinforcement learning.

This module provides tools to automatically optimize translation prompts using
a genetic algorithm with LLM-based fitness evaluation.

Usage:
    python -m prompt_optimizer.optimize --config prompt_optimizer_config.yaml

Modules:
    - config: Configuration loading and validation
    - prompt_template: Prompt representation and mutation strategies
    - llm_adapter: Adapters for Ollama (translation) and OpenRouter (evaluation)
    - fitness: Fitness calculation with anti-overfitting penalties
    - cross_validator: K-fold cross-validation
    - history: Result persistence and reporting
    - optimize: Main optimization loop
"""

from prompt_optimizer.config import (
    OptimizerConfig,
    load_config,
    validate_config,
)
from prompt_optimizer.prompt_template import (
    PromptTemplate,
    MutationStrategy,
    EvaluationFeedback,
)
from prompt_optimizer.fitness import (
    FitnessCalculator,
    FitnessScore,
)
from prompt_optimizer.llm_adapter import (
    LLMAdapter,
    TranslationResult,
    EvaluationResult,
)
from prompt_optimizer.cross_validator import (
    CrossValidator,
    CrossValidationSplit,
)
from prompt_optimizer.history import (
    HistoryManager,
    OptimizationReport,
)
from prompt_optimizer.optimize import (
    PromptOptimizer,
)

__version__ = "2.0.0"
__all__ = [
    # Config
    "OptimizerConfig",
    "load_config",
    "validate_config",
    # Templates
    "PromptTemplate",
    "MutationStrategy",
    "EvaluationFeedback",
    # Fitness
    "FitnessCalculator",
    "FitnessScore",
    # LLM
    "LLMAdapter",
    "TranslationResult",
    "EvaluationResult",
    # Cross-validation
    "CrossValidator",
    "CrossValidationSplit",
    # History
    "HistoryManager",
    "OptimizationReport",
    # Main
    "PromptOptimizer",
]
