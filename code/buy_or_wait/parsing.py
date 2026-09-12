"""Strict conversion helpers for raw CSV strings."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class ParseError(ValueError):
    """A CSV value does not conform to the challenge schema."""


def optional_text(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value


def required_text(value: str | None, field: str) -> str:
    result = optional_text(value)
    if result is None:
        raise ParseError(f"{field} is required")
    return result


def optional_decimal(value: str | None, field: str) -> Decimal | None:
    text = optional_text(value)
    if text is None:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ParseError(f"{field} must be a decimal, got {value!r}") from exc


def required_decimal(value: str | None, field: str) -> Decimal:
    result = optional_decimal(value, field)
    if result is None:
        raise ParseError(f"{field} is required")
    return result


def optional_date(value: str | None, field: str) -> date | None:
    text = optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ParseError(f"{field} must be YYYY-MM-DD, got {value!r}") from exc


def required_date(value: str | None, field: str) -> date:
    result = optional_date(value, field)
    if result is None:
        raise ParseError(f"{field} is required")
    return result


def required_datetime(value: str | None, field: str) -> datetime:
    text = required_text(value, field)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ParseError(f"{field} must be ISO-8601, got {value!r}") from exc


def optional_int(value: str | None, field: str) -> int | None:
    text = optional_text(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ParseError(f"{field} must be an integer, got {value!r}") from exc


def required_int(value: str | None, field: str) -> int:
    result = optional_int(value, field)
    if result is None:
        raise ParseError(f"{field} is required")
    return result


def required_bool(value: str | None, field: str) -> bool:
    text = required_text(value, field)
    if text == "true":
        return True
    if text == "false":
        return False
    raise ParseError(f"{field} must be true or false, got {value!r}")


def pipe_list(value: str | None) -> tuple[str, ...]:
    text = optional_text(value)
    if text is None:
        return ()
    return tuple(part.strip() for part in text.split("|") if part.strip())
