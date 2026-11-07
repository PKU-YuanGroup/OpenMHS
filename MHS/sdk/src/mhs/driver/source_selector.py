"""Source-only Python selectors. These values are never runtime import targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


LEGACY_SELECTOR_PATTERN = r"[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*"
SOURCE_PATH_PATTERN = r"(?!/)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*//)[A-Za-z0-9._@+ /-]+(?<!/)"
EXPLICIT_SELECTOR_PATTERN = (
    r"pyfile:(?!/)(?!\.{1,2}/)(?!.*\/\.{1,2}/)(?!.*//)"
    r"[A-Za-z0-9._@+ /-]+\.py#(?:\*|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)
SELECTOR_PATTERN = rf"(?:{LEGACY_SELECTOR_PATTERN}|{EXPLICIT_SELECTOR_PATTERN})"


@dataclass(frozen=True)
class SourceSelector:
    value: str
    kind: str
    name: str
    path: str | None = None

    @property
    def explicit(self) -> bool:
        return self.path is not None


def source_path(value: Any) -> str | None:
    """A source-evidence path, allowing spaces without relaxing package paths."""
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        return None
    if re.fullmatch(SOURCE_PATH_PATTERN, value) is None:
        return None
    if any(part in ("", ".", "..") for part in value.split("/")):
        return None
    return value


def parse_selector(value: Any) -> SourceSelector | None:
    if not isinstance(value, str):
        return None
    if value.startswith("pyfile:"):
        path, sep, name = value[7:].partition("#")
        if not sep or source_path(path) is None or not path.endswith(".py"):
            return None
        if name != "*" and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", name) is None:
            return None
        return SourceSelector(value, "module" if name == "*" else "class", name, path)
    if re.fullmatch(LEGACY_SELECTOR_PATTERN, value):
        return SourceSelector(value, "class", value.partition(":")[2])
    return None


def entry_shape(symbol: Any, file: Any, line: Any) -> bool:
    """Validate entry syntax; the pinned AST separately proves identity and line."""
    selector = parse_selector(symbol)
    return bool(selector is not None and source_path(file) is not None
                and isinstance(line, int) and not isinstance(line, bool) and line >= 1
                and (not selector.explicit or selector.path == file)
                and (selector.kind != "module" or line == 1))


# pybind11 binding-source selectors (mhs.driver.pybind_surface reads them; G7)
_PYBIND_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")


@dataclass(frozen=True)
class PybindSelector:
    value: str
    path: str
    #: the C++ namespace of binder's ``M("...")`` getter, ``""`` for a selector without a scope
    scope: str
    name: str


def parse_pybind_selector(value: Any) -> PybindSelector | None:
    """``PybindSelector`` for ``pybind:<path>#<scope>.<Name>`` (``None`` for anything else)."""
    if not isinstance(value, str) or not value.startswith("pybind:"):
        return None
    path, sep, dotted = value[len("pybind:"):].partition("#")
    if (not sep or source_path(path) is None or not path.endswith((".cpp", ".cc", ".cxx"))
            or not _PYBIND_NAME.match(dotted)):
        return None
    *scope, name = dotted.split(".")
    return PybindSelector(value, path, "::".join(scope), name)
