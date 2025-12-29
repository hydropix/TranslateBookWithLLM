"""
LLM Provider abstraction and implementations
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
import re
import httpx
import json
import asyncio

from src.config import (
    API_ENDPOINT, DEFAULT_MODEL, REQUEST_TIMEOUT, OLLAMA_NUM_CTX,
    MAX_TRANSLATION_ATTEMPTS, RETRY_DELAY_SECONDS,
    TRANSLATE_TAG_IN, TRANSLATE_TAG_OUT,
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_API_ENDPOINT,
    THINKING_MODELS, UNCONTROLLABLE_THINKING_MODELS, CONTROLLABLE_THINKING_MODELS,
    REPETITION_MIN_PHRASE_LENGTH, REPETITION_MIN_COUNT,
    REPETITION_MIN_COUNT_THINKING, REPETITION_MIN_COUNT_STREAMING
)
from enum import Enum
from dataclasses import dataclass


class ThinkingBehavior(Enum):
    """Classification of model thinking behavior"""
    STANDARD = "standard"              # No thinking capability
    CONTROLLABLE = "controllable"      # Thinks but respects think=false
    UNCONTROLLABLE = "uncontrollable"  # CANNOT stop thinking - needs WARNING


# =============================================================================
# THINKING BEHAVIOR CACHE
# =============================================================================
# Persistent cache to avoid re-testing models on every startup
# Cache is stored in data/thinking_cache.json

import os
from pathlib import Path

_THINKING_CACHE_FILE = Path("data/thinking_cache.json")
_thinking_cache: Dict[str, Dict[str, Any]] = {}
_cache_loaded = False


def _load_thinking_cache():
    """Load thinking behavior cache from disk."""
    global _thinking_cache, _cache_loaded
    if _cache_loaded:
        return

    try:
        if _THINKING_CACHE_FILE.exists():
            with open(_THINKING_CACHE_FILE, "r", encoding="utf-8") as f:
                _thinking_cache = json.load(f)
    except Exception:
        _thinking_cache = {}

    _cache_loaded = True


def _save_thinking_cache():
    """Save thinking behavior cache to disk."""
    try:
        _THINKING_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_THINKING_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_thinking_cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Silently fail - cache is just an optimization


def _model_matches_pattern(model: str, pattern: str) -> bool:
    """
    Check if model name matches a pattern precisely.

    Matching rules:
    - "qwen3:30b" matches "qwen3:30b" exactly
    - "qwen3:30b" does NOT match "qwen3:30b-instruct"
    - "qwen3-vl" matches "qwen3-vl:4b", "qwen3-vl:8b" (prefix match with colon)
    - "phi4-reasoning" matches "phi4-reasoning:latest", "phi4-reasoning:14b"

    Args:
        model: Full model name (e.g., "qwen3:30b-instruct")
        pattern: Pattern from config (e.g., "qwen3:30b")

    Returns:
        True if model matches pattern
    """
    model_lower = model.lower()
    pattern_lower = pattern.lower()

    # Exact match
    if model_lower == pattern_lower:
        return True

    # Pattern with size (e.g., "qwen3:30b") - must match exactly or be a prefix followed by nothing valid
    # "qwen3:30b" should NOT match "qwen3:30b-instruct"
    if ":" in pattern_lower:
        # Check if model starts with pattern and next char (if any) is not alphanumeric or hyphen
        if model_lower.startswith(pattern_lower):
            remaining = model_lower[len(pattern_lower):]
            # If nothing remains, it's exact match (already handled above)
            # If something remains and starts with alphanumeric or hyphen, it's a different model
            if remaining and (remaining[0].isalnum() or remaining[0] == '-'):
                return False
            return True
        return False

    # Pattern without size (e.g., "qwen3-vl", "phi4-reasoning") - prefix match
    # "qwen3-vl" should match "qwen3-vl:4b", "qwen3-vl:8b"
    if model_lower.startswith(pattern_lower):
        remaining = model_lower[len(pattern_lower):]
        # Must be followed by nothing, ":", or end
        if not remaining or remaining[0] == ':':
            return True

    return False


def get_cached_thinking_behavior(model: str, endpoint: str = "") -> Optional[ThinkingBehavior]:
    """
    Get cached thinking behavior for a model (instant lookup).

    Args:
        model: Model name (e.g., "qwen3:14b")
        endpoint: Optional endpoint to differentiate same model on different servers

    Returns:
        ThinkingBehavior if cached, None if not tested yet
    """
    _load_thinking_cache()

    # Create cache key (model + endpoint hash for uniqueness)
    cache_key = f"{model}@{endpoint}" if endpoint else model

    if cache_key in _thinking_cache:
        behavior_str = _thinking_cache[cache_key].get("behavior")
        if behavior_str:
            try:
                return ThinkingBehavior(behavior_str)
            except ValueError:
                pass

    # Check known lists as fallback (instant) - use precise matching
    for pattern in UNCONTROLLABLE_THINKING_MODELS:
        if _model_matches_pattern(model, pattern):
            return ThinkingBehavior.UNCONTROLLABLE
    for pattern in CONTROLLABLE_THINKING_MODELS:
        if _model_matches_pattern(model, pattern):
            return ThinkingBehavior.CONTROLLABLE

    return None


def cache_thinking_behavior(
    model: str,
    behavior: ThinkingBehavior,
    supports_think_param: bool = True,
    endpoint: str = ""
):
    """
    Cache thinking behavior for a model.

    Args:
        model: Model name
        behavior: Detected behavior
        supports_think_param: Whether model supports think parameter
        endpoint: Optional endpoint
    """
    _load_thinking_cache()

    cache_key = f"{model}@{endpoint}" if endpoint else model
    _thinking_cache[cache_key] = {
        "behavior": behavior.value,
        "supports_think_param": supports_think_param,
        "tested_at": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
    }

    _save_thinking_cache()


def get_thinking_behavior_sync(model: str, endpoint: str = "") -> Optional[ThinkingBehavior]:
    """
    Synchronous version for UI - returns cached or known list result instantly.

    This is safe to call from sync code (UI dropdowns, etc.) as it never
    makes network requests - only checks cache and known lists.

    Args:
        model: Model name
        endpoint: Optional endpoint

    Returns:
        ThinkingBehavior if known, None if needs async testing
    """
    return get_cached_thinking_behavior(model, endpoint)


def get_model_warning_message(model: str, endpoint: str = "") -> Optional[str]:
    """
    Get warning message for a model if it's uncontrollable (for UI display).

    Args:
        model: Model name
        endpoint: Optional endpoint

    Returns:
        Warning message string if uncontrollable, None otherwise
    """
    behavior = get_thinking_behavior_sync(model, endpoint)

    if behavior == ThinkingBehavior.UNCONTROLLABLE:
        model_lower = model.lower()

        # Build recommendation based on model
        recommendation = ""
        if "qwen3" in model_lower and "instruct" not in model_lower:
            size_match = re.search(r':(\d+b)', model_lower)
            size = size_match.group(1) if size_match else ""
            if size:
                recommendation = f"Recommended: qwen3:{size}-instruct"
            else:
                recommendation = "Recommended: Use a Qwen3 instruct variant"
        elif "phi4-reasoning" in model_lower:
            recommendation = "Recommended: phi4:latest"
        elif "deepseek" in model_lower or "qwq" in model_lower:
            recommendation = "Recommended: Use a non-reasoning model"

        warning = "⚠️ This model cannot disable thinking mode (slower, uses more tokens)"
        if recommendation:
            warning += f"\n{recommendation}"

        return warning

    return None


class ContextOverflowError(Exception):
    """Raised when prompt exceeds model's context window"""
    pass


