"""
Configuration loader and validator for the prompt optimizer.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml
from dotenv import load_dotenv


@dataclass
class TextConfig:
    """Configuration for a reference text."""
    id: str
    title: str
    author: str
    style: str
    source_language: str
    target_language: str
    content: str
    challenges: list[str] = field(default_factory=list)


@dataclass
class OllamaConfig:
    """Configuration for Ollama (test LLM)."""
    endpoint: str = "http://localhost:11434/api/generate"
    model: str = "qwen3:4b"
    timeout: int = 120
    num_ctx: int = 8192


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter (evaluator LLM)."""
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"
    model: str = "anthropic/claude-sonnet-4"
    api_key: str = ""
    timeout: int = 60
    site_url: str = "https://github.com/hydropix/TranslateBookWithLLM"
    site_name: str = "PromptOptimizer"


@dataclass
class MutationConfig:
    """
    Configuration for prompt mutations.

    Note: Mutations are now LLM-based. The frontier model (OpenRouter) uses
    4 strategies: CORRECT, SIMPLIFY, REFORMULATE, RADICAL.
    Strategy selection is automatic based on context.
    """
    # Legacy fields kept for backwards compatibility
    enabled_strategies: list[str] = field(default_factory=list)
    mutation_rate: float = 0.3
    sections_library: list[str] = field(default_factory=list)


@dataclass
class OptimizationConfig:
    """Configuration for the optimization process."""
    iterations: int = 10
    population_size: int = 5
    elite_count: int = 2
    tournament_size: int = 3


@dataclass
class CrossValidationConfig:
    """Configuration for cross-validation."""
    k_folds: int = 3
    holdout_final: bool = True
    holdout_index: int = 0  # Index of text to use as holdout


@dataclass
class FitnessConfig:
    """Configuration for fitness calculation."""
    accuracy_weight: float = 0.35
    fluency_weight: float = 0.30
    style_weight: float = 0.20
    overall_weight: float = 0.15
    variance_penalty_weight: float = 0.1
    length_penalty_threshold: int = 500
    length_penalty_rate: float = 0.001
    specificity_penalty_rate: float = 0.05
    generalization_gap_weight: float = 0.5


