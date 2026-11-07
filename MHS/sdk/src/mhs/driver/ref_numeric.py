"""Bounded, source-only numeric evidence for local ones-based Box bounds.

This is not Python evaluation or general constant propagation. A citation must
contain the complete straight-line definitions used by its bounds. Shape names
are opaque: this reader proves numeric values, never array widths or runtime
compatibility. The conventional np/numpy and Box spellings are lexical evidence,
as in the existing citation reader; no module is imported to resolve them.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import struct
import textwrap

MAX_TEXT = 16384
MAX_NODES = 512
MAX_STATEMENTS = 64
_ROOTS = {"np", "numpy", "gym", "gymnasium", "spaces", "Box", "self"}
_ONES = {"np.ones", "numpy.ones"}
_BOX = {"Box", "spaces.Box", "gym.spaces.Box", "gymnasium.spaces.Box"}


class _Unsupported(Exception):
    pass


@dataclass(frozen=True)
class _Value:
    number: float
    array: bool = False
    dtype: int = 64
    scaled: bool = False


def _path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _path(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _key(node: ast.AST) -> str | None:
    name = _path(node)
    if name and ("." not in name or name.startswith("self.") and name.count(".") == 1):
        if name not in _ROOTS and not any(part.startswith("__") for part in name.split(".")):
            return name
    return None


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _Unsupported
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise _Unsupported from None
    if not math.isfinite(number):
        raise _Unsupported
    return number


def _exact(number: float, dtype: int) -> None:
    # Do not claim a mathematical scale if an explicit/default float32 bound
    # would round it, overflow it, or use unsigned/bool negation semantics.
    if dtype == 32:
        try:
            if struct.unpack("!f", struct.pack("!f", number))[0] != number:
                raise _Unsupported
        except (OverflowError, struct.error):
            raise _Unsupported from None


def _dtype(node: ast.AST | None, default: int) -> int:
    if node is None:
        return default
    name = _path(node)
    if name in ("np.float32", "numpy.float32"):
        return 32
    if name in ("np.float64", "numpy.float64"):
        return 64
    raise _Unsupported


class _Reader:
    def __init__(self):
        self.values: dict[str, _Value | None] = {}
        self.shapes: set[str] = set()
        self.unresolved_assignments: set[str] = set()
        self.found: list[float] = []

    def shape(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            if type(node.value) is not int or node.value <= 0:
                raise _Unsupported
            return
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            for item in node.elts:
                if isinstance(item, (ast.List, ast.Tuple)):
                    raise _Unsupported
                self.shape(item)
            return
        name = _key(node)
        if name:
            value = self.values.get(name)
            if value is not None and (value.array or value.number <= 0 or not value.number.is_integer()):
                raise _Unsupported
            self.shapes.add(name)
            return  # symbolic dimensions are deliberately not resolved
        if isinstance(node, ast.Attribute) and node.attr == "shape":
            value = self.values.get(_key(node.value) or "")
            if value is not None and value.array:
                return
        raise _Unsupported

    def expression(self, node: ast.AST) -> _Value | None:
        if isinstance(node, ast.Constant):
            return _Value(_finite(node.value))
        name = _key(node)
        if name:
            return self.values.get(name)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self.expression(node.operand)
            if value is None:
                return None
            number = -value.number if isinstance(node.op, ast.USub) else value.number
            return _Value(number, value.array, value.dtype, value.scaled)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            left, right = self.expression(node.left), self.expression(node.right)
            if left is None or right is None:
                return None
            if left.array == right.array:
                raise _Unsupported  # no array products or scalar arithmetic
            array, scalar = (left, right) if left.array else (right, left)
            if array.scaled:
                raise _Unsupported
            number = _finite(array.number * scalar.number)
            _exact(number, array.dtype)
            return _Value(number, True, array.dtype, True)
        if isinstance(node, ast.Call) and _path(node.func) in _ONES:
            keywords = self.keywords(node, {"shape", "dtype"})
            if len(node.args) == 1 and "shape" not in keywords:
                shape = node.args[0]
            elif not node.args and "shape" in keywords:
                shape = keywords["shape"]
            else:
                raise _Unsupported
            self.shape(shape)
            return _Value(1.0, True, _dtype(keywords.get("dtype"), 64))
        raise _Unsupported

    @staticmethod
    def keywords(node: ast.Call, allowed: set[str]) -> dict[str, ast.AST]:
        result = {}
        for item in node.keywords:
            if item.arg not in allowed or item.arg in result:
                raise _Unsupported
            result[item.arg] = item.value
        if any(isinstance(item, ast.Starred) for item in node.args):
            raise _Unsupported
        return result

    def box(self, node: ast.Call) -> None:
        keywords = self.keywords(node, {"low", "high", "shape", "dtype"})
        if len(node.args) == 2 and not (set(keywords) & {"low", "high"}):
            low_node, high_node = node.args
        elif not node.args and {"low", "high"} <= set(keywords):
            low_node, high_node = keywords["low"], keywords["high"]
        else:
            raise _Unsupported
        low, high = self.expression(low_node), self.expression(high_node)
        dtype = _dtype(keywords.get("dtype"), 32)
        if "shape" in keywords:
            self.shape(keywords["shape"])
        # An intervening observation Box may have bounds defined outside this
        # citation. It contributes no values and cannot infer those definitions.
        if low is None or high is None or not (low.array or high.array):
            return
        if low.number > high.number:
            raise _Unsupported
        for value in (low, high):
            _exact(value.number, dtype)
        self.found.extend((low.number, high.number))

    def statement(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return  # a standalone docstring has no runtime effect
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            key = _key(node.targets[0])
            if key is None or key in self.values or key in self.shapes:
                raise _Unsupported
            value = node.value
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and _path(node.value.func) in _BOX:
            self.box(node.value)
            return
        else:
            raise _Unsupported  # control flow, scope, mutation, imports, unpacking
        if isinstance(value, ast.Call) and _path(value.func) in _BOX:
            self.box(value)
            self.values[key] = None
            return
        # Copying a tracked array/space or scalar through a plain name would
        # introduce aliases. Unary negation and multiplication create values;
        # unknown names are tolerated only as opaque, never inferred dimensions.
        source_key = _key(value)
        if source_key in self.values:
            raise _Unsupported
        self.values[key] = self.expression(value)
        if self.values[key] is None:
            self.unresolved_assignments.add(key)


def ones_box_bounds(text: str) -> list[float]:
    """Return only proved Box bounds, or [] for unsupported/hazardous spans.

    Whole-span rejection is intentional, including hazards after a Box call.
    Ordinary literal/angle evidence remains the caller's separate legacy path.
    """
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        return []
    try:
        tree = ast.parse(textwrap.dedent(text))
        if len(tree.body) > MAX_STATEMENTS:
            return []
        for count, _ in enumerate(ast.walk(tree), 1):
            if count > MAX_NODES:
                return []
        reader = _Reader()
        for node in tree.body:
            reader.statement(node)
        if not reader.unresolved_assignments <= reader.shapes:
            return []
        return reader.found
    except (SyntaxError, ValueError, RecursionError, _Unsupported):
        return []