class RepetitionLoopError(Exception):
    """Raised when model enters a repetition loop (common with thinking models on insufficient context)"""
    pass


def detect_repetition_loop(
    text: str,
    min_phrase_length: int = None,
    min_repetitions: int = None,
    is_thinking_content: bool = False
) -> bool:
    """
    Detect if text contains a repetition loop pattern.

    This is common with thinking models (Qwen, DeepSeek) when context window is too small -
    they enter loops like "I'm not sure. I'm not sure. I'm not sure..."

    The detection uses different thresholds for:
    - Regular content: stricter detection (fewer repetitions needed)
    - Thinking content: more lenient (thinking models may naturally repeat phrases)

    Args:
        text: Text to analyze
        min_phrase_length: Minimum phrase length to detect (default from config)
        min_repetitions: Minimum number of repetitions to trigger detection (default from config)
        is_thinking_content: If True, uses more lenient thresholds for thinking model output

    Returns:
        True if repetition loop detected, False otherwise
    """
    # Use config defaults if not specified
    if min_phrase_length is None:
        min_phrase_length = REPETITION_MIN_PHRASE_LENGTH
    if min_repetitions is None:
        min_repetitions = REPETITION_MIN_COUNT_THINKING if is_thinking_content else REPETITION_MIN_COUNT

    if not text or len(text) < min_phrase_length * min_repetitions:
        return False

    # Check last portion of text for repetition patterns
    # Use a larger window for better detection
    check_text = text[-3000:] if len(text) > 3000 else text

    # Look for repeated phrases of various lengths
    # Longer phrases are more indicative of pathological loops
    for phrase_len in range(min_phrase_length, min(80, len(check_text) // min_repetitions)):
        # For longer phrases, we need fewer repetitions (they're more indicative of a loop)
        # Short phrases (5-10 chars) need more repetitions to avoid false positives
        adjusted_min_reps = min_repetitions
        if phrase_len >= 20:
            adjusted_min_reps = max(5, min_repetitions - 5)  # Longer phrases need fewer reps
        elif phrase_len >= 40:
            adjusted_min_reps = max(3, min_repetitions - 8)  # Very long phrases are very suspicious

        # Find potential repeating phrases
        for start in range(len(check_text) - phrase_len * adjusted_min_reps):
            phrase = check_text[start:start + phrase_len]

            # Skip if phrase is just whitespace or punctuation
            if not any(c.isalnum() for c in phrase):
                continue

            # Skip very common short phrases that might naturally repeat
            # These are normal in thinking and don't indicate a loop
            if phrase_len <= 10:
                common_phrases = ['the ', 'and ', 'to ', 'of ', 'in ', 'is ', 'it ', 'that ', 'for ']
                if phrase.lower().strip() in common_phrases:
                    continue

            # Count consecutive occurrences
            count = 1
            pos = start + phrase_len
            while pos + phrase_len <= len(check_text):
                if check_text[pos:pos + phrase_len] == phrase:
                    count += 1
                    pos += phrase_len
                else:
                    break

            if count >= adjusted_min_reps:
                return True

    return False


@dataclass
class LLMResponse:
    """Response from LLM with token usage information"""
    content: str
    prompt_tokens: int = 0  # Number of tokens in the prompt
    completion_tokens: int = 0  # Number of tokens in the response
    context_used: int = 0  # Total context used (prompt + completion)
    context_limit: int = 0  # Context limit that was set for this request
    was_truncated: bool = False  # True if response was truncated due to context limit


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, model: str):
        self.model = model
        self._compiled_regex = re.compile(
            rf"{re.escape(TRANSLATE_TAG_IN)}(.*?){re.escape(TRANSLATE_TAG_OUT)}",
            re.DOTALL
        )
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a persistent HTTP client with connection pooling"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                timeout=httpx.Timeout(REQUEST_TIMEOUT)
            )
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional["LLMResponse"]:
        """
        Generate text from prompt.

        Args:
            prompt: The user prompt (content to process)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse object with content and token usage info, or None if failed
        """
        pass
    
    def extract_translation(self, response: str) -> Optional[str]:
        """
        Extract translation from response using configured tags with strict validation.

        Returns the content between TRANSLATE_TAG_IN and TRANSLATE_TAG_OUT.
        Prefers responses where tags are at exact boundaries for better reliability.

        NOTE: This method completely ignores content within <think></think> tags,
        as these are used by certain LLMs for internal reasoning and should not
        be searched for translation tags.
        """
        if not response:
            return None

        # Trim whitespace from response
        response = response.strip()
        original_length = len(response)

        # IMPORTANT: Remove all <think>...</think> blocks completely
        # These contain LLM's internal reasoning and should be completely ignored
        # Do NOT search for <Translate> tags inside these blocks!

        # Case 1: Complete <think>...</think> blocks
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)

        # Case 2: Orphan closing tag </think> (when Ollama truncates the opening tag)
        # Remove everything from the beginning up to and including </think>
        before_orphan_removal = response
        response = re.sub(r'^.*?</think>\s*', '', response, flags=re.DOTALL | re.IGNORECASE)

        if before_orphan_removal != response:
            removed_length = len(before_orphan_removal) - len(response)
            print(f"[DEBUG] Orphan </think> detected - removed {removed_length} characters from beginning")

        response = response.strip()

        if len(response) < original_length:
            print(f"[DEBUG] Think blocks removed: {original_length} -> {len(response)} chars (-{original_length - len(response)})")
            print(f"[DEBUG] Response after think removal (first 200 chars): {response[:200]}")

        # STRICT VALIDATION: Check if response starts and ends with correct tags
        starts_correctly = response.startswith(TRANSLATE_TAG_IN)
        ends_correctly = response.endswith(TRANSLATE_TAG_OUT)

        if starts_correctly and ends_correctly:
            # Perfect format - extract content between boundary tags
            content = response[len(TRANSLATE_TAG_IN):-len(TRANSLATE_TAG_OUT)]
            return content.strip()

        # FALLBACK: Try regex search for tags anywhere in response (less strict)
        match = self._compiled_regex.search(response)
        if match:
            extracted = match.group(1).strip()

            # Warn if extraction was from middle of response (indicates LLM didn't follow instructions)
            if not starts_correctly or not ends_correctly:
                print(f"⚠️  Warning: Translation tags found but not at response boundaries.")
                print(f"   Response started with tags: {starts_correctly}")
                print(f"   Response ended with tags: {ends_correctly}")
                print(f"   This may indicate the LLM added extra text. Using extracted content anyway.")

            return extracted

        # No tags found at all
        return None
    
    async def translate_text(self, prompt: str) -> Optional[str]:
        """Complete translation workflow: request + extraction"""
        response = await self.generate(prompt)
        if response:
            return self.extract_translation(response.content)
        return None


