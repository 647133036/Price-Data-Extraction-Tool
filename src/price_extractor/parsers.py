from __future__ import annotations

import re
from typing import Any


def first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "yes", "in stock", "available"}:
        return True
    if text in {"false", "no", "out of stock", "unavailable"}:
        return False
    return None


def walk(node: Any, *keys: str) -> Any:
    current = node
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def collect_dicts(node: Any, wanted_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            if any(key in value for key in wanted_keys):
                found.append(value)
            for child in value.values():
                _walk(child)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(node)
    return found


def join_url(base: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def package_size(*values: Any) -> str | None:
    raw = first(*values)
    if raw is None:
        return None
    return str(raw).strip() or None
