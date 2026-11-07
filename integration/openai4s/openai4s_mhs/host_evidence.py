"""Host-side evidence ledger and portable host+endpoint package (HOST-004).

The generic OpenAI4S ``CallMCPTool`` path is transport-only for non-MHS
connectors.  For an MHS capability row the stock host hook
(``openai4s/host/mcp.py`` -> ``openai4s_mhs.hostroute``) wraps that same manager
call, and this module is the durable host chain the wrapper writes:

* :class:`HostLedger` -- an append-only JSONL hash chain.  Every record carries
  ``seq``, ``prev_digest`` and ``digest``; the digest is
  ``sha256(JCS(record without digest) || prev_digest)`` (HOST-051).  A genesis
  record anchors the ledger.  Appends are fsynced by default and reloading a
  tampered ledger fails closed with ``MHS.EVIDENCE.CHAIN_BROKEN``.
* :func:`export_package` -- combines the host ledger, the endpoint evidence
  bundle(s), referenced manifests, an optional transcript and a
  ``manifest_sha256`` over the package manifest (HOST-054).
* :func:`verify_package` -- offline verification of the host chain and every
  endpoint bundle via :func:`mhs.evidence.verify_bundle`; tampering either chain
  makes the package invalid.

What this does **not** prove (HOST-055): that the endpoint was honest, that the
device was safe, or that the experiment succeeded.  A hash chain proves
internal consistency and tamper evidence relative to its genesis anchor.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # POSIX advisory locks are the cross-process transaction primitive.
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
try:  # pragma: no cover - Windows
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

from mhs import canonical
from mhs.evidence import verify_bundle

__all__ = [
    "GENESIS_SEQ",
    "HOST_PACKAGE_VERSION",
    "HostLedger",
    "HostLedgerError",
    "LIMITATIONS",
    "export_package",
    "verify_host_chain",
    "verify_package",
]

HOST_PACKAGE_VERSION = "1.0"
GENESIS_SEQ = 0
ZERO_DIGEST = canonical.ZERO_DIGEST
HOST_NAME = "openai4s-mhs"
HOST_VERSION = "1.0.0"
LIMITATIONS = (
    "This package proves internal consistency of the host ledger and the endpoint "
    "evidence chain relative to their genesis anchors. It does not prove that the "
    "endpoint was honest, that the device was safe, or that the experiment "
    "succeeded (MHS EVID-022 / HOST-055)."
)


class HostLedgerError(RuntimeError):
    """A durable host-ledger failure carrying a stable MHS-ish code."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.message, "mhs_code": self.code, "details": self.details}


def _normalise_path(path: str | os.PathLike[str]) -> Path:
    """One canonical spelling for the chain, its lock and every instance.

    ``Path.resolve()``/``realpath`` matters here because the lock's identity is
    the persistent path, not the Python object: two instances must serialise on
    the same file even when one reached it through a symlink or ``..``.
    """
    return Path(os.path.realpath(os.path.expanduser(os.fspath(path))))


#: One threading lock per normalised ledger path.  ``flock`` already separates
#: independent open descriptions, but a per-path RLock also makes same-process
#: threads deterministic (and is the only serialisation where ``fcntl`` is
#: unavailable).
_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(path: Path) -> threading.RLock:
    key = str(path)
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


