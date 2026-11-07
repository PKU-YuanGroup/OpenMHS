"""Explicit, bounded JSON checkpoints; no native-state discovery or codec coercion."""
from __future__ import annotations

from dataclasses import dataclass
import json
import inspect
import math
import re
from typing import Any, Mapping

from .. import canonical

MAX_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_NODES = 65_536


def bounded_json(value: Any, max_bytes: int) -> Any:
    """Validate builtin JSON types before a bounded encoding/copy.

    Native arrays, tuples, object hooks and non-string mapping keys are deliberately
    excluded. A backend needing them must expose an explicit lossless JSON codec.
    The native getter's own allocation is outside this post-return bound.
    """
    active: set[int] = set()
    nodes = 0
    lower_bytes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes, lower_bytes
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError("checkpoint exceeds the JSON node/depth bound")
        kind = type(item)
        if item is None or kind is bool:
            lower_bytes += 4
        elif kind is int:
            if abs(item) > 2**53 - 1:
                raise ValueError("checkpoint integers must be exactly representable; use decimal strings above 2**53-1")
            lower_bytes += 1
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError("checkpoint contains a non-finite number")
            lower_bytes += 1
        elif kind is str:
            # UTF-8 may expand, but this prevents encoding unbounded input first.
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                raise ValueError("checkpoint contains a lone Unicode surrogate")
            lower_bytes += len(item) + 2
        elif kind in (list, dict):
            if id(item) in active:
                raise ValueError("checkpoint contains a cycle")
            active.add(id(item))
            lower_bytes += 2
            try:
                if kind is dict:
                    for key, child in item.items():
                        if type(key) is not str:
                            raise ValueError("checkpoint object keys must be strings")
                        visit(key, depth + 1)
                        visit(child, depth + 1)
                else:
                    for child in item:
                        visit(child, depth + 1)
            finally:
                active.remove(id(item))
        else:
            raise ValueError(f"checkpoint requires builtin JSON values, got {kind.__name__}")
        if lower_bytes > max_bytes:
            raise ValueError("checkpoint exceeds max_bytes")

    visit(value, 0)
    text = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    if len(text.encode("ascii")) > max_bytes:
        raise ValueError("checkpoint exceeds max_bytes")
    return json.loads(text)


def checkpoint_opt_out(config: Mapping[str, Any]) -> str:
    """Validate an explicit opt-out ``{"profile": "none", "reason": "..."}``; return the reason.

    The opt-out records, per backend, that protocol snapshots are deliberately
    unavailable (for example because the native state API omits task, RNG or
    wrapper state). It configures nothing native and claims nothing.
    """
    if not isinstance(config, Mapping) or set(config) - {"profile", "reason"} or config.get("profile") != "none":
        raise ValueError("a checkpoint opt-out is exactly {'profile': 'none', 'reason': '...'}")
    reason = config.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 300:
        raise ValueError("a checkpoint opt-out needs a reason of 1..300 characters")
    return reason.strip()


@dataclass(frozen=True)
class JsonCheckpoint:
    getter: str
    setter: str
    max_bytes: int = 262_144

    @classmethod
    def resolve(cls, config: Mapping[str, Any]) -> JsonCheckpoint:
        if not isinstance(config, Mapping) or set(config) - {"profile", "getter", "setter", "max_bytes"}:
            raise ValueError("checkpoint requires profile/getter/setter and optional max_bytes")
        if config.get("profile") != "json_state_v1":
            raise ValueError("checkpoint profile must be json_state_v1")
        names = [config.get("getter"), config.get("setter")]
        for name in names:
            if (not isinstance(name, str) or len(name) > 200
                    or not all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", part) for part in name.split("."))):
                raise ValueError("checkpoint getter/setter must be explicit public attribute paths")
        limit = config.get("max_bytes", 262_144)
        if type(limit) is not int or not 1024 <= limit <= MAX_BYTES:
            raise ValueError(f"checkpoint max_bytes must be an integer from 1024 to {MAX_BYTES}")
        return cls(names[0], names[1], limit)

    def descriptor(self) -> dict[str, Any]:
        return {"profile": "json_state_v1", "getter": self.getter,
                "setter": self.setter, "max_bytes": self.max_bytes}

    @property
    def digest(self) -> str:
        return canonical.digest(self.descriptor())

    def access(self, env: Any) -> tuple[Any, Any]:
        result = []
        for path in (self.getter, self.setter):
            value = env
            for part in path.split("."):
                value = getattr(value, part)
            if (inspect.iscoroutinefunction(value) or inspect.iscoroutinefunction(getattr(value, "__call__", None))
                    or inspect.isasyncgenfunction(value)
                    or inspect.isgeneratorfunction(value)):
                raise ValueError("checkpoint methods must complete synchronously")
            if not callable(value):
                raise ValueError(f"checkpoint method {path!r} is not callable")
            result.append(value)
        return tuple(result)
