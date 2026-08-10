"""Prompt loading utility.

Prompts are never hardcoded inside agent Python files — they live as
`.md` files under `app/prompts/<agent>/<name>.md` and are rendered here
using `string.Template` (`$variable` syntax, chosen specifically because
prompt bodies contain literal JSON with `{}` braces that would collide
with `str.format`).
"""

from __future__ import annotations

import functools
from pathlib import Path
from string import Template

_PROMPTS_ROOT = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=64)
def _read_template(relative_path: str) -> Template:
    path = _PROMPTS_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {relative_path}")
    return Template(path.read_text(encoding="utf-8"))


def render_prompt(relative_path: str, /, **variables: object) -> str:
    """Load and render a prompt template.

    Args:
        relative_path: e.g. "supervisor/request_analysis.md"
        variables: substituted using `$name` placeholders.
    """

    template = _read_template(relative_path)
    return template.safe_substitute(**{k: _stringify(v) for k, v in variables.items()})


def _stringify(value: object) -> str:
    if value is None:
        return "(none provided)"
    if isinstance(value, (list, tuple)):
        return "\n".join(f"- {item}" for item in value) if value else "(none)"
    return str(value)
