"""
Error recovery strategies for translation adapters.

This module provides recovery mechanisms for common failure scenarios:
- Content splitting when chunks are too large
- Fallback translation methods
- Partial result recovery
- Graceful degradation
"""

import asyncio
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass

from .exceptions import (
    ContextOverflowError,
    RepetitionLoopError,
    UnitTranslationError,
    ChunkSizeExceededError,
    PlaceholderValidationError,
)


@dataclass
class RecoveryResult:
    """Result of an error recovery attempt.

    Attributes:
        success: Whether recovery was successful
        data: Recovered data (if any)
        fallback_used: Whether a fallback method was used
        message: Description of recovery action
    """
    success: bool
    data: Any = None
    fallback_used: bool = False
    message: str = ""


class ContentSplitter:
    """Handles splitting content when it's too large."""

    @staticmethod
    def split_at_boundary(
        content: str,
        target_ratio: float = 0.5,
        boundary_chars: Tuple[str, ...] = ('.', '!', '?', '\n', ' ')
    ) -> Tuple[str, str]:
        """Split content at a natural boundary.

        Args:
            content: Content to split
            target_ratio: Target split position (0.0-1.0)
            boundary_chars: Characters to use as split boundaries (in priority order)

        Returns:
            Tuple of (first_part, second_part)
        """
        if not content or len(content) < 100:
            # Too small to split meaningfully
            mid = len(content) // 2
            return content[:mid], content[mid:]

        target_pos = int(len(content) * target_ratio)
        search_window = len(content) // 10  # 10% window around target

        best_split_pos = target_pos

        # Try each boundary character in order
        for boundary in boundary_chars:
            # Search backwards from target position
            search_start = max(0, target_pos - search_window)
            search_end = min(len(content), target_pos + search_window)
            search_area = content[search_start:search_end]

            # Find last occurrence of boundary in search area
            boundary_pos = search_area.rfind(boundary)
            if boundary_pos != -1:
                actual_pos = search_start + boundary_pos + len(boundary)
                # Use this if it's better than current best
                if abs(actual_pos - target_pos) < abs(best_split_pos - target_pos):
                    best_split_pos = actual_pos
                    break  # Found good boundary, stop searching

        return content[:best_split_pos].strip(), content[best_split_pos:].strip()

    @staticmethod
    def split_into_n_parts(
        content: str,
        n: int,
        boundary_chars: Tuple[str, ...] = ('.', '!', '?', '\n')
    ) -> List[str]:
        """Split content into n roughly equal parts.

        Args:
            content: Content to split
            n: Number of parts
            boundary_chars: Characters to use as boundaries

        Returns:
            List of content parts
        """
        if n <= 1:
            return [content]

        parts = []
        remaining = content

        for i in range(n - 1):
            # Calculate target ratio for this split
            # Split remaining content so all parts are equal
            ratio = 1.0 / (n - i)

            first, remaining = ContentSplitter.split_at_boundary(
                remaining, ratio, boundary_chars
            )
            if first:
                parts.append(first)

        # Add remaining content as last part
        if remaining:
            parts.append(remaining)

        return parts


