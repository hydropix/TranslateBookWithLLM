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
from benchmark.translator import get_available_ollama_models, get_available_openrouter_models


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
+---------------------------------------------------------------+
|          TranslateBookWithLLM - Benchmark System              |
|                                                               |
|  Test translation quality across 40+ languages and models     |
+---------------------------------------------------------------+
"""
    print(colored(banner, Colors.HEADER))


def cmd_run(args: argparse.Namespace) -> int:
    """Execute benchmark run command."""
    print_banner()

    # Determine provider
    provider = getattr(args, 'provider', 'ollama') or 'ollama'

    # Build configuration
    config = BenchmarkConfig.from_cli_args(
        openrouter_key=args.openrouter_key,
        evaluator_model=args.evaluator,
        ollama_endpoint=args.ollama_endpoint,
        translation_provider=provider,
    )

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            log_callback("error", error)
        return 1

    # Get models based on provider
    models = args.models
    if not models:
        if provider == "openrouter":
            print(colored("Fetching available OpenRouter models...", Colors.CYAN))
            models_data = asyncio.run(get_available_openrouter_models(config))
            if not models_data:
                log_callback("error", "No OpenRouter models available.")
                return 1
            # Extract model IDs
            models = [m["id"] if isinstance(m, dict) else m for m in models_data[:10]]
            print(colored(f"Found {len(models_data)} models. Using top 10: {', '.join(models[:3])}...", Colors.GREEN))
        else:
            print(colored("Detecting available Ollama models...", Colors.CYAN))
            models = asyncio.run(get_available_ollama_models(config))
            if not models:
                log_callback("error", "No Ollama models found. Run 'ollama pull <model>' first.")
                return 1
            print(colored(f"Found {len(models)} models: {', '.join(models[:5])}...", Colors.GREEN))

    # Show provider info
    print(colored(f"Translation provider: {provider.upper()}", Colors.YELLOW))

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


def cmd_models(args: argparse.Namespace) -> int:
    """List available models for benchmarking."""
    print_banner()

    config = BenchmarkConfig.from_cli_args(openrouter_key=args.openrouter_key)
    provider = args.provider

    if provider == "openrouter":
        print(colored("Fetching OpenRouter models...\n", Colors.CYAN))
        models = asyncio.run(get_available_openrouter_models(config))

        if not models:
            log_callback("error", "Failed to fetch OpenRouter models")
            return 1

        print(colored(f"Available OpenRouter Models ({len(models)} text-only models):\n", Colors.BOLD))

        # Table header
        print(f"{'Model ID':<50} {'Price (per 1M tokens)':<25}")
        print("-" * 75)

        for model in models[:50]:  # Limit to 50 for readability
            if isinstance(model, dict):
                model_id = model.get("id", "unknown")
                pricing = model.get("pricing", {})
                prompt_price = pricing.get("prompt_per_million", 0)
                completion_price = pricing.get("completion_per_million", 0)
                price_str = f"${prompt_price:.2f} / ${completion_price:.2f}"
            else:
                model_id = model
                price_str = "N/A"

            print(f"{model_id:<50} {price_str:<25}")

        print()
        print(colored("Tip: Use -m to specify models, e.g.:", Colors.YELLOW))
        print("  python -m benchmark.cli run -p openrouter -m anthropic/claude-sonnet-4 openai/gpt-4o")

    else:
        print(colored("Detecting Ollama models...\n", Colors.CYAN))
        models = asyncio.run(get_available_ollama_models(config))

        if not models:
            log_callback("error", "No Ollama models found. Is Ollama running? Try 'ollama pull <model>'")
            return 1

        print(colored(f"Available Ollama Models ({len(models)}):\n", Colors.BOLD))
        for model in models:
            print(f"  - {model}")

        print()
        print(colored("Tip: Use -m to specify models, e.g.:", Colors.YELLOW))
        print("  python -m benchmark.cli run -m llama3:8b qwen2.5:14b")

    return 0


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


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge multiple benchmark runs into one."""
    print_banner()

    config = BenchmarkConfig()
    storage = ResultsStorage(config)

    run_ids = args.run_ids

    # Validate all runs exist
    for run_id in run_ids:
        run = storage.load_run(run_id)
        if run is None:
            log_callback("error", f"Run {run_id} not found")
            return 1

    print(colored(f"Merging {len(run_ids)} runs...", Colors.CYAN))

    merged = storage.merge_runs(run_ids, new_run_id=args.output)

    if merged is None:
        log_callback("error", "No valid results to merge")
        return 1

    print(colored(f"\nMerged run created: {merged.run_id}", Colors.GREEN))
    print(f"  Models: {', '.join(merged.models)}")
    print(f"  Languages: {len(merged.languages)}")
    print(f"  Total results: {len(merged.results)}")

    # Optionally regenerate wiki
    if args.publish:
        print(colored("\nPublishing merged results to wiki...", Colors.CYAN))
        from benchmark.wiki.generator import WikiGenerator
        generator = WikiGenerator(config)
        generator.generate_all(merged.run_id)
        print(colored("Wiki updated.", Colors.GREEN))

    return 0