class OllamaProvider(LLMProvider):
    """Ollama API provider - uses /api/chat for proper think parameter support"""

    def __init__(self, api_endpoint: str = API_ENDPOINT, model: str = DEFAULT_MODEL,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        # Convert /api/generate endpoint to /api/chat for proper think support
        self.api_endpoint = api_endpoint.replace('/api/generate', '/api/chat')
        self.context_window = context_window
        self.log_callback = log_callback
        # Will be detected on first request via _detect_thinking_behavior()
        self._thinking_behavior: Optional[ThinkingBehavior] = None
        self._supports_think_param: bool = True
        # Quick check against known model lists (fallback if detection fails)
        self._known_uncontrollable = any(_model_matches_pattern(model, tm) for tm in UNCONTROLLABLE_THINKING_MODELS)
        self._known_controllable = any(_model_matches_pattern(model, tm) for tm in CONTROLLABLE_THINKING_MODELS)

    def _check_known_model_lists(self) -> Optional[ThinkingBehavior]:
        """Check if model matches known model lists for quick classification."""
        # Check uncontrollable list first (more specific matches)
        for pattern in UNCONTROLLABLE_THINKING_MODELS:
            if _model_matches_pattern(self.model, pattern):
                return ThinkingBehavior.UNCONTROLLABLE

        # Check controllable list
        for pattern in CONTROLLABLE_THINKING_MODELS:
            if _model_matches_pattern(self.model, pattern):
                return ThinkingBehavior.CONTROLLABLE

        return None

    async def _test_thinking(self, think_param: Optional[bool] = None) -> tuple[bool, bool, bool]:
        """
        Test model thinking behavior with specific think parameter.

        Args:
            think_param: True/False/None (None = don't include param)

        Returns:
            (has_thinking_field, has_think_tags, supports_param)
        """
        test_prompt = "What is 2+2? Reply with just the number."

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": test_prompt}],
            "stream": False,
            "options": {"num_ctx": 2048},
        }

        if think_param is not None:
            payload["think"] = think_param

        client = await self._get_client()
        response = await client.post(self.api_endpoint, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")
        thinking = message.get("thinking", "")

        has_thinking_field = bool(thinking)
        has_think_tags = bool(re.search(r'<think>|</think>', content, re.IGNORECASE))

        return has_thinking_field, has_think_tags, True

    async def _detect_thinking_behavior(self) -> ThinkingBehavior:
        """
        Detect model's thinking behavior by testing with different think parameters.

        Classification:
        - STANDARD: Model never thinks
        - CONTROLLABLE: Model thinks but respects think=false
        - UNCONTROLLABLE: Model thinks even with think=false (needs WARNING)

        Uses persistent cache to avoid re-testing on every startup.

        Returns:
            ThinkingBehavior classification
        """
        # Check cache first (instant)
        cached = get_cached_thinking_behavior(self.model, self.api_endpoint)
        if cached:
            if self.log_callback:
                self.log_callback("info", f"[MODEL] {self.model}: {cached.value} (from cache)")
            return cached

        # Check known model lists (instant fallback)
        known_behavior = self._check_known_model_lists()
        if known_behavior:
            if self.log_callback:
                self.log_callback("info", f"[MODEL] {self.model}: {known_behavior.value} (from known list)")
            # Cache for future use
            cache_thinking_behavior(self.model, known_behavior, True, self.api_endpoint)
            return known_behavior

        # Need to run dynamic tests (slow - 3 LLM requests)
        if self.log_callback:
            self.log_callback("info", f"[MODEL] {self.model}: Testing thinking behavior (first time)...")

        try:
            # Test 1: Without think parameter (baseline)
            field_none, tags_none, _ = await self._test_thinking(think_param=None)
            thinks_without_param = field_none or tags_none

            # Test 2: With think=true (does model support thinking?)
            try:
                field_true, tags_true, _ = await self._test_thinking(think_param=True)
                thinks_when_enabled = field_true or tags_true
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    # Model doesn't support think param
                    self._supports_think_param = False
                    if thinks_without_param:
                        return ThinkingBehavior.UNCONTROLLABLE
                    return ThinkingBehavior.STANDARD
                raise

            # Test 3: With think=false (can we disable thinking?)
            try:
                field_false, tags_false, _ = await self._test_thinking(think_param=False)
                thinks_when_disabled = field_false or tags_false
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    self._supports_think_param = False
                    if thinks_without_param:
                        return ThinkingBehavior.UNCONTROLLABLE
                    return ThinkingBehavior.STANDARD
                raise

            # Classify based on test results
            if thinks_when_disabled:
                # Model thinks even with think=false - UNCONTROLLABLE
                behavior = ThinkingBehavior.UNCONTROLLABLE
            elif thinks_when_enabled or thinks_without_param:
                # Model can think but respects think=false - CONTROLLABLE
                behavior = ThinkingBehavior.CONTROLLABLE
            else:
                # Model never thinks - STANDARD
                behavior = ThinkingBehavior.STANDARD

            # Cache the result for future use
            cache_thinking_behavior(self.model, behavior, self._supports_think_param, self.api_endpoint)
            if self.log_callback:
                self.log_callback("info", f"[MODEL] {self.model}: {behavior.value} (tested & cached)")

            return behavior

        except Exception as e:
            # If detection fails, use known lists or default to standard
            if self.log_callback:
                self.log_callback("warning", f"[MODEL DETECTION] Failed for {self.model}: {e}")

            if self._known_uncontrollable:
                return ThinkingBehavior.UNCONTROLLABLE
            elif self._known_controllable:
                return ThinkingBehavior.CONTROLLABLE
            return ThinkingBehavior.STANDARD

    def _show_thinking_warning(self):
        """Display warning for uncontrollable thinking models."""
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

        print(f"\n{RED}{'='*70}{RESET}")
        print(f"{RED}{BOLD}[WARNING] UNCONTROLLABLE THINKING MODEL: {self.model}{RESET}")
        print(f"{RED}{'='*70}{RESET}")
        print(f"{YELLOW}This model produces <think> blocks that CANNOT be disabled.{RESET}")
        print(f"{YELLOW}Consequences:{RESET}")
        print(f"{YELLOW}  - SLOWER translations (model thinks before answering){RESET}")
        print(f"{YELLOW}  - MORE tokens consumed (reasoning uses context window){RESET}")
        print(f"{YELLOW}  - LESS consistent results for translation tasks{RESET}")
        print()

        # Suggest alternatives based on model
        model_lower = self.model.lower()
        if "qwen3" in model_lower and "instruct" not in model_lower:
            size_match = re.search(r':(\d+b)', model_lower)
            size = size_match.group(1) if size_match else ""
            if size:
                print(f"{GREEN}{BOLD}RECOMMENDATION: Use 'qwen3:{size}-instruct' instead{RESET}")
                print(f"{GREEN}  → Instruct models give direct answers without thinking{RESET}")
                print(f"{GREEN}  → Same quality, faster speed, less token usage{RESET}")
            else:
                print(f"{GREEN}{BOLD}RECOMMENDATION: Use a Qwen3 instruct variant{RESET}")
                print(f"{GREEN}  → Example: qwen3:14b-instruct, qwen3:30b-instruct{RESET}")
        elif "phi4-reasoning" in model_lower:
            print(f"{GREEN}{BOLD}RECOMMENDATION: Use 'phi4:latest' instead{RESET}")
            print(f"{GREEN}  → Standard Phi4 doesn't use reasoning mode{RESET}")
        elif "deepseek" in model_lower or "qwq" in model_lower:
            print(f"{GREEN}{BOLD}RECOMMENDATION: Use a non-reasoning model{RESET}")
            print(f"{GREEN}  → Reasoning models are for complex problems, not translation{RESET}")

        print(f"{RED}{'='*70}{RESET}\n")
        print(f"{CYAN}[INFO] Using think=true to cleanly separate thinking from content{RESET}\n")

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using Ollama Chat API with streaming for real-time token monitoring.

        Uses streaming to detect context overflow in real-time (Ollama doesn't return
        errors when context is exceeded - it just keeps generating garbage).

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        # Detect thinking behavior on first request
        if self._thinking_behavior is None:
            self._thinking_behavior = await self._detect_thinking_behavior()

            # Show warning only for uncontrollable thinking models
            if self._thinking_behavior == ThinkingBehavior.UNCONTROLLABLE and self.log_callback:
                self._show_thinking_warning()
            elif self._thinking_behavior == ThinkingBehavior.CONTROLLABLE and self.log_callback:
                GREEN = '\033[92m'
                RESET = '\033[0m'
                print(f"\n{GREEN}[MODEL] {self.model}: Controllable thinking model - using think=false{RESET}")
            elif self._thinking_behavior == ThinkingBehavior.STANDARD and self.log_callback:
                GREEN = '\033[92m'
                RESET = '\033[0m'
                print(f"\n{GREEN}[MODEL] {self.model}: Standard model (no thinking){RESET}")

        # Build messages array for chat API
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Determine think parameter based on behavior:
        # - UNCONTROLLABLE: use think=true to cleanly separate thinking into dedicated field
        # - CONTROLLABLE: use think=false to disable thinking
        # - STANDARD: don't include think param (model doesn't support it)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,  # Enable streaming for real-time token monitoring
            "options": {
                "num_ctx": self.context_window,
                "truncate": False
            },
        }

        # Only add think param if model supports it
        if self._supports_think_param:
            if self._thinking_behavior == ThinkingBehavior.UNCONTROLLABLE:
                # For uncontrollable models, use think=true to get clean separation
                payload["think"] = True
            else:
                # For controllable and standard models, use think=false
                payload["think"] = False

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                # Use streaming to monitor tokens in real-time
                content_chunks = []
                thinking_chunks = []
                prompt_tokens = 0
                completion_tokens = 0
                exceeded_context = False

                # Calculate safe limit for completion tokens
                # Reserve space for prompt (we'll get actual count from first chunk)
                # Use 90% of remaining context as safety margin
                max_completion_tokens = int(self.context_window * 0.85)

                async with client.stream("POST", self.api_endpoint, json=payload, timeout=timeout) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            chunk_data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Get prompt tokens from first chunk (Ollama sends this once)
                        if chunk_data.get("prompt_eval_count"):
                            prompt_tokens = chunk_data["prompt_eval_count"]
                            # Recalculate max completion tokens based on actual prompt size
                            max_completion_tokens = int((self.context_window - prompt_tokens) * 0.90)

                        # Accumulate content
                        message = chunk_data.get("message", {})
                        if message.get("content"):
                            content_chunks.append(message["content"])
                        if message.get("thinking"):
                            thinking_chunks.append(message["thinking"])

                        # Update completion token count
                        if chunk_data.get("eval_count"):
                            completion_tokens = chunk_data["eval_count"]

                        # Check for context overflow during streaming
                        # This catches the case where Ollama keeps generating past the limit
                        current_completion_len = len("".join(content_chunks)) + len("".join(thinking_chunks))

                        # Heuristic: ~4 chars per token on average
                        estimated_tokens = current_completion_len // 3

                        if estimated_tokens > max_completion_tokens:
                            exceeded_context = True
                            if self.log_callback:
                                RED = '\033[91m'
                                RESET = '\033[0m'
                                print(f"\n{RED}[STREAM ABORT] Estimated {estimated_tokens} tokens exceeds "
                                      f"safe limit {max_completion_tokens} (context: {self.context_window}){RESET}")
                            break

                        # Also check for repetition in real-time during streaming
                        current_content = "".join(content_chunks)
                        current_thinking = "".join(thinking_chunks)

                        # Only check periodically (every ~500 chars) to avoid overhead
                        # Use streaming thresholds (slightly more sensitive for early detection)
                        if len(current_content) > 500 and len(current_content) % 500 < 50:
                            if detect_repetition_loop(
                                current_content,
                                min_repetitions=REPETITION_MIN_COUNT_STREAMING,
                                is_thinking_content=False
                            ):
                                exceeded_context = True
                                if self.log_callback:
                                    RED = '\033[91m'
                                    RESET = '\033[0m'
                                    print(f"\n{RED}[STREAM ABORT] Repetition loop detected in content{RESET}")
                                break

                        # For thinking content, use more lenient detection
                        if len(current_thinking) > 800 and len(current_thinking) % 500 < 50:
                            if detect_repetition_loop(
                                current_thinking,
                                min_repetitions=REPETITION_MIN_COUNT_STREAMING,
                                is_thinking_content=True
                            ):
                                exceeded_context = True
                                if self.log_callback:
                                    RED = '\033[91m'
                                    RESET = '\033[0m'
                                    print(f"\n{RED}[STREAM ABORT] Repetition loop detected in thinking{RESET}")
                                break

                        # Check if stream is done
                        if chunk_data.get("done"):
                            # Get final token counts
                            prompt_tokens = chunk_data.get("prompt_eval_count", prompt_tokens)
                            completion_tokens = chunk_data.get("eval_count", completion_tokens)
                            break

                # If we exceeded context, raise error for retry with larger context
                if exceeded_context:
                    raise RepetitionLoopError(
                        f"Context overflow detected during streaming. "
                        f"Context window ({self.context_window}) is too small. "
                        f"Prompt used ~{prompt_tokens} tokens, leaving insufficient space for response."
                    )

                # Combine chunks
                content = "".join(content_chunks)
                thinking = "".join(thinking_chunks)

                # Estimate thinking tokens if present
                # Ollama's eval_count may or may not include thinking tokens depending on version
                # We estimate thinking tokens (~3.5 chars per token for English text) and use
                # the MAX of reported completion_tokens or our estimate to be safe
                thinking_tokens_estimate = len(thinking) // 3 if thinking else 0
                content_tokens_estimate = len(content) // 3 if content else 0
                total_completion_estimate = thinking_tokens_estimate + content_tokens_estimate

                # Use the higher value to avoid underestimating (which causes premature context reduction)
                effective_completion_tokens = max(completion_tokens, total_completion_estimate)

                # If there's a significant difference, the reported count likely excludes thinking
                if thinking and effective_completion_tokens > completion_tokens * 1.2:
                    if self.log_callback:
                        self.log_callback("token_usage_warning",
                            f"⚠️ Thinking tokens likely not in eval_count: reported={completion_tokens}, "
                            f"estimated={total_completion_estimate} (thinking~{thinking_tokens_estimate}, content~{content_tokens_estimate})")

                context_used = prompt_tokens + effective_completion_tokens

                # Detect if context was nearly exhausted
                truncation_threshold = self.context_window * 0.95
                was_truncated = context_used >= truncation_threshold

                # Log token usage
                if self.log_callback:
                    status = "⚠️ NEAR LIMIT" if was_truncated else "✓"
                    thinking_info = f" (incl. ~{thinking_tokens_estimate} thinking)" if thinking else ""
                    self.log_callback("token_usage",
                        f"Tokens: prompt={prompt_tokens}, response={effective_completion_tokens}{thinking_info}, "
                        f"total={context_used}/{self.context_window} {status}")

                # Log thinking content if present
                CYAN = '\033[96m'
                RESET = '\033[0m'

                if thinking and self.log_callback:
                    print(f"\n{CYAN}{'='*80}")
                    print(f"[THINKING FIELD] Model produced thinking ({len(thinking)} chars):")
                    print(f"{thinking}")
                    print(f"{'='*80}{RESET}\n")

                # Check for <think> blocks in content
                if "<think>" in content.lower() and self.log_callback:
                    think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL | re.IGNORECASE)
                    if think_match:
                        think_content = think_match.group(1)
                        print(f"\n{CYAN}{'='*80}")
                        print(f"[THINK BLOCK IN CONTENT] Model embedded thinking ({len(think_content)} chars):")
                        print(f"{think_content}")
                        print(f"{'='*80}{RESET}\n")

                # Final repetition loop check on complete response
                # Use appropriate thresholds for thinking vs content
                loop_detected_in = None
                if thinking and detect_repetition_loop(thinking, is_thinking_content=True):
                    loop_detected_in = "thinking"
                elif content and detect_repetition_loop(content, is_thinking_content=False):
                    loop_detected_in = "content"

                if loop_detected_in:
                    RED = '\033[91m'
                    error_msg = (
                        f"Repetition loop detected in {loop_detected_in}! "
                        f"This usually means the context window ({self.context_window}) is too small for thinking models. "
                        f"Try increasing OLLAMA_NUM_CTX or reducing chunk size."
                    )
                    print(f"\n{RED}{'='*80}")
                    print(f"[REPETITION LOOP DETECTED] {error_msg}")
                    print(f"{'='*80}{RESET}\n")
                    raise RepetitionLoopError(error_msg)

                return LLMResponse(
                    content=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=effective_completion_tokens,  # Use effective count (includes thinking estimate)
                    context_used=context_used,
                    context_limit=self.context_window,
                    was_truncated=was_truncated
                )

            except httpx.TimeoutException:
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except httpx.HTTPStatusError as e:
                error_message = str(e)
                if e.response:
                    try:
                        error_data = e.response.json()
                        error_message = error_data.get("error", str(e))
                    except:
                        pass

                if any(keyword in error_message.lower()
                       for keyword in ["context", "truncate", "length", "too long"]):
                    if self.log_callback:
                        self.log_callback("error",
                            f"Context size exceeded! Prompt is too large for model's context window.\n"
                            f"Error: {error_message}\n"
                            f"Consider: 1) Reducing chunk_size, or 2) Increasing OLLAMA_NUM_CTX")
                    raise ContextOverflowError(error_message)

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except (RepetitionLoopError, ContextOverflowError):
                # These errors should propagate up for handling by translator
                raise
            except (json.JSONDecodeError, Exception) as e:
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None

        return None

    async def get_model_context_size(self) -> int:
        """
        Query Ollama API to get the model's context size.

        Returns:
            int: Maximum context size in tokens
        """
        try:
            client = await self._get_client()
            # Build /api/show endpoint from chat endpoint
            show_endpoint = self.api_endpoint.replace('/api/chat', '/api/show').replace('/api/generate', '/api/show')

            response = await client.post(
                show_endpoint,
                json={"name": self.model},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

            # Parse modelfile and parameters to find num_ctx
            modelfile = data.get("modelfile", "")
            parameters = data.get("parameters", "")
            combined = modelfile + "\n" + parameters

            # Look for PARAMETER num_ctx or num_ctx in parameters
            match = re.search(r'num_ctx[\s"]+(\d+)', combined, re.IGNORECASE)
            if match:
                detected_ctx = int(match.group(1))
                if self.log_callback:
                    self.log_callback("info", f"Detected model context size: {detected_ctx} tokens")
                return detected_ctx

            # Default values by model family (use shared constants)
            from src.config import MODEL_FAMILY_CONTEXT_DEFAULTS, DEFAULT_CONTEXT_FALLBACK

            model_lower = self.model.lower()
            for family, default_ctx in MODEL_FAMILY_CONTEXT_DEFAULTS.items():
                if family in model_lower:
                    if self.log_callback:
                        self.log_callback("info",
                            f"Using default context size for {family}: {default_ctx} tokens")
                    return default_ctx

            # Conservative fallback
            if self.log_callback:
                self.log_callback("warning",
                    f"Could not detect model context size, using default: {DEFAULT_CONTEXT_FALLBACK} tokens")
            return DEFAULT_CONTEXT_FALLBACK

        except Exception as e:
            if self.log_callback:
                self.log_callback("warning",
                    f"Failed to query model context size: {e}. Using configured value.")
            return self.context_window


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (works with llama.cpp, LM Studio, vLLM, OpenAI, etc.)"""

    def __init__(self, api_endpoint: str, model: str, api_key: Optional[str] = None,
                 context_window: int = OLLAMA_NUM_CTX, log_callback: Optional[Callable] = None):
        super().__init__(model)
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.context_window = context_window
        self.log_callback = log_callback
        self._detected_context_size: Optional[int] = None

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using an OpenAI compatible API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build messages array with optional system prompt
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Disable thinking/reasoning mode for local servers and compatible APIs
            # This prevents models from outputting <think>...</think> blocks
            "thinking": False,
            "enable_thinking": False,
            # Some servers use chat_template_kwargs
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        }

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()

                response_json = response.json()
                response_text = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Extract token usage if available
                usage = response_json.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                return LLMResponse(
                    content=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    context_used=prompt_tokens + completion_tokens,
                    context_limit=self.context_window,
                    was_truncated=False  # OpenAI API doesn't provide truncation info
                )

            except httpx.TimeoutException as e:
                    print(f"OpenAI-compatible API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except httpx.HTTPStatusError as e:
                    error_message = str(e)
                    error_body = ""
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        error_body = e.response.text[:500]
                        error_message = f"{e} - {error_body}"

                    print(f"OpenAI-compatible API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if error_body:
                        print(f"Response details: Status {e.response.status_code}, Body: {error_body}...")

                    # Detect context overflow errors (OpenAI-compatible APIs use "context_length_exceeded" or similar)
                    context_overflow_keywords = ["context_length", "maximum context", "token limit",
                                                  "too many tokens", "reduce the length", "max_tokens"]
                    if any(keyword in error_message.lower() for keyword in context_overflow_keywords):
                        raise ContextOverflowError(f"Context overflow: {error_message}")

                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except json.JSONDecodeError as e:
                    print(f"OpenAI-compatible API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except Exception as e:
                    print(f"OpenAI-compatible API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None

        return None

    async def get_model_context_size(self) -> int:
        """Query server to get model's context size. Tries multiple endpoints."""
        if self._detected_context_size:
            return self._detected_context_size

        client = await self._get_client()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Try endpoints in order: /props -> /v1/models/{model} -> /v1/models -> fallback
        for strategy in [self._try_props_endpoint, self._try_model_info_endpoint,
                         self._try_models_list_endpoint]:
            ctx = await strategy(client, headers)
            if ctx:
                self._detected_context_size = ctx
                return ctx

        # Fallback to model family defaults
        ctx = self._get_model_family_default()
        self._detected_context_size = ctx
        return ctx

    async def _try_props_endpoint(self, client, headers) -> Optional[int]:
        """Try llama.cpp /props endpoint."""
        try:
            base_url = self.api_endpoint.replace("/v1/chat/completions", "").replace("/chat/completions", "")
            response = await client.get(f"{base_url}/props", headers=headers, timeout=5.0)
            if response.status_code == 200:
                n_ctx = response.json().get("default_generation_settings", {}).get("n_ctx")
                if n_ctx and isinstance(n_ctx, int) and n_ctx > 0:
                    if self.log_callback:
                        self.log_callback("info", f"Detected context size from /props: {n_ctx}")
                    return n_ctx
        except Exception:
            pass
        return None

    async def _try_model_info_endpoint(self, client, headers) -> Optional[int]:
        """Try OpenAI /v1/models/{model} endpoint."""
        try:
            base_url = self.api_endpoint.replace("/v1/chat/completions", "").replace("/chat/completions", "")
            response = await client.get(f"{base_url}/v1/models/{self.model}", headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                for field in ["context_length", "max_model_len", "context_window", "max_context_length"]:
                    ctx = data.get(field)
                    if ctx and isinstance(ctx, int) and ctx > 0:
                        if self.log_callback:
                            self.log_callback("info", f"Detected context size: {ctx}")
                        return ctx
        except Exception:
            pass
        return None

    async def _try_models_list_endpoint(self, client, headers) -> Optional[int]:
        """Try /v1/models list and find matching model."""
        try:
            base_url = self.api_endpoint.replace("/v1/chat/completions", "").replace("/chat/completions", "")
            response = await client.get(f"{base_url}/v1/models", headers=headers, timeout=5.0)
            if response.status_code == 200:
                for model_info in response.json().get("data", []):
                    if model_info.get("id", "") == self.model:
                        for field in ["context_length", "max_model_len", "context_window"]:
                            ctx = model_info.get(field)
                            if ctx and isinstance(ctx, int) and ctx > 0:
                                return ctx
        except Exception:
            pass
        return None

    def _get_model_family_default(self) -> int:
        """Get default context size based on model family."""
        from src.config import MODEL_FAMILY_CONTEXT_DEFAULTS, DEFAULT_CONTEXT_FALLBACK

        model_lower = self.model.lower()
        for family, default_ctx in MODEL_FAMILY_CONTEXT_DEFAULTS.items():
            if family in model_lower:
                if self.log_callback:
                    self.log_callback("info", f"Using default for {family}: {default_ctx}")
                return default_ctx

        if self.log_callback:
            self.log_callback("warning", f"Using fallback: {DEFAULT_CONTEXT_FALLBACK}")
        return DEFAULT_CONTEXT_FALLBACK


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider with cost tracking and model validation"""

    # OpenRouter API endpoints
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"

    # Session cost tracking (class-level)
    _session_cost = 0.0
    _session_tokens = {"prompt": 0, "completion": 0}
    _cost_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    # Fallback text-only models (sorted by cost, cheapest first)
    FALLBACK_MODELS = [
        # === CHEAP MODELS ===
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
        "qwen/qwen-2.5-72b-instruct",
        "mistralai/mistral-small-24b-instruct-2501",
        # === MID-TIER MODELS ===
        "anthropic/claude-3-5-haiku-20241022",
        "openai/gpt-4o-mini",
        "google/gemini-1.5-pro",
        "deepseek/deepseek-chat",
        # === PREMIUM MODELS ===
        "anthropic/claude-sonnet-4",
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet-20241022",
    ]

    def __init__(self, api_key: str, model: str = "anthropic/claude-sonnet-4"):
        super().__init__(model)
        self.api_key = api_key

    @classmethod
    def get_session_cost(cls) -> tuple:
        """Get the current session cost and token usage.

        Returns:
            Tuple of (total_cost_usd, token_counts_dict)
        """
        return cls._session_cost, cls._session_tokens.copy()

    @classmethod
    def reset_session_cost(cls) -> None:
        """Reset the session cost tracking."""
        cls._session_cost = 0.0
        cls._session_tokens = {"prompt": 0, "completion": 0}

    @classmethod
    def set_cost_callback(cls, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Set a callback to receive cost updates after each API call.

        Args:
            callback: Function that receives a dict with:
                - request_cost: Cost of this specific request (USD)
                - session_cost: Cumulative session cost (USD)
                - prompt_tokens: Tokens used for this request's prompt
                - completion_tokens: Tokens generated in this request
                - total_prompt_tokens: Cumulative prompt tokens
                - total_completion_tokens: Cumulative completion tokens
        """
        cls._cost_callback = callback

    async def get_available_models(self, text_only: bool = True) -> list:
        """Fetch available OpenRouter models from API.

        Args:
            text_only: If True, filter out vision/multimodal models (default: True)

        Returns:
            List of model dicts with id, name, pricing info, sorted by price
        """
        if not self.api_key:
            return self._get_fallback_models()

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            client = await self._get_client()

            response = await client.get(
                self.MODELS_URL,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()

            models_data = response.json().get("data", [])
            filtered_models = []

            for model in models_data:
                model_id = model.get("id", "")
                architecture = model.get("architecture", {})
                modality = architecture.get("modality", "")

                # Skip free models (they don't work reliably)
                if ":free" in model_id:
                    continue

                # Filter logic for text-only models
                if text_only:
                    # Skip multimodal/vision models
                    if modality == "multimodal":
                        continue
                    # Skip models with vision keywords
                    model_id_lower = model_id.lower()
                    vision_keywords = ["vision", "vl", "-v-", "image"]
                    if any(kw in model_id_lower for kw in vision_keywords):
                        continue

                # Get pricing info
                pricing = model.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "0") or "0")
                completion_price = float(pricing.get("completion", "0") or "0")

                # Calculate cost per 1M tokens for display
                prompt_per_million = prompt_price * 1_000_000
                completion_per_million = completion_price * 1_000_000

                filtered_models.append({
                    "id": model_id,
                    "name": model.get("name", model_id),
                    "context_length": model.get("context_length", 0),
                    "pricing": {
                        "prompt": prompt_price,
                        "completion": completion_price,
                        "prompt_per_million": prompt_per_million,
                        "completion_per_million": completion_per_million,
                    },
                    "total_price": prompt_price + completion_price,  # For sorting
                })

            # Sort by total price (cheapest first)
            filtered_models.sort(key=lambda x: x["total_price"])

            if len(filtered_models) < 5:
                return self._get_fallback_models()

            return filtered_models

        except Exception as e:
            print(f"⚠️ Failed to fetch OpenRouter models: {e}")
            return self._get_fallback_models()

    def _get_fallback_models(self) -> list:
        """Return fallback models list when API fetch fails."""
        return [{"id": m, "name": m, "pricing": {"prompt": 0, "completion": 0}}
                for m in self.FALLBACK_MODELS]

    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using OpenRouter API with cost tracking.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/hydropix/TranslateBookWithLLM",
            "X-Title": "TranslateBookWithLLM",
        }

        # Build messages array
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Disable thinking/reasoning mode for models like DeepSeek, Qwen via OpenRouter
            # OpenRouter passes these parameters to the underlying model
            "thinking": False,
            "enable_thinking": False,
        }

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()

                result = response.json()

                if "choices" not in result or len(result["choices"]) == 0:
                    print(f"⚠️ OpenRouter: Unexpected response format: {result}")
                    return None

                response_text = result["choices"][0].get("message", {}).get("content", "")

                # Track cost from usage data
                usage = result.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                # OpenRouter returns cost in the response (in USD)
                if "cost" in result:
                    cost = float(result.get("cost", 0))
                else:
                    # Fallback estimate (using typical rates)
                    cost = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 1.50 / 1_000_000)

                # Update session tracking
                OpenRouterProvider._session_cost += cost
                OpenRouterProvider._session_tokens["prompt"] += prompt_tokens
                OpenRouterProvider._session_tokens["completion"] += completion_tokens

                # Log cost info
                print(f"💰 OpenRouter: {prompt_tokens}+{completion_tokens} tokens | "
                      f"Cost: ${cost:.6f} (session: ${OpenRouterProvider._session_cost:.4f})")

                # Call cost callback if set
                if OpenRouterProvider._cost_callback:
                    try:
                        OpenRouterProvider._cost_callback({
                            "request_cost": cost,
                            "session_cost": OpenRouterProvider._session_cost,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_prompt_tokens": OpenRouterProvider._session_tokens["prompt"],
                            "total_completion_tokens": OpenRouterProvider._session_tokens["completion"],
                        })
                    except Exception as cb_err:
                        print(f"⚠️ Cost callback error: {cb_err}")

                return LLMResponse(
                    content=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    context_used=prompt_tokens + completion_tokens,
                    context_limit=0,  # OpenRouter manages context internally
                    was_truncated=False
                )

            except httpx.TimeoutException as e:
                print(f"OpenRouter API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except httpx.HTTPStatusError as e:
                error_body = ""
                error_message = str(e)
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    error_body = e.response.text[:500]
                    error_message = f"{e} - {error_body}"

                # Parse OpenRouter specific error messages
                if e.response.status_code == 404:
                    print(f"❌ OpenRouter: Model '{self.model}' not found!")
                    print(f"   Check available models at https://openrouter.ai/models")
                    print(f"   Response: {error_body}")
                elif e.response.status_code == 401:
                    print(f"❌ OpenRouter: Invalid API key!")
                elif e.response.status_code == 402:
                    print(f"❌ OpenRouter: Insufficient credits!")
                else:
                    print(f"OpenRouter API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    print(f"Response details: Status {e.response.status_code}, Body: {error_body}...")

                # Detect context overflow errors
                context_overflow_keywords = ["context_length", "maximum context", "token limit",
                                              "too many tokens", "reduce the length", "max_tokens",
                                              "context window", "exceeds"]
                if any(keyword in error_message.lower() for keyword in context_overflow_keywords):
                    raise ContextOverflowError(f"OpenRouter context overflow: {error_message}")

                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except json.JSONDecodeError as e:
                print(f"OpenRouter API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None
            except Exception as e:
                print(f"OpenRouter API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                return None

        return None


class GeminiProvider(LLMProvider):
    """Google Gemini API provider"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        super().__init__(model)
        self.api_key = api_key
        self.api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    async def get_available_models(self) -> list[dict]:
        """Fetch available Gemini models from API, excluding thinking models"""
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        models_endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        
        client = await self._get_client()
        try:
            response = await client.get(
                models_endpoint,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model in data.get("models", []):
                model_name = model.get("name", "").replace("models/", "")
                
                # Skip experimental, latest, and vision models
                model_name_lower = model_name.lower()
                skip_keywords = ["experimental", "latest", "vision", "-exp-"]
                if any(keyword in model_name_lower for keyword in skip_keywords):
                    continue
                
                # Only include models that support generateContent
                supported_methods = model.get("supportedGenerationMethods", [])
                if "generateContent" in supported_methods:
                    models.append({
                        "name": model_name,
                        "displayName": model.get("displayName", model_name),
                        "description": model.get("description", ""),
                        "inputTokenLimit": model.get("inputTokenLimit", 0),
                        "outputTokenLimit": model.get("outputTokenLimit", 0)
                    })
                
            return models
            
        except Exception as e:
            print(f"Error fetching Gemini models: {e}")
            return []
    
    async def generate(self, prompt: str, timeout: int = REQUEST_TIMEOUT,
                      system_prompt: Optional[str] = None) -> Optional[LLMResponse]:
        """
        Generate text using Gemini API.

        Args:
            prompt: The user prompt (content to translate)
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt (role/instructions)

        Returns:
            LLMResponse with content and token usage info, or None if failed
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }

        # Add system instruction if provided (Gemini API supports systemInstruction field)
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{
                    "text": system_prompt
                }]
            }

        client = await self._get_client()
        for attempt in range(MAX_TRANSLATION_ATTEMPTS):
            try:
                response = await client.post(
                    self.api_endpoint,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()

                response_json = response.json()
                # Extract text from Gemini response structure
                response_text = ""
                if "candidates" in response_json and response_json["candidates"]:
                    content = response_json["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        response_text = parts[0].get("text", "")

                # Extract token usage if available
                usage_metadata = response_json.get("usageMetadata", {})
                prompt_tokens = usage_metadata.get("promptTokenCount", 0)
                completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

                return LLMResponse(
                    content=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    context_used=prompt_tokens + completion_tokens,
                    context_limit=0,  # Gemini manages context internally
                    was_truncated=False
                )

            except httpx.TimeoutException as e:
                    print(f"Gemini API Timeout (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except httpx.HTTPStatusError as e:
                    error_message = str(e)
                    error_body = ""
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        error_body = e.response.text[:500]
                        error_message = f"{e} - {error_body}"

                    print(f"Gemini API HTTP Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if error_body:
                        print(f"Response details: Status {e.response.status_code}, Body: {error_body[:200]}...")

                    # Detect context overflow errors (Gemini uses "RESOURCE_EXHAUSTED" or token limits)
                    context_overflow_keywords = ["resource_exhausted", "token limit", "input too long",
                                                  "maximum input", "context length", "too many tokens"]
                    if any(keyword in error_message.lower() for keyword in context_overflow_keywords):
                        raise ContextOverflowError(f"Gemini context overflow: {error_message}")

                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except json.JSONDecodeError as e:
                    print(f"Gemini API JSON Decode Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None
            except Exception as e:
                    print(f"Gemini API Unknown Error (attempt {attempt + 1}/{MAX_TRANSLATION_ATTEMPTS}): {e}")
                    if attempt < MAX_TRANSLATION_ATTEMPTS - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
                        continue
                    return None

        return None


def create_llm_provider(provider_type: str = "ollama", **kwargs) -> LLMProvider:
    """Factory function to create LLM providers"""
    # Auto-detect provider from model name if not explicitly set
    model = kwargs.get("model", DEFAULT_MODEL)
    if provider_type == "ollama" and model and model.startswith("gemini"):
        # Auto-switch to Gemini provider when Gemini model is detected
        # print(f"[INFO] Auto-switching to Gemini provider for model '{model}'")
        provider_type = "gemini"

    if provider_type.lower() == "ollama":
        return OllamaProvider(
            api_endpoint=kwargs.get("api_endpoint", API_ENDPOINT),
            model=kwargs.get("model", DEFAULT_MODEL),
            context_window=kwargs.get("context_window") or OLLAMA_NUM_CTX,
            log_callback=kwargs.get("log_callback")
        )
    elif provider_type.lower() == "openai":
        return OpenAICompatibleProvider(
            api_endpoint=kwargs.get("api_endpoint"),
            model=kwargs.get("model", DEFAULT_MODEL),
            api_key=kwargs.get("api_key"),
            context_window=kwargs.get("context_window") or OLLAMA_NUM_CTX,
            log_callback=kwargs.get("log_callback")
        )
    elif provider_type.lower() == "gemini":
        api_key = kwargs.get("api_key")
        if not api_key:
            # Try to get from environment
            import os
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini provider requires an API key. Set GEMINI_API_KEY environment variable or pass api_key parameter.")
        return GeminiProvider(
            api_key=api_key,
            model=kwargs.get("model", "gemini-2.0-flash")
        )
    elif provider_type.lower() == "openrouter":
        api_key = kwargs.get("api_key")
        if not api_key:
            # Try to get from environment
            import os
            api_key = os.getenv("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
            if not api_key:
                raise ValueError("OpenRouter provider requires an API key. Set OPENROUTER_API_KEY environment variable or pass api_key parameter.")
        return OpenRouterProvider(
            api_key=api_key,
            model=kwargs.get("model", OPENROUTER_MODEL)
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")