class ErrorRecoveryManager:
    """Manages error recovery strategies for translation operations."""

    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            log_callback: Callback for logging (log_type, message)
        """
        self.log_callback = log_callback
        self._recovery_stats: Dict[str, int] = {}

    def _log(self, log_type: str, message: str):
        """Internal logging helper."""
        if self.log_callback:
            self.log_callback(log_type, message)

    def _record_recovery(self, recovery_type: str):
        """Record recovery attempt for statistics."""
        self._recovery_stats[recovery_type] = self._recovery_stats.get(recovery_type, 0) + 1

    async def recover_from_context_overflow(
        self,
        content: str,
        translate_func: Callable[[str], Any],
        max_splits: int = 3
    ) -> RecoveryResult:
        """Recover from context overflow by splitting content.

        Args:
            content: Content that caused overflow
            translate_func: Translation function to retry with smaller content
            max_splits: Maximum number of times to split

        Returns:
            RecoveryResult with translated parts
        """
        self._log("info", "Attempting recovery from context overflow")
        self._record_recovery("context_overflow")

        # Calculate split factor based on attempt
        n_parts = 2

        for attempt in range(max_splits):
            try:
                self._log(
                    "info",
                    f"Splitting content into {n_parts} parts (attempt {attempt + 1}/{max_splits})"
                )

                # Split content
                parts = ContentSplitter.split_into_n_parts(content, n_parts)

                # Translate each part
                translated_parts = []
                for i, part in enumerate(parts):
                    self._log("info", f"Translating part {i + 1}/{len(parts)}")
                    translated_part = await translate_func(part)
                    translated_parts.append(translated_part)

                # Success - combine parts
                combined = " ".join(translated_parts)
                self._log("info", f"Successfully recovered by splitting into {n_parts} parts")

                return RecoveryResult(
                    success=True,
                    data=combined,
                    fallback_used=True,
                    message=f"Split into {n_parts} parts"
                )

            except ContextOverflowError:
                # Still too large, try more splits
                n_parts += 1
                if attempt < max_splits - 1:
                    self._log(
                        "warning",
                        f"Content still too large, will try {n_parts} parts"
                    )
                continue

            except Exception as e:
                self._log("error", f"Error during split recovery: {e}")
                return RecoveryResult(
                    success=False,
                    message=f"Split recovery failed: {e}"
                )

        return RecoveryResult(
            success=False,
            message=f"Could not recover after {max_splits} split attempts"
        )

    async def recover_from_repetition_loop(
        self,
        content: str,
        translate_func: Callable[[str, Dict[str, Any]], Any],
        original_params: Dict[str, Any]
    ) -> RecoveryResult:
        """Recover from repetition loop by adjusting parameters.

        Args:
            content: Content that caused loop
            translate_func: Translation function
            original_params: Original parameters

        Returns:
            RecoveryResult with translation
        """
        self._log("info", "Attempting recovery from repetition loop")
        self._record_recovery("repetition_loop")

        # Try different parameter adjustments
        strategies = [
            {"temperature": 0.7, "max_tokens": original_params.get("max_tokens", 2000) * 0.8},
            {"temperature": 0.5, "top_p": 0.9},
            {"temperature": 0.3},
        ]

        for i, strategy_params in enumerate(strategies):
            try:
                self._log(
                    "info",
                    f"Trying strategy {i + 1}/{len(strategies)}: {strategy_params}"
                )

                # Merge with original params
                adjusted_params = {**original_params, **strategy_params}

                # Retry with adjusted parameters
                result = await translate_func(content, adjusted_params)

                self._log("info", f"Successfully recovered with strategy {i + 1}")
                return RecoveryResult(
                    success=True,
                    data=result,
                    fallback_used=True,
                    message=f"Adjusted parameters: {strategy_params}"
                )

            except RepetitionLoopError:
                if i < len(strategies) - 1:
                    continue
                else:
                    break
            except Exception as e:
                self._log("error", f"Error in strategy {i + 1}: {e}")
                continue

        return RecoveryResult(
            success=False,
            message="All parameter adjustment strategies failed"
        )

    async def recover_from_placeholder_validation(
        self,
        translated_text: str,
        expected_placeholders: List[str],
        translate_func: Callable[[str, List[str]], Any]
    ) -> RecoveryResult:
        """Recover from placeholder validation failure.

        Args:
            translated_text: Text with missing placeholders
            expected_placeholders: Placeholders that should be present
            translate_func: Function to retry translation with placeholder hints

        Returns:
            RecoveryResult with corrected translation
        """
        self._log("info", "Attempting recovery from placeholder validation failure")
        self._record_recovery("placeholder_validation")

        # Check which placeholders are missing
        missing = [p for p in expected_placeholders if p not in translated_text]

        if not missing:
            return RecoveryResult(
                success=True,
                data=translated_text,
                message="No placeholders actually missing"
            )

        self._log("warning", f"Missing placeholders: {missing}")

        try:
            # Retry translation with explicit instruction about placeholders
            result = await translate_func(translated_text, expected_placeholders)

            # Verify all placeholders are now present
            still_missing = [p for p in expected_placeholders if p not in result]

            if not still_missing:
                self._log("info", "Successfully recovered all placeholders")
                return RecoveryResult(
                    success=True,
                    data=result,
                    fallback_used=True,
                    message="Placeholder correction succeeded"
                )
            else:
                self._log("warning", f"Still missing: {still_missing}")
                return RecoveryResult(
                    success=False,
                    message=f"Could not recover placeholders: {still_missing}"
                )

        except Exception as e:
            self._log("error", f"Error during placeholder recovery: {e}")
            return RecoveryResult(
                success=False,
                message=f"Placeholder recovery failed: {e}"
            )

    async def recover_partial_results(
        self,
        failed_units: List[Dict[str, Any]],
        translate_func: Callable[[Dict[str, Any]], Any],
        max_concurrent: int = 3
    ) -> RecoveryResult:
        """Attempt to recover failed translation units.

        Args:
            failed_units: List of units that failed translation
            translate_func: Function to retry translation
            max_concurrent: Maximum concurrent retry attempts

        Returns:
            RecoveryResult with recovered translations
        """
        self._log("info", f"Attempting to recover {len(failed_units)} failed units")
        self._record_recovery("partial_results")

        recovered = []
        still_failed = []

        # Process in batches to avoid overwhelming the system
        for i in range(0, len(failed_units), max_concurrent):
            batch = failed_units[i:i + max_concurrent]

            # Retry each unit in batch
            tasks = [translate_func(unit) for unit in batch]

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for unit, result in zip(batch, results):
                    if isinstance(result, Exception):
                        still_failed.append(unit)
                        self._log(
                            "warning",
                            f"Unit {unit.get('unit_id', 'unknown')} still failed: {result}"
                        )
                    else:
                        recovered.append({"unit": unit, "translation": result})
                        self._log(
                            "info",
                            f"Recovered unit {unit.get('unit_id', 'unknown')}"
                        )

            except Exception as e:
                self._log("error", f"Batch recovery failed: {e}")
                still_failed.extend(batch)

        success_rate = len(recovered) / len(failed_units) if failed_units else 0
        self._log(
            "info",
            f"Recovered {len(recovered)}/{len(failed_units)} units ({success_rate:.1%})"
        )

        return RecoveryResult(
            success=len(recovered) > 0,
            data={
                "recovered": recovered,
                "still_failed": still_failed,
                "success_rate": success_rate
            },
            fallback_used=True,
            message=f"Recovered {len(recovered)}/{len(failed_units)} units"
        )

    def get_recovery_stats(self) -> Dict[str, int]:
        """Get statistics on recovery attempts.

        Returns:
            Dict mapping recovery type to count
        """
        return self._recovery_stats.copy()

    def reset_stats(self):
        """Reset recovery statistics."""
        self._recovery_stats.clear()


class GracefulDegradation:
    """Handles graceful degradation when recovery fails."""

    @staticmethod
    def create_fallback_translation(
        original_content: str,
        error: Exception,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a fallback when translation completely fails.

        Args:
            original_content: Original untranslated content
            error: The error that caused failure
            metadata: Optional metadata about the failure

        Returns:
            Fallback content (original with error marker)
        """
        # Return original content with a comment about the failure
        error_msg = f"[Translation failed: {type(error).__name__}]"
        return f"{error_msg}\n{original_content}"

    @staticmethod
    def should_use_original(
        translation: str,
        original: str,
        quality_threshold: float = 0.3
    ) -> bool:
        """Determine if original content should be used instead of poor translation.

        Args:
            translation: Translated content
            original: Original content
            quality_threshold: Minimum quality score (0.0-1.0)

        Returns:
            True if original should be used
        """
        # Simple quality checks
        if not translation or not translation.strip():
            return True

        # Check if translation is much shorter than original (possible truncation)
        length_ratio = len(translation) / len(original) if original else 0
        if length_ratio < quality_threshold:
            return True

        # Check for repetitive content
        words = translation.split()
        if len(words) > 10:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:  # Less than 30% unique words
                return True

        return False

    @staticmethod
    async def merge_partial_results(
        successful_translations: List[Dict[str, Any]],
        failed_units: List[Dict[str, Any]],
        use_original_for_failed: bool = True
    ) -> str:
        """Merge successful and failed translations.

        Args:
            successful_translations: List of successfully translated units
            failed_units: List of units that failed
            use_original_for_failed: Whether to use original content for failed units

        Returns:
            Combined content
        """
        # Create a map of all units
        all_units = {}

        for item in successful_translations:
            unit_id = item.get("unit_id") or item.get("unit", {}).get("unit_id")
            all_units[unit_id] = item.get("translation") or item.get("translated_content")

        for unit in failed_units:
            unit_id = unit.get("unit_id")
            if use_original_for_failed:
                content = unit.get("content", unit.get("original_content", ""))
                all_units[unit_id] = GracefulDegradation.create_fallback_translation(
                    content,
                    Exception("Translation failed")
                )
            else:
                all_units[unit_id] = ""

        # Combine in order
        sorted_units = sorted(all_units.items(), key=lambda x: x[0])
        return "\n\n".join(content for _, content in sorted_units if content)