def cmd_wiki_publish(args: argparse.Namespace) -> int:
    """Generate wiki pages and publish to GitHub wiki repository."""
    import shutil
    import subprocess

    print_banner()

    config = BenchmarkConfig()
    generator = WikiGenerator(config)

    wiki_clone_dir = config.paths.wiki_clone_dir
    wiki_output_dir = config.paths.wiki_output_dir
    wiki_repo_url = config.paths.wiki_repo_url

    run_id = args.run_id

    try:
        # Step 1: Generate wiki pages
        print(colored("Step 1/4: Generating wiki pages...", Colors.CYAN))
        generator.generate_all(run_id)
        print(colored("Wiki pages generated.", Colors.GREEN))

        # Step 2: Clone or update wiki repo
        print(colored("Step 2/4: Cloning/updating wiki repository...", Colors.CYAN))

        if wiki_clone_dir.exists():
            # Pull latest changes
            result = subprocess.run(
                ["git", "-C", str(wiki_clone_dir), "pull", "--rebase"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                # If pull fails, delete and re-clone
                shutil.rmtree(wiki_clone_dir)
                subprocess.run(
                    ["git", "clone", wiki_repo_url, str(wiki_clone_dir)],
                    check=True,
                    capture_output=True
                )
        else:
            # Clone fresh
            result = subprocess.run(
                ["git", "clone", wiki_repo_url, str(wiki_clone_dir)],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                log_callback("error", f"Failed to clone wiki repo: {result.stderr}")
                log_callback("error", "Make sure you have created at least one wiki page on GitHub first.")
                return 1

        print(colored("Wiki repository ready.", Colors.GREEN))

        # Step 3: Copy generated files to wiki repo
        print(colored("Step 3/4: Copying files to wiki repository...", Colors.CYAN))

        # Copy all markdown files
        for md_file in wiki_output_dir.glob("*.md"):
            shutil.copy2(md_file, wiki_clone_dir / md_file.name)

        # Copy subdirectories (languages, models)
        for subdir in ["languages", "models"]:
            src_dir = wiki_output_dir / subdir
            dst_dir = wiki_clone_dir / subdir
            if src_dir.exists():
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)

        print(colored("Files copied.", Colors.GREEN))

        # Step 4: Commit and push
        print(colored("Step 4/4: Committing and pushing changes...", Colors.CYAN))

        # Add all changes
        subprocess.run(
            ["git", "-C", str(wiki_clone_dir), "add", "-A"],
            check=True,
            capture_output=True
        )

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "-C", str(wiki_clone_dir), "status", "--porcelain"],
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            print(colored("No changes to commit.", Colors.YELLOW))
            return 0

        # Commit
        commit_msg = f"Update benchmark results ({run_id or 'latest'})"
        subprocess.run(
            ["git", "-C", str(wiki_clone_dir), "commit", "-m", commit_msg],
            check=True,
            capture_output=True
        )

        # Push
        result = subprocess.run(
            ["git", "-C", str(wiki_clone_dir), "push"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            log_callback("error", f"Failed to push: {result.stderr}")
            return 1

        print(colored("\nWiki published successfully!", Colors.GREEN))
        print(colored(f"View at: https://github.com/hydropix/TranslateBookWithLLM/wiki", Colors.CYAN))

        return 0

    except subprocess.CalledProcessError as e:
        log_callback("error", f"Git command failed: {e}")
        return 1
    except Exception as e:
        log_callback("error", f"Wiki publish failed: {e}")
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
  # Quick benchmark with Ollama (local models)
  python -m benchmark.cli run --openrouter-key YOUR_KEY

  # Quick benchmark with OpenRouter (cloud models)
  python -m benchmark.cli run --provider openrouter --openrouter-key YOUR_KEY

  # Full benchmark (all 40+ languages)
  python -m benchmark.cli run --full --openrouter-key YOUR_KEY

  # Specific Ollama models and languages
  python -m benchmark.cli run -m llama3:8b qwen2.5:14b -l fr de ja zh

  # Specific OpenRouter models
  python -m benchmark.cli run -p openrouter -m anthropic/claude-sonnet-4 openai/gpt-4o -l fr de ja

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
        help="Models to benchmark. For Ollama: model names (e.g., llama3:8b). "
             "For OpenRouter: model IDs (e.g., anthropic/claude-sonnet-4). "
             "If not specified, auto-detects available models."
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
        "-p", "--provider",
        choices=["ollama", "openrouter"],
        default="ollama",
        help="Translation provider: 'ollama' (local, default) or 'openrouter' (cloud, 200+ models)"
    )
    run_parser.add_argument(
        "--openrouter-key",
        help="OpenRouter API key (for evaluation, and translation if using --provider openrouter). "
             "Can also be set via OPENROUTER_API_KEY env var."
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

    # Wiki-publish command
    wiki_publish_parser = subparsers.add_parser(
        "wiki-publish",
        help="Generate and publish wiki pages to GitHub"
    )
    wiki_publish_parser.add_argument(
        "run_id",
        nargs="?",
        help="Run ID to publish. If not specified, uses latest run."
    )
    wiki_publish_parser.set_defaults(func=cmd_wiki_publish)

    # Merge command
    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge multiple benchmark runs into one"
    )
    merge_parser.add_argument(
        "run_ids",
        nargs="+",
        help="Run IDs to merge (at least 2)"
    )
    merge_parser.add_argument(
        "-o", "--output",
        help="Custom ID for the merged run"
    )
    merge_parser.add_argument(
        "--publish",
        action="store_true",
        help="Regenerate and publish wiki after merging"
    )
    merge_parser.set_defaults(func=cmd_merge)

    # List command
    list_parser = subparsers.add_parser("list", help="List available benchmark runs")
    list_parser.set_defaults(func=cmd_list)

    # Models command
    models_parser = subparsers.add_parser("models", help="List available models for benchmarking")
    models_parser.add_argument(
        "-p", "--provider",
        choices=["ollama", "openrouter"],
        default="ollama",
        help="Provider to list models for (default: ollama)"
    )
    models_parser.add_argument(
        "--openrouter-key",
        help="OpenRouter API key (required for listing OpenRouter models)"
    )
    models_parser.set_defaults(func=cmd_models)

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
