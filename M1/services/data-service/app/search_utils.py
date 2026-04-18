from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    value = value.lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def build_token_variants(token: str) -> list[str]:
    token = normalize_text(token)
    if not token:
        return []

    variants = {token}

    if len(token) >= 5:
        variants.add(token[:-1])
    if len(token) >= 6:
        variants.add(token[:-2])
    if len(token) >= 7:
        variants.add(token[:5])
        variants.add(token[:6])

    return [v for v in variants if v]


def score_text_match(query: str, text: str) -> int:
    normalized_text = normalize_text(text)
    if not normalized_text:
        return 0

    words = normalized_text.split()
    total_score = 0

    for raw_token in query.split():
        matched = False

        for variant in build_token_variants(raw_token):
            if variant in normalized_text:
                total_score += 2
                matched = True
                break

            if len(variant) >= 4 and any(word.startswith(variant) for word in words):
                total_score += 1
                matched = True
                break

        if not matched:
            total_score += 0

    return total_score