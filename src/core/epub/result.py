"""
Result type for explicit error handling.

Provides Railway-Oriented Programming pattern for safer error handling
without exceptions.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar, Union, Callable

T = TypeVar('T')  # Success type
E = TypeVar('E')  # Error type
R = TypeVar('R')  # Return type for map/and_then


@dataclass
class Ok(Generic[T]):
    """Successful result.

    Attributes:
        value: The successful value
    """
    value: T

    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return True

    def is_err(self) -> bool:
        """Check if result is Err."""
        return False

    def unwrap(self) -> T:
        """Get the value (safe for Ok)."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get value or default."""
        return self.value

    def map(self, func: Callable[[T], R]) -> 'Union[Ok[R], Err]':
        """Map function over Ok value.

        Args:
            func: Function to apply to value

        Returns:
            New Ok with transformed value
        """
        return Ok(func(self.value))

    def and_then(self, func: Callable[[T], 'Union[Ok[R], Err]']) -> 'Union[Ok[R], Err]':
        """Chain operations (flatMap).

        Args:
            func: Function returning a Result

        Returns:
            Result from function
        """
        return func(self.value)


@dataclass
class Err(Generic[E]):
    """Error result.

    Attributes:
        error: The error value
    """
    error: E

    def is_ok(self) -> bool:
        """Check if result is Ok."""
        return False

    def is_err(self) -> bool:
        """Check if result is Err."""
        return True

    def unwrap(self) -> None:
        """Raises ValueError (unsafe for Err)."""
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Get default value."""
        return default

    def map(self, func: Callable) -> 'Err[E]':
        """No-op for Err."""
        return self

    def and_then(self, func: Callable) -> 'Err[E]':
        """No-op for Err."""
        return self


# Type alias for Result
Result = Union[Ok[T], Err[E]]


# === Convenience Functions ===

def wrap_exception(func: Callable[..., T]) -> Callable[..., Union[Ok[T], Err[Exception]]]:
    """Decorator to wrap function exceptions in Result.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function returning Result

    Example:
        @wrap_exception
        def parse_int(s: str) -> int:
            return int(s)

        result = parse_int("42")
        if result.is_ok():
            print(result.unwrap())  # 42
    """
    def wrapper(*args, **kwargs) -> Union[Ok[T], Err[Exception]]:
        try:
            return Ok(func(*args, **kwargs))
        except Exception as e:
            return Err(e)
    return wrapper


def wrap_async_exception(
    func: Callable[..., T]
) -> Callable[..., Union[Ok[T], Err[Exception]]]:
    """Decorator for async functions.

    Args:
        func: Async function to wrap

    Returns:
        Wrapped async function returning Result

    Example:
        @wrap_async_exception
        async def fetch_data(url: str) -> str:
            response = await httpx.get(url)
            return response.text

        result = await fetch_data("https://example.com")
        if result.is_ok():
            print(result.unwrap())
    """
    async def wrapper(*args, **kwargs) -> Union[Ok[T], Err[Exception]]:
        try:
            return Ok(await func(*args, **kwargs))
        except Exception as e:
            return Err(e)
    return wrapper


def collect_results(results: list) -> Union[Ok[list], Err]:
    """Collect a list of Results into a single Result.

    If all Results are Ok, returns Ok with list of values.
    If any Result is Err, returns the first Err.

    Args:
        results: List of Result objects

    Returns:
        Ok(list of values) or first Err

    Example:
        results = [Ok(1), Ok(2), Ok(3)]
        collected = collect_results(results)
        # collected = Ok([1, 2, 3])

        results = [Ok(1), Err("failed"), Ok(3)]
        collected = collect_results(results)
        # collected = Err("failed")
    """
    values = []
    for result in results:
        if result.is_err():
            return result
        values.append(result.unwrap())
    return Ok(values)
