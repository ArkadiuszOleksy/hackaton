import os
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

_jinja_env = Environment(
    loader=FileSystemLoader(os.path.abspath(_PROMPTS_DIR)),
    autoescape=select_autoescape([]),
    keep_trailing_newline=True,
)
_jinja_env.globals["enumerate"] = enumerate


def build_messages(
    template_name: str,
    context_articles: list[dict[str, Any]],
    user_input: str,
    extra: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    template = _jinja_env.get_template(template_name)
    rendered = template.render(
        articles=context_articles,
        user_input=user_input,
        **(extra or {}),
    )

    # Split on ---USER--- delimiter; everything before is system, after is user
    if "---USER---" in rendered:
        parts = rendered.split("---USER---", 1)
        return [
            {"role": "system", "content": parts[0].strip()},
            {"role": "user", "content": parts[1].strip()},
        ]

    return [
        {"role": "system", "content": rendered.strip()},
        {"role": "user", "content": user_input},
    ]
