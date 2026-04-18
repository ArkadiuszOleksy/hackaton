from __future__ import annotations

import re


ARTICLE_HEADER_RE = re.compile(r"(Art\.\s*\d+[A-Za-z]?)\.?", re.IGNORECASE)


def extract_articles_from_text(full_text: str | None) -> list[dict[str, str]]:
    if not full_text:
        return []

    text = full_text.strip()
    if not text:
        return []

    matches = list(ARTICLE_HEADER_RE.finditer(text))
    if not matches:
        return []

    articles: list[dict[str, str]] = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

        chunk = text[start:end].strip()
        article_number = match.group(1).strip()

        body_start = match.end()
        body = text[body_start:end].strip(" \n\t.:;-")
        body = re.sub(r"\s+", " ", body).strip()

        if not body:
            body = chunk

        articles.append(
            {
                "article_number": article_number,
                "text": body,
            }
        )

    return articles