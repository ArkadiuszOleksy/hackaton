import json
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class SchemaValidationError(ValueError):
    pass


async def validate_llm_output(
    raw: str,
    schema: type[T],
    retry_fn: Callable[[str], Awaitable[str]],
) -> T:
    def _clean_json(s: str) -> str:
        s = s.strip()
        if s.startswith("```"):
            # Remove ```json or ``` at start and ``` at end
            s = re.sub(r"^```(?:json)?\n?", "", s)
            s = re.sub(r"\n?```$", "", s)
        return s.strip()

    # Step 1: JSON parse
    try:
        data = json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        raw = await retry_fn("Reply with VALID JSON only. Do not include any text outside the JSON object.")
        try:
            data = json.loads(_clean_json(raw))
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(f"LLM returned invalid JSON after retry: {raw[:200]}") from exc

    # Step 2: Pydantic validate
    try:
        return schema.model_validate(data)
    except ValidationError:
        raw = await retry_fn(
            "Your previous response did not match the required JSON schema. "
            "Reply ONLY with a valid JSON object matching the schema exactly."
        )
        try:
            return schema.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise SchemaValidationError(f"Schema validation failed after retry: {exc}") from exc