class _LedgerFileLock:
    """Exclusive lock spanning load -> verify -> seq/head -> append -> commit.

    The predecessor locked only the Python object: two ``HostLedger`` instances
    on one file each loaded the same head, then both appended ``seq`` 1.  A file
    lock keyed by the normalised path is what makes the chain a single writer
    across instances, threads and processes.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")
        self._thread_lock = _thread_lock_for(path)
        self._handle: Any = None

    def __enter__(self) -> "_LedgerFileLock":
        self._thread_lock.acquire()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = open(self.lock_path, "a+b")
            if fcntl is not None:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
            elif msvcrt is not None:  # pragma: no cover - Windows
                if os.fstat(self._handle.fileno()).st_size == 0:
                    self._handle.write(b"\0")
                    self._handle.flush()
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
        except OSError as exc:
            if self._handle is not None:
                self._handle.close()
            self._thread_lock.release()
            raise HostLedgerError(
                "MHS.HOST.EVIDENCE_WRITE_FAILED",
                f"host ledger lock could not be acquired: {exc}",
                details={"path": str(self.path), "lock": str(self.lock_path)},
            ) from exc
        except BaseException:
            if self._handle is not None:
                self._handle.close()
            self._thread_lock.release()
            raise
        return self

    def __exit__(self, *exc: Any) -> None:
        try:
            if self._handle is not None:
                if fcntl is not None:
                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:  # pragma: no cover - Windows
                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                self._handle.close()
        finally:
            self._handle = None
            self._thread_lock.release()


def _record_digest(record_without_digest: Mapping[str, Any], prev_digest: str) -> str:
    """``sha256(JCS(record without digest) || prev_digest)`` (HOST-051)."""
    payload = canonical.jcs(dict(record_without_digest)) + str(prev_digest).encode("utf-8")
    return canonical.digest_bytes(payload)


def _without_digest(record: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): copy.deepcopy(value) for key, value in record.items() if key != "digest"}


def verify_host_chain(
    records: Iterable[Mapping[str, Any]], *, expected_head: str | None = None
) -> dict[str, Any]:
    """Recompute the host chain and return an endpoint-style verify report."""
    errors: list[dict[str, Any]] = []
    items = list(records)
    head: str | None = None
    expected_seq = GENESIS_SEQ
    checked = 0
    for index, record in enumerate(items):
        checked += 1
        if not isinstance(record, Mapping):
            errors.append(
                {
                    "seq": expected_seq,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": f"record {index}: not an object",
                }
            )
            expected_seq += 1
            continue
        seq = record.get("seq")
        if seq != expected_seq:
            errors.append(
                {
                    "seq": seq if isinstance(seq, int) else None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": f"unexpected seq {seq!r} (expected {expected_seq})",
                }
            )
        expected_prev = ZERO_DIGEST if expected_seq == GENESIS_SEQ else head
        prev = record.get("prev_digest")
        if prev != expected_prev:
            errors.append(
                {
                    "seq": seq if isinstance(seq, int) else None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "prev_digest does not match the previous chain digest",
                }
            )
        if expected_seq == GENESIS_SEQ and record.get("kind") != "genesis":
            errors.append(
                {
                    "seq": seq if isinstance(seq, int) else None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "the first record must be the genesis anchor",
                }
            )
        chain_prev = prev if isinstance(prev, str) else ZERO_DIGEST
        recomputed = _record_digest(_without_digest(record), chain_prev)
        claimed = record.get("digest")
        if claimed != recomputed:
            errors.append(
                {
                    "seq": seq if isinstance(seq, int) else None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": f"digest mismatch (recomputed {recomputed}, record claims {claimed!r})",
                }
            )
        head = claimed if isinstance(claimed, str) else recomputed
        expected_seq += 1
    if not items:
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": "host ledger is empty (no genesis anchor)",
            }
        )
    if expected_head is not None and head != expected_head:
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": f"head_digest mismatch (package claims {expected_head!r}, chain head is {head!r})",
            }
        )
    return {
        "valid": not errors,
        "checked": checked,
        "head_digest": head,
        "errors": errors,
    }


class HostLedger:
    """Append-only, hash-chained host ledger (JSONL, fsync by default)."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        ledger_id: str | None = None,
        fsync: bool = True,
    ) -> None:
        self.path = _normalise_path(path) if path is not None else None
        self.fsync = bool(fsync)
        self.ledger_id = ledger_id or canonical.ulid()
        self._lock = threading.RLock()
        self._records: list[dict[str, Any]] = []
        self._head: str = ZERO_DIGEST
        self._closed = False
        if self.path is not None:
            # Genesis creation is part of the same transaction as load: two
            # first writers on an absent file must not both anchor it.
            with _LedgerFileLock(self.path):
                self._sync_from_disk_locked()
        else:
            record = self._new_genesis_record()
            self._records = [record]
            self._head = str(record["digest"])

    # -- construction ------------------------------------------------------
    def _new_genesis_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "kind": "genesis",
            "seq": GENESIS_SEQ,
            "prev_digest": ZERO_DIGEST,
            "ledger_id": self.ledger_id,
            "mhs_version": "1.0",
            "host": {"name": HOST_NAME, "version": HOST_VERSION},
            "created_at": canonical.now_rfc3339(),
        }
        record["digest"] = _record_digest(record, ZERO_DIGEST)
        return record

    def _sync_from_disk_locked(self) -> None:
        """Re-read and strictly verify the chain. Caller holds the file lock.

        An absent or zero-byte file is the one recoverable state: that is a
        genesis that never committed, not a chain, and anchoring it invents no
        history.  Every other ambiguity (bad JSON, a final line without its
        newline, a broken link) fails closed without touching the bytes.
        """
        assert self.path is not None
        try:
            exists = self.path.exists()
            size = self.path.stat().st_size if exists else 0
        except OSError as exc:
            raise HostLedgerError(
                "MHS.EVIDENCE.CHAIN_BROKEN",
                f"host ledger could not be inspected: {exc}",
                details={"path": str(self.path)},
            ) from exc
        if not exists or size == 0:
            record = self._new_genesis_record()
            self._append_line(record)
            self._records = [record]
            self._head = str(record["digest"])
            return
        self._load()
        self.ledger_id = str(self._records[0].get("ledger_id") or self.ledger_id)

    def _load(self) -> None:
        loaded: list[dict[str, Any]] = []
        assert self.path is not None
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise HostLedgerError(
                "MHS.EVIDENCE.CHAIN_BROKEN",
                f"host ledger could not be read: {exc}",
                details={"path": str(self.path)},
            ) from exc
        if raw and not raw.endswith(b"\n"):
            raise HostLedgerError(
                "MHS.EVIDENCE.CHAIN_BROKEN",
                "host ledger ends with a torn record (no trailing newline); "
                "refusing to append past an uncommitted tail",
                details={"path": str(self.path)},
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HostLedgerError(
                "MHS.EVIDENCE.CHAIN_BROKEN",
                f"host ledger is not UTF-8: {exc}",
                details={"path": str(self.path)},
            ) from exc
        for line_number, line in enumerate(text.splitlines(), 1):
            text_line = line.strip()
            if not text_line:
                continue
            try:
                record = json.loads(text_line)
            except json.JSONDecodeError as exc:
                raise HostLedgerError(
                    "MHS.EVIDENCE.CHAIN_BROKEN",
                    f"host ledger line {line_number} is not valid JSON: {exc.msg}",
                    details={"path": str(self.path), "line": line_number},
                ) from exc
            if not isinstance(record, dict):
                raise HostLedgerError(
                    "MHS.EVIDENCE.CHAIN_BROKEN",
                    f"host ledger line {line_number} is not a JSON object",
                    details={"path": str(self.path), "line": line_number},
                )
            loaded.append(record)
        report = verify_host_chain(loaded)
        if not report["valid"]:
            raise HostLedgerError(
                "MHS.EVIDENCE.CHAIN_BROKEN",
                "host ledger failed verification on load",
                details={"path": str(self.path), "errors": report["errors"]},
            )
        self._records = loaded
        self._head = str(report["head_digest"])

    def _append_line(self, record: Mapping[str, Any]) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        try:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                if self.fsync:
                    os.fsync(handle.fileno())
        except OSError as exc:
            raise HostLedgerError(
                "MHS.HOST.EVIDENCE_WRITE_FAILED",
                f"host ledger append failed: {exc}",
                details={"path": str(self.path)},
            ) from exc

    # -- reading / writing -------------------------------------------------
    def append(self, record: Mapping[str, Any], *, kind: str = "record") -> dict[str, Any]:
        """Append one record and return it (including seq/prev_digest/digest)."""
        if not isinstance(record, Mapping):
            raise HostLedgerError(
                "MHS.HOST.EVIDENCE_WRITE_FAILED", "host ledger record must be an object"
            )
        if self.path is None:
            with self._lock:
                return self._append_locked(record, kind)
        with _LedgerFileLock(self.path):
            # The head that matters is the one on disk *now*: another instance
            # (or process) may have appended since this object last looked.
            self._sync_from_disk_locked()
            return self._append_locked(record, kind)

    def _append_locked(self, record: Mapping[str, Any], kind: str) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                raise HostLedgerError(
                    "MHS.HOST.EVIDENCE_WRITE_FAILED", "host ledger is closed"
                )
            entry: dict[str, Any] = {
                str(key): copy.deepcopy(value)
                for key, value in record.items()
                if key not in ("seq", "prev_digest", "digest")
            }
            entry.setdefault("kind", kind)
            entry.setdefault("ts", canonical.now_rfc3339())
            seq = len(self._records)
            entry["seq"] = seq
            entry["prev_digest"] = self._head
            entry["digest"] = _record_digest(entry, self._head)
            self._append_line(entry)
            self._records.append(entry)
            self._head = str(entry["digest"])
            return copy.deepcopy(entry)

    def records(self) -> list[dict[str, Any]]:
        if self.path is None:
            with self._lock:
                return copy.deepcopy(self._records)
        with _LedgerFileLock(self.path):
            self._sync_from_disk_locked()
            return copy.deepcopy(self._records)

    def snapshot(self) -> tuple[list[dict[str, Any]], str]:
        """Records and head sampled under one lock (never a torn read)."""
        records = self.records()
        return records, self._head

    @property
    def head_digest(self) -> str:
        return self._head

    def verify(self) -> dict[str, Any]:
        return verify_host_chain(self.records(), expected_head=self._head)

    def export_package(
        self,
        endpoint_bundles: Iterable[Mapping[str, Any]] | None = None,
        *,
        manifests: Iterable[Mapping[str, Any]] | None = None,
        transcript: Iterable[Any] | None = None,
        limitations: str | None = None,
    ) -> dict[str, Any]:
        return export_package(
            self,
            endpoint_bundles or [],
            manifests=manifests,
            transcript=transcript,
            limitations=limitations,
        )

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "HostLedger":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def export_package(
    ledger: HostLedger | Iterable[Mapping[str, Any]],
    endpoint_bundles: Iterable[Mapping[str, Any]] | None = None,
    *,
    manifests: Iterable[Mapping[str, Any]] | None = None,
    transcript: Iterable[Any] | None = None,
    limitations: str | None = None,
) -> dict[str, Any]:
    """Build a portable host+endpoint evidence package (HOST-054)."""
    if isinstance(ledger, HostLedger):
        records, head = ledger.snapshot()
        ledger_id = ledger.ledger_id
    else:
        records = [copy.deepcopy(dict(item)) for item in ledger]
        head = str(records[-1].get("digest")) if records else ZERO_DIGEST
        ledger_id = str((records[0].get("ledger_id") if records else "") or "")
    bundles = [copy.deepcopy(dict(item)) for item in (endpoint_bundles or [])]
    manifest_list = [copy.deepcopy(dict(item)) for item in (manifests or [])]
    transcript_list = [copy.deepcopy(item) for item in (transcript or [])]
    exported_at = canonical.now_rfc3339()

    bundle_entries: list[dict[str, Any]] = []
    for bundle in bundles:
        bundle_entries.append(
            {
                "endpoint_id": bundle.get("endpoint_id") or bundle.get("endpoint"),
                "digest": canonical.digest(bundle),
                "head_digest": bundle.get("head_digest"),
                "count": bundle.get("count"),
            }
        )
    manifest_entries: list[dict[str, Any]] = [
        {
            "device_id": item.get("device_id"),
            "digest": canonical.digest(item),
        }
        for item in manifest_list
    ]
    package_manifest: dict[str, Any] = {
        "package_version": HOST_PACKAGE_VERSION,
        "format": "mhs-host-evidence-package",
        "exported_at": exported_at,
        "host": {"name": HOST_NAME, "version": HOST_VERSION},
        "ledger_id": ledger_id,
        "host_ledger_head": head,
        "host_ledger_count": len(records),
        "endpoint_bundles": bundle_entries,
        "manifests": manifest_entries,
        "transcript_digest": canonical.digest(transcript_list),
    }
    return {
        "package_version": HOST_PACKAGE_VERSION,
        "format": "mhs-host-evidence-package",
        "exported_at": exported_at,
        "host": {"name": HOST_NAME, "version": HOST_VERSION},
        "ledger_id": ledger_id,
        "host_ledger": records,
        "host_ledger_head": head,
        "endpoint_bundles": bundles,
        "manifests": manifest_list,
        "transcript": transcript_list,
        "manifest": package_manifest,
        "manifest_sha256": canonical.digest(package_manifest),
        "limitations": limitations or LIMITATIONS,
    }


def verify_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Verify a host+endpoint package offline (host chain + endpoint bundles)."""
    errors: list[dict[str, Any]] = []
    if not isinstance(package, Mapping):
        return {
            "valid": False,
            "errors": [
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "package is not a JSON object",
                }
            ],
        }
    if package.get("format") != "mhs-host-evidence-package":
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": f"unexpected package format {package.get('format')!r}",
            }
        )
    if package.get("package_version") != HOST_PACKAGE_VERSION:
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": f"unsupported package_version {package.get('package_version')!r}",
            }
        )
    records = package.get("host_ledger")
    if not isinstance(records, list):
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": "package has no host_ledger array",
            }
        )
        records = []
    host_chain = verify_host_chain(records, expected_head=package.get("host_ledger_head"))
    if not host_chain["valid"]:
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": "host ledger chain is invalid",
            }
        )

    bundles = package.get("endpoint_bundles")
    bundle_results: list[dict[str, Any]] = []
    if not isinstance(bundles, list):
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": "package has no endpoint_bundles array",
            }
        )
        bundles = []
    for index, bundle in enumerate(bundles):
        if not isinstance(bundle, Mapping):
            result = {
                "valid": False,
                "checked": 0,
                "head_digest": None,
                "errors": [
                    {
                        "seq": None,
                        "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                        "detail": "endpoint bundle is not an object",
                    }
                ],
            }
        else:
            report = verify_bundle(bundle)
            result = {
                "valid": bool(report.get("valid")),
                "checked": int(report.get("checked") or 0),
                "head_digest": report.get("head_digest"),
                "errors": list(report.get("errors") or []),
            }
        bundle_results.append(
            {
                "index": index,
                "endpoint_id": (bundle or {}).get("endpoint_id") if isinstance(bundle, Mapping) else None,
                **result,
            }
        )
        if not result["valid"]:
            errors.append(
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": f"endpoint bundle {index} is invalid",
                }
            )

    manifest = package.get("manifest")
    manifest_sha256 = package.get("manifest_sha256")
    manifest_ok = isinstance(manifest, Mapping)
    if not manifest_ok:
        errors.append(
            {
                "seq": None,
                "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                "detail": "package has no manifest object",
            }
        )
    else:
        computed_manifest = canonical.digest(manifest)
        if computed_manifest != manifest_sha256:
            errors.append(
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "manifest_sha256 does not match the package manifest",
                }
            )
        if manifest.get("host_ledger_head") != host_chain.get("head_digest"):
            errors.append(
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "manifest host_ledger_head does not match the verified chain",
                }
            )
        if manifest.get("host_ledger_count") != len(records):
            errors.append(
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "manifest host_ledger_count does not match the ledger",
                }
            )
        transcript = package.get("transcript")
        if manifest.get("transcript_digest") != canonical.digest(
            transcript if isinstance(transcript, list) else []
        ):
            errors.append(
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "manifest transcript_digest does not match the package transcript",
                }
            )
        expected_bundles = manifest.get("endpoint_bundles")
        if isinstance(expected_bundles, list):
            actual_digests = [canonical.digest(bundle) for bundle in bundles]
            claimed_digests = [
                item.get("digest") for item in expected_bundles if isinstance(item, Mapping)
            ]
            if claimed_digests != actual_digests:
                errors.append(
                    {
                        "seq": None,
                        "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                        "detail": "endpoint bundle digests do not match the package manifest",
                    }
                )
        expected_manifests = manifest.get("manifests")
        if isinstance(expected_manifests, list):
            actual_manifest_digests = [
                canonical.digest(item) for item in (package.get("manifests") or [])
            ]
            claimed_manifest_digests = [
                item.get("digest") for item in expected_manifests if isinstance(item, Mapping)
            ]
            if claimed_manifest_digests != actual_manifest_digests:
                errors.append(
                    {
                        "seq": None,
                        "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                        "detail": "manifest digests do not match the package manifest",
                    }
                )
    return {
        "valid": not errors,
        "host_chain": host_chain,
        "endpoint_bundles": bundle_results,
        "manifest_sha256": canonical.digest(manifest) if isinstance(manifest, Mapping) else None,
        "errors": errors,
    }
