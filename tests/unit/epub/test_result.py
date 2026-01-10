"""Unit tests for Result type."""

import pytest
from src.core.epub.result import (
    Ok,
    Err,
    Result,
    wrap_exception,
    wrap_async_exception,
    collect_results
)


class TestOk:
    """Test Ok result type."""

    def test_ok_creation(self):
        """Create Ok result."""
        result = Ok(42)
        assert result.value == 42
        assert result.is_ok() is True
        assert result.is_err() is False

    def test_ok_unwrap(self):
        """Unwrap Ok value."""
        result = Ok("success")
        assert result.unwrap() == "success"

    def test_ok_unwrap_or(self):
        """unwrap_or should return value for Ok."""
        result = Ok(42)
        assert result.unwrap_or(0) == 42

    def test_ok_map(self):
        """Map function over Ok value."""
        result = Ok(5)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_ok()
        assert mapped.unwrap() == 10

    def test_ok_and_then(self):
        """Chain operations with and_then."""
        def validate(x: int) -> Result:
            if x > 0:
                return Ok(x * 2)
            else:
                return Err("Value must be positive")

        result = Ok(5).and_then(validate)
        assert result.is_ok()
        assert result.unwrap() == 10


class TestErr:
    """Test Err result type."""

    def test_err_creation(self):
        """Create Err result."""
        result = Err("error message")
        assert result.error == "error message"
        assert result.is_ok() is False
        assert result.is_err() is True

    def test_err_unwrap_raises(self):
        """Unwrap on Err should raise."""
        result = Err("error")
        with pytest.raises(ValueError, match="Called unwrap on Err"):
            result.unwrap()

    def test_err_unwrap_or(self):
        """unwrap_or should return default for Err."""
        result = Err("error")
        assert result.unwrap_or(42) == 42

    def test_err_map(self):
        """Map on Err should be no-op."""
        result = Err("error")
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_err()
        assert mapped.error == "error"

    def test_err_and_then(self):
        """and_then on Err should be no-op."""
        def never_called(x):
            pytest.fail("Should not be called")
            return Ok(x)

        result = Err("error").and_then(never_called)
        assert result.is_err()
        assert result.error == "error"


class TestResultChaining:
    """Test Result chaining operations."""

    def test_chaining_all_ok(self):
        """Chain multiple operations, all succeed."""
        result = (Ok(5)
                  .map(lambda x: x * 2)
                  .map(lambda x: x + 3)
                  .map(lambda x: str(x)))

        assert result.is_ok()
        assert result.unwrap() == "13"

    def test_chaining_with_err(self):
        """Chain operations, one fails."""
        def validate_positive(x: int) -> Result:
            if x > 0:
                return Ok(x)
            else:
                return Err("negative")

        result = (Ok(5)
                  .map(lambda x: x - 10)  # Results in -5
                  .and_then(validate_positive))

        assert result.is_err()
        assert result.error == "negative"

    def test_early_termination(self):
        """Err should short-circuit remaining operations."""
        call_count = [0]

        def count_call(x):
            call_count[0] += 1
            return x

        result = (Err("error")
                  .map(count_call)
                  .map(count_call)
                  .map(count_call))

        assert result.is_err()
        assert call_count[0] == 0  # Never called


class TestWrapException:
    """Test wrap_exception decorator."""

    def test_wrap_exception_success(self):
        """Wrap function that succeeds."""
        @wrap_exception
        def parse_int(s: str) -> int:
            return int(s)

        result = parse_int("42")
        assert result.is_ok()
        assert result.unwrap() == 42

    def test_wrap_exception_failure(self):
        """Wrap function that raises exception."""
        @wrap_exception
        def parse_int(s: str) -> int:
            return int(s)

        result = parse_int("not a number")
        assert result.is_err()
        assert isinstance(result.error, ValueError)

    def test_wrap_exception_with_args(self):
        """Wrap function with multiple arguments."""
        @wrap_exception
        def divide(a: int, b: int) -> float:
            return a / b

        result = divide(10, 2)
        assert result.is_ok()
        assert result.unwrap() == 5.0

        result = divide(10, 0)
        assert result.is_err()
        assert isinstance(result.error, ZeroDivisionError)


class TestWrapAsyncException:
    """Test wrap_async_exception decorator."""

    @pytest.mark.asyncio
    async def test_wrap_async_success(self):
        """Wrap async function that succeeds."""
        @wrap_async_exception
        async def async_parse(s: str) -> int:
            return int(s)

        result = await async_parse("42")
        assert result.is_ok()
        assert result.unwrap() == 42

    @pytest.mark.asyncio
    async def test_wrap_async_failure(self):
        """Wrap async function that raises."""
        @wrap_async_exception
        async def async_parse(s: str) -> int:
            return int(s)

        result = await async_parse("invalid")
        assert result.is_err()
        assert isinstance(result.error, ValueError)


class TestCollectResults:
    """Test collect_results function."""

    def test_collect_all_ok(self):
        """Collect list of Ok results."""
        results = [Ok(1), Ok(2), Ok(3), Ok(4)]
        collected = collect_results(results)

        assert collected.is_ok()
        assert collected.unwrap() == [1, 2, 3, 4]

    def test_collect_with_err(self):
        """Collect list with one Err."""
        results = [Ok(1), Ok(2), Err("error"), Ok(4)]
        collected = collect_results(results)

        assert collected.is_err()
        assert collected.error == "error"

    def test_collect_first_err_wins(self):
        """First Err should be returned."""
        results = [Ok(1), Err("first"), Err("second"), Ok(4)]
        collected = collect_results(results)

        assert collected.is_err()
        assert collected.error == "first"

    def test_collect_empty_list(self):
        """Collect empty list."""
        results = []
        collected = collect_results(results)

        assert collected.is_ok()
        assert collected.unwrap() == []


class TestRealWorldUsage:
    """Test Result type in realistic scenarios."""

    def test_validation_pipeline(self):
        """Simulate validation pipeline."""
        def validate_length(text: str) -> Result:
            if len(text) > 0:
                return Ok(text)
            return Err("Text cannot be empty")

        def validate_max_length(text: str) -> Result:
            if len(text) <= 100:
                return Ok(text)
            return Err("Text too long")

        def process_text(text: str) -> str:
            return text.upper()

        # Valid input
        result = (Ok("hello")
                  .and_then(validate_length)
                  .and_then(validate_max_length)
                  .map(process_text))

        assert result.is_ok()
        assert result.unwrap() == "HELLO"

        # Empty input
        result = (Ok("")
                  .and_then(validate_length)
                  .and_then(validate_max_length)
                  .map(process_text))

        assert result.is_err()
        assert result.error == "Text cannot be empty"

    def test_error_recovery(self):
        """Simulate error recovery with unwrap_or."""
        def risky_operation(x: int) -> Result:
            if x > 0:
                return Ok(x * 2)
            return Err("Invalid input")

        # With error
        value = risky_operation(-5).unwrap_or(0)
        assert value == 0

        # Without error
        value = risky_operation(5).unwrap_or(0)
        assert value == 10
