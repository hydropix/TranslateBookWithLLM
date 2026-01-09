"""
LLM logging utilities for debugging and transparency

Provides utilities to log LLM interactions (prompts and responses)
when DEBUG_MODE is enabled.
"""
import os
from typing import Optional
from src.config import DEBUG_MODE


def log_llm_interaction(
    system_prompt: Optional[str],
    user_prompt: str,
    raw_response: str,
    interaction_type: str = "translation",
    prefix: str = ""
):
    """
    Log full LLM interaction details when DEBUG_MODE is enabled.

    This provides complete transparency for debugging LLM behavior,
    showing exactly what is sent and received.

    Args:
        system_prompt: The system prompt (role/instructions)
        user_prompt: The user prompt (content to process)
        raw_response: Raw LLM response before extraction
        interaction_type: Type of interaction (e.g., "translation", "correction", "refinement")
        prefix: Optional prefix for log messages (e.g., "Correction attempt 1")
    """
    if not DEBUG_MODE:
        return

    # ANSI color codes
    YELLOW = '\033[93m'
    ORANGE = '\033[38;5;214m'  # Orange clair - INPUT vers LLM
    GREEN = '\033[92m'         # Vert clair - OUTPUT du LLM
    GRAY = '\033[90m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    # Check if running on Windows without color support
    if os.name == 'nt' and os.environ.get('NO_COLOR'):
        YELLOW = ORANGE = GREEN = GRAY = ENDC = BOLD = ''

    separator = "=" * 80
    prefix_str = f"[{prefix}] " if prefix else ""

    print(f"\n{YELLOW}{BOLD}{separator}{ENDC}")
    print(f"{YELLOW}{BOLD}🔍 DEBUG: {prefix_str}LLM Interaction - {interaction_type.upper()}{ENDC}")
    print(f"{YELLOW}{BOLD}{separator}{ENDC}\n")

    # System Prompt
    if system_prompt:
        print(f"{ORANGE}{BOLD}📤 System Prompt:{ENDC}")
        print(f"{GRAY}{'-' * 80}{ENDC}")
        print(f"{ORANGE}{system_prompt}{ENDC}")
        print(f"{GRAY}{'-' * 80}{ENDC}\n")

    # User Prompt
    print(f"{ORANGE}{BOLD}📤 User Prompt:{ENDC}")
    print(f"{GRAY}{'-' * 80}{ENDC}")
    print(f"{ORANGE}{user_prompt}{ENDC}")
    print(f"{GRAY}{'-' * 80}{ENDC}\n")

    # Raw Response
    print(f"{GREEN}{BOLD}📥 Raw Response:{ENDC}")
    print(f"{GRAY}{'-' * 80}{ENDC}")
    print(f"{GREEN}{raw_response}{ENDC}")
    print(f"{GRAY}{'-' * 80}{ENDC}\n")

    print(f"{YELLOW}{BOLD}{separator}{ENDC}\n")


def should_log_llm_details() -> bool:
    """
    Check if LLM detailed logging should be enabled.

    Returns:
        True if DEBUG_MODE is enabled, False otherwise
    """
    return DEBUG_MODE
