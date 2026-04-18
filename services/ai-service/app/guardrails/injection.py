import re


class InjectionDetectedError(ValueError):
    pass


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"system(owa)?\s+rola\s*:",
    r"system\s*:",
    r"</?(system|context|task|output_schema)>",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\s+if\b",
    r"forget\s+all\s+previous",
    r"\bDAN\b",
    r"prompt\s+injection",
    r"jailbreak",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_injection(text: str) -> None:
    for pattern in _compiled:
        if pattern.search(text):
            raise InjectionDetectedError(f"Potential prompt injection detected in input.")
