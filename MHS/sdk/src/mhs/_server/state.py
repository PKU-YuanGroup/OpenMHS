"""Endpoint state on disk: ``MHSServer(state_dir=...)`` (WP-04 step 4f).

Layout of a state directory (one endpoint process at a time)::

    <state_dir>/evidence.jsonl  the evidence chain (EvidenceLog(path=...)):
                                every receipt, so the source of truth for
                                outcomes and revisions
    <state_dir>/latch.json      the e-stop latch of every device the endpoint
                                knows; rewritten atomically (temp file, fsync,
                                rename, directory fsync) under the server's
                                global lock before any bridge I/O
    <state_dir>/journal.jsonl   the idempotency index and the write-ahead
                                records the evidence cannot hold (see below);
                                append-only, compacted atomically at start-up
    <state_dir>/lock            advisory lock (POSIX ``flock``) held while the
                                endpoint runs

Journal lines (one JSON object per line, ``op`` first)::

    {"op": "header", "format", "endpoint_id", "created_at", "revisions": {device_id: n}}
    {"op": "put",   "device_id", "command_id", "input_digest", "receipt_id", "seq"}
    {"op": "drop",  "device_id", "command_id", "receipt_id"}
    {"op": "begin", "device_id", "command_id", "input_digest", "capability_id",
                    "resource", "session_id", "principal", "mode", "accepted_at", "evidence_seq"}
    {"op": "end",   "device_id", "command_id"}
    {"op": "draw",  "key", "window", "t", "amount", "id"}
    {"op": "release", "id"}

``put`` / ``drop`` are the idempotency index: ``(device_id, command_id)`` ->
the retained receipt, which lives in the evidence log at ``seq``.  ``begin`` /
``end`` bracket a command between its idempotency reservation and its final
receipt (only the request that made the reservation writes its ``end``): a
``begin`` without an ``end`` or an outcome after a crash is a command that may
have acted, and the restarted endpoint records an ``unknown`` receipt for it
instead of running it again.  Its outcome is a receipt of the same command id
and input digest that is not ``rejected``, recorded after the ``begin``: a
rejected duplicate (``COMMAND_ID_REUSE``, ``DEVICE.BUSY``) never settles it,
and neither does the command's own refusal when the crash hit before its
``end`` (it becomes ``unknown``: the safe direction).  ``draw`` / ``release``
are the cumulative budget reservations (SAFE-016), so a restart never refills
a budget.

Loading (:meth:`StateDir.load_journal`) rebuilds the index from the verified
evidence chain with exactly the server's retention rule (every receipt that is
not ``rejected`` is the command's outcome, a later one replaces it, and a late
rejection that reconciles the retained receipt frees the command id) and
checks every ``put`` line against it.  A torn final line (a crash during an
append) is ignored with a warning; any other unreadable line, or an index
entry that contradicts the evidence record it names, refuses the start
(:class:`StateDirError`): without a trustworthy index a retried command could
run twice.  An index entry past the end of the evidence (the evidence lost its
tail while the journal kept its own: a power failure without ``fsync=True``)
makes its command ``unknown``, like a command in flight.  A missing journal is
rebuilt from the evidence.

The latch is derived from the evidence too (:func:`derive_latches`): a device
whose last e-stop receipt has no later completed reset is latched whatever
``latch.json`` says.  ``latch.json`` is written before the e-stop's receipt
and before the reset's, so the union of the two never releases a latch it
should keep.  A missing ``latch.json`` in a directory whose evidence holds a
receipt is lost state (the endpoint writes the file at every start, before any
receipt): it fails latched like an unreadable one.

Nothing here talks to a bridge or takes a server lock.
"""

from __future__ import annotations

import json
import os
import threading
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .. import canonical

try:  # POSIX only; elsewhere the single-process rule is the operator's job.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None  # type: ignore[assignment]

__all__ = [
    "ESTOP_CAPABILITIES",
    "EVIDENCE_FILE",
    "HAVE_FLOCK",
    "JOURNAL_FILE",
    "JOURNAL_FORMAT",
    "LATCH_FILE",
    "LATCH_FORMAT",
    "LOCK_FILE",
    "RESET_CAPABILITY",
    "JournalState",
    "LatchState",
    "StateDir",
    "StateDirError",
    "atomic_write_bytes",
    "derive_index",
    "derive_latches",
    "holds_receipts",
]

