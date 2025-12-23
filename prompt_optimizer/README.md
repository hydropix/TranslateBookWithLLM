# Prompt Optimizer

Automatic optimization tool for translation prompts using reinforcement learning.

## Principle

The optimizer evolves a population of prompts through successive mutations, keeping the best candidates at each generation. A cross-validation system prevents overfitting on specific texts.

## Quick Start (Windows)

`.bat` scripts are provided to simplify usage:

| Script | Description |
|--------|-------------|
| `1_check_prerequisites.bat` | Checks that everything is installed |
| `2_install_dependencies.bat` | Installs Python packages |
| `3_run_optimization.bat` | Runs optimization (default config) |
| `3_run_optimization_custom.bat` | Runs with custom parameters |
| `4_dry_run.bat` | Tests config without executing |
| `5_view_results.bat` | Displays results |
| `6_open_best_prompt.bat` | Opens the best prompt |

**Recommended workflow:**
```
1_check_prerequisites.bat  -->  2_install_dependencies.bat  -->  4_dry_run.bat  -->  3_run_optimization.bat
```

## Prerequisites

### 1. `.env` Configuration

Make sure your `.env` file at the project root contains:

```env
# Ollama (translation LLM)
API_ENDPOINT=http://localhost:11434/api/generate
DEFAULT_MODEL=qwen3:4b

# OpenRouter (evaluator LLM)
OPENROUTER_API_KEY=sk-or-...
```

### 2. Ollama Running

Start Ollama with the configured model:
```bash
ollama run qwen3:4b
```

### 3. Python Dependencies

```bash
pip install pyyaml python-dotenv requests
```

## Usage

### Running the Optimization

```bash
cd c:\Users\bruno\Documents\GitHub\TranslateBookWithLLM
python -m prompt_optimizer.optimize --config prompt_optimizer/prompt_optimizer_config.yaml --verbose
```

### Available Options

| Option | Description | Default |
|--------|-------------|---------|
| `--iterations N` | Number of generations | 10 |
| `--population N` | Population size | 5 |
| `--output DIR` | Output directory | `prompt_optimization_results/` |
| `--verbose` | **Detailed display with colors** | no |
| `--dry-run` | Validate config without executing | no |

### Colored Display

The `--verbose` mode enables a detailed colored display showing in real-time:

- **CYAN**: Ollama requests and responses (qwen3:4b translations)
  - System/user prompt sent
  - Translated text received
  - Time and tokens used

- **MAGENTA**: OpenRouter requests and responses (Claude Haiku evaluations)
  - Source text and translation
  - Detailed scores (accuracy, fluency, style, overall)
  - Evaluator feedback

- **YELLOW**: LLM mutations (Claude Haiku improvements)
  - Mutation strategy (CORRECT, SIMPLIFY, REFORMULATE, RADICAL)
  - Feedbacks used to guide the mutation
  - New generated prompt
  - Size change (tokens)

- **GREEN/RED**: Scores and fitness
  - Green: good scores (>=8)
  - Yellow: average scores (6-8)
  - Red: low scores (<6)

### Example with Options

```bash
python -m prompt_optimizer.optimize \
  --config prompt_optimizer/prompt_optimizer_config.yaml \
  --iterations 20 \
  --population 8 \
  --verbose
```

## Optimization Process

```
1. Load configuration and reference texts
                    |
2. Initialize prompt population
                    |
    +---------------+---------------+
    |           LOOP                |
    |                               |
    |  3. Translation (Ollama)      |
    |              |                |
    |  4. Evaluation (OpenRouter)   |
    |              |                |
    |  5. Fitness + penalties calc  |
    |              |                |
    |  6. Select best candidates    |
    |              |                |
    |  7. Genetic mutations         |
    |              |                |
    |  8. Cross-validation rotation |
    |              |                |
    +---------------+---------------+
                    |
9. Final validation on holdout set
                    |
10. Export best prompts
```

## Results

After execution, results are in `prompt_optimization_results/`:

```
prompt_optimization_results/
├── iteration_001.json     # Iteration 1 results
├── iteration_002.json     # ...
├── final_report.json      # Complete report
└── best_prompts/
    ├── prompt_01.yaml     # Best prompt
    ├── prompt_02.yaml     # 2nd best
    └── ...
```

### Using the Best Prompt

1. Open `best_prompts/prompt_01.yaml`
2. Copy the contents of `system_prompt` and `user_prompt`
3. Integrate them into your main configuration (`config.yaml`)

## Advanced Configuration

Edit `prompt_optimizer_config.yaml` to adjust:

- **texts**: Reference texts for training
- **mutation.available_sections**: Sections that can be added to prompts
- **optimization**: Genetic algorithm parameters
- **cross_validation**: Validation strategy

## Fitness Formula

```
FITNESS = BASE_SCORE - PENALTIES

BASE_SCORE = accuracy*0.35 + fluency*0.30 + style*0.20 + overall*0.15

PENALTIES:
- Variance between texts (avoids specialization)
- Excessive prompt length
- Text-specific terms
- Train/test gap (overfitting)
```

## Mutation Strategies (LLM-based)

The optimizer uses Claude Haiku to improve prompts via 4 intelligent strategies:

### 1. **CORRECT** - Fix weaknesses

- Used when: fitness < 6.0
- Action: Adds instructions to correct problems identified in feedbacks
- Example: If fluency is low, adds "Prioritize natural expression over literal translation"

### 2. **SIMPLIFY** - Reduce and optimize

- Used when: prompt > 300 tokens
- Action: Removes redundant or unnecessary instructions
- Goal: Reduce cost and improve clarity

### 3. **REFORMULATE** - Clarify

- Used when: average fitness
- Action: Rewrites instructions more clearly and directly
- Keeps the same length or reduces

### 4. **RADICAL** - Explore new approaches

- Used when: early optimization (generation < 3)
- Action: Tries a completely different structure
- Examples: minimalist, rule-based, with examples, etc.

**Automatic selection:** The strategy is intelligently chosen based on:

- Current prompt length
- Fitness scores
- Generation number
