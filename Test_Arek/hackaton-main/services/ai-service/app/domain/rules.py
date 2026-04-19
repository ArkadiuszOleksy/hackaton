import hashlib

DISCLAIMER_TEXT = "To nie jest porada prawna. Skonsultuj się z prawnikiem."

ENDPOINT_TEMPERATURES: dict[str, float] = {
    "/qa": 0.1,
    "/analyze/impact": 0.1,
    "/analyze/patent-check": 0.1,
    "/analyze/trends": 0.5,
    "/summarize": 0.3,
}


def ensure_disclaimer(text: str) -> str:
    if DISCLAIMER_TEXT not in text:
        return text + "\n" + DISCLAIMER_TEXT
    return text


def normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.lower().split())


def compute_cache_key(endpoint: str, prompt_full: str, prompt_version: str) -> str:
    digest = hashlib.sha256(normalize_prompt(prompt_full).encode()).hexdigest()
    ep = endpoint.lstrip("/").replace("/", ":")
    return f"ai:{ep}:{digest}:{prompt_version}"


def validate_top_k(top_k: int, max_k: int = 15) -> int:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if top_k > max_k:
        raise ValueError(f"top_k cannot exceed {max_k}")
    return top_k
