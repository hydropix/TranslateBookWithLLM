"""
Benchmark CLI - Command line interface for the benchmark system.

Provides commands for:
- Running benchmarks (quick or full)
- Generating wiki pages
- Listing and managing runs
"""

import argparse
import asyncio
import sys
from typing import Optional

from benchmark.config import BenchmarkConfig, DEFAULT_EVALUATOR_MODEL
from benchmark.runner import BenchmarkRunner, quick_benchmark, full_benchmark
from benchmark.results.storage import ResultsStorage
from benchmark.wiki.generator import WikiGenerator
from benchmark.translator import get_available_ollama_models


# ANSI color codes for terminal output
class Colors:
    """Terminal color codes."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def colored(text: str, color: str) -> str:
    """Apply color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.ENDC}"
    return text


def log_callback(level: str, message: str) -> None:
    """Colored logging callback for CLI output."""
    level_colors = {
        "info": Colors.CYAN,
        "warning": Colors.YELLOW,
        "error": Colors.RED,
        "debug": Colors.BLUE,
    }
    color = level_colors.get(level.lower(), Colors.ENDC)
    prefix = colored(f"[{level.upper()}]", color)
    print(f"{prefix} {message}")


def print_banner() -> None:
    """Print CLI banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║          TranslateBookWithLLM - Benchmark System              ║
║                                                               ║
║  Test translation quality across 40+ languages and models    ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(colored(banner, Colors.HEADER))


def cmd_run(args: argparse.Namespace) -> int:
    """Execute benchmark run command."""
    print_banner()

    # Build configuration
    config = BenchmarkConfig.from_cli_args(
        openrouter_key=args.openrouter_key,
        evaluator_model=args.evaluator,
        ollama_endpoint=args.ollama_endpoint,
    )

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            log_callback("error", error)
        return 1

    # Get models
    models = args.models
    if not models:
        print(colored("Detecting available Ollama models...", Colors.CYAN))
        models = asyncio.run(get_available_ollama_models(config))
        if not models:
            log_callback("error", "No Ollama models found. Run 'ollama pull <model>' first.")
            return 1
        print(colored(f"Found {len(models)} models: {', '.join(models[:5])}...", Colors.GREEN))

    # Determine languages
    if args.full:
        language_codes = None  # Full benchmark uses all languages
        print(colored("Running FULL benchmark with all 40+ languages", Colors.YELLOW))
    elif args.languages:
        language_codes = args.languages
        print(colored(f"Running benchmark with languages: {', '.join(language_codes)}", Colors.CYAN))
    else:
        language_codes = config.quick_languages
        print(colored(f"Running QUICK benchmark with {len(language_codes)} languages", Colors.CYAN))

    # Check for resumable run
    storage = ResultsStorage(config)
    resume_run = None

    if args.resume:
        resume_run = storage.load_run(args.resume)
        if resume_run:
            print(colored(f"Resuming run {args.resume}...", Colors.YELLOW))
        else:
            log_callback("warning", f"Run {args.resume} not found, starting fresh")

    # Create runner
    runner = BenchmarkRunner(
        config=config,
        log_callback=log_callback,
    )

    # Run benchmark
    try:
        print(colored("\nStarting benchmark...\n", Colors.BOLD))

        run = asyncio.run(runner.run(
            models=models,
            language_codes=language_codes,
            resume_run=resume_run,
        ))

        # Save results
        storage.save_run(run)
        print(colored(f"\nResults saved to: {storage._get_run_path(run.run_id)}", Colors.GREEN))

        # Print summary
        print_run_summary(run)

        return 0

    except KeyboardInterrupt:
        print(colored("\nBenchmark interrupted by user", Colors.YELLOW))
        return 130
    except Exception as e:
        log_callback("error", f"Benchmark failed: {e}")
        return 1


def cmd_wiki(args: argparse.Namespace) -> int:
    """Generate wiki pages from benchmark results."""
    print_banner()

    config = BenchmarkConfig()
    generator = WikiGenerator(config)

    run_id = args.run_id

    try:
        print(colored("Generating wiki pages...", Colors.CYAN))

        output_dir = generator.generate_all(run_id)

        print(colored(f"\nWiki pages generated successfully!", Colors.GREEN))
        print(colored(f"Output directory: {output_dir}", Colors.CYAN))
        print()
        print("Generated pages:")
        print(f"  - Home.md")
        print(f"  - All-Languages.md")
        print(f"  - All-Models.md")
        print(f"  - languages/*.md")
        print(f"  - models/*.md")
        print()
        print(colored("Copy the contents of the 'wiki' directory to your GitHub wiki repository.", Colors.YELLOW))

        return 0

    except ValueError as e:
        log_callback("error", str(e))
        return 1
    except Exception as e:
        log_callback("error", f"Wiki generation failed: {e}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List available benchmark runs."""
    config = BenchmarkConfig()
    storage = ResultsStorage(config)

    runs = storage.list_runs()

    if not runs:
        print(colored("No benchmark runs found.", Colors.YELLOW))
        return 0

    print(colored("\nAvailable benchmark runs:\n", Colors.BOLD))

    # Table header
    print(f"{'Run ID':<20} {'Status':<12} {'Started':<20} {'Models':<30} {'Results'}")
    print("-" * 100)

    for run in runs:
        status_color = {
            "completed": Colors.GREEN,
            "running": Colors.YELLOW,
            "failed": Colors.RED,
        }.get(run["status"], Colors.ENDC)

        status = colored(run["status"], status_color)
        models_str = ", ".join(run["models"][:2])
        if len(run["models"]) > 2:
            models_str += f" (+{len(run['models']) - 2})"

        started = run["started_at"][:19] if run["started_at"] else "N/A"

        print(f"{run['run_id']:<20} {status:<22} {started:<20} {models_str:<30} {run['total_results']}")

    print()
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show details of a specific benchmark run."""
    config = BenchmarkConfig()
    storage = ResultsStorage(config)

    run = storage.load_run(args.run_id)
    if not run:
        log_callback("error", f"Run {args.run_id} not found")
        return 1

    print_run_summary(run)

    # Show detailed stats if requested
    if args.detailed:
        stats = storage.get_aggregated_stats(args.run_id)
        if stats:
            print(colored("\nModel Statistics:", Colors.BOLD))
            for model_stat in stats["model_stats"]:
                print(f"  {model_stat['model']}: avg={model_stat['avg_overall']:.1f}, "
                      f"best_lang={model_stat.get('best_language', 'N/A')}")

            print(colored("\nLanguage Statistics:", Colors.BOLD))
            for lang_stat in stats["language_stats"]:
                print(f"  {lang_stat['language_code']}: avg={lang_stat['avg_overall']:.1f}, "
                      f"best_model={lang_stat.get('best_model', 'N/A')}")

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export benchmark run to CSV."""
    config = BenchmarkConfig()
    storage = ResultsStorage(config)

    output_path = storage.export_csv(args.run_id, args.output)

    if output_path:
        print(colored(f"Exported to: {output_path}", Colors.GREEN))
        return 0
    else:
        log_callback("error", f"Run {args.run_id} not found")
        return 1


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a benchmark run."""
    config = BenchmarkConfig()
    storage = ResultsStorage(config)

    if not args.force:
        confirm = input(f"Delete run {args.run_id}? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return 0

    if storage.delete_run(args.run_id):
        print(colored(f"Deleted run {args.run_id}", Colors.GREEN))
        return 0
    else:
        log_callback("error", f"Run {args.run_id} not found")
        return 1


def print_run_summary(run) -> None:
    """Print a summary of a benchmark run."""
    print(colored("\n" + "=" * 60, Colors.BOLD))
    print(colored(f"Benchmark Run: {run.run_id}", Colors.BOLD))
    print("=" * 60)

    print(f"Status: {colored(run.status, Colors.GREEN if run.status == 'completed' else Colors.YELLOW)}")
    print(f"Started: {run.started_at}")
    if run.completed_at:
        print(f"Completed: {run.completed_at}")
    print(f"Evaluator: {run.evaluator_model}")
    print()

    print(f"Models: {', '.join(run.models)}")
    print(f"Languages: {len(run.languages)} ({', '.join(run.languages[:7])}...)")
    print()

    print(f"Total translations: {run.total_completed}/{run.total_expected}")
    success_count = sum(1 for r in run.results if r.success)
    success_rate = (success_count / len(run.results) * 100) if run.results else 0
    print(f"Success rate: {success_rate:.1f}%")

    # Calculate average scores
    scores = [r.scores.overall for r in run.results if r.scores]
    if scores:
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        print(f"Scores: avg={avg_score:.1f}, min={min_score:.1f}, max={max_score:.1f}")

    print()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="TranslateBookWithLLM Benchmark System - Test translation quality across languages and models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick benchmark (7 test languages)
  python -m benchmark.cli run --openrouter-key YOUR_KEY

  # Full benchmark (all 40+ languages)
  python -m benchmark.cli run --full --openrouter-key YOUR_KEY

  # Specific models and languages
  python -m benchmark.cli run -m llama3:8b qwen2.5:14b -l fr de ja zh

  # Generate wiki pages
  python -m benchmark.cli wiki

  # List all runs
  python -m benchmark.cli list
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a benchmark")
    run_parser.add_argument(
        "-m", "--models",
        nargs="+",
        help="Ollama models to benchmark. If not specified, uses all available models."
    )
    run_parser.add_argument(
        "-l", "--languages",
        nargs="+",
        help="Language codes to test (e.g., fr de ja zh). If not specified, uses quick test set."
    )
    run_parser.add_argument(
        "--full",
        action="store_true",
        help="Run full benchmark with all 40+ languages"
    )
    run_parser.add_argument(
        "--openrouter-key",
        help="OpenRouter API key for evaluation. Can also be set via OPENROUTER_API_KEY env var."
    )
    run_parser.add_argument(
        "--evaluator",
        default=DEFAULT_EVALUATOR_MODEL,
        help=f"OpenRouter model for evaluation (default: {DEFAULT_EVALUATOR_MODEL})"
    )
    run_parser.add_argument(
        "--ollama-endpoint",
        help="Custom Ollama API endpoint"
    )
    run_parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="Resume an interrupted run by ID"
    )
    run_parser.set_defaults(func=cmd_run)

    # Wiki command
    wiki_parser = subparsers.add_parser("wiki", help="Generate wiki pages from results")
    wiki_parser.add_argument(
        "run_id",
        nargs="?",
        help="Run ID to generate pages for. If not specified, uses latest run."
    )
    wiki_parser.set_defaults(func=cmd_wiki)

    # List command
    list_parser = subparsers.add_parser("list", help="List available benchmark runs")
    list_parser.set_defaults(func=cmd_list)

    # Show command
    show_parser = subparsers.add_parser("show", help="Show details of a benchmark run")
    show_parser.add_argument("run_id", help="Run ID to show")
    show_parser.add_argument(
        "-d", "--detailed",
        action="store_true",
        help="Show detailed statistics"
    )
    show_parser.set_defaults(func=cmd_show)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export run results to CSV")
    export_parser.add_argument("run_id", help="Run ID to export")
    export_parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path (default: benchmark_results/<run_id>.csv)"
    )
    export_parser.set_defaults(func=cmd_export)

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a benchmark run")
    delete_parser.add_argument("run_id", help="Run ID to delete")
    delete_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Delete without confirmation"
    )
    delete_parser.set_defaults(func=cmd_delete)

    return parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
