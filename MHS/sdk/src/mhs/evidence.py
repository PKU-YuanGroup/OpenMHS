"""Tamper-evident evidence log for MHS receipts (normative MHS-000 §6.6 / MHS-002 §8).

Chain construction (MHS-004 §8.1, EVID-010)::

    digest_0 = sha256(JCS(genesis_document))
    digest_i = sha256(JCS(receipt_i without "evidence") || digest_{i-1})
    receipt_i.evidence = {seq: i, prev_digest: digest_{i-1}, digest: digest_i}

``genesis_document`` is an endpoint-level record
``{endpoint_id, created_at, mhs_version, instance_salt}`` whose digest is
published in ``evidence.export.endpoint_info.genesis_digest``.  ``seq`` is a
contiguous integer starting at 1 and is per-endpoint, not per-session.

Export bundle (MHS-002 §14.1)::

    {"bundle_version": "1.0.0",
     "endpoint_info": {"endpoint_id", "mhs_version", "server",
                       "genesis_digest"},
     "created_at", "receipts": [...], "head_digest",
     "telemetry": [], "truncation": null, "signature": null}

:func:`verify_bundle` re-derives the chain offline, validates every receipt
against ``receipt.schema.json`` and reports *all* failures (not just the
first), as structured objects ``{seq, mhs_code, detail}`` (EVID-015/016).

The log is append-only: an endpoint that cannot append MUST fail the mutation
rather than lose the audit record.  Optional JSON Lines persistence writes one
record per line (genesis first) and verifies the chain on load.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import _ids, canonical
from .errors import ErrorCode, MHSError

__all__ = [
    "BUNDLE_VERSION",
    "GENESIS_KIND",
    "GENESIS_SEQ",
    "FIRST_RECEIPT_SEQ",
    "EvidenceError",
    "EvidenceLog",
    "VerifyReport",
    "compute_record_digest",
    "compute_genesis_digest",
    "export_bundle",
    "make_genesis_document",
    "verify_bundle",
    "verify_chain",
]

BUNDLE_VERSION = "1.0.0"
SUPPORTED_BUNDLE_VERSIONS = frozenset({"1.0", "1.0.0"})
GENESIS_KIND = "genesis"
GENESIS_SEQ = 0
FIRST_RECEIPT_SEQ = 1
_CHAIN_SEPARATOR = b""

#: Signature status values reported by :class:`VerifyReport` (EVID-017).
SIGNATURE_ABSENT = "absent"
SIGNATURE_UNVERIFIABLE = "unverifiable"
SIGNATURE_VALID = "valid"
SIGNATURE_INVALID = "invalid"
SIGNATURE_STATUSES = frozenset(
    {SIGNATURE_ABSENT, SIGNATURE_UNVERIFIABLE, SIGNATURE_VALID, SIGNATURE_INVALID}
)

#: Receipt-schema verification states reported by :class:`VerifyReport`.
SCHEMA_VALIDATED = "validated"
SCHEMA_UNAVAILABLE = "unavailable"
SCHEMA_SKIPPED = "skipped"
_SCHEMA_STATES = frozenset({SCHEMA_VALIDATED, SCHEMA_UNAVAILABLE, SCHEMA_SKIPPED})

#: Error codes used for evidence failures that are not chain-link failures.
SCHEMA_INVALID_CODE = "MHS.EVIDENCE.SCHEMA_INVALID"
SCHEMA_UNAVAILABLE_CODE = "MHS.EVIDENCE.SCHEMA_UNAVAILABLE"
SIGNATURE_INVALID_CODE = "MHS.EVIDENCE.SIGNATURE_INVALID"
SIGNATURE_UNVERIFIABLE_CODE = "MHS.EVIDENCE.SIGNATURE_UNVERIFIABLE"

#: JWS algorithms MHS permits for detached evidence signatures (EVID-017).
SUPPORTED_SIGNATURE_ALGORITHMS = frozenset({"EdDSA", "ES256"})

#: Optional hook: ``key_resolver(signature, head_digest) -> bool``.
KeyResolver = Callable[[Mapping[str, Any], str | None], bool]


class EvidenceError(MHSError):
    """Raised when the evidence log is corrupted or cannot be appended to."""


def make_genesis_document(
    endpoint_id: str,
    *,
    mhs_version: str = "1.0",
    instance_salt: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the normative genesis document for ``endpoint_id``."""
    return {
        "endpoint_id": endpoint_id,
        "created_at": created_at or canonical.now_rfc3339(),
        "mhs_version": mhs_version,
        "instance_salt": instance_salt or canonical.ulid(),
    }


