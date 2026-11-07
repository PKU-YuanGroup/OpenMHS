"""Schema discovery and ``$ref`` resolution for the OpenMHS schema set.

The canonical JSON Schemas live in ``MHS/schema/`` at the repository root.
``MHS/sdk/tools/sync_data.py`` copies them (with ``spec/capabilities.json`` and
``spec/errors.json``) into the package as ``mhs/_data/`` before a wheel is
built, so an installed SDK carries its own copy.

:func:`find_schema_dir` looks for a schema directory in this order:

1. ``$MHS_SCHEMA_DIR``;
2. an explicit ``start`` directory and its parents (when given);
3. the packaged ``mhs/_data/schema`` (via :mod:`importlib.resources`), unless
   the package runs from a source checkout whose ``MHS/schema`` has changed
   since the last sync, in which case the checkout wins and a warning says so;
4. the repository walk upwards from this module, then the working directory.

:class:`SchemaStore` loads ``*.schema.json`` documents on demand, indexes them
by filename, path and ``$id``, and resolves relative references such as
``defs.schema.json#/$defs/ulid``.  Identifiers under
:data:`mhs._ids.SCHEMA_BASE` and under the read-only
:data:`mhs._ids.LEGACY_SCHEMA_PREFIX` resolve to the same document.

Network-facing code must use :meth:`SchemaStore.resolve_public`, which only
returns schemas shipped in the store roots and rejects anything that looks
like a path.  Loading an arbitrary file is a developer-only operation:
:meth:`SchemaStore.load_path`.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import re
import threading
import warnings
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from .._ids import LEGACY_SCHEMA_PREFIX, SCHEMA_BASE
from .validator import SchemaError, resolve_pointer

__all__ = [
    "KNOWN_SCHEMA_PREFIXES",
    "SchemaStore",
    "clear_default_store",
    "default_store",
    "find_schema_dir",
    "mhs_schema_dir",
    "packaged_data_dir",
    "public_schema_name",
]

#: ``$id`` prefixes the store accepts.  The legacy prefix is read-only and is
#: scheduled for removal in 0.10.
KNOWN_SCHEMA_PREFIXES = (SCHEMA_BASE, LEGACY_SCHEMA_PREFIX)

_PUBLIC_NAME = re.compile(r"[a-z0-9][a-z0-9-]*(?:\.schema)?\.json")
_PUBLIC_REF_MAX = 512

_stale_lock = threading.Lock()
_stale_cache: dict[tuple, bool] = {}
_stale_warned = False


# -- discovery ---------------------------------------------------------------


def packaged_data_dir() -> Path | None:
    """Return the packaged ``mhs/_data`` directory, or ``None`` when absent.

    The directory is created by ``MHS/sdk/tools/sync_data.py`` and shipped as
    package data; it holds ``schema/*.json`` and ``spec/{capabilities,errors}.json``.
    Only a real directory on disk is returned (zip imports are not supported).
    """
    package = (__package__ or "mhs.schema").split(".")[0]
    try:
        candidate: Any = importlib.resources.files(package) / "_data"
    except (ModuleNotFoundError, TypeError, ValueError):  # pragma: no cover
        candidate = Path(__file__).resolve().parent.parent / "_data"
    try:
        path = candidate if isinstance(candidate, Path) else Path(os.fspath(candidate))
    except TypeError:  # pragma: no cover - non-filesystem resource reader
        return None
    return path if path.is_dir() else None


def _has_schemas(directory: Path) -> bool:
    """Return True when ``directory`` holds at least one ``*.schema.json``."""
    try:
        return directory.is_dir() and any(directory.glob("*.schema.json"))
    except OSError:  # pragma: no cover - unreadable dir
        return False


def _packaged_schema_dir() -> Path | None:
    """Return ``mhs/_data/schema`` when it holds schemas."""
    data = packaged_data_dir()
    if data is None:
        return None
    schema_dir = data / "schema"
    return schema_dir if _has_schemas(schema_dir) else None


def _checkout_schema_dir() -> Path | None:
    """Return ``MHS/schema`` when this package runs from a source checkout.

    The source layout is ``MHS/sdk/src/mhs/schema/store.py``; an installed
    package never matches it.
    """
    here = Path(__file__).resolve()
    parents = here.parents
    if len(parents) < 5 or parents[2].name != "src" or parents[3].name != "sdk":
        return None
    candidate = parents[4] / "schema"
    return candidate if _has_schemas(candidate) else None


def _tree_signature(directory: Path) -> tuple:
    """Return a cheap ``(name, size, mtime)`` signature of top-level JSON files."""
    rows = []
    for path in sorted(directory.glob("*.json")):
        try:
            stat = path.stat()
        except OSError:  # pragma: no cover - vanished file
            continue
        rows.append((path.name, stat.st_size, stat.st_mtime_ns))
    return tuple(rows)


def _same_json_files(left: Path, right: Path) -> bool:
    """Return True when both directories hold byte-identical top-level JSON files."""
    key = (str(left), _tree_signature(left), str(right), _tree_signature(right))
    with _stale_lock:
        cached = _stale_cache.get(key)
    if cached is not None:
        return cached
    left_files = {p.name: p for p in left.glob("*.json")}
    right_files = {p.name: p for p in right.glob("*.json")}
    same = left_files.keys() == right_files.keys()
    if same:
        try:
            same = all(
                left_files[name].read_bytes() == right_files[name].read_bytes()
                for name in left_files
            )
        except OSError:  # pragma: no cover - unreadable file
            same = False
    with _stale_lock:
        _stale_cache[key] = same
    return same


def _usable_packaged_schema_dir() -> Path | None:
    """Return the packaged schema dir unless a checkout has newer sources."""
    global _stale_warned
    packaged = _packaged_schema_dir()
    if packaged is None:
        return None
    checkout = _checkout_schema_dir()
    if checkout is None or _same_json_files(packaged, checkout):
        return packaged
    with _stale_lock:
        warn = not _stale_warned
        _stale_warned = True
    if warn:
        warnings.warn(
            f"packaged schema data in {packaged} differs from the checkout's "
            f"{checkout}; using the checkout (run MHS/sdk/tools/sync_data.py "
            "before building a wheel)",
            RuntimeWarning,
            stacklevel=3,
        )
    return None


def find_schema_dir(start: str | os.PathLike[str] | None = None) -> Path | None:
    """Return the first directory containing OpenMHS ``*.schema.json`` files.

    Search order: ``$MHS_SCHEMA_DIR``, ``start`` (and its parents), the
    packaged ``mhs/_data/schema``, then the path this module lives under
    (walking up to the repository checkout), then the current working
    directory and its parents.  Returns ``None`` when nothing is found.
    """
    candidates: list[Path] = []
    env = os.environ.get("MHS_SCHEMA_DIR")
    if env:
        candidates.append(Path(env).expanduser())
    if start is not None:
        base = Path(start).expanduser().resolve()
        if base.is_file():
            base = base.parent
        candidates.append(base)
        candidates.extend(base.parents)
    packaged = _usable_packaged_schema_dir()
    if packaged is not None:
        candidates.append(packaged)
    here = Path(__file__).resolve()
    # .../MHS/sdk/src/mhs/schema/store.py -> walk upwards for a sibling schema/
    for parent in here.parents:
        candidates.append(parent / "schema")
        candidates.append(parent / "MHS" / "schema")
    cwd = Path.cwd().resolve()
    candidates.append(cwd / "MHS" / "schema")
    candidates.append(cwd / "schema")
    candidates.append(cwd.parent / "MHS" / "schema")
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:  # pragma: no cover - unreadable path
            continue
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        if _has_schemas(candidate):
            return candidate
    return None


def mhs_schema_dir() -> Path | None:
    """Return the default schema directory, or ``None`` if not found.

    Alias of :func:`find_schema_dir` kept for a readable call site.
    """
    return find_schema_dir()


def public_schema_name(ref: Any) -> str:
    """Return the bare schema file name a public ``ref`` designates.

    Accepted forms are a bare file name made of lowercase letters, digits and
    hyphens ending in ``.schema.json`` or ``.json`` (``device.schema.json``),
    or a full ``$id`` under one of :data:`KNOWN_SCHEMA_PREFIXES` whose last
    segment is such a name.  Anything else -- a slash, a backslash, ``..``,
    ``~``, a drive letter, an absolute path, another host -- raises
    :class:`SchemaError`.
    """
    if not isinstance(ref, str) or not ref:
        raise SchemaError("schema ref must be a non-empty string")
    if len(ref) > _PUBLIC_REF_MAX:
        raise SchemaError("schema ref is too long")
    name = ref
    for prefix in KNOWN_SCHEMA_PREFIXES:
        if ref.startswith(prefix):
            name = ref[len(prefix):]
            break
    if (
        "/" in name
        or "\\" in name
        or ".." in name
        or "~" in name
        or ":" in name
        or PureWindowsPath(name).drive
        or not _PUBLIC_NAME.fullmatch(name)
    ):
        raise SchemaError(
            f"schema ref {ref!r} is not a bare schema file name or a known schema $id"
        )
    return name


def _prefixed_aliases(schema_id: Any) -> set[str]:
    """Return the ``$id`` spellings under every known prefix for ``schema_id``."""
    if not isinstance(schema_id, str):
        return set()
    for prefix in KNOWN_SCHEMA_PREFIXES:
        if schema_id.startswith(prefix):
            rest = schema_id[len(prefix):]
            return {known + rest for known in KNOWN_SCHEMA_PREFIXES}
    return set()


def _inside(root: Path, relative: str | None) -> Path | None:
    """Return ``root/relative`` resolved, or ``None`` if it leaves ``root``."""
    if not relative:
        return None
    if os.path.isabs(relative) or PureWindowsPath(relative).drive:
        return None
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


def _existing_file(key: Any) -> Path | None:
    """Return ``key`` as a path when it names an existing file."""
    try:
        direct = Path(key).expanduser()
        return direct if direct.is_file() else None
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


class SchemaStore:
    """Load and resolve a directory of JSON Schema documents.

    Documents are indexed by filename (``device.schema.json``), basename,
    absolute path, and ``$id`` (under every known prefix).  ``resolve``
    accepts a relative reference plus the referring document's base (path or
    URL) and returns ``(schema_document, base)``.
    """

    def __init__(
        self,
        root: str | os.PathLike[str] | None = None,
        extra_roots: list[str | os.PathLike[str]] | None = None,
        *,
        autoload: bool = True,
    ) -> None:
        """Create a store rooted at ``root`` (default: the discovered dir)."""
        self._lock = threading.RLock()
        self._documents: dict[str, tuple[Mapping[str, Any], str]] = {}
        self._by_name: dict[str, str] = {}
        roots: list[Path] = []
        if root is not None:
            roots.append(Path(root).expanduser())
        else:
            found = find_schema_dir()
            if found is not None:
                roots.append(found)
        for extra in extra_roots or []:
            roots.append(Path(extra).expanduser())
        self.roots = tuple(r.resolve() for r in roots if r.exists())
        if autoload:
            self.load_all()

    # -- discovery ---------------------------------------------------------

    def load_all(self) -> int:
        """Index every ``*.schema.json`` document under the store roots.

        Returns the number of documents in the index afterwards.
        """
        with self._lock:
            for root in self.roots:
                try:
                    files = sorted(root.glob("*.schema.json"))
                except OSError:  # pragma: no cover - unreadable root
                    continue
                for path in files:
                    try:
                        self._load_path(path)
                    except (OSError, json.JSONDecodeError, SchemaError):
                        continue
            return len(self._documents)

    @property
    def documents(self) -> dict[str, Mapping[str, Any]]:
        """Return the indexed documents keyed by filename."""
        return {name: doc for name, (doc, _base) in self._documents.items()}

    def names(self) -> list[str]:
        """Return the sorted list of indexed document filenames."""
        with self._lock:
            return sorted(self._by_name)

    # -- loading -----------------------------------------------------------

    def _load_path(self, path: Path) -> tuple[Mapping[str, Any], str]:
        """Read, parse and index a single schema file."""
        with self._lock:
            key = str(path.resolve())
            if key in self._documents:
                return self._documents[key]
            text = path.read_text(encoding="utf-8")
            document = json.loads(text)
            if not isinstance(document, Mapping):
                raise SchemaError(f"{path} is not a JSON object")
            entry = (document, key)
            self._documents[key] = entry
            schema_id = document.get("$id")
            for alias in {
                path.name,
                str(path),
                key,
                schema_id if isinstance(schema_id, str) else None,
                _url_basename(schema_id) if schema_id else None,
                *_prefixed_aliases(schema_id),
            }:
                if alias:
                    self._by_name[alias] = key
            return entry

    def load_path(self, path: str | os.PathLike[str]) -> tuple[Mapping[str, Any], str]:
        """Load an arbitrary schema file by path (developer-only API).

        This follows any filesystem path, including ``~`` and absolute paths,
        so it must never be called with input that arrived over the network;
        use :meth:`resolve_public` for that.
        """
        candidate = Path(path).expanduser()
        if not candidate.is_file():
            raise SchemaError(f"schema file not found: {candidate}")
        return self._load_path(candidate)

    def load(self, key: str) -> tuple[Mapping[str, Any], str]:
        """Return ``(schema, base)`` for an indexed name, ``$id``, or root file.

        ``key`` is looked up in the index (filename, ``$id`` under any known
        prefix, or an indexed path) and then as a file name inside a store
        root.  Paths that leave the store roots are not followed; load an
        arbitrary file with :meth:`load_path`.
        """
        if not isinstance(key, str):
            raise SchemaError(f"schema key must be a string, got {type(key).__name__}")
        with self._lock:
            match = self._by_name.get(key) or self._by_name.get(
                _url_basename(key) or ""
            )
            if match:
                return self._documents[match]
        for root in self.roots:
            for relative in (key, _url_basename(key)):
                candidate = _inside(root, relative)
                if candidate is not None and candidate.is_file():
                    return self._load_path(candidate)
        if not self.roots:
            raise SchemaError(
                f"schema {key!r} not found: no schema directory was found "
                "(set MHS_SCHEMA_DIR, install a wheel built after "
                "MHS/sdk/tools/sync_data.py, or run from a source checkout)"
            )
        raise SchemaError(f"schema {key!r} not found in store {[str(r) for r in self.roots]}")

    def resolve_public(self, ref: str) -> tuple[Mapping[str, Any], str]:
        """Resolve a client-supplied schema reference to a shipped schema.

        Accepts only what :func:`public_schema_name` accepts and only returns
        a document that is a direct child of one of the store roots.  This is
        the only lookup network-facing code (``mhs.schema.get``, ``GET
        /mhs/v1/schema/<ref>``) may use.
        """
        name = public_schema_name(ref)
        with self._lock:
            match = self._by_name.get(name)
            if match and Path(match).parent in self.roots:
                return self._documents[match]
        for root in self.roots:
            candidate = root / name
            if candidate.is_file():
                return self._load_path(candidate)
        raise SchemaError(f"schema {name!r} is not a shipped schema")

    def _load_for_validation(self, schema: str) -> tuple[Mapping[str, Any], str]:
        """Load a schema named by the local caller: an existing file or a key."""
        direct = _existing_file(schema)
        if direct is not None:
            return self.load_path(direct)
        return self.load(schema)

    # -- resolution --------------------------------------------------------

    def resolve(
        self, uri: str, base: str | os.PathLike[str] | None = None
    ) -> tuple[Mapping[str, Any], str]:
        """Resolve the document part of a ``$ref`` to ``(document, base)``.

        ``uri`` is the part of a reference before ``#``.  Relative references
        are resolved against ``base`` when it is known (a file path or URL);
        otherwise the filename/``$id`` index is consulted directly.
        """
        if not uri:
            raise SchemaError("cannot resolve an empty $ref document part")
        with self._lock:
            if uri in self._by_name:
                return self._documents[self._by_name[uri]]
            if uri in self._documents:
                return self._documents[uri]
        candidates: list[str] = []
        base_str = str(base) if base is not None else None
        if base_str:
            if _looks_like_url(base_str):
                candidates.append(urljoin(base_str, uri))
            else:
                try:
                    base_path = Path(base_str)
                    if base_path.is_file():
                        base_path = base_path.parent
                    candidates.append(str((base_path / uri).resolve()))
                except OSError:  # pragma: no cover - odd base path
                    pass
        candidates.extend(
            [
                uri,
                _url_basename(uri) or "",
            ]
        )
        for candidate in candidates:
            if not candidate:
                continue
            with self._lock:
                match = self._by_name.get(candidate) or self._by_name.get(
                    _url_basename(candidate) or ""
                )
                if match:
                    return self._documents[match]
            path = Path(candidate)
            if path.is_file():
                return self._load_path(path)
        # Last resort: ask every root for the basename.
        basename = _url_basename(uri)
        if basename:
            with self._lock:
                match = self._by_name.get(basename)
                if match:
                    return self._documents[match]
            for root in self.roots:
                path = root / basename
                if path.is_file():
                    return self._load_path(path)
        raise SchemaError(f"cannot resolve $ref document {uri!r} (base={base!r})")

    def resolve_ref(
        self, ref: str, base: str | os.PathLike[str] | None = None
    ) -> tuple[Any, Mapping[str, Any], str]:
        """Resolve a complete ``$ref`` string to ``(subschema, root, base)``."""
        uri, _, fragment = ref.partition("#")
        if uri:
            document, new_base = self.resolve(uri, base=base)
        else:  # pragma: no cover - handled by the validator directly
            raise SchemaError("resolve_ref requires a document part")
        target = resolve_pointer(document, fragment) if fragment else document
        return target, document, new_base

    # -- convenience -------------------------------------------------------

    def validate(
        self,
        instance: Any,
        schema: str,
        *,
        base_uri: str | None = None,
    ) -> list[str]:
        """Validate ``instance`` against a named schema or a local schema file."""
        from .validator import Validator

        document, base = self._load_for_validation(schema)
        return Validator(resolver=self).validate(
            instance, document, base_uri=base_uri or base
        )

    def validate_by_id(self, instance: Any, schema_id: str) -> list[str]:
        """Validate ``instance`` against the schema identified by its ``$id``."""
        return self.validate(instance, schema_id)

    def __len__(self) -> int:
        """Return the number of indexed schema documents."""
        with self._lock:
            return len(self._documents)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        """Return a short description for debugging."""
        return f"SchemaStore(roots={[str(r) for r in self.roots]!r}, docs={len(self)})"


def _url_basename(value: Any) -> str | None:
    """Return the last path segment of a URL, path or ``None``."""
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    name = path.rstrip("/").rsplit("/", 1)[-1]
    return name or None


def _looks_like_url(value: str) -> bool:
    """Return True when ``value`` is an absolute URL."""
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


_default_lock = threading.Lock()
_default_store: SchemaStore | None = None


def default_store() -> SchemaStore:
    """Return the process-wide default :class:`SchemaStore` (lazy, thread-safe)."""
    global _default_store
    with _default_lock:
        if _default_store is None:
            _default_store = SchemaStore()
        return _default_store


def clear_default_store() -> None:
    """Discard the cached default store (useful for tests and after env changes)."""
    global _default_store
    with _default_lock:
        _default_store = None
