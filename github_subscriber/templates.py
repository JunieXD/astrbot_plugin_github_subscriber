from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render_template(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = variables.get(key, "")
        return "" if value is None else str(value)

    return _PLACEHOLDER.sub(replace, template)


def truncate_text(value: str | None, max_chars: int) -> str:
    text = value or ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
