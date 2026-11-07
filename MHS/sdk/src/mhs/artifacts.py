"""Opt-in ephemeral artifacts, scoped to the command's original session.

This local SDK service is not an MHS wire transport or an arbitrary file server.
Only bytes published through a command publisher become retrievable. Receipts
remain evidence after a grant expires; they do not promise permanent storage.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import stat
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from . import canonical
from .errors import MHSError

CONTEXT_KEY = "_mhs_artifact_publisher"
DEFAULT_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_METADATA_BYTES = 4096
_ENDPOINT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_MEDIA = re.compile(r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*\Z")
_ID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}\Z")


def _error(message: str, *, reason: str = "artifact_unavailable") -> MHSError:
    return MHSError("MHS.CAPABILITY.OUTPUT_INVALID", message,
                    {"retryable": False, "details": {"reason": reason}})


def _bound(value: Any, label: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be an integer in 1..{maximum}")
    return value


def _vendor_metadata(value: Any) -> dict[str, Any] | None:
    """Detach a small JSON extension before any store allocation or lock wait."""
    if value is None:
        return None
    if type(value) is not dict:
        raise _error("artifact x-vendor must be a JSON object")
    remaining = 128
    def detach(item: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 6:
            raise _error("artifact metadata exceeds its structural limit")
        if item is None or type(item) is bool:
            return item
        if type(item) is int and abs(item) <= 9007199254740991:
            return item
        if type(item) is float and math.isfinite(item):
            return item
        if type(item) is str:
            if len(item) > MAX_ARTIFACT_METADATA_BYTES:
                raise _error("artifact metadata string is too long")
            return item
        if type(item) is dict and len(item) <= 128:
            if any(type(key) is not str or len(key) > 128 for key in item):
                raise _error("artifact metadata keys must be bounded strings")
            return {key: detach(child, depth + 1) for key, child in item.items()}
        if type(item) is list and len(item) <= 128:
            return [detach(child, depth + 1) for child in item]
        raise _error("artifact metadata must be bounded finite JSON")
    detached = detach(value, 0)
    try:
        encoded = json.dumps(detached, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise _error("artifact metadata must be valid UTF-8 JSON") from exc
    if len(encoded) > MAX_ARTIFACT_METADATA_BYTES:
        raise _error("artifact metadata exceeds its byte limit")
    return detached


@dataclass(frozen=True)
class ArtifactScope:
    session_id: str
    device_id: str
    resource: str
    capability_id: str
    command_id: str


@dataclass
class _Grant:
    scope: ArtifactScope
    descriptor: dict[str, Any]
    digest: str
    deadline: float
    committed: bool = False


class LocalArtifactStore:
    """Bounded, private, content-addressed temporary blobs with separate grants.

    ``directory`` is only the parent for a new private temporary directory. No
    existing file in that parent is indexed, served or removed. A store binds to
    one endpoint; the endpoint owns its lifecycle after receiving it.
    """

    def __init__(self, *, directory: str | os.PathLike[str] | None = None,
                 max_artifact_bytes: int = DEFAULT_ARTIFACT_BYTES,
                 max_total_bytes: int = 32 * 1024 * 1024,
                 max_artifacts: int = 128, ttl_s: int = 300,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_artifact_bytes = _bound(max_artifact_bytes, "max_artifact_bytes", MAX_ARTIFACT_BYTES)
        self.max_total_bytes = _bound(max_total_bytes, "max_total_bytes", 256 * 1024 * 1024)
        self.max_artifacts = _bound(max_artifacts, "max_artifacts", 4096)
        self.ttl_s = _bound(ttl_s, "ttl_s", 86400)
        if self.max_total_bytes < self.max_artifact_bytes:
            raise ValueError("max_total_bytes must cover max_artifact_bytes")
        self._temp = tempfile.TemporaryDirectory(prefix="openmhs-artifacts-", dir=directory)
        self._root = Path(self._temp.name)
        os.chmod(self._root, 0o700)
        self._clock = clock
        self._lock = threading.RLock()
        self._endpoint: str | None = None
        self._closed = False
        self._write_fault = False
        self._grants: dict[str, _Grant] = {}
        self._blobs: dict[str, tuple[int, int]] = {}  # size, references (including staged)
        self._total_bytes = 0

    def bind(self, endpoint_id: str) -> None:
        if not isinstance(endpoint_id, str) or len(endpoint_id) > 1024:
            raise ValueError("artifact endpoint_id must be a bounded mhs URI")
        parsed = urlsplit(endpoint_id)
        if (parsed.scheme != "mhs" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or not _ENDPOINT.fullmatch(parsed.hostname)):
            raise ValueError("artifact endpoint_id needs an mhs URI with a simple hostname")
        port = parsed.port  # validates the optional port
        authority = parsed.hostname + (f":{port}" if port is not None else "")
        with self._lock:
            self._check_open()
            if self._endpoint is not None:
                raise ValueError("an artifact store belongs to exactly one endpoint instance")
            self._endpoint = authority

    def publisher(self, scope: ArtifactScope, guard: Callable[[], None]) -> "ArtifactPublisher":
        # Every command receives a publisher, including independent stop paths.
        # Construct it without touching storage or waiting for another image's
        # evidence I/O. Only actual publication validates/binds storage state.
        return ArtifactPublisher(self, scope, guard)

    def _check_open(self) -> None:
        if self._closed:
            raise _error("artifact store is closed")

    def _remove(self, ident: str) -> None:
        grant = self._grants.get(ident)
        if grant is None:
            return
        size, refs = self._blobs[grant.digest]
        if refs > 1:
            self._blobs[grant.digest] = (size, refs - 1)
        else:
            try:
                (self._root / grant.digest).unlink(missing_ok=True)
            except OSError:
                # Do not free quota for bytes that may still occupy the disk.
                # Further writes are refused until this store is closed.
                self._write_fault = True
                raise
            del self._blobs[grant.digest]
            self._total_bytes -= size
        del self._grants[ident]

    def _prune(self) -> None:
        now = self._clock()
        for ident, grant in list(self._grants.items()):
            if grant.deadline <= now:
                self._remove(ident)

    def _stage(self, scope: ArtifactScope, data: bytes, media_type: str, *,
               x_vendor: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
        if not isinstance(data, bytes) or not 0 < len(data) <= self.max_artifact_bytes:
            raise _error("artifact bytes are empty or exceed the configured limit", reason="artifact_size")
        if (not isinstance(media_type, str) or len(media_type) > 127
                or not _MEDIA.fullmatch(media_type)):
            raise _error("artifact media type is invalid")
        metadata = _vendor_metadata(x_vendor)
        digest = hashlib.sha256(data).hexdigest()
        with self._lock:
            self._check_open()
            if self._endpoint is None:
                raise _error("bind the artifact store before publishing bytes")
            if self._write_fault:
                raise _error("artifact storage fault refuses further publication")
            self._prune()
            extra = 0 if digest in self._blobs else len(data)
            if len(self._grants) >= self.max_artifacts or self._total_bytes + extra > self.max_total_bytes:
                raise _error("artifact store capacity is exhausted", reason="artifact_capacity")
            if digest not in self._blobs:
                path = self._root / digest
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                except BaseException:
                    self._write_fault = True
                    path.unlink(missing_ok=True)
                    raise
                self._blobs[digest] = (len(data), 0)
                self._total_bytes += len(data)
            size, refs = self._blobs[digest]
            self._blobs[digest] = (size, refs + 1)
            ident = canonical.ulid()
            if ident in self._grants:
                raise AssertionError("artifact id collision")
            descriptor = {"uri": f"mhs+artifact://{self._endpoint}/{ident}",
                          "media_type": media_type, "size_bytes": len(data),
                          "digest": "sha256:" + digest,
                          "expires_at": datetime.fromtimestamp(time.time() + self.ttl_s, timezone.utc)
                          .isoformat(timespec="milliseconds").replace("+00:00", "Z")}
            if metadata is not None:
                descriptor["x-vendor"] = metadata
            self._grants[ident] = _Grant(scope, descriptor, digest, self._clock() + self.ttl_s)
            return ident, copy.deepcopy(descriptor)

    def _prepare(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        with self._lock:
            self._check_open()
            self._prune()
            if any(ident not in self._grants for ident in ids):
                raise _error("artifact expired before command completion")
            return [copy.deepcopy(self._grants[ident].descriptor) for ident in ids]


    def _abort(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._lock:
            for ident in ids:
                self._remove(ident)

    def read(self, uri: str, session_id: str, authorize: Callable[[ArtifactScope], None]) -> dict[str, Any]:
        """Endpoint-only read: caller supplies authenticated session and scope check.

        There is deliberately no public read-by-path or read-without-owner API.
        The endpoint repeats its live-session check after this bounded read.
        """
        prefix = f"mhs+artifact://{self._endpoint}/"
        if not isinstance(uri, str) or not uri.startswith(prefix) or not _ID.fullmatch(uri[len(prefix):]):
            raise _error("unknown artifact")
        ident = uri[len(prefix):]
        with self._lock:
            self._check_open()
            self._prune()
            grant = self._grants.get(ident)
            if grant is None or not grant.committed or grant.scope.session_id != session_id:
                raise _error("unknown artifact")
            authorize(grant.scope)
            expected = grant.descriptor["size_bytes"]
            try:
                fd = os.open(self._root / grant.digest, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size != expected:
                        raise _error("artifact integrity check failed")
                    data = stream.read(expected + 1)
            except OSError as exc:
                raise _error("artifact cannot be read from its immutable store") from exc
            if len(data) != expected or hashlib.sha256(data).hexdigest() != grant.digest:
                raise _error("artifact integrity check failed")
            return {"descriptor": copy.deepcopy(grant.descriptor), "data": data}

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._grants.clear()
            self._blobs.clear()
            self._total_bytes = 0
            self._temp.cleanup()


class ArtifactPublisher:
    """One command's staged artifact; never share it between executions."""

    def __init__(self, store: LocalArtifactStore, scope: ArtifactScope, guard: Callable[[], None]):
        self._store, self._scope, self._guard = store, scope, guard
        self._lock = threading.Lock()
        self._ids: list[str] = []
        self._finished = False
        self._prepared = False
        self._output_field = "image_ref"

    @property
    def max_bytes(self) -> int:
        return self._store.max_artifact_bytes

    def preflight(self, max_bytes: int) -> None:
        """Refuse known storage exhaustion before an effectful acquisition.

        This conservative capacity observation does not reserve quota. Another
        publisher may consume it before publish, which still checks atomically.
        """
        if type(max_bytes) is not int or not 0 < max_bytes <= self.max_bytes:
            raise _error("complete artifact exceeds the configured limit", reason="artifact_size")
        with self._lock:
            if self._finished or self._ids:
                raise _error("this command's artifact publisher is already used")
            self._guard()
            with self._store._lock:
                self._store._check_open()
                if self._store._endpoint is None or self._store._write_fault:
                    raise _error("artifact storage is not ready for publication")
                self._store._prune()
                if (len(self._store._grants) >= self._store.max_artifacts
                        or self._store._total_bytes + max_bytes > self._store.max_total_bytes):
                    raise _error("artifact store capacity is exhausted", reason="artifact_capacity")

    def publish(self, data: bytes, media_type: str, *, output_field: str = "image_ref",
                x_vendor: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._finished or self._ids:
                raise _error("this command's artifact publisher is already used")
            if output_field not in ("image_ref", "artifact_ref"):
                raise _error("unsupported artifact output reference field")
            self._guard()
            ident, descriptor = self._store._stage(self._scope, data, media_type, x_vendor=x_vendor)
            self._output_field = output_field
            self._ids.append(ident)
            return descriptor

    def prepare(self, output: Any) -> list[dict[str, Any]]:
        with self._lock:
            if self._finished or self._prepared:
                raise _error("artifact publisher already finalized or prepared")
            if not self._ids:
                self._prepared = True
                return []
            self._guard()
            # Publication is for one explicitly named primary artifact. No
            # grant may be smuggled into a receipt unrelated to its output.
            expected_uri = f"mhs+artifact://{self._store._endpoint}/{self._ids[0]}"
            if (not isinstance(output, Mapping) or output.get(self._output_field) != expected_uri
                    or sum(output.get(name) == expected_uri for name in ("image_ref", "artifact_ref")) != 1):
                self._store._abort(self._ids)
                self._finished = True
                raise _error("published artifact does not match the validated command output")
            descriptors = self._store._prepare(self._ids)
            self._prepared = True
            return descriptors

    def commit(self, record: Callable[[], Any] | None = None,
               retain: Callable[[Any], None] | None = None) -> Any:
        """Commit after fallible preparation, before any receipt is published.

        The server serializes evidence export around this transaction. Store
        reads and expiry cannot interleave. ``record`` is the last fallible
        step; ``retain`` is an internal no-I/O index publication, not a user hook.
        Notification/journaling happen after this irreversible transition.
        """
        with self._lock:
            if not self._prepared or self._finished:
                raise _error("artifact publisher is not prepared for commit")
            self._guard()
            with self._store._lock:
                self._store._check_open()
                now = self._store._clock()
                grants = [self._store._grants.get(ident) for ident in self._ids]
                if any(grant is None or grant.deadline <= now for grant in grants):
                    raise _error("artifact expired before receipt commit")
                receipt = record() if record is not None else None
                # No external callback, file I/O or clock call lies between
                # activation and the server's prepared index publication.
                for grant in grants:
                    grant.committed = True
                self._finished = True
                if retain is not None:
                    retain(receipt)
                return receipt

    def abort(self) -> None:
        with self._lock:
            if not self._finished:
                if self._ids:
                    self._store._abort(self._ids)
                self._finished = True


def publisher_from_context(context: Any) -> ArtifactPublisher | None:
    extra = getattr(context, "extra", None)
    publisher = extra.get(CONTEXT_KEY) if isinstance(extra, Mapping) else None
    return publisher if isinstance(publisher, ArtifactPublisher) else None