@dataclass
class OptimizerConfig:
    """Main configuration for the prompt optimizer."""
    ollama: OllamaConfig
    openrouter: OpenRouterConfig
    texts: list[TextConfig]
    initial_system_prompt: str
    initial_user_prompt: str
    default_target_language: str = "French"
    default_source_language: str = "English"
    mutation: MutationConfig = field(default_factory=MutationConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    cross_validation: CrossValidationConfig = field(default_factory=CrossValidationConfig)
    fitness: FitnessConfig = field(default_factory=FitnessConfig)
    output_dir: str = "prompt_optimization_results"


def load_config(config_path: str, env_path: Optional[str] = None) -> OptimizerConfig:
    """
    Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to the YAML configuration file
        env_path: Optional path to .env file (defaults to project root)

    Returns:
        OptimizerConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    # Load environment variables
    if env_path:
        load_dotenv(env_path)
    else:
        # Try to find .env in project root
        project_root = Path(__file__).parent.parent
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    # Load YAML config
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    # Parse Ollama config
    ollama_raw = raw_config.get('ollama', {})
    ollama_config = OllamaConfig(
        endpoint=ollama_raw.get('endpoint', OllamaConfig.endpoint),
        model=ollama_raw.get('model', OllamaConfig.model),
        timeout=ollama_raw.get('timeout', OllamaConfig.timeout),
        num_ctx=ollama_raw.get('num_ctx', OllamaConfig.num_ctx)
    )

    # Parse OpenRouter config
    openrouter_raw = raw_config.get('openrouter', {})
    api_key = openrouter_raw.get('api_key') or os.getenv('OPENROUTER_API_KEY', '')
    openrouter_config = OpenRouterConfig(
        endpoint=openrouter_raw.get('endpoint', OpenRouterConfig.endpoint),
        model=openrouter_raw.get('model', OpenRouterConfig.model),
        api_key=api_key,
        timeout=openrouter_raw.get('timeout', OpenRouterConfig.timeout),
        site_url=openrouter_raw.get('site_url', OpenRouterConfig.site_url),
        site_name=openrouter_raw.get('site_name', OpenRouterConfig.site_name)
    )

    # Get default languages
    default_source = raw_config.get('default_source_language', 'English')
    default_target = raw_config.get('default_target_language', 'French')

    # Parse texts
    texts = []
    texts_raw = raw_config.get('texts', [])
    for text_data in texts_raw:
        texts.append(TextConfig(
            id=text_data['id'],
            title=text_data.get('title', ''),
            author=text_data.get('author', ''),
            style=text_data.get('style', ''),
            source_language=text_data.get('source_language', default_source),
            target_language=text_data.get('target_language', default_target),
            content=text_data.get('text', text_data.get('content', '')),
            challenges=text_data.get('challenges', [])
        ))

    # Parse mutation config
    mutation_raw = raw_config.get('mutation', {})
    mutation_config = MutationConfig(
        enabled_strategies=mutation_raw.get('enabled_strategies', MutationConfig().enabled_strategies),
        mutation_rate=mutation_raw.get('mutation_rate', MutationConfig().mutation_rate),
        sections_library=mutation_raw.get('sections_library', [])
    )

    # Parse optimization config
    opt_raw = raw_config.get('optimization', {})
    optimization_config = OptimizationConfig(
        iterations=opt_raw.get('iterations', OptimizationConfig().iterations),
        population_size=opt_raw.get('population_size', OptimizationConfig().population_size),
        elite_count=opt_raw.get('elite_count', OptimizationConfig().elite_count),
        tournament_size=opt_raw.get('tournament_size', OptimizationConfig().tournament_size)
    )

    # Parse cross-validation config
    cv_raw = raw_config.get('cross_validation', {})
    cv_config = CrossValidationConfig(
        k_folds=cv_raw.get('k_folds', CrossValidationConfig().k_folds),
        holdout_final=cv_raw.get('holdout_final', CrossValidationConfig().holdout_final),
        holdout_index=cv_raw.get('holdout_index', CrossValidationConfig().holdout_index)
    )

    # Parse fitness config
    fitness_raw = raw_config.get('fitness', {})
    fitness_config = FitnessConfig(
        accuracy_weight=fitness_raw.get('accuracy_weight', FitnessConfig().accuracy_weight),
        fluency_weight=fitness_raw.get('fluency_weight', FitnessConfig().fluency_weight),
        style_weight=fitness_raw.get('style_weight', FitnessConfig().style_weight),
        overall_weight=fitness_raw.get('overall_weight', FitnessConfig().overall_weight),
        variance_penalty_weight=fitness_raw.get('variance_penalty_weight', FitnessConfig().variance_penalty_weight),
        length_penalty_threshold=fitness_raw.get('length_penalty_threshold', FitnessConfig().length_penalty_threshold),
        length_penalty_rate=fitness_raw.get('length_penalty_rate', FitnessConfig().length_penalty_rate),
        specificity_penalty_rate=fitness_raw.get('specificity_penalty_rate', FitnessConfig().specificity_penalty_rate),
        generalization_gap_weight=fitness_raw.get('generalization_gap_weight', FitnessConfig().generalization_gap_weight)
    )

    # Get prompts
    initial_system = raw_config.get('initial_system_prompt', '')
    initial_user = raw_config.get('initial_user_prompt', '')

    if not initial_system or not initial_user:
        raise ValueError("initial_system_prompt and initial_user_prompt are required")

    if not texts:
        raise ValueError("At least one text is required for optimization")

    return OptimizerConfig(
        ollama=ollama_config,
        openrouter=openrouter_config,
        texts=texts,
        initial_system_prompt=initial_system,
        initial_user_prompt=initial_user,
        default_target_language=default_target,
        default_source_language=default_source,
        mutation=mutation_config,
        optimization=optimization_config,
        cross_validation=cv_config,
        fitness=fitness_config,
        output_dir=raw_config.get('output_dir', 'prompt_optimization_results')
    )


def validate_config(config: OptimizerConfig) -> list[str]:
    """
    Validate the configuration and return any warnings.

    Args:
        config: OptimizerConfig to validate

    Returns:
        List of warning messages (empty if all good)
    """
    warnings = []

    # Check API key
    if not config.openrouter.api_key:
        warnings.append("OpenRouter API key not set - evaluation will fail")

    # Check text count for cross-validation
    n_texts = len(config.texts)
    if config.cross_validation.holdout_final and n_texts < 3:
        warnings.append(f"Only {n_texts} texts available - consider adding more for reliable cross-validation")

    # Check k_folds
    available_texts = n_texts - (1 if config.cross_validation.holdout_final else 0)
    if config.cross_validation.k_folds > available_texts:
        warnings.append(f"k_folds ({config.cross_validation.k_folds}) > available texts ({available_texts})")

    # Check elite count
    if config.optimization.elite_count >= config.optimization.population_size:
        warnings.append("elite_count should be less than population_size")

    # Validate weights sum to ~1.0
    weight_sum = (config.fitness.accuracy_weight + config.fitness.fluency_weight +
                  config.fitness.style_weight + config.fitness.overall_weight)
    if abs(weight_sum - 1.0) > 0.01:
        warnings.append(f"Fitness weights sum to {weight_sum:.2f}, expected ~1.0")

    return warnings
