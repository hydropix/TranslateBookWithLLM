# Prompt Optimizer

Outil d'optimisation automatique des prompts de traduction via apprentissage par renforcement.

## Principe

L'optimiseur fait evoluer une population de prompts a travers des mutations successives, en gardant les meilleurs candidats a chaque generation. Un systeme de cross-validation empeche l'overfitting sur des textes specifiques.

## Demarrage Rapide (Windows)

Des scripts `.bat` sont fournis pour simplifier l'utilisation:

| Script | Description |
|--------|-------------|
| `1_check_prerequisites.bat` | Verifie que tout est installe |
| `2_install_dependencies.bat` | Installe les packages Python |
| `3_run_optimization.bat` | Lance l'optimisation (config par defaut) |
| `3_run_optimization_custom.bat` | Lance avec parametres personnalises |
| `4_dry_run.bat` | Teste la config sans executer |
| `5_view_results.bat` | Affiche les resultats |
| `6_open_best_prompt.bat` | Ouvre le meilleur prompt |

**Workflow recommande:**
```
1_check_prerequisites.bat  -->  2_install_dependencies.bat  -->  4_dry_run.bat  -->  3_run_optimization.bat
```

## Prerequis

### 1. Configuration `.env`

Assurez-vous que votre fichier `.env` a la racine du projet contient:

```env
# Ollama (LLM de traduction)
API_ENDPOINT=http://localhost:11434/api/generate
DEFAULT_MODEL=qwen3:4b

# OpenRouter (LLM evaluateur)
OPENROUTER_API_KEY=sk-or-...
```

### 2. Ollama en cours d'execution

Demarrez Ollama avec le modele configure:
```bash
ollama run qwen3:4b
```

### 3. Dependances Python

```bash
pip install pyyaml python-dotenv requests
```

## Utilisation

### Lancement de l'optimisation

```bash
cd c:\Users\bruno\Documents\GitHub\TranslateBookWithLLM
python -m prompt_optimizer.optimize --config prompt_optimizer/prompt_optimizer_config.yaml --verbose
```

### Options disponibles

| Option | Description | Defaut |
|--------|-------------|--------|
| `--iterations N` | Nombre de generations | 10 |
| `--population N` | Taille de la population | 5 |
| `--output DIR` | Repertoire de sortie | `prompt_optimization_results/` |
| `--verbose` | **Affichage detaille avec couleurs** | non |
| `--dry-run` | Valider config sans executer | non |

### Affichage coloré

Le mode `--verbose` active un affichage coloré détaillé montrant en temps réel:

- **CYAN**: Requêtes et réponses Ollama (traductions qwen3:4b)
  - Prompt system/user envoyé
  - Texte traduit reçu
  - Temps et tokens utilisés

- **MAGENTA**: Requêtes et réponses OpenRouter (évaluations Claude Haiku)
  - Texte source et traduction
  - Scores détaillés (accuracy, fluency, style, overall)
  - Feedback de l'évaluateur

- **JAUNE**: Mutations LLM (améliorations Claude Haiku)
  - Stratégie de mutation (CORRECT, SIMPLIFY, REFORMULATE, RADICAL)
  - Feedbacks utilisés pour guider la mutation
  - Nouveau prompt généré
  - Changement de taille (tokens)

- **VERT/ROUGE**: Scores et fitness
  - Vert: bons scores (≥8)
  - Jaune: scores moyens (6-8)
  - Rouge: scores faibles (<6)

### Exemple avec options

```bash
python -m prompt_optimizer.optimize \
  --config prompt_optimizer/prompt_optimizer_config.yaml \
  --iterations 20 \
  --population 8 \
  --verbose
```

## Processus d'optimisation

```
1. Chargement de la configuration et des textes de reference
                    |
2. Initialisation de la population de prompts
                    |
    +---------------+---------------+
    |           BOUCLE              |
    |                               |
    |  3. Traduction (Ollama)       |
    |              |                |
    |  4. Evaluation (OpenRouter)   |
    |              |                |
    |  5. Calcul fitness + penalites|
    |              |                |
    |  6. Selection des meilleurs   |
    |              |                |
    |  7. Mutations genetiques      |
    |              |                |
    |  8. Rotation cross-validation |
    |              |                |
    +---------------+---------------+
                    |
9. Validation finale sur holdout set
                    |
10. Export des meilleurs prompts
```

## Resultats

Apres execution, les resultats sont dans `prompt_optimization_results/`:

```
prompt_optimization_results/
├── iteration_001.json     # Resultats iteration 1
├── iteration_002.json     # ...
├── final_report.json      # Rapport complet
└── best_prompts/
    ├── prompt_01.yaml     # Meilleur prompt
    ├── prompt_02.yaml     # 2eme meilleur
    └── ...
```

### Utiliser le meilleur prompt

1. Ouvrez `best_prompts/prompt_01.yaml`
2. Copiez le contenu de `system_prompt` et `user_prompt`
3. Integrez-les dans votre configuration principale (`config.yaml`)

## Configuration avancee

Editez `prompt_optimizer_config.yaml` pour ajuster:

- **texts**: Textes de reference pour l'entrainement
- **mutation.available_sections**: Sections pouvant etre ajoutees aux prompts
- **optimization**: Parametres de l'algorithme genetique
- **cross_validation**: Strategie de validation

## Formule de fitness

```
FITNESS = BASE_SCORE - PENALTIES

BASE_SCORE = accuracy*0.35 + fluency*0.30 + style*0.20 + overall*0.15

PENALTIES:
- Variance entre textes (evite specialisation)
- Longueur excessive du prompt
- Termes trop specifiques au texte
- Ecart train/test (overfitting)
```

## Strategies de mutation (LLM-based)

L'optimiseur utilise Claude Haiku pour améliorer les prompts via 4 stratégies intelligentes:

### 1. **CORRECT** - Corriger les faiblesses

- Utilisée quand: fitness < 6.0
- Action: Ajoute des instructions pour corriger les problèmes identifiés dans les feedbacks
- Exemple: Si fluency est faible, ajoute "Prioritize natural expression over literal translation"

### 2. **SIMPLIFY** - Réduire et optimiser

- Utilisée quand: prompt > 300 tokens
- Action: Retire les instructions redondantes ou inutiles
- Objectif: Réduire le coût et améliorer la clarté

### 3. **REFORMULATE** - Clarifier

- Utilisée quand: fitness moyen
- Action: Réécrit les instructions de manière plus claire et directe
- Garde la même longueur ou réduit

### 4. **RADICAL** - Explorer de nouvelles approches

- Utilisée quand: début d'optimisation (génération < 3)
- Action: Essaie une structure complètement différente
- Exemples: minimaliste, basé sur des règles, avec exemples, etc.

**Sélection automatique:** La stratégie est choisie intelligemment selon:

- Longueur du prompt actuel
- Scores de fitness
- Numéro de génération
