from __future__ import annotations

from typing import Any


SUSPICIOUS_SEQUENCES = (
    "Ã",
    "Å",
    "Ä",
    "â€",
    "â€“",
    "â€”",
    "â€ž",
    "â€ś",
    "â€™",
)


def fix_mojibake(value: str | None) -> str | None:
    if value is None:
        return None

    if not any(seq in value for seq in SUSPICIOUS_SEQUENCES):
        return value

    for source_encoding in ("latin-1", "cp1250", "cp1252"):
        try:
            repaired = value.encode(source_encoding).decode("utf-8")
            if repaired and repaired != value:
                return repaired
        except UnicodeError:
            continue

    return value


def normalize_payload(value: Any) -> Any:
    if isinstance(value, str):
        return fix_mojibake(value)

    if isinstance(value, list):
        return [normalize_payload(item) for item in value]

    if isinstance(value, dict):
        return {key: normalize_payload(item) for key, item in value.items()}

    return value