def compute_genesis_digest(document: Mapping[str, Any]) -> str:
    """Return ``digest_0 = sha256(JCS(genesis_document))``."""
    core = {
        key: value
        for key, value in document.items()
        if key not in ("digest", "seq", "kind")
    }
    return canonical.digest(core)


def compute_record_digest(record: Mapping[str, Any], prev_digest: str | None) -> str:
    """Return ``sha256(JCS(record without "evidence") || prev_digest)``.

    ``prev_digest`` must be a well-formed ``sha256:<64 lowercase hex>`` string
    (or ``None`` for a headless record).  Malformed values raise
    :class:`mhs.canonical.DigestError` *before* hashing, so no non-ASCII
    ``prev_digest`` can escape as :class:`UnicodeEncodeError` (CODE-005).
    """
    if prev_digest is not None and not canonical.is_digest(prev_digest):
        raise canonical.DigestError(
            f"prev_digest is not a sha256:<64 lowercase hex> digest: {prev_digest!r}"
        )
    core = {key: value for key, value in record.items() if key != "evidence"}
    payload = canonical.jcs(core)
    if prev_digest is not None:
        payload = payload + _CHAIN_SEPARATOR + prev_digest.encode("ascii")
    return canonical.digest_bytes(payload)


class VerifyReport(dict):
    """Result of verifying an evidence bundle.

    Keys: ``valid`` (bool), ``checked`` (int), ``head_digest`` (str|None),
    ``errors`` (list of structured ``{seq, mhs_code, detail}`` objects),
    ``signature`` (``absent|unverifiable|valid|invalid``) and ``schema``
    (``validated|unavailable|skipped``).  Attribute access is provided for
    convenience (``report.valid``).
    """

    @property
    def valid(self) -> bool:
        """True when the chain, receipts and disclosed signature all verified."""
        return bool(self.get("valid"))

    @property
    def checked(self) -> int:
        """Number of receipt records checked."""
        return int(self.get("checked", 0))

    @property
    def errors(self) -> list[dict[str, Any]]:
        """Structured verification failures (empty when valid)."""
        return list(self.get("errors") or [])

    @property
    def error_messages(self) -> list[str]:
        """Human-readable versions of :attr:`errors`."""
        return [
            str(error.get("detail")) if isinstance(error, Mapping) else str(error)
            for error in self.get("errors") or []
        ]

    @property
    def head_digest(self) -> str | None:
        """Head digest recomputed from the bundle, or ``None``."""
        return self.get("head_digest")

    @property
    def signature(self) -> str:
        """Signature verification status (EVID-017)."""
        return str(self.get("signature") or SIGNATURE_ABSENT)

    @property
    def schema(self) -> str:
        """Receipt-schema verification state."""
        return str(self.get("schema") or SCHEMA_SKIPPED)

    def to_dict(self) -> dict[str, Any]:
        """Return the plain JSON-ready report (normative response shape)."""
        return {
            "valid": self.valid,
            "checked": self.checked,
            "head_digest": self.head_digest,
            "errors": self.errors,
            "signature": self.signature,
            "schema": self.schema,
        }


def _error(
    errors: list[dict[str, Any]],
    seq: int | None,
    detail: str,
    code: str = "MHS.EVIDENCE.CHAIN_BROKEN",
) -> None:
    """Append one structured verification error."""
    errors.append({"seq": seq, "mhs_code": code, "detail": detail})


def _receipt_schema_errors(receipt: Mapping[str, Any]) -> list[str]:
    """Validate one receipt against ``receipt.schema.json``.

    Calls the real :func:`mhs.schema.store.default_store` validation API and
    returns its error strings.  A missing or malformed schema set propagates
    the schema-layer exception (:class:`FileNotFoundError`/:class:`SchemaError`);
    callers MUST report that as an explicit incomplete verification state
    instead of silently accepting the receipt (CODE-002).
    """
    from .schema.store import default_store

    return list(default_store().validate(receipt, "receipt.schema.json"))


def _signature_shape_errors(signature: Any) -> list[str]:
    """Return reasons a detached-JWS signature object is malformed.

    Every field is type-checked before any set membership test: a JSON-domain
    list/object/bool/number must produce a structured ``invalid`` signature
    report, never an unhashable-type ``TypeError`` (RECHECK-CODE-001).
    """
    if not isinstance(signature, Mapping):
        return [f"signature must be an object, got {type(signature).__name__}"]
    problems: list[str] = []
    algorithm = signature.get("alg")
    if not isinstance(algorithm, str):
        problems.append(
            f"signature.alg must be a string, got {type(algorithm).__name__}"
        )
    elif algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
        problems.append(
            f"signature.alg must be one of {sorted(SUPPORTED_SIGNATURE_ALGORITHMS)}, "
            f"got {algorithm!r}"
        )
    key_id = signature.get("key_id")
    if not isinstance(key_id, str) or not key_id:
        problems.append("signature.key_id must be a non-empty string")
    jws = signature.get("jws")
    if not isinstance(jws, str) or not jws:
        problems.append("signature.jws must be a non-empty string")
    return problems


