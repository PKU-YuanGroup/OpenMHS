"""Shared paths and helpers for the data-contract tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SDK = HERE.parents[1]                 # MHS/sdk
MHS_ROOT = SDK.parent                 # MHS
SCHEMA_DIR = MHS_ROOT / "schema"
SPEC_DIR = MHS_ROOT / "spec"
EXAMPLES = SCHEMA_DIR / "examples"
VALID = EXAMPLES / "valid"
INVALID = EXAMPLES / "invalid"
CAPABILITIES = SPEC_DIR / "capabilities.json"
ERRORS = SPEC_DIR / "errors.json"
TOOLS = SDK / "tools"


def load_json(path: Path) -> Any:
    """Return the parsed JSON document at ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_tool(name: str):
    """Import ``MHS/sdk/tools/<name>.py`` as a module."""
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_openmhs_tool_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def schema_for(path: Path) -> str:
    """Schema file named by an example's ``<schema stem>.<slug>.json`` file name."""
    return path.name.split(".", 1)[0] + ".schema.json"


def pointer_tokens(pointer: str) -> list[str]:
    """Split an RFC 6901 JSON pointer into unescaped tokens."""
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer!r}")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def escape_token(token: Any) -> str:
    """Escape one JSON pointer token."""
    return str(token).replace("~", "~0").replace("/", "~1")


def pointer(*tokens: Any) -> str:
    """Build a JSON pointer from raw tokens."""
    return "".join("/" + escape_token(token) for token in tokens)


def error_tokens(error: str) -> list[str] | None:
    """Return the pointer tokens of a validator error string (``$.a[0]["b"]: ...``).

    A property-name error (``... (property name): ...``) points at the key
    itself.  Returns None when the string does not start with a path.
    """
    if not error.startswith("$"):
        return None
    tokens: list[str] = []
    decoder = json.JSONDecoder()
    index = 1
    while index < len(error):
        char = error[index]
        if char == ".":
            end = index + 1
            while end < len(error) and (error[end].isalnum() or error[end] == "_"):
                end += 1
            tokens.append(error[index + 1:end])
            index = end
        elif char == "[" and error[index + 1:index + 2] == '"':
            value, end = decoder.raw_decode(error, index + 1)
            tokens.append(str(value))
            index = end + 1          # skip the closing bracket
        elif char == "[":
            end = error.index("]", index)
            tokens.append(error[index + 1:end])
            index = end + 1
        else:
            break
    return tokens
