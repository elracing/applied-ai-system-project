"""Input validation and prompt sanitization for PawPal+."""
from __future__ import annotations

import re

_SAFE_NAME = re.compile(r"^[\w\s\-',.]+$")

_PROMPT_INJECTION = re.compile(
    r"(ignore previous|system prompt|you are now|disregard all|jailbreak"
    r"|---+|\[INST\]|<\|im_start\||forget your instructions)",
    re.IGNORECASE,
)

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_CATEGORIES = {"walk", "feed", "meds", "enrichment", "grooming", "general"}


class ValidationError(ValueError):
    pass


# ── User-facing input validators ─────────────────────────────────────────────

def validate_name(name: str, field: str = "Name") -> str:
    name = name.strip()
    if not name:
        raise ValidationError(f"{field} cannot be empty.")
    if len(name) > 50:
        raise ValidationError(f"{field} must be 50 characters or fewer.")
    if not _SAFE_NAME.match(name):
        raise ValidationError(
            f"{field} contains invalid characters. "
            "Use letters, numbers, spaces, hyphens, or apostrophes."
        )
    return name


def validate_task_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise ValidationError("Task title cannot be empty.")
    if len(title) > 100:
        raise ValidationError("Task title must be 100 characters or fewer.")
    return title


def validate_available_minutes(minutes: int) -> int:
    if minutes < 10:
        raise ValidationError("Available minutes must be at least 10.")
    if minutes > 1440:
        raise ValidationError("Available minutes cannot exceed 1440 (24 hours).")
    return int(minutes)


def validate_task_duration(duration: int) -> int:
    if duration < 1:
        raise ValidationError("Duration must be at least 1 minute.")
    if duration > 480:
        raise ValidationError("Duration cannot exceed 480 minutes (8 hours).")
    return int(duration)


# ── Prompt sanitization (prevent injection via pet name / breed fields) ───────

def sanitize_for_prompt(text: str, max_length: int = 80) -> str:
    """Strip control characters, cap length, and reject injection attempts."""
    # Remove non-printable control characters (keep normal whitespace)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()[:max_length]
    if _PROMPT_INJECTION.search(text):
        raise ValidationError(
            "Input contains disallowed content and cannot be used in a suggestion."
        )
    return text


# ── LLM output validator ──────────────────────────────────────────────────────

def validate_llm_task(td: object) -> dict:
    """Validate and normalise a single task dict returned by the LLM.

    Raises ValidationError if required fields are missing or out of range.
    Silently coerces minor issues (e.g. unknown category → 'general').
    """
    if not isinstance(td, dict):
        raise ValidationError("LLM returned a non-dict task entry.")

    title = str(td.get("title", "")).strip()[:100]
    if not title:
        raise ValidationError("LLM task is missing a title.")

    try:
        duration = int(td["duration_minutes"])
    except (KeyError, TypeError, ValueError):
        raise ValidationError(f"LLM task '{title}' has a missing or non-integer duration.")
    if not 1 <= duration <= 480:
        raise ValidationError(
            f"LLM task '{title}' has duration {duration} outside allowed range (1–480 min)."
        )

    priority = str(td.get("priority", "")).strip().lower()
    if priority not in VALID_PRIORITIES:
        raise ValidationError(
            f"LLM task '{title}' has invalid priority '{priority}'. "
            f"Expected one of: {', '.join(sorted(VALID_PRIORITIES))}."
        )

    category = str(td.get("category", "general")).strip().lower()
    if category not in VALID_CATEGORIES:
        category = "general"

    return {
        "title": title,
        "duration_minutes": duration,
        "priority": priority,
        "category": category,
        "required": bool(td.get("required", True)),
    }
