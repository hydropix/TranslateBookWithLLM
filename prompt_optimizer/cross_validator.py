"""
Cross-validation with train/test split and k-fold rotation.
"""

from dataclasses import dataclass, field
from typing import Generator

from prompt_optimizer.config import TextConfig, CrossValidationConfig


@dataclass
class Fold:
    """Represents a single fold in cross-validation."""
    fold_number: int
    train_indices: list[int]
    test_indices: list[int]
    train_texts: list[TextConfig] = field(default_factory=list)
    test_texts: list[TextConfig] = field(default_factory=list)


@dataclass
class CrossValidationSplit:
    """Complete cross-validation split with holdout."""
    folds: list[Fold]
    holdout_index: int
    holdout_text: TextConfig
    all_texts: list[TextConfig]
    current_fold: int = 0

    def get_current_fold(self) -> Fold:
        """Get the current fold."""
        return self.folds[self.current_fold]

    def advance_fold(self) -> bool:
        """
        Advance to the next fold.

        Returns:
            True if advanced, False if all folds completed
        """
        if self.current_fold < len(self.folds) - 1:
            self.current_fold += 1
            return True
        return False

    def reset(self) -> None:
        """Reset to the first fold."""
        self.current_fold = 0

    @property
    def num_folds(self) -> int:
        """Number of folds."""
        return len(self.folds)


class CrossValidator:
    """
    Handles cross-validation with k-fold rotation.

    With 5 texts and holdout_final=True:
    - 1 text reserved as holdout (final validation)
    - 4 texts in rotation for k-fold cross-validation

    Example with k=3 folds:
    - Fold 1: Train [0,1,2], Test [3]
    - Fold 2: Train [0,1,3], Test [2]
    - Fold 3: Train [0,2,3], Test [1]
    """

    def __init__(self, config: CrossValidationConfig):
        """
        Initialize the cross-validator.

        Args:
            config: Cross-validation configuration
        """
        self.config = config

    def create_split(self, texts: list[TextConfig]) -> CrossValidationSplit:
        """
        Create a cross-validation split from texts.

        Args:
            texts: List of text configurations

        Returns:
            CrossValidationSplit with folds and holdout
        """
        n_texts = len(texts)

        if n_texts < 2:
            raise ValueError("At least 2 texts required for cross-validation")

        # Determine holdout
        holdout_index = self.config.holdout_index
        if self.config.holdout_final:
            if holdout_index >= n_texts:
                holdout_index = 0  # Default to first if index invalid
            holdout_text = texts[holdout_index]

            # Remaining texts for k-fold
            available_indices = [i for i in range(n_texts) if i != holdout_index]
            available_texts = [texts[i] for i in available_indices]
        else:
            # No holdout - use all texts for k-fold
            holdout_index = -1
            holdout_text = None
            available_indices = list(range(n_texts))
            available_texts = texts.copy()

        # Create k-fold splits
        k = min(self.config.k_folds, len(available_texts))
        if k < 2:
            k = len(available_texts)  # Use leave-one-out if k is too small

        folds = []
        for fold_num in range(k):
            # Test set: one text (rotating)
            test_idx_in_available = fold_num % len(available_indices)
            test_indices = [available_indices[test_idx_in_available]]

            # Train set: all other available texts
            train_indices = [
                available_indices[i]
                for i in range(len(available_indices))
                if i != test_idx_in_available
            ]

            fold = Fold(
                fold_number=fold_num + 1,
                train_indices=train_indices,
                test_indices=test_indices,
                train_texts=[texts[i] for i in train_indices],
                test_texts=[texts[i] for i in test_indices]
            )
            folds.append(fold)

        return CrossValidationSplit(
            folds=folds,
            holdout_index=holdout_index,
            holdout_text=holdout_text,
            all_texts=texts
        )

    def iterate_folds(self, split: CrossValidationSplit) -> Generator[Fold, None, None]:
        """
        Iterate through all folds.

        Args:
            split: The cross-validation split

        Yields:
            Each fold in sequence
        """
        for fold in split.folds:
            yield fold


def describe_split(split: CrossValidationSplit) -> str:
    """
    Generate a human-readable description of a cross-validation split.

    Args:
        split: The cross-validation split

    Returns:
        Formatted string description
    """
    lines = [
        f"Cross-Validation Split ({split.num_folds} folds)",
        "=" * 40,
    ]

    # Holdout info
    if split.holdout_text:
        lines.append(f"Holdout (final validation): {split.holdout_text.id} - {split.holdout_text.title}")
    else:
        lines.append("Holdout: None")

    lines.append("")

    # Fold info
    for fold in split.folds:
        train_ids = [split.all_texts[i].id for i in fold.train_indices]
        test_ids = [split.all_texts[i].id for i in fold.test_indices]

        lines.append(f"Fold {fold.fold_number}:")
        lines.append(f"  Train: {', '.join(train_ids)}")
        lines.append(f"  Test:  {', '.join(test_ids)}")

    return "\n".join(lines)


def create_simple_split(
    texts: list[TextConfig],
    test_ratio: float = 0.2
) -> tuple[list[TextConfig], list[TextConfig]]:
    """
    Create a simple train/test split without k-fold.

    Args:
        texts: List of text configurations
        test_ratio: Ratio of texts to use for testing

    Returns:
        Tuple of (train_texts, test_texts)
    """
    n_texts = len(texts)
    n_test = max(1, int(n_texts * test_ratio))

    # Use last n_test texts as test set
    train_texts = texts[:-n_test] if n_test < n_texts else texts[:1]
    test_texts = texts[-n_test:] if n_test < n_texts else texts[1:]

    return train_texts, test_texts