EVIDENCE_FILE = "evidence.jsonl"
LATCH_FILE = "latch.json"
JOURNAL_FILE = "journal.jsonl"
LOCK_FILE = "lock"
LATCH_FORMAT = "openmhs.state.latch/1"
JOURNAL_FORMAT = "openmhs.state.journal/1"
HAVE_FLOCK = _fcntl is not None

#: Journal operations a line may carry.
_JOURNAL_OPS = frozenset({"header", "put", "drop", "begin", "end", "draw", "release"})

#: Receipts of these classes engage the e-stop latch (``mhs.safety.estop`` and
#: the catalogue e-stop class); a completed reset receipt releases it.
ESTOP_CAPABILITIES = frozenset({"cap.internal.safety_estop.v1", "cap.motion.estop.v1"})
RESET_CAPABILITY = "cap.internal.safety_reset.v1"


class StateDirError(ValueError):
    """The state directory cannot be used: the endpoint refuses to start."""


def _fsync_directory(directory: Path) -> None:
    """Make a rename in ``directory`` durable (best effort; POSIX only)."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes, *, fsync: bool = True) -> None:
    """Replace ``path`` with ``data`` atomically: temp file, fsync, rename.

    A reader (or a restart after a crash) sees either the old content or the
    new one, never a mix.  On any failure the temp file is removed and the old
    file is left as it was; the ``OSError`` propagates.
    """
    path = Path(path)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{canonical.ulid()}.tmp")
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    if fsync:
        _fsync_directory(path.parent)


def _encode_line(entry: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(entry), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            + "\n").encode("utf-8")


def _key_of(record: Mapping[str, Any]) -> tuple[str, str] | None:
    device_id, command_id = record.get("device_id"), record.get("command_id")
    if isinstance(device_id, str) and isinstance(command_id, str):
        return device_id, command_id
    return None


def _seq_of(record: Mapping[str, Any]) -> int | None:
    evidence = record.get("evidence")
    seq = evidence.get("seq") if isinstance(evidence, Mapping) else None
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else None


def _is_receipt(record: Mapping[str, Any]) -> bool:
    return record.get("kind") in (None, "receipt") and isinstance(record.get("status"), str)


def derive_index(records: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], tuple[str, dict[str, Any]]]:
    """The idempotency index the server kept while it recorded ``records``.

    ``records`` are evidence records in chain order.  The rule is the server's:
    a receipt that is not ``rejected`` is the command's retained outcome (a
    later one, such as the final receipt after ``unknown``, replaces it); a
    ``rejected`` receipt is never the outcome, and one that reconciles the
    retained receipt (``x-vendor.reconciles``: a late ``Busy``) frees the
    command id.  Non-terminal (``accepted`` / ``running``) receipts are never
    evidence and are ignored.
    """
    index: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, Mapping) or not _is_receipt(record):
            continue
        key = _key_of(record)
        if key is None:
            continue
        status = record.get("status")
        if status == "rejected":
            vendor = record.get("x-vendor")
            reconciles = vendor.get("reconciles") if isinstance(vendor, Mapping) else None
            stored = index.get(key)
            if (isinstance(reconciles, Mapping) and stored is not None
                    and stored[1].get("receipt_id") == reconciles.get("receipt_id")):
                index.pop(key, None)
            continue
        if status in ("accepted", "running"):
            continue
        index[key] = (str(record.get("input_digest")), dict(record))
    return index


def holds_receipts(records: Iterable[Mapping[str, Any]]) -> bool:
    """True when the evidence ``records`` hold at least one receipt."""
    return any(isinstance(record, Mapping) and _is_receipt(record) for record in records)


def _engages_latch(record: Mapping[str, Any]) -> bool:
    """An e-stop receipt that engaged the latch (not a refusal, not a confirmation)."""
    if record.get("capability_id") not in ESTOP_CAPABILITIES:
        return False
    if record.get("status") in ("rejected", "accepted", "running"):
        return False
    output = record.get("output")
    # The background confirmation of a latch already engaged (it may be
    # written just after a reset released that latch).
    return not (isinstance(output, Mapping) and "confirms_command_ids" in output)


def derive_latches(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """device_id -> the e-stop receipt that keeps it latched, from ``records``.

    ``records`` are evidence records in chain order.  A device is latched when
    its last e-stop receipt that engaged the latch (``cap.internal.safety_estop.v1``
    or ``cap.motion.estop.v1``, any status but ``rejected``; a confirmation
    receipt engages nothing) comes after its last ``completed``
    ``cap.internal.safety_reset.v1`` receipt.  The rule errs on the latched
    side: a reset whose receipt was lost, or an e-stop whose receipt was
    recorded after that of the reset that released it (the reset raced the
    receipt write), leaves the device latched until the next reset.
    """
    latched: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping) or not _is_receipt(record):
            continue
        device_id = record.get("device_id")
        if not isinstance(device_id, str):
            continue
        if _engages_latch(record):
            latched[device_id] = dict(record)
        elif record.get("capability_id") == RESET_CAPABILITY and record.get("status") == "completed":
            latched.pop(device_id, None)
    return latched


@dataclass
class LatchState:
    """What :meth:`StateDir.load_latches` found."""

    #: device_id -> ``{"latched": bool, "reason": str | None, "since": str | None}``
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Why an existing latch file could not be used (None when it could, or was absent).
    unreadable: str | None = None
    #: The unreadable file's bytes (None when they could not be read at all).
    raw: bytes | None = None
    #: Where :meth:`StateDir.preserve_unreadable_latch` kept a copy of them.
    preserved: Path | None = None
    #: True when there was no latch file at all.
    absent: bool = False


@dataclass
class JournalState:
    """What :meth:`StateDir.load_journal` rebuilt."""

    #: (device_id, command_id) -> (input_digest, retained receipt)
    index: dict[tuple[str, str], tuple[str, dict[str, Any]]] = field(default_factory=dict)
    #: (device_id, command_id) -> the ``begin`` entry of a command that has no outcome.
    pending: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    #: Live cumulative draws, ``{"key", "window", "t", "amount", "id"}``.
    draws: list[dict[str, Any]] = field(default_factory=list)
    #: device_id -> highest revision the previous runs reached.
    revisions: dict[str, int] = field(default_factory=dict)


class StateDir:
    """One endpoint's state directory: lock, latch file and journal.

    Construct it before anything else is loaded: it takes the directory's lock
    (:class:`StateDirError` when another endpoint holds it).  Latch writes and
    journal appends are serialised by two internal locks of their own (a slow
    journal fsync never delays an e-stop's latch write); neither takes any
    other lock.
    """

    def __init__(self, path: str | os.PathLike[str], endpoint_id: str, *, fsync: bool = False) -> None:
        self.path = Path(path).expanduser()
        self.endpoint_id = endpoint_id
        self.fsync = bool(fsync)
        self._latch_lock = threading.Lock()
        self._write_lock = threading.Lock()  # the journal
        self._journal: Any = None
        self._lock_handle: Any = None
        self._closed = False
        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StateDirError(f"state_dir {self.path} cannot be created: {exc}") from exc
        if not self.path.is_dir():
            raise StateDirError(f"state_dir {self.path} is not a directory")
        self._acquire_lock()

    # -- paths ---------------------------------------------------------
    @property
    def evidence_path(self) -> Path:
        return self.path / EVIDENCE_FILE

    @property
    def latch_path(self) -> Path:
        return self.path / LATCH_FILE

    @property
    def journal_path(self) -> Path:
        return self.path / JOURNAL_FILE

    # -- lock ----------------------------------------------------------
    def _acquire_lock(self) -> None:
        lock_path = self.path / LOCK_FILE
        try:
            handle = open(lock_path, "a+", encoding="utf-8")
        except OSError as exc:
            raise StateDirError(f"state_dir {self.path}: cannot open {LOCK_FILE}: {exc}") from exc
        if _fcntl is not None:
            try:
                _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            except OSError as exc:
                try:
                    handle.seek(0)
                    holder = handle.read().strip()
                except OSError:
                    holder = ""
                handle.close()
                raise StateDirError(
                    f"state_dir {self.path} is in use by another endpoint"
                    + (f" ({holder})" if holder else "")
                    + "; one endpoint process per state_dir"
                ) from exc
            try:
                handle.seek(0)
                handle.truncate()
                handle.write(f"pid {os.getpid()} endpoint {self.endpoint_id}\n")
                handle.flush()
            except OSError:
                pass
        self._lock_handle = handle

    def close(self) -> None:
        """Close the journal and release the lock (idempotent)."""
        with self._latch_lock, self._write_lock:
            if self._closed:
                return
            self._closed = True
            if self._journal is not None:
                try:
                    self._journal.close()
                except OSError:
                    pass
                self._journal = None
            handle, self._lock_handle = self._lock_handle, None
        if handle is not None:
            try:
                if _fcntl is not None:
                    _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()

    @property
    def closed(self) -> bool:
        return self._closed

    # -- latch ---------------------------------------------------------
    def load_latches(self) -> LatchState:
        """Read ``latch.json``.

        An absent file is reported in :attr:`LatchState.absent` (a fresh
        directory, unless the evidence already holds receipts).  An existing
        file that cannot be read or does not have the expected shape is
        reported in :attr:`LatchState.unreadable`: the server then starts with
        every device latched.  Nothing is changed on disk here: the file stays
        in place (so a start refused later still finds it unreadable) until
        :meth:`preserve_unreadable_latch` copied it and :meth:`write_latches`
        replaced it.  A file written for another endpoint refuses the start.
        """
        path = self.latch_path
        if not path.exists() and not path.is_symlink():
            return LatchState(absent=True)
        problem: str | None = None
        entries: dict[str, dict[str, Any]] = {}
        raw: bytes | None = None
        try:
            raw = path.read_bytes()
            document = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            document = None
            problem = f"{type(exc).__name__}: {exc}"
        if problem is None:
            if not isinstance(document, Mapping):
                problem = "not a JSON object"
            elif document.get("format") != LATCH_FORMAT:
                problem = f"format is {document.get('format')!r}, expected {LATCH_FORMAT!r}"
            elif document.get("endpoint_id") != self.endpoint_id:
                raise StateDirError(
                    f"state_dir {self.path}: {LATCH_FILE} belongs to endpoint "
                    f"{document.get('endpoint_id')!r}, not {self.endpoint_id!r}")
            elif not isinstance(document.get("devices"), Mapping):
                problem = "devices is not an object"
            else:
                for device_id, entry in document["devices"].items():
                    if not isinstance(entry, Mapping) or not isinstance(entry.get("latched"), bool):
                        problem = f"device {device_id!r}: latched is not a boolean"
                        break
                    entries[str(device_id)] = {
                        "latched": entry["latched"],
                        "reason": entry.get("reason") if isinstance(entry.get("reason"), str) else None,
                        "since": entry.get("since") if isinstance(entry.get("since"), str) else None,
                    }
        if problem is None:
            return LatchState(entries=entries)
        return LatchState(unreadable=problem, raw=raw)

    def preserve_unreadable_latch(self, latches: LatchState) -> Path | None:
        """Keep a copy of an unreadable latch file as ``latch.json.unreadable-<ULID>``.

        A copy, never a rename: ``latch.json`` itself is only ever replaced
        atomically by :meth:`write_latches`, so no crash leaves the directory
        without a latch file.  Returns None when the bytes could not be read
        (or the copy failed).
        """
        if latches.raw is None:
            return None
        kept = self.latch_path.with_name(f"{LATCH_FILE}.unreadable-{canonical.ulid()}")
        try:
            atomic_write_bytes(kept, latches.raw, fsync=True)
        except OSError:
            return None
        latches.preserved = kept
        return kept

    def write_latches(self, entries: Mapping[str, Mapping[str, Any]]) -> None:
        """Atomically rewrite ``latch.json`` (always fsynced). Raises ``OSError``."""
        document = {
            "format": LATCH_FORMAT,
            "endpoint_id": self.endpoint_id,
            "updated_at": canonical.now_rfc3339(),
            "devices": {str(device_id): dict(entry) for device_id, entry in sorted(entries.items())},
        }
        data = json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8") + b"\n"
        with self._latch_lock:
            if self._closed:
                raise OSError("state_dir is closed")
            atomic_write_bytes(self.latch_path, data, fsync=True)

    # -- journal -------------------------------------------------------
    def _read_journal(self) -> list[dict[str, Any]] | None:
        """Parse the journal; None when absent.  A torn final line is dropped."""
        path = self.journal_path
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise StateDirError(f"state_dir {self.path}: cannot read {JOURNAL_FILE}: {exc}") from exc
        lines = data.split(b"\n")
        torn = lines.pop() if lines else b""  # bytes after the last newline
        entries: list[dict[str, Any]] = []
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise StateDirError(
                    f"state_dir {self.path}: {JOURNAL_FILE} line {number} is not JSON ({exc}); "
                    f"move {JOURNAL_FILE} away to rebuild the index from {EVIDENCE_FILE} "
                    "(commands in flight at the crash are then not reconciled)") from exc
            if not isinstance(entry, dict) or entry.get("op") not in _JOURNAL_OPS:
                raise StateDirError(
                    f"state_dir {self.path}: {JOURNAL_FILE} line {number} is not a journal entry")
            entries.append(entry)
        if torn.strip():
            try:
                entry = json.loads(torn.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                warnings.warn(
                    f"state_dir {self.path}: ignoring a torn final line of {JOURNAL_FILE} "
                    "(a crash during an append); the evidence log fills the gap",
                    RuntimeWarning, stacklevel=4)
            else:
                if isinstance(entry, dict) and entry.get("op") in _JOURNAL_OPS:
                    entries.append(entry)
        return entries

    def load_journal(self, records: list[Mapping[str, Any]]) -> JournalState:
        """Rebuild the journal state against the verified evidence ``records``."""
        entries = self._read_journal()
        state = JournalState(index=derive_index(records))
        for record in records:
            if not isinstance(record, Mapping) or not _is_receipt(record):
                continue
            device_id, revision = record.get("device_id"), record.get("state_revision_after")
            if (isinstance(device_id, str) and isinstance(revision, int)
                    and not isinstance(revision, bool)):
                state.revisions[device_id] = max(state.revisions.get(device_id, 0), revision)
        if entries is None:
            return state
        by_seq = {seq: record for record in records if (seq := _seq_of(record)) is not None}
        if entries and entries[0].get("op") == "header":
            header, body = entries[0], entries[1:]
            if header.get("format") != JOURNAL_FORMAT:
                raise StateDirError(
                    f"state_dir {self.path}: {JOURNAL_FILE} format is {header.get('format')!r}, "
                    f"expected {JOURNAL_FORMAT!r}")
            if header.get("endpoint_id") != self.endpoint_id:
                raise StateDirError(
                    f"state_dir {self.path}: {JOURNAL_FILE} belongs to endpoint "
                    f"{header.get('endpoint_id')!r}, not {self.endpoint_id!r}")
            revisions = header.get("revisions")
            if isinstance(revisions, Mapping):
                for device_id, revision in revisions.items():
                    if isinstance(revision, int) and not isinstance(revision, bool):
                        state.revisions[str(device_id)] = max(state.revisions.get(str(device_id), 0), revision)
        else:
            body = entries
        draws: dict[str, dict[str, Any]] = {}
        last_seq = max(by_seq) if by_seq else 0
        #: key -> (its begin entry or None, the put) for a retained receipt past
        #: the end of the evidence: the evidence lost its tail while the journal
        #: kept its own (a power failure without fsync=True reorders the two
        #: files).  The command ran; its receipt is gone.
        lost: dict[tuple[str, str], tuple[dict[str, Any] | None, dict[str, Any]]] = {}
        for entry in body:
            op = entry.get("op")
            key = _key_of(entry)
            if op == "put":
                seq = entry.get("seq")
                seq_ok = isinstance(seq, int) and not isinstance(seq, bool)
                if key is not None and seq_ok and seq > last_seq:
                    begin = state.pending.pop(key, None)
                    if begin is None and key in lost:
                        begin = lost[key][0]
                    lost[key] = (begin, entry)
                    continue
                record = by_seq.get(seq) if seq_ok else None
                if (key is None or record is None or record.get("receipt_id") != entry.get("receipt_id")
                        or _key_of(record) != key):
                    raise StateDirError(
                        f"state_dir {self.path}: {JOURNAL_FILE} retains receipt "
                        f"{entry.get('receipt_id')!r} at evidence seq {seq!r}, which {EVIDENCE_FILE} "
                        "does not hold; the index and the evidence disagree")
                state.pending.pop(key, None)
                lost.pop(key, None)
            elif op == "drop":
                if key is not None:
                    state.pending.pop(key, None)
            elif op == "begin":
                if key is not None:
                    state.pending[key] = dict(entry)
            elif op == "end":
                if key is not None:
                    state.pending.pop(key, None)
            elif op == "draw":
                if (isinstance(entry.get("id"), str) and isinstance(entry.get("key"), str)
                        and isinstance(entry.get("window"), str)
                        and isinstance(entry.get("amount"), (int, float))
                        and isinstance(entry.get("t"), (int, float))):
                    draws[entry["id"]] = dict(entry)
            elif op == "release":
                draws.pop(str(entry.get("id")), None)
        for key, (begin, put) in lost.items():
            if key in state.index:
                # An earlier outcome of the command (the unknown answer at its
                # deadline) is in the evidence: it stays the retained receipt.
                continue
            if begin is None:
                raise StateDirError(
                    f"state_dir {self.path}: {JOURNAL_FILE} retains receipt {put.get('receipt_id')!r} "
                    f"at evidence seq {put.get('seq')!r}, past the end of {EVIDENCE_FILE} "
                    f"(seq {last_seq}), and records no begin for command {key[1]!r}")
            # Recorded as unknown (the command ran; its receipt was lost).
            state.pending[key] = {**begin, "lost_receipt_id": put.get("receipt_id")}
        # A begin whose outcome reached the evidence (the crash hit between the
        # evidence append and the journal line) is settled by that receipt: one
        # of the same command id and input, recorded after the begin, that is
        # not rejected (a receipt derive_index retains).  A rejected receipt may
        # be a duplicate's refusal while the command was still running
        # (COMMAND_ID_REUSE, DEVICE.BUSY): it never settles the command.
        for key, begin in list(state.pending.items()):
            after = begin.get("evidence_seq")
            after = after if isinstance(after, int) and not isinstance(after, bool) else 0
            for record in records:
                seq = _seq_of(record)
                if (seq is not None and seq > after and _is_receipt(record) and _key_of(record) == key
                        and record.get("status") not in ("accepted", "running", "rejected")
                        and record.get("input_digest") == begin.get("input_digest")):
                    state.pending.pop(key, None)
                    break
        state.draws = list(draws.values())
        return state

    def compact(self, journal: JournalState) -> None:
        """Atomically rewrite the journal from ``journal``, then open it for appends."""
        lines = [_encode_line({
            "op": "header",
            "format": JOURNAL_FORMAT,
            "endpoint_id": self.endpoint_id,
            "created_at": canonical.now_rfc3339(),
            "revisions": dict(sorted(journal.revisions.items())),
        })]
        retained = sorted(journal.index.items(), key=lambda item: _seq_of(item[1][1]) or 0)
        for (device_id, command_id), (digest, receipt) in retained:
            lines.append(_encode_line({
                "op": "put", "device_id": device_id, "command_id": command_id, "input_digest": digest,
                "receipt_id": receipt.get("receipt_id"), "seq": _seq_of(receipt),
            }))
        for draw in journal.draws:
            lines.append(_encode_line({"op": "draw", **{k: draw[k] for k in ("key", "window", "t", "amount", "id")}}))
        for begin in journal.pending.values():  # kept only when the caller could not settle them
            lines.append(_encode_line(begin))
        with self._write_lock:
            if self._closed:
                raise OSError("state_dir is closed")
            atomic_write_bytes(self.journal_path, b"".join(lines), fsync=True)
            self._journal = open(self.journal_path, "ab")

    def append(self, entry: Mapping[str, Any]) -> None:
        """Append one journal line (flushed; fsynced when ``fsync``). Raises ``OSError``."""
        data = _encode_line(entry)
        with self._write_lock:
            if self._closed or self._journal is None:
                raise OSError("state_dir is closed")
            self._journal.write(data)
            self._journal.flush()
            if self.fsync:
                os.fsync(self._journal.fileno())
