from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx

from app.text_utils import fix_mojibake, normalize_payload


class SejmEliClient:
    def __init__(self, base_url: str = "https://api.sejm.gov.pl/eli", timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_acts_in_year(self, publisher: str, year: int) -> list[dict[str, Any]]:
        url = f"{self.base_url}/acts/{publisher}/{year}"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = normalize_payload(response.json())

        if isinstance(payload, dict) and "items" in payload:
            return payload["items"]

        if isinstance(payload, list):
            return payload

        return []

    def get_act_details(self, publisher: str, year: int, position: int) -> dict[str, Any]:
        url = f"{self.base_url}/acts/{publisher}/{year}/{position}"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()

        return normalize_payload(payload)

    def get_act_html_text(self, publisher: str, year: int, position: int) -> str | None:
        url = f"{self.base_url}/acts/{publisher}/{year}/{position}/text.html"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()

            raw = response.content
            candidates: list[str] = []

            try:
                candidates.append(raw.decode("utf-8"))
            except UnicodeError:
                pass

            try:
                candidates.append(raw.decode("cp1250"))
            except UnicodeError:
                pass

            try:
                candidates.append(raw.decode("cp1252"))
            except UnicodeError:
                pass

            candidates.append(response.text)

        best_text = ""
        for candidate in candidates:
            cleaned = self._html_to_text(fix_mojibake(candidate) or "")
            if len(cleaned) > len(best_text):
                best_text = cleaned

        return best_text or None

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?is)<br\s*/?>", "\n", text)
        text = re.sub(r"(?is)</p>|</div>|</li>|</tr>|</h\d>", "\n", text)
        text = re.sub(r"(?is)<.*?>", " ", text)
        text = unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()