def _apply_signature_status(
    report: VerifyReport,
    bundle: Mapping[str, Any],
    key_resolver: KeyResolver | None,
) -> str:
    """Inspect ``bundle.signature`` and record its truthful status on ``report``.

    ``absent`` when the bundle has no signature; ``invalid`` for a malformed
    signature object or a resolver rejection; ``unverifiable`` when a
    well-formed signature cannot be checked (no resolver, resolver failure);
    ``valid`` only when the supplied resolver returns ``True``.  Only ``valid``
    leaves the report's ``valid`` flag untouched; every other present-but-not-
    verified state is a failure with a signature-specific ``mhs_code`` (never a
    chain failure), per EVID-017.
    """
    signature = bundle.get("signature")
    if signature is None:
        report["signature"] = SIGNATURE_ABSENT
        return SIGNATURE_ABSENT

    errors: list[dict[str, Any]] = report.setdefault("errors", [])
    problems = _signature_shape_errors(signature)
    if problems:
        report["signature"] = SIGNATURE_INVALID
        report["valid"] = False
        _error(
            errors,
            None,
            "malformed evidence signature: " + "; ".join(problems),
            SIGNATURE_INVALID_CODE,
        )
        return SIGNATURE_INVALID

    head = report.get("head_digest")
    if not canonical.is_digest(head):
        report["signature"] = SIGNATURE_UNVERIFIABLE
        report["valid"] = False
        _error(
            errors,
            None,
            "cannot verify the evidence signature: the bundle has no valid "
            "recomputed head_digest",
            SIGNATURE_UNVERIFIABLE_CODE,
        )
        return SIGNATURE_UNVERIFIABLE

    if key_resolver is None:
        report["signature"] = SIGNATURE_UNVERIFIABLE
        report["valid"] = False
        _error(
            errors,
            None,
            "no signature key resolver is available; EVID-017 requires "
            "signature: 'unverifiable' rather than success",
            SIGNATURE_UNVERIFIABLE_CODE,
        )
        return SIGNATURE_UNVERIFIABLE

    try:
        verified = key_resolver(dict(signature), head)
    except Exception as exc:  # noqa: BLE001 - untrusted resolver: report, don't escape
        report["signature"] = SIGNATURE_UNVERIFIABLE
        report["valid"] = False
        _error(
            errors,
            None,
            f"signature key resolver failed: {type(exc).__name__}: {exc}",
            SIGNATURE_UNVERIFIABLE_CODE,
        )
        return SIGNATURE_UNVERIFIABLE

    if verified is True:
        report["signature"] = SIGNATURE_VALID
        return SIGNATURE_VALID
    if verified is False:
        report["signature"] = SIGNATURE_INVALID
        report["valid"] = False
        _error(
            errors,
            None,
            "evidence signature did not verify against the resolved key",
            SIGNATURE_INVALID_CODE,
        )
        return SIGNATURE_INVALID
    report["signature"] = SIGNATURE_UNVERIFIABLE
    report["valid"] = False
    _error(
        errors,
        None,
        "signature key resolver returned a non-boolean result; EVID-017 "
        "requires True or False",
        SIGNATURE_UNVERIFIABLE_CODE,
    )
    return SIGNATURE_UNVERIFIABLE


class EvidenceLog:
    """An append-only, hash-chained log of receipts.

    Parameters
    ----------
    endpoint_id:
        Endpoint identity recorded in the genesis document.
    path:
        Optional JSON Lines file; an existing file is loaded and verified, new
        records are appended with ``flush`` (and ``fsync`` when requested).
    mhs_version:
        Protocol version recorded in the genesis document.
    server:
        Optional ``{"name", "version"}`` advertised in ``bundle.endpoint_info``.
    genesis:
        Optional existing genesis document (e.g. restored on restart).  When
        omitted a fresh one with a new ``instance_salt`` is created.
    strict:
        Raise :class:`EvidenceError` when loading a corrupt log.
    fsync:
        fsync after every append (durable, slower).
    recover_torn_tail:
        Before loading ``path``, repair a final line that a crash cut short
        during an append: its bytes are moved to ``<path>.torn-<ULID>`` and
        the file is truncated to the last complete record (that record was
        never returned to anyone: an append returns only after its line was
        written).  A complete final record that lost only its newline gets
        the newline back.  What was done is in :attr:`recovered_tail`.  Any
        other damaged line still fails verification.
    """

    def __init__(
        self,
        endpoint_id: str,
        path: str | os.PathLike[str] | None = None,
        *,
        mhs_version: str = "1.0",
        server: Mapping[str, Any] | None = None,
        genesis: Mapping[str, Any] | None = None,
        strict: bool = True,
        fsync: bool = False,
        recover_torn_tail: bool = False,
    ) -> None:
        """Create an evidence log, loading and verifying ``path`` if it exists."""
        self.endpoint_id = endpoint_id
        self.mhs_version = mhs_version
        self.server = dict(server or {"name": _ids.DIST_NAME, "version": _ids.SDK_VERSION})
        self.path = Path(path).expanduser() if path is not None else None
        self.fsync = bool(fsync)
        self._lock = threading.RLock()
        self._records: list[dict[str, Any]] = []
        self._head: str = ""
        self._genesis_digest: str = ""
        self._genesis: dict[str, Any] | None = None
        self.load_errors: list[str] = []
        #: ``{"bytes": n, "kept_as": path}`` (or ``{"newline_added": True}``)
        #: when ``recover_torn_tail`` repaired the file; None otherwise.
        self.recovered_tail: dict[str, Any] | None = None
        self._closed = False
        if self.path is not None and self.path.exists():
            if recover_torn_tail:
                self._recover_torn_tail()
            self._load(strict=strict)
        else:
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self._init_genesis(genesis)

    # -- construction --------------------------------------------------

    def _init_genesis(self, genesis: Mapping[str, Any] | None = None) -> None:
        """Create (or adopt) and persist the genesis document for this log."""
        document = (
            dict(genesis)
            if genesis is not None
            else make_genesis_document(self.endpoint_id, mhs_version=self.mhs_version)
        )
        digest = compute_genesis_digest(document)
        record = {
            "kind": GENESIS_KIND,
            "seq": GENESIS_SEQ,
            "genesis_document": document,
            "digest": digest,
        }
        self._genesis = document
        self._genesis_digest = digest
        self._head = digest
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                if self.fsync:
                    os.fsync(handle.fileno())

    def _recover_torn_tail(self) -> None:
        """Repair a final line cut short by a crash during an append (see ``recover_torn_tail``)."""
        try:
            data = self.path.read_bytes()
        except OSError:
            return  # _load reports the read failure
        if not data or data.endswith(b"\n"):
            return
        cut = data.rfind(b"\n") + 1
        tail = data[cut:]
        try:
            json.loads(tail.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            pass
        else:
            # A complete record whose newline was not written: the next append
            # must not continue its line.
            with self.path.open("ab") as handle:
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.recovered_tail = {"newline_added": True}
            return
        kept = self.path.with_name(f"{self.path.name}.torn-{canonical.ulid()}")
        kept.write_bytes(tail)
        with self.path.open("r+b") as handle:
            handle.truncate(cut)
            handle.flush()
            os.fsync(handle.fileno())
        self.recovered_tail = {"bytes": len(tail), "kept_as": str(kept)}

    def _load(self, *, strict: bool) -> None:
        """Load records from the JSONL file and verify the chain."""
        loaded: list[dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.load_errors.append(
                            f"line {line_number}: invalid JSON ({exc.msg})"
                        )
                        continue
                    if not isinstance(record, dict):
                        self.load_errors.append(
                            f"line {line_number}: record is not a JSON object"
                        )
                        continue
                    loaded.append(record)
        except OSError as exc:
            raise EvidenceError(
                ErrorCode.EVIDENCE_UNKNOWN,
                f"cannot read evidence log {self.path}: {exc}",
                cause=exc,
            ) from exc
        if not loaded:
            self._init_genesis()
            return
        first = loaded[0]
        document = first.get("genesis_document") if isinstance(first, dict) else None
        if not isinstance(document, Mapping):
            self.load_errors.append("first record is not a genesis record")
            self._genesis = None
            self._records = loaded
            self._head = ""
        else:
            try:
                expected = compute_genesis_digest(document)
            except (canonical.CanonicalJSONError, canonical.DigestError, TypeError, ValueError) as exc:
                expected = None
                self.load_errors.append(
                    "genesis document is not canonical JSON: "
                    f"{type(exc).__name__}: {exc}"
                )
            if expected is not None and first.get("digest") != expected:
                self.load_errors.append("genesis digest mismatch")
            self._genesis = dict(document)
            self._genesis_digest = expected or ""
            self._records = loaded[1:]
            self._head = expected or ""
        report = verify_chain(
            self._genesis,
            self._records,
            # The genesis digest is the *start* of the chain, not the expected
            # terminal head: a nonempty log ends at the final receipt digest.
            expected_head=None,
            check_receipt_schema=False,
        )
        self.load_errors.extend(report.error_messages)
        # Adopt the recomputed terminal digest so a strict reopen can append.
        self._head = report.head_digest or self._head
        if self.load_errors and strict:
            raise EvidenceError(
                ErrorCode.EVIDENCE_CHAIN_BROKEN,
                f"evidence log {self.path} failed verification",
                {"errors": self.load_errors[:20], "retryable": False},
            )

    # -- inspection ----------------------------------------------------

    @property
    def genesis(self) -> dict[str, Any]:
        """The genesis *document* (not the wrapper record)."""
        with self._lock:
            if self._genesis is None:
                self._init_genesis()
            return dict(self._genesis or {})

    @property
    def genesis_digest(self) -> str:
        """``digest_0`` of the genesis document (never the running head)."""
        with self._lock:
            if not self._genesis_digest:
                self._init_genesis()
            return self._genesis_digest

    @property
    def head(self) -> str:
        """The digest of the most recent record (genesis digest when empty)."""
        with self._lock:
            if not self._head:
                self._init_genesis()
            return self._head

    @property
    def head_digest(self) -> str:
        """Alias of :attr:`head`."""
        return self.head

    @property
    def seq(self) -> int:
        """The ``seq`` of the most recent receipt (0 when empty)."""
        with self._lock:
            return len(self._records) + GENESIS_SEQ

    @property
    def count(self) -> int:
        """Number of receipt records in the log (genesis excluded)."""
        with self._lock:
            return len(self._records)

    def records(self) -> list[dict[str, Any]]:
        """Return a deep copy of all receipt records (genesis excluded)."""
        with self._lock:
            return json.loads(json.dumps(self._records))

    def genesis_record(self) -> dict[str, Any]:
        """Return the persisted genesis wrapper record."""
        return {
            "kind": GENESIS_KIND,
            "seq": GENESIS_SEQ,
            "genesis_document": self.genesis,
            "digest": self.genesis_digest,
        }

    def endpoint_info(self) -> dict[str, Any]:
        """Return the normative ``bundle.endpoint_info`` object."""
        return {
            "endpoint_id": self.endpoint_id,
            "mhs_version": self.mhs_version,
            "server": dict(self.server),
            "genesis_digest": self.genesis_digest,
        }

    # -- appending -----------------------------------------------------

    def append(self, record: Mapping[str, Any], *, kind: str = "receipt") -> dict[str, Any]:
        """Append ``record`` to the chain and return it with its evidence link."""
        if not isinstance(record, Mapping):
            raise EvidenceError(
                ErrorCode.EVIDENCE_CHAIN_BROKEN,
                f"evidence record must be an object, got {type(record).__name__}",
            )
        with self._lock:
            if self._closed:
                raise EvidenceError(ErrorCode.TRANSPORT_CLOSED, "evidence log is closed")
            if self.load_errors:
                raise EvidenceError(
                    ErrorCode.EVIDENCE_CHAIN_BROKEN,
                    "refusing to extend a corrupt evidence chain",
                    {"errors": self.load_errors[:20], "retryable": False},
                )
            if self._genesis is None:
                self._init_genesis()
            stored = dict(record)
            stored.pop("evidence", None)
            # Receipts are validated against receipt.schema.json (closed object):
            # a top-level "kind" would make a valid receipt invalid.  Non-receipt
            # records keep their kind for log discrimination.
            if kind != "receipt":
                stored.setdefault("kind", kind)
            prev = self._head
            seq = len(self._records) + FIRST_RECEIPT_SEQ
            digest = compute_record_digest(stored, prev)
            stored["evidence"] = {
                "seq": seq,
                "prev_digest": prev,
                "digest": digest,
            }
            self._records.append(stored)
            self._head = digest
            if self.path is not None:
                try:
                    with self.path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(stored, ensure_ascii=False) + "\n")
                        handle.flush()
                        if self.fsync:
                            os.fsync(handle.fileno())
                except OSError as exc:
                    self._records.pop()
                    self._head = prev
                    raise EvidenceError(
                        ErrorCode.EVIDENCE_UNKNOWN,
                        f"cannot write evidence log {self.path}: {exc}",
                        cause=exc,
                    ) from exc
            return json.loads(json.dumps(stored))

    def append_receipt(self, receipt: Mapping[str, Any]) -> dict[str, Any]:
        """Append a receipt record (alias of :meth:`append`)."""
        return self.append(receipt, kind="receipt")

    # -- export / verify -----------------------------------------------

    def export(
        self,
        *,
        include_telemetry: bool = False,
        selection: Mapping[str, Any] | None = None,
        truncation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Export a self-contained, verifiable evidence bundle (MHS-002 §14.1)."""
        with self._lock:
            bundle: dict[str, Any] = {
                "bundle_version": BUNDLE_VERSION,
                "endpoint_info": self.endpoint_info(),
                "created_at": canonical.now_rfc3339(),
                "receipts": self.records(),
                "head_digest": self.head,
                "telemetry": [],
                "truncation": dict(truncation) if truncation else None,
                "signature": None,
                # Compatibility extras (not normative, harmless):
                "endpoint": self.endpoint_id,
                "mhs_version": self.mhs_version,
                "genesis": self.genesis_record(),
                "count": self.count,
                "include_telemetry": bool(include_telemetry),
            }
            if selection:
                bundle["selection"] = dict(selection)
            return bundle

    def verify(self) -> VerifyReport:
        """Verify the in-memory chain and return a :class:`VerifyReport`."""
        with self._lock:
            return verify_chain(
                self._genesis,
                self._records,
                expected_head=self._head,
            )

    def close(self) -> None:
        """Mark the log closed; further appends raise :class:`EvidenceError`."""
        with self._lock:
            self._closed = True

    def __len__(self) -> int:
        """Return the number of receipt records (genesis excluded)."""
        return self.count

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        """Return a short debugging representation."""
        return (
            f"EvidenceLog(endpoint_id={self.endpoint_id!r}, "
            f"count={self.count}, head={self.head[:19]}...)"
        )


def verify_chain(
    genesis: Mapping[str, Any] | None,
    receipts: Iterable[Mapping[str, Any]],
    *,
    genesis_digest: str | None = None,
    expected_head: str | None = None,
    start_seq: int = FIRST_RECEIPT_SEQ,
    truncation: Mapping[str, Any] | None = None,
    check_receipt_schema: bool = True,
    max_errors: int = 200,
) -> VerifyReport:
    """Verify a genesis document plus a sequence of receipt records.

    Implements EVID-015: every failure is reported as
    ``{seq, mhs_code, detail}``, including receipt-schema failures (reported
    separately from chain failures with ``MHS.EVIDENCE.SCHEMA_INVALID``).  A
    missing or malformed schema set is reported as
    ``MHS.EVIDENCE.SCHEMA_UNAVAILABLE`` with ``schema: "unavailable"`` rather
    than passing silently.  ``genesis`` may be ``None`` when only
    ``genesis_digest`` is available (e.g. a truncated bundle).

    Malformed JSON-domain values and malformed ``sha256:`` digest shapes never
    escape as exceptions; they become structured errors carrying the failing
    receipt ``seq`` (CODE-005).
    """
    errors: list[dict[str, Any]] = []
    checked = 0
    head: str | None = None
    schema_state = SCHEMA_SKIPPED
    schema_broken = False

    # -- genesis and initial head ----------------------------------------
    if genesis is not None:
        computed: str | None = None
        try:
            computed = compute_genesis_digest(genesis)
        except (
            canonical.CanonicalJSONError,
            canonical.DigestError,
            TypeError,
            ValueError,
            RecursionError,
        ) as exc:
            _error(
                errors,
                None,
                f"genesis document is not canonical JSON: {type(exc).__name__}: {exc}",
            )
        if genesis_digest is None:
            genesis_digest = computed
        elif computed is not None and computed != genesis_digest:
            _error(
                errors,
                None,
                "genesis_digest does not match endpoint_info.genesis_digest",
            )
        head = genesis_digest
    elif genesis_digest is not None:
        head = genesis_digest
    else:
        _error(errors, None, "bundle has neither a genesis record nor a genesis_digest")
        head = None
    if genesis_digest is not None and not canonical.is_digest(genesis_digest):
        _error(
            errors,
            None,
            f"genesis_digest is not a valid sha256 digest: {genesis_digest!r}",
        )

    # -- expected terminal head ------------------------------------------
    compare_head = expected_head is not None
    if compare_head and not canonical.is_digest(expected_head):
        _error(
            errors,
            None,
            f"head_digest is not a valid sha256 digest: {expected_head!r}",
        )
        compare_head = False

    # -- truncation / starting sequence ----------------------------------
    try:
        start_seq_value = int(start_seq)
    except (TypeError, ValueError):
        start_seq_value = FIRST_RECEIPT_SEQ
        _error(errors, None, f"start_seq is not an integer: {start_seq!r}")
    expected_seq = start_seq_value
    if truncation is not None and not isinstance(truncation, Mapping):
        _error(errors, None, "truncation is not an object")
        truncation = None
    if truncation:
        try:
            expected_seq = max(
                expected_seq,
                int(truncation.get("first_retained_seq", expected_seq)),
            )
        except (TypeError, ValueError):
            _error(errors, None, "truncation.first_retained_seq is not an integer")
    skip_first_prev = bool(truncation) and start_seq_value != FIRST_RECEIPT_SEQ

    for index, record in enumerate(receipts):
        checked += 1
        if not isinstance(record, Mapping):
            _error(errors, None, f"record {index}: not an object")
            expected_seq += 1
            continue
        link = record.get("evidence")
        if not isinstance(link, Mapping):
            _error(errors, expected_seq, f"record {index}: missing evidence link")
            expected_seq += 1
            continue

        this_seq = expected_seq
        seq = link.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            _error(errors, this_seq, f"evidence.seq must be an integer, got {seq!r}")
        elif seq != expected_seq:
            _error(
                errors,
                this_seq,
                f"unexpected seq {seq!r} (expected {expected_seq}); records must be "
                "ordered and contiguous",
            )

        prev = link.get("prev_digest")
        prev_valid = canonical.is_digest(prev)
        if not (skip_first_prev and index == 0) and prev != head:
            _error(
                errors,
                this_seq,
                "prev_digest does not match the previous chain digest",
            )
        if not prev_valid:
            _error(
                errors,
                this_seq,
                f"prev_digest is not a valid sha256 digest: {prev!r}",
            )

        actual: str | None = None
        try:
            actual = compute_record_digest(record, prev if prev_valid else None)
        except (
            canonical.CanonicalJSONError,
            canonical.DigestError,
            TypeError,
            ValueError,
            RecursionError,
        ) as exc:
            _error(
                errors,
                this_seq,
                "record cannot be canonicalised for hashing: "
                f"{type(exc).__name__}: {exc}",
            )

        claimed = link.get("digest")
        claimed_valid = canonical.is_digest(claimed)
        if not claimed_valid:
            _error(
                errors,
                this_seq,
                f"evidence.digest is not a valid sha256 digest: {claimed!r}",
            )
        if actual is not None and claimed != actual:
            _error(
                errors,
                this_seq,
                f"digest mismatch (recomputed {actual}, receipt claims {claimed!r})",
            )

        if check_receipt_schema and not schema_broken:
            try:
                details = _receipt_schema_errors(record)
            except Exception as exc:  # noqa: BLE001 - untrusted schema set
                schema_broken = True
                schema_state = SCHEMA_UNAVAILABLE
                _error(
                    errors,
                    this_seq,
                    "receipt schema validation unavailable: "
                    f"{type(exc).__name__}: {exc}",
                    SCHEMA_UNAVAILABLE_CODE,
                )
            else:
                schema_state = SCHEMA_VALIDATED
                # EVID-015: report every failure found, not the first.
                for detail in details:
                    _error(
                        errors,
                        this_seq,
                        f"receipt schema: {detail}",
                        SCHEMA_INVALID_CODE,
                    )

        if claimed_valid:
            head = claimed
        elif actual is not None:
            head = actual
        elif prev_valid:
            head = prev
        expected_seq += 1
        if len(errors) >= max_errors:
            _error(errors, None, "further errors suppressed")
            break

    if compare_head and head != expected_head:
        _error(
            errors,
            None,
            f"head_digest mismatch (bundle claims {expected_head!r}, chain head is {head!r})",
        )
    return VerifyReport(
        valid=not errors,
        checked=checked,
        head_digest=head,
        errors=errors,
        signature=SIGNATURE_ABSENT,
        schema=schema_state,
    )


def _resolve_bundle_parts(
    bundle: Mapping[str, Any],
) -> tuple[
    Mapping[str, Any] | None,
    str | None,
    list[Mapping[str, Any]],
    Mapping[str, Any] | None,
    list[dict[str, Any]],
]:
    """Extract ``(genesis_document, genesis_digest, receipts, truncation, errors)``."""
    errors: list[dict[str, Any]] = []
    version = bundle.get("bundle_version", BUNDLE_VERSION)
    # RECHECK-CODE-001: a JSON array/object/bool/number is not a supported
    # version and is not hashable either; type-check before set membership so
    # malformed metadata is reported as a structured field error.
    if not isinstance(version, str):
        _error(
            errors,
            None,
            f"bundle_version must be a string, got {type(version).__name__}",
        )
    elif version not in SUPPORTED_BUNDLE_VERSIONS:
        _error(errors, None, f"unsupported bundle_version {version!r}")
    info = bundle.get("endpoint_info")
    genesis_digest: str | None = None
    if isinstance(info, Mapping):
        candidate = info.get("genesis_digest")
        if isinstance(candidate, str):
            genesis_digest = candidate
    if genesis_digest is None:
        candidate = bundle.get("genesis_digest")
        if isinstance(candidate, str):
            genesis_digest = candidate
    genesis = bundle.get("genesis")
    genesis_document: Mapping[str, Any] | None = None
    if isinstance(genesis, Mapping):
        inner = genesis.get("genesis_document")
        genesis_document = inner if isinstance(inner, Mapping) else genesis
        digest = genesis.get("digest")
        if genesis_digest is None and isinstance(digest, str):
            genesis_digest = digest
    receipts = bundle.get("receipts")
    receipt_list: list[Mapping[str, Any]] = []
    if receipts is None:
        _error(errors, None, "bundle has no receipts member", "MHS.EVIDENCE.UNKNOWN")
    elif not isinstance(receipts, list):
        _error(errors, None, "bundle receipts is not an array", "MHS.EVIDENCE.UNKNOWN")
    else:
        receipt_list = receipts
    truncation = bundle.get("truncation")
    if not isinstance(truncation, Mapping):
        truncation = None
    return genesis_document, genesis_digest, receipt_list, truncation, errors


def verify_bundle(
    bundle: Mapping[str, Any],
    *,
    key_resolver: KeyResolver | None = None,
) -> VerifyReport:
    """Verify an exported evidence bundle offline (EVID-015/EVID-017).

    Returns a :class:`VerifyReport` with ``valid``, ``checked``,
    ``head_digest``, ``errors`` (structured ``{seq, mhs_code, detail}``),
    ``signature`` (``absent|unverifiable|valid|invalid``) and ``schema``
    (``validated|unavailable|skipped``).

    ``key_resolver`` is the optional detached-JWS hook required by EVID-017:
    ``key_resolver(signature_mapping, head_digest) -> bool``.  Without it a
    present, well-formed signature is reported as ``signature: "unverifiable"``
    and verification fails with ``MHS.EVIDENCE.SIGNATURE_UNVERIFIABLE`` (never
    a chain failure and never a silent success).  A resolver returning ``False``
    yields ``signature: "invalid"``; a malformed signature object is ``invalid``
    even when a resolver is supplied.
    """
    if not isinstance(bundle, Mapping):
        return VerifyReport(
            valid=False,
            checked=0,
            head_digest=None,
            errors=[
                {
                    "seq": None,
                    "mhs_code": "MHS.EVIDENCE.CHAIN_BROKEN",
                    "detail": "bundle is not a JSON object",
                }
            ],
            signature=SIGNATURE_ABSENT,
            schema=SCHEMA_SKIPPED,
        )
    genesis_document, genesis_digest, receipts, truncation, pre_errors = (
        _resolve_bundle_parts(bundle)
    )
    if pre_errors and ("receipts" not in bundle or bundle.get("receipts") is None):
        report = VerifyReport(
            valid=False,
            checked=0,
            head_digest=genesis_digest,
            errors=pre_errors,
            signature=SIGNATURE_ABSENT,
            schema=SCHEMA_SKIPPED,
        )
        _apply_signature_status(report, bundle, key_resolver)
        return report
    start_seq = FIRST_RECEIPT_SEQ
    if truncation is not None:
        try:
            start_seq = int(truncation.get("first_retained_seq", FIRST_RECEIPT_SEQ))
        except (TypeError, ValueError):
            start_seq = FIRST_RECEIPT_SEQ
    expected_head = bundle.get("head_digest")
    if not canonical.is_digest(expected_head):
        _error(
            pre_errors,
            None,
            f"head_digest is not a valid sha256 digest: {expected_head!r}",
        )
        expected_head_arg: str | None = None
    else:
        expected_head_arg = expected_head
    report = verify_chain(
        genesis_document,
        receipts,
        genesis_digest=genesis_digest,
        expected_head=expected_head_arg,
        start_seq=start_seq,
        truncation=truncation,
    )
    if pre_errors:
        report["errors"] = list(pre_errors) + list(report.errors)
        report["valid"] = False
    _apply_signature_status(report, bundle, key_resolver)
    return report


def export_bundle(
    log: EvidenceLog,
    *,
    include_telemetry: bool = False,
    selection: Mapping[str, Any] | None = None,
    truncation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper around :meth:`EvidenceLog.export`."""
    return log.export(
        include_telemetry=include_telemetry,
        selection=selection,
        truncation=truncation,
    )
