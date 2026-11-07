"""MHS error taxonomy and exception type (generated from the normative registry).

Two layers of error information travel on the wire:

* the **JSON-RPC** ``code`` (an integer in ``-32000..-32099`` for server
  errors, plus the standard ``-32700..-32603`` codes) tells a generic
  JSON-RPC peer *how* the request failed structurally;
* ``error.data.mhs_code`` is the **stable semantic code**
  (``MHS.SAFETY.INTERLOCK_OPEN``).  Implementations MUST branch on
  ``mhs_code``, never on the human-readable message.

The single source of truth is the normative error registry
``MHS/spec/errors.json`` (``errors.schema.json``; appendix MHS-B is generated
from it too).  The table between the ``BEGIN GENERATED``/``END GENERATED``
markers below is written by ``MHS/sdk/tools/gen_errors.py``, so the SDK stays
stdlib-only and needs no spec checkout at runtime.  Edit ``errors.json`` and
run the generator; ``gen_errors.py --check`` fails when the two drift.

:data:`DRIVER_SUBSET` is the small set of codes a driver or bridge may raise
(through ``mhs.signals.DriverFailed``); every other code is produced by the
runtime.  :data:`DEPRECATED_CODES` maps deprecated registry codes to their
replacement; they stay registered (and are not rewritten) during 0.9.

Legacy names from earlier SDK drafts remain importable through
:data:`LEGACY_ALIASES`/:class:`ErrorCode` for one MINOR version, but **only
normative codes are emitted on the wire**: :class:`MHSError` normalises a
legacy code to its normative replacement on construction.

``MHS.SAFETY.NOT_CERTIFIED`` is a *feature* string (``hello.features``), never
an error; it is kept in :data:`FEATURE_STRINGS` for discoverability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

__all__ = [
    "DEPRECATED_CODES",
    "DRIVER_SUBSET",
    "ErrorCode",
    "ErrorSpec",
    "MHSError",
    "MHS_ERROR_CODES",
    "ERROR_CODES",
    "FEATURE_STRINGS",
    "LEGACY_ALIASES",
    "NORMATIVE_REGISTRY_VERSION",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "all_error_codes",
    "describe_error",
    "error_from_json",
    "error_to_json",
    "is_driver_code",
    "is_known_code",
    "is_normative_code",
    "jsonrpc_code",
    "normalize_code",
    "retryable",
    "spec_for",
    "validate_code",
]

# Standard JSON-RPC 2.0 structural codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass(frozen=True)
class ErrorSpec:
    """Metadata for one ``MHS.*`` code from the normative registry.

    Attributes
    ----------
    code:
        Stable semantic code, e.g. ``"MHS.SAFETY.INTERLOCK_OPEN"``.
    jsonrpc:
        Integer JSON-RPC code used when the error crosses the wire
        (``None`` for feature strings that are never emitted as errors).
    retryable:
        Default client advice: may the identical request be retried without
        observing state first?  ``None`` for feature strings.
    area:
        Registry area (``SAFETY``, ``CONFLICT``, ...).
    summary:
        Normative one-line meaning (``meaning`` in errors.json).
    remediation:
        Normative remediation hint.
    kind:
        ``"error"`` or ``"feature"``.
    status:
        Lifecycle status, in the vocabulary capability classes use:
        ``stable``, ``deprecated``, ``retired`` or ``feature`` (``active`` is
        the pre-0.9 spelling of ``stable``).
    since:
        OpenMHS specification release (``MAJOR.MINOR.PATCH`` of
        ``spec_version``) that registered the code with its current meaning;
        not the registry format / wire revision
        (:data:`NORMATIVE_REGISTRY_VERSION`).
    driver_subset:
        True when drivers and bridges may raise the code.
    replaced_by:
        For a deprecated code, the code to emit instead.
    """

    code: str
    jsonrpc: int | None
    retryable: bool | None
    area: str
    summary: str
    remediation: str = ""
    kind: str = "error"
    status: str = "stable"
    since: str = ""
    driver_subset: bool = False
    replaced_by: str | None = None


# --- BEGIN GENERATED: MHS/sdk/tools/gen_errors.py from MHS/spec/errors.json (do not edit) ---
#: Version of the normative error registry embedded below (wire revision 1).
NORMATIVE_REGISTRY_VERSION = '1.0'

#: Normative registry rows, in registry order: (code, jsonrpc, retryable, area,
#: meaning, remediation, kind, status, since, driver_subset, replaced_by).
_NORMATIVE_ERRORS = (
    ('MHS.PROTOCOL.PARSE_ERROR', -32700, False, 'PROTOCOL', 'The frame is not valid JSON.', 'Fix framing; send one JSON value per line/message.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.INVALID_REQUEST', -32600, False, 'PROTOCOL', 'Not a JSON-RPC 2.0 request (missing `jsonrpc`, `method`, bad `id`).', 'Send a valid JSON-RPC request.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.METHOD_NOT_FOUND', -32601, False, 'PROTOCOL', 'Method unknown or not implemented by this endpoint/profile.', "Check `hello.features` and the profile's method matrix.", 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.INVALID_PARAMS', -32602, False, 'PROTOCOL', 'Params missing or malformed (not an input-schema failure — see `CAPABILITY.INPUT_INVALID`).', 'Check the method reference in [MHS-002](02-wire-protocol.md).', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.DEADLINE_INVALID', -32602, False, 'PROTOCOL', 'Blocking method called without a valid `deadline_ms`.', 'Supply `deadline_ms` ≥ 1.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.VERSION_UNSUPPORTED', -32000, False, 'PROTOCOL', 'No mutually supported protocol MAJOR.MINOR.', 'Upgrade client or connect to an endpoint supporting your version.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.BATCH_NOT_ATOMIC', -32000, False, 'PROTOCOL', 'Batch mixes mutations the endpoint cannot order safely.', 'Split the batch or order the mutations as separate requests.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.BATCH_TOO_LARGE', -32000, False, 'PROTOCOL', 'Batch exceeds the advertised maximum.', 'Split into smaller batches.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.PROTOCOL.UNSUPPORTED_FEATURE', -32000, False, 'PROTOCOL', 'A feature the client requested in `hello` is not implemented.', 'Do not request the feature; re-read `hello.features`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SESSION.UNKNOWN', -32011, False, 'SESSION', '`session_id` does not exist.', 'Open a session.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SESSION.EXPIRED', -32011, True, 'SESSION', 'Session passed `expires_at`.', 'Open a new session; re-read state; re-check permits.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SESSION.CLOSED', -32011, False, 'SESSION', 'Session was closed.', 'Open a new session.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SESSION.CAPABILITY_NOT_GRANTED', -32011, False, 'SESSION', 'Capability not in the session grant.', 'Open a new session requesting the capability (least privilege).', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SESSION.DEVICE_NOT_GRANTED', -32011, False, 'SESSION', 'Device not covered by the session.', 'Open a session including the device.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SESSION.MODE_MISMATCH', -32011, False, 'SESSION', 'Requested mode ≠ device mode.', 'Request the declared mode; never fall back.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.UNAUTHENTICATED', -32012, False, 'AUTH', 'No or invalid credentials.', "Authenticate per the endpoint descriptor's `auth`.", 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.TOKEN_EXPIRED', -32012, True, 'AUTH', 'Token expired.', 'Refresh the token; retry is safe only for reads.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.FORBIDDEN', -32012, False, 'AUTH', 'Principal not allowed to perform this action.', 'Use a principal with the required grant/approval.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.SCOPE_INSUFFICIENT', -32012, False, 'AUTH', 'Token scope does not cover the endpoint/device/capability.', 'Request a narrower-scope-compatible token.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.PRINCIPAL_REQUIRED', -32012, False, 'AUTH', 'Operation requires an authenticated principal (human principal for approvals).', 'Authenticate as the required principal kind.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.TRANSPORT_INSECURE', -32012, False, 'AUTH', 'Plaintext transport to a non-loopback endpoint.', 'Use TLS or a loopback/stdio binding.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.AUTH.HARDWARE_DISABLED', -32012, False, 'AUTH', 'Hardware operation refused because the deployment policy disallows hardware.', 'Set allow_hardware=true through a trusted operator configuration, or use a simulated endpoint.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.DEVICE.UNKNOWN', -32013, False, 'DEVICE', '`device_id` not served by this endpoint.', 'Re-run `devices.list`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.DEVICE.BUSY', -32013, True, 'DEVICE', 'Exclusive capability is held by another operation.', 'Wait for the operation to finish or cancel it; retry with backoff.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.DEVICE.OFFLINE', -32013, True, 'DEVICE', 'Device is unreachable or powered down.', "Bring it online; check the adapter's lifecycle state.", 'error', 'stable', '0.9.0', False, None),
    ('MHS.DEVICE.NOT_READY', -32013, True, 'DEVICE', 'Device initialising; commands not accepted yet.', 'Retry after readiness (`hello`).', 'error', 'stable', '0.9.0', False, None),
    ('MHS.DEVICE.FAULTED', -32013, False, 'DEVICE', 'Device reports a fault state.', 'Clear the fault (self-test/reset) before further commands.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.DEVICE.PRECONDITION_UNMET', -32013, False, 'DEVICE', 'A declared physical precondition is false (tip attached, plate present, homed).', 'Satisfy the precondition, then retry.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.DEVICE.FAILED', -32013, False, 'DEVICE', 'Device reported a terminal failure unrelated to the request shape.', 'Observe state, recover the device, then re-plan.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.RESOURCE.UNKNOWN', -32014, False, 'RESOURCE', '`resource_id` not present on the device.', 'Re-read `devices.get`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.RESOURCE.FIELD_UNKNOWN', -32014, False, 'RESOURCE', 'Write/read referenced a field not in the resource state schema.', 'Use declared fields only.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.RESOURCE.NOT_WRITABLE', -32014, False, 'RESOURCE', 'Resource does not accept writes.', 'Use a capability of verb `invoke`/`write`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.RESOURCE.STATE_INVALID', -32014, False, 'RESOURCE', 'Resource state failed its own schema (driver bug).', 'Report to the adapter maintainer; do not retry blindly.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CAPABILITY.UNKNOWN', -32015, False, 'CAPABILITY', 'Class id not implemented by this endpoint/device.', 'Re-read the manifest; check class MAJOR.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CAPABILITY.NOT_BOUND', -32015, False, 'CAPABILITY', 'Class known but not bound to this device/resource.', 'Use a bound capability.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CAPABILITY.KIND_MISMATCH', -32015, False, 'CAPABILITY', 'Binding resource kind is not in the class `resource_kinds`.', 'Adapter defect; report it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CAPABILITY.INPUT_INVALID', -32015, False, 'CAPABILITY', 'Input failed the binding/class JSON Schema.', 'Fix the input; `data.details.errors[]` lists violations.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.CAPABILITY.OUTPUT_INVALID', -32015, False, 'CAPABILITY', 'Native result did not produce a valid capability output.', 'Adapter/shim defect; the receipt is `failed`.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.CAPABILITY.EXPERIMENTAL_PRESENT', None, None, 'CAPABILITY', 'Not an error: feature marker that an experimental class is bound.', 'Treat experimental classes as unstable.', 'feature', 'feature', '0.9.0', False, None),
    ('MHS.CONFLICT.REVISION', -32016, False, 'CONFLICT', '`expected_revision` ≠ current revision.', 'Read state, re-plan, retry with the current revision.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CONFLICT.COMMAND_ID_REUSE', -32016, False, 'CONFLICT', '`command_id` reused with a different input digest.', 'Use a new ULID for a new command.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CONFLICT.LEASE_CONFLICT', -32016, True, 'CONFLICT', 'Concurrency lease is held by another operation.', 'Wait for release; do not force.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CONFLICT.SNAPSHOT_MISMATCH', -32016, False, 'CONFLICT', 'Snapshot does not belong to the target device/instance.', 'Take a snapshot from this device.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.CONFLICT.STATE_HASH', -32016, False, 'CONFLICT', 'Declared state hash does not recompute from the supplied state document.', 'Recapture the state/snapshot; do not trust the hash.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.OUTCOME.UNKNOWN', -32017, False, 'OUTCOME', 'Effect may have occurred; outcome not observable.', 'Observe state and the retained receipt; never retry blindly.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.OUTCOME.TIMEOUT', -32017, False, 'OUTCOME', 'Deadline exceeded; the effect may be in flight, so observe state first.', 'Observe state; retry only idempotently with the same `command_id`.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.OUTCOME.ABORTED', -32017, False, 'OUTCOME', 'Operation aborted by a device-level event (power loss, watchdog).', 'Recover device state, then re-plan.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.OPERATION.UNKNOWN', -32018, False, 'OPERATION', '`operation_id` not known (or retention expired).', 'Use `operations.list`; retain receipts.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.OPERATION.NOT_CANCELLABLE', -32018, False, 'OPERATION', 'Capability is declared non-cancellable.', 'Use `mhs.safety.estop` for emergencies.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.OPERATION.ALREADY_FINISHED', -32018, False, 'OPERATION', 'Operation reached a terminal state.', 'Read the final receipt; no cancellation needed.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.MODE.READ_ONLY', -32019, False, 'MODE', 'Mutation attempted in `replay` mode.', 'Replay is read-only; use the source endpoint for live actions.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.MODE.SNAPSHOT_UNSUPPORTED', -32019, False, 'MODE', 'Device does not support snapshots.', 'Check `fidelity.snapshot_restore`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.MODE.RESTORE_UNSUPPORTED', -32019, False, 'MODE', 'Device/snapshot cannot be restored (hardware or unsupported).', 'Use a simulator with snapshot support.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.MODE.SWITCH_FORBIDDEN', -32019, False, 'MODE', 'A mode change was attempted on a live session/device.', 'Open a session on the device with the correct declared mode.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.FIDELITY.CONTRACT_REQUIRED', -32020, False, 'FIDELITY', 'Simulated/hybrid device lacks a valid fidelity contract.', 'Fix the manifest; a simulator without a contract is CL0 only.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.FIDELITY.SEED_REQUIRED', -32020, False, 'FIDELITY', 'Deterministic replay claimed but no seed supplied on reset.', 'Call `world.reset` with a seed.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.FIDELITY.REPLAY_DIVERGENCE', -32020, False, 'FIDELITY', 'Replay state hashes diverged from the recording.', 'Treat the replay claim as invalid; investigate the model/seed.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.FIDELITY.GAP_UNDISCLOSED', -32020, False, 'FIDELITY', 'Host/endpoint detected a known gap not shown to the agent.', 'Disclose gaps before actuation.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.FIDELITY.DETERMINISM_UNSUPPORTED', -32020, False, 'FIDELITY', 'Requested determinism-based operation on a `statistical`/`none` device.', 'Use repeated trials, not replay equality.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.FIDELITY.VALIDATION_MISSING', -32020, False, 'FIDELITY', 'F3 claimed without a validation record.', 'Provide or downgrade to F2.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.LIMIT.BACKPRESSURE', -32021, True, 'LIMIT', 'Consumer cannot keep up; buffering would be unbounded.', 'Slow down, reduce `rate_hz`, resume from a gap/state read.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.LIMIT.RATE_EXCEEDED', -32021, True, 'LIMIT', 'Rate limit exceeded.', 'Wait `data.details.retry_after_ms`; batch or reduce rate.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.LIMIT.SUBSCRIPTION_LIMIT', -32021, False, 'LIMIT', 'Max concurrent subscriptions reached.', 'Close a subscription first.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.LIMIT.OPERATION_LIMIT', -32021, False, 'LIMIT', 'Max concurrent operations reached.', 'Finish/cancel operations; wait.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.LIMIT.PAYLOAD_TOO_LARGE', -32021, False, 'LIMIT', 'Frame/request exceeds the size limit.', 'Reduce payload; use artifact references for large data.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.LIMIT.CONNECTION_LIMIT', -32021, True, 'LIMIT', 'Too many concurrent connections.', 'Close idle connections; reconnect with backoff.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.CHAIN_BROKEN', -32022, False, 'EVIDENCE', 'Receipt chain does not recompute.', 'Re-export from the endpoint; investigate tampering.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.SIGNATURE_INVALID', -32022, False, 'EVIDENCE', 'Detached JWS does not verify or key unknown/revoked.', 'Treat as unsigned; resolve the key in the registry.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.TRUNCATED', -32022, False, 'EVIDENCE', 'History was truncated by retention; marker present.', 'Continue from `first_retained_seq`; do not assume continuity.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.UNKNOWN', -32022, False, 'EVIDENCE', 'Bundle/endpoint evidence not available.', 'Check `include_telemetry`/retention; export a smaller range.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.EXPORT_TOO_LARGE', -32022, True, 'EVIDENCE', 'Export would exceed the advertised size.', 'Page with `since_receipt`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.RETENTION_EXCEEDED', -32022, False, 'EVIDENCE', 'Requested receipt is outside retention.', 'Use the oldest retained receipt or the truncated marker.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.SCHEMA_INVALID', -32022, False, 'EVIDENCE', 'A receipt in the evidence bundle violates receipt.schema.json.', 'Re-export from the endpoint and investigate the producer.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.SCHEMA_UNAVAILABLE', -32022, False, 'EVIDENCE', 'Receipt schemas were unavailable, so schema verification could not complete.', 'Install the MHS schema set and verify again; do not treat as validated.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.EVIDENCE.SIGNATURE_UNVERIFIABLE', -32022, True, 'EVIDENCE', 'A detached signature exists but no key resolver is available.', 'Resolve the signing key through the registry and verify offline.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.INTERLOCK_OPEN', -32010, False, 'SAFETY', 'A required interlock reads `open`.', 'Close/clear the interlock, then reset if latched.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.SAFETY.ENVELOPE_VIOLATION', -32010, False, 'SAFETY', 'Input outside declared limits/allowed values.', 'Adjust the input to the declared envelope.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.SAFETY.CUMULATIVE_LIMIT', -32010, False, 'SAFETY', 'Cumulative budget (time/travel/volume/dose) exhausted.', 'Wait for the window to reset or obtain a new authorization.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.PERMIT_INVALID', -32010, False, 'SAFETY', 'Missing, expired, consumed or mismatched permit.', 'Obtain a permit for exactly this input via approval.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.APPROVAL_REQUIRED', -32010, False, 'SAFETY', 'Human approval required (R3, R2 policy, human presence).', 'Collect the required approval; retry with permit.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.RESET_REFUSED', -32010, False, 'SAFETY', 'Reset while interlock open/unknown or not latched.', 'Clear interlocks; reset only a latched device.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.SAFE_STATE_UNREACHED', -32010, False, 'SAFETY', 'Device could not reach the declared safe state in time.', 'Use the physical e-stop; inspect the device.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.SAFETY.ESTOP_ENGAGED', -32010, False, 'SAFETY', 'Device is e-stopped/latched and refuses actuation.', 'Reset after clearing interlocks; issue a new start command.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.SAFETY.RISK_CLASS_BLOCKED', -32010, False, 'SAFETY', "Session/action not permitted at the device's risk class.", 'Use an authorized session with the required approvals.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.NOT_CERTIFIED', None, None, 'SAFETY', 'Not an error: mandatory `hello.features` disclosure.', 'Display it; never treat MHS as a safety channel.', 'feature', 'feature', '0.9.0', False, None),
    ('MHS.SAFETY.ESTOP_UNAVAILABLE', -32010, False, 'SAFETY', 'The endpoint exposes no software e-stop path for this device.', 'Use the hardware e-stop; software conformance never replaces it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.SAFE_STATE', -32010, False, 'SAFETY', 'A safe-state attempt failed or could not be verified.', 'Inspect safety.status and the bridge stop path.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.SAFETY.LIMITS_UNSET', -32010, False, 'SAFETY', 'A hardware or hybrid write/invoke at risk R1 or above has a numeric input with no declared limit, or a limit declared `operator_required` that no operator overlay fills.', 'Declare a sourced limit in the driver or have the operator supply `site-limits.json`; never invent a bound.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.ADAPTER.MANIFEST_INVALID', -32023, False, 'ADAPTER', 'Adapter manifest/bindings fail schema or reference checks.', 'Fix the manifest; see `data.details.errors[]`.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.ADAPTER.LICENSE_BLOCKED', -32023, False, 'ADAPTER', 'Upstream licence incompatible with use/redistribution.', 'Change use, obtain a licence, or do not use the adapter.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.ADAPTER.SOURCE_UNPINNED', -32023, False, 'ADAPTER', 'Runnable adapter has no pinned source commit.', 'Pin `source.commit` and regenerate evidence.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.ADAPTER.BRIDGE_UNAVAILABLE', -32023, True, 'ADAPTER', 'Bridge runtime/dependency not installed.', 'Run `runtime.install`; check the lifecycle.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.ADAPTER.SHIM_FAILED', -32023, False, 'ADAPTER', 'Shim raised or returned an uninterpretable result.', 'Inspect the redacted message; fix the shim; do not report success.', 'error', 'stable', '0.9.0', True, None),
    ('MHS.ADAPTER.NATIVE_SYMBOL_MISSING', -32023, False, 'ADAPTER', 'Declared native symbol does not exist at runtime.', 'Fix the binding; mark `stability: fragile` if private.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.ADAPTER.CONTRACT_MISMATCH', -32023, False, 'ADAPTER', 'Served manifest differs from the adapter declaration.', 'Regenerate from the adapter; report drift.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.REGISTRY.UNAVAILABLE', -32024, True, 'REGISTRY', 'Registry not reachable.', 'Use a local mirror; retry with backoff.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.REGISTRY.RECORD_INVALID', -32024, False, 'REGISTRY', 'Record fails its schema or reference checks.', 'Fix the record; re-publish.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.REGISTRY.SIGNATURE_INVALID', -32024, False, 'REGISTRY', 'Record/claim signature invalid or key revoked.', 'Treat as unsigned; resolve keys.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.REGISTRY.FEDERATION_FAILED', -32024, True, 'REGISTRY', 'A federated peer failed; partial results.', 'Retry if `require_all_peers`; otherwise use partial results.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.REGISTRY.CLAIM_INVALID', -32024, False, 'REGISTRY', 'Claim does not match its report (subject/profile/level/digest).', 'Re-run the suite and re-issue the claim.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.COMPOSITION.UNKNOWN', -32025, False, 'COMPOSITION', '`composition_ref` does not resolve.', 'Publish/serve the composition document.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.COMPOSITION.INVALID', -32025, False, 'COMPOSITION', 'Composition document invalid or exceeds session grants.', 'Fix the composition; request the needed grants.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.COMPOSITION.CYCLE', -32025, False, 'COMPOSITION', 'Composition includes itself (directly or transitively).', 'Remove the cycle.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.COMPOSITION.CHILD_FAILED', -32025, False, 'COMPOSITION', 'A child receipt failed and the composition stops on failure.', 'Inspect the embedded child receipt.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.COMPOSITION.CANCELLED', -32025, False, 'COMPOSITION', 'The composition was cancelled.', 'Inspect child safe-state results.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.COMPOSITION.GRANT_EXCEEDED', -32025, False, 'COMPOSITION', 'A child requested a capability beyond the session grants.', 'Open a session with the required grants; compositions cannot escalate.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.TRANSPORT.UNAVAILABLE', -32026, True, 'TRANSPORT', 'Transport cannot connect.', 'Check the endpoint address/process; retry with backoff.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.TRANSPORT.CLOSED', -32026, True, 'TRANSPORT', 'Connection closed by the peer.', 'Reconnect; re-read state; never retry unknown outcomes blindly.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.TRANSPORT.TLS_REQUIRED', -32026, False, 'TRANSPORT', 'TLS required but not negotiated.', 'Use TLS.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.TRANSPORT.PROTOCOL_ERROR', -32026, False, 'TRANSPORT', 'Framing error not covered by `MHS.PROTOCOL.*` (e.g. SSE corruption).', 'Fix the transport; reconnect.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.BRIDGE.CAPABILITY_NOT_SUPPORTED', -32023, False, 'BRIDGE', 'The bridge does not implement the requested capability.', 'Inspect the adapter manifest; declare the capability unsupported or add a mapping.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.BRIDGE.MAPPING_ERROR', -32023, False, 'BRIDGE', 'A declarative binding mapping could not be applied.', 'Fix the binding; unmapped values are never guessed.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.CAPABILITY_REQUIRED', -32027, False, 'HOST', 'A capability id is required for this host operation.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.CONFIG_REQUIRED', -32027, False, 'HOST', 'A trusted MHS host configuration file is required.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.DEVICE_AMBIGUOUS', -32027, False, 'HOST', 'The device is ambiguous; bind it explicitly in policy.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.DEVICE_NOT_ALLOWED', -32027, False, 'HOST', 'The device is not on the trusted host allow-list.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.DEVICE_NOT_FOUND', -32027, False, 'HOST', 'The requested device is unknown to the host.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.DEVICE_REQUIRED', -32027, False, 'HOST', 'A device id is required for this host operation.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.ENDPOINT_NOT_ALLOWED', -32027, False, 'HOST', 'The endpoint is not on the trusted host allow-list.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.ENDPOINT_UNAVAILABLE', -32027, False, 'HOST', 'The configured endpoint could not be reached.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.EVIDENCE_EXPORT_FAILED', -32027, False, 'HOST', 'The endpoint evidence bundle could not be exported.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.EVIDENCE_WRITE_FAILED', -32027, False, 'HOST', 'The durable host evidence store could not be written.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.HARDWARE_GATED', -32027, False, 'HOST', 'The host requires allow_hardware=true for this hardware call.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.INVALID_ARGUMENT', -32027, False, 'HOST', 'The host call arguments are invalid.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.NO_CAPABILITIES', -32027, False, 'HOST', 'The endpoint exposes no callable capability for the host policy.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.NO_ENDPOINTS', -32027, False, 'HOST', 'No MHS endpoint is configured for the host.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.NO_READ_CAPABILITY', -32027, False, 'HOST', 'The device exposes no read capability for reconciliation.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.NO_RESOURCES', -32027, False, 'HOST', 'The device exposes no resource to read.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.OPENAI4S_MISSING', -32027, False, 'HOST', 'Deprecated alias of `MHS.HOST.ADAPTER_MISSING` (the OpenAI4S host package is not importable).', 'The OpenAI4S host package (its MCP client) is not importable in the host process: install OpenAI4S in that environment or add its source tree to PYTHONPATH, or disable the OpenAI4S integration, then retry. Handle it exactly like MHS.HOST.ADAPTER_MISSING, which replaces this deprecated alias in 0.10.', 'error', 'deprecated', '0.9.0', False, 'MHS.HOST.ADAPTER_MISSING'),
    ('MHS.HOST.OPERATION_NOT_FOUND', -32027, False, 'HOST', 'The host operation id is unknown.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.OPERATION_REQUIRED', -32027, False, 'HOST', 'An operation id is required for reconciliation.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.PROTOCOL_ERROR', -32027, False, 'HOST', 'The host received an invalid MCP/MHS protocol response.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.READ_FAILED', -32027, False, 'HOST', 'The host could not read device state for reconciliation.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.RECONCILE_REQUIRED', -32027, False, 'HOST', 'A prior ambiguous outcome must be reconciled before a new command.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.SDK_MISSING', -32027, False, 'HOST', 'The MHS SDK is not importable in the host environment.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.SESSION_FAILED', -32027, False, 'HOST', 'The host could not open an MHS session.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.TOOL_ERROR', -32027, False, 'HOST', 'An MCP tool call failed at the host boundary.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.UNEXPECTED', -32027, False, 'HOST', 'An unexpected host integration failure occurred.', 'Inspect the host policy/configuration and retry after fixing it.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.ADAPTER_MISSING', -32027, False, 'HOST', 'The host-integration package for the configured host is not importable.', 'Install the host integration package in the host environment, or disable the integration.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.HOST.JOURNAL_CORRUPT', -32027, False, 'HOST', "The host's durable command journal is unreadable or fails its integrity check; the affected record is never skipped.", 'Repair or restore the journal and reconcile pending commands before issuing new ones.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.INTERNAL.ERROR', -32603, False, 'INTERNAL', 'Unexpected server fault.', 'Report with the request id; do not retry mutations.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.INTERNAL.NOT_IMPLEMENTED', -32603, False, 'INTERNAL', 'Code path not implemented (endpoint defect).', 'Implement or avoid; report to maintainer.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.INTERNAL.OVERLOADED', -32603, True, 'INTERNAL', 'Server overloaded (queue full).', 'Retry with backoff.', 'error', 'stable', '0.9.0', False, None),
    ('MHS.INTERNAL.SCHEMA_DRIFT', -32603, False, 'INTERNAL', 'Served schema differs from validated schema.', 'Restart/regenerate endpoint; report adapter defect.', 'error', 'stable', '0.9.0', False, None),
)
# --- END GENERATED ---

#: Stable code -> :class:`ErrorSpec`.
MHS_ERROR_CODES: dict[str, ErrorSpec] = {
    row[0]: ErrorSpec(
        code=row[0],
        jsonrpc=row[1],
        retryable=row[2],
        area=row[3],
        summary=row[4],
        remediation=row[5],
        kind=row[6],
        status=row[7],
        since=row[8],
        driver_subset=row[9],
        replaced_by=row[10],
    )
    for row in _NORMATIVE_ERRORS
}
#: Alternative name for :data:`MHS_ERROR_CODES`.
ERROR_CODES = MHS_ERROR_CODES

#: Codes that are feature strings, not errors (never emitted as errors).
FEATURE_STRINGS = frozenset(
    code for code, spec in MHS_ERROR_CODES.items() if spec.kind == "feature"
)

#: Codes a driver or bridge may raise (``driver_subset`` in errors.json).
DRIVER_SUBSET = frozenset(
    code for code, spec in MHS_ERROR_CODES.items() if spec.driver_subset
)

#: Deprecated registry codes -> replacement.  Unlike :data:`LEGACY_ALIASES`
#: these stay registered and are not rewritten by :func:`normalize_code`.
DEPRECATED_CODES: dict[str, str] = {
    code: spec.replaced_by
    for code, spec in MHS_ERROR_CODES.items()
    if spec.status == "deprecated" and spec.replaced_by
}

#: Deprecated SDK codes -> normative replacement (removed after one MINOR).
LEGACY_ALIASES: dict[str, str] = {
    'MHS.PROTOCOL.CONTENT_TYPE': 'MHS.PROTOCOL.INVALID_REQUEST',
    'MHS.PROTOCOL.INVALID_MESSAGE': 'MHS.PROTOCOL.INVALID_REQUEST',
    'MHS.PROTOCOL.CANCELLED': 'MHS.OUTCOME.ABORTED',
    'MHS.PROTOCOL.INTERNAL_ERROR': 'MHS.INTERNAL.ERROR',
    'MHS.PROTOCOL.HTTP_ERROR': 'MHS.TRANSPORT.PROTOCOL_ERROR',
    'MHS.PROTOCOL.TRANSPORT_CLOSED': 'MHS.TRANSPORT.CLOSED',
    'MHS.TRANSPORT.CONNECT_FAILED': 'MHS.TRANSPORT.UNAVAILABLE',
    'MHS.TRANSPORT.TIMEOUT': 'MHS.OUTCOME.TIMEOUT',
    'MHS.AUTH.UNAUTHORIZED': 'MHS.AUTH.UNAUTHENTICATED',
    'MHS.AUTH.INVALID_PRINCIPAL': 'MHS.AUTH.PRINCIPAL_REQUIRED',
    'MHS.SAFETY.PERMIT_REQUIRED': 'MHS.SAFETY.PERMIT_INVALID',
    'MHS.SAFETY.PERMIT_EXPIRED': 'MHS.SAFETY.PERMIT_INVALID',
    'MHS.SAFETY.RISK_CLASS_DENIED': 'MHS.SAFETY.RISK_CLASS_BLOCKED',
    'MHS.SAFETY.SAFE_STATE_UNREACHABLE': 'MHS.SAFETY.SAFE_STATE_UNREACHED',
    'MHS.SAFETY.LIMIT_EXCEEDED': 'MHS.SAFETY.ENVELOPE_VIOLATION',
    'MHS.SESSION.INVALID': 'MHS.SESSION.UNKNOWN',
    'MHS.SESSION.NOT_FOUND': 'MHS.SESSION.UNKNOWN',
    'MHS.SESSION.INVALID_TTL': 'MHS.PROTOCOL.INVALID_PARAMS',
    'MHS.SESSION.CAPABILITIES_EMPTY': 'MHS.SESSION.CAPABILITY_NOT_GRANTED',
    'MHS.CAPABILITY.NOT_GRANTED': 'MHS.SESSION.CAPABILITY_NOT_GRANTED',
    'MHS.CAPABILITY.UNHANDLED': 'MHS.CAPABILITY.NOT_BOUND',
    'MHS.CAPABILITY.AMBIGUOUS': 'MHS.CAPABILITY.NOT_BOUND',
    'MHS.SCHEMA.INVALID_INPUT': 'MHS.CAPABILITY.INPUT_INVALID',
    'MHS.SCHEMA.INVALID_STATE': 'MHS.RESOURCE.STATE_INVALID',
    'MHS.SCHEMA.INVALID_RESOURCE': 'MHS.RESOURCE.STATE_INVALID',
    'MHS.SCHEMA.NOT_FOUND': 'MHS.PROTOCOL.INVALID_PARAMS',
    'MHS.CONFLICT.SNAPSHOT': 'MHS.CONFLICT.SNAPSHOT_MISMATCH',
    'MHS.CONFLICT.PRECONDITION': 'MHS.DEVICE.PRECONDITION_UNMET',
    'MHS.CONFLICT.LEASE': 'MHS.CONFLICT.LEASE_CONFLICT',
    'MHS.DEVICE.NOT_FOUND': 'MHS.DEVICE.UNKNOWN',
    'MHS.DEVICE.FAULT': 'MHS.DEVICE.FAULTED',
    'MHS.DEVICE.UNSUPPORTED': 'MHS.CAPABILITY.NOT_BOUND',
    'MHS.RESOURCE.NOT_FOUND': 'MHS.RESOURCE.UNKNOWN',
    'MHS.RESOURCE.READ_ONLY': 'MHS.RESOURCE.NOT_WRITABLE',
    'MHS.RESOURCE.REVISION_STALE': 'MHS.CONFLICT.REVISION',
    'MHS.OPERATION.NOT_FOUND': 'MHS.OPERATION.UNKNOWN',
    'MHS.OUTCOME.CANCELLED': 'MHS.OUTCOME.ABORTED',
    'MHS.OUTCOME.FAILED': 'MHS.OUTCOME.ABORTED',
    'MHS.SUBSCRIPTION.NOT_FOUND': 'MHS.SESSION.UNKNOWN',
    'MHS.SUBSCRIPTION.CLOSED': 'MHS.SESSION.CLOSED',
    'MHS.LIMIT.DEADLINE_INVALID': 'MHS.PROTOCOL.DEADLINE_INVALID',
    'MHS.LIMIT.TOO_LARGE': 'MHS.LIMIT.PAYLOAD_TOO_LARGE',
    'MHS.LIMIT.QUEUE_FULL': 'MHS.INTERNAL.OVERLOADED',
    'MHS.LIMIT.QUOTA_EXCEEDED': 'MHS.LIMIT.RATE_EXCEEDED',
    'MHS.EVIDENCE.CHAIN_INVALID': 'MHS.EVIDENCE.CHAIN_BROKEN',
    'MHS.EVIDENCE.NOT_FOUND': 'MHS.EVIDENCE.UNKNOWN',
    'MHS.EVIDENCE.EXPORT_FAILED': 'MHS.EVIDENCE.UNKNOWN',
    'MHS.FIDELITY.MISSING': 'MHS.FIDELITY.CONTRACT_REQUIRED',
    'MHS.FIDELITY.INVALID': 'MHS.FIDELITY.CONTRACT_REQUIRED',
    'MHS.FIDELITY.NOT_REPRODUCIBLE': 'MHS.FIDELITY.REPLAY_DIVERGENCE',
    'MHS.ADAPTER.INVALID': 'MHS.ADAPTER.MANIFEST_INVALID',
    'MHS.REGISTRY.INVALID_RECORD': 'MHS.REGISTRY.RECORD_INVALID',
    'MHS.REGISTRY.NOT_FOUND': 'MHS.REGISTRY.UNAVAILABLE',
    'MHS.CONFORMANCE.NOT_AVAILABLE': 'MHS.INTERNAL.NOT_IMPLEMENTED',
    'MHS.CONFORMANCE.FAILED': 'MHS.INTERNAL.ERROR',
    'MHS.UNSUPPORTED.OPERATION': 'MHS.PROTOCOL.UNSUPPORTED_FEATURE',
    'MHS.UNSUPPORTED.FEATURE': 'MHS.PROTOCOL.UNSUPPORTED_FEATURE',
    'MHS.INTERNAL.SHUTTING_DOWN': 'MHS.TRANSPORT.CLOSED',
    'MHS.UPSTREAM.BRIDGE_FAILURE': 'MHS.DEVICE.FAULTED',
    'MHS.SAFETY.NOT_READY': 'MHS.DEVICE.NOT_READY',
}


def normalize_code(code: str) -> str:
    """Return the normative code for ``code`` (following legacy aliases)."""
    return LEGACY_ALIASES.get(code, code)


def is_normative_code(code: Any) -> bool:
    """Return True when ``code`` is a code from the normative registry."""
    return isinstance(code, str) and code in MHS_ERROR_CODES


def is_driver_code(code: Any) -> bool:
    """Return True when ``code`` is in the driver subset (legacy names are normalised)."""
    return isinstance(code, str) and normalize_code(code) in DRIVER_SUBSET


def is_known_code(code: Any) -> bool:
    """Return True for normative codes and deprecated legacy aliases."""
    return is_normative_code(code) or (isinstance(code, str) and code in LEGACY_ALIASES)


def all_error_codes(*, include_legacy: bool = False) -> list[str]:
    """Return the sorted normative error codes (optionally plus legacy names)."""
    codes = set(MHS_ERROR_CODES)
    if include_legacy:
        codes.update(LEGACY_ALIASES)
    return sorted(codes)


def spec_for(code: str) -> ErrorSpec | None:
    """Return the :class:`ErrorSpec` for ``code`` (legacy names are normalised)."""
    return MHS_ERROR_CODES.get(normalize_code(code))


def jsonrpc_code(code: str, default: int = INTERNAL_ERROR) -> int:
    """Return the JSON-RPC structural code carrying ``code``."""
    spec = MHS_ERROR_CODES.get(normalize_code(code))
    if spec is None or spec.jsonrpc is None:
        return default
    return int(spec.jsonrpc)


def retryable(code: str, default: bool = False) -> bool:
    """Return the registry's retryability advice for ``code``."""
    spec = MHS_ERROR_CODES.get(normalize_code(code))
    if spec is None or spec.retryable is None:
        return default
    return bool(spec.retryable)


def describe_error(code: str) -> dict[str, Any]:
    """Return a JSON-ready description of ``code`` (empty for unknown codes)."""
    spec = MHS_ERROR_CODES.get(normalize_code(code))
    if spec is None:
        return {}
    return {
        "mhs_code": spec.code,
        "jsonrpc_code": spec.jsonrpc,
        "area": spec.area,
        "kind": spec.kind,
        "retryable": spec.retryable,
        "summary": spec.summary,
        "remediation": spec.remediation,
        "status": spec.status,
        "driver_subset": spec.driver_subset,
        "replaced_by": spec.replaced_by,
        "legacy_code": code if code != spec.code else None,
    }


def validate_code(code: str) -> None:
    """Raise :class:`ValueError` unless ``code`` is known (normative or legacy)."""
    if not is_known_code(code):
        raise ValueError(f"unknown MHS error code: {code!r}")


def _make_error_code_class() -> type:
    """Build the :class:`ErrorCode` constant namespace from the registry."""
    attributes: dict[str, str] = {}
    for code in MHS_ERROR_CODES:
        _, _, remainder = code.partition(".")
        area, _, detail = remainder.partition(".")
        if area and detail:
            attributes[f"{area}_{detail}"] = code
    for legacy, normative in LEGACY_ALIASES.items():
        _, _, remainder = legacy.partition(".")
        area, _, detail = remainder.partition(".")
        name = f"{area}_{detail}"
        attributes.setdefault(name, normative)
    return type("ErrorCodeBase", (), attributes)


class ErrorCode:
    """Stable ``MHS.*`` error code vocabulary (normative registry only).

    Every normative code is exposed as an upper-snake-case constant, e.g.
    ``ErrorCode.SAFETY_INTERLOCK_OPEN``, ``ErrorCode.CONFLICT_REVISION``.
    Deprecated legacy names are also present and map to their normative
    replacement.  Use these constants instead of string literals.
    """


_generated = _make_error_code_class()
for _name, _value in vars(_generated).items():
    if not _name.startswith("_"):
        setattr(ErrorCode, _name, _value)
del _generated


class MHSError(Exception):
    """A semantic MHS error.

    Attributes
    ----------
    code:
        Normative ``MHS.*`` code (legacy codes are normalised on construction).
    legacy_code:
        The original legacy code when ``code`` was passed in deprecated form.
    message:
        Human-readable message (never branch on this).
    data:
        Structured details (``retryable``, ``current_revision``,
        ``interlocks``, ``remediation``, ``details``, ...).
    jsonrpc:
        Integer structural code used by :meth:`to_error_object`.
    """

    def __init__(
        self,
        code: str,
        message: str | None = None,
        data: Mapping[str, Any] | None = None,
        *,
        retryable: bool | None = None,
        jsonrpc: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        """Create an MHS error; legacy codes are mapped to normative ones."""
        original = str(code)
        normalised = normalize_code(original)
        self.legacy_code: str | None = original if normalised != original else None
        spec = MHS_ERROR_CODES.get(normalised)
        self.code = normalised
        self.message = message or (spec.summary if spec else normalised)
        self.data: dict[str, Any] = dict(data or {})
        if retryable is not None:
            self.data.setdefault("retryable", bool(retryable))
        elif spec is not None and spec.retryable is not None:
            self.data.setdefault("retryable", bool(spec.retryable))
        if spec is not None and spec.remediation and "remediation" not in self.data:
            self.data["remediation"] = spec.remediation
        if jsonrpc is None:
            self.jsonrpc = int(spec.jsonrpc) if spec and spec.jsonrpc is not None else INTERNAL_ERROR
        else:
            self.jsonrpc = int(jsonrpc)
        self.cause = cause
        super().__init__(self.message)

    @property
    def retryable(self) -> bool:
        """The retryability advice carried in ``data.retryable``."""
        return bool(self.data.get("retryable", False))

    @property
    def current_revision(self) -> int | None:
        """The ``data.current_revision`` hint for conflict errors, if present."""
        value = self.data.get("current_revision")
        return value if isinstance(value, int) else None

    def with_data(self, **extra: Any) -> "MHSError":
        """Return a copy of this error with additional data fields."""
        merged = dict(self.data)
        merged.update(extra)
        return MHSError(self.code, self.message, merged, jsonrpc=self.jsonrpc, cause=self.cause)

    def to_error_object(self) -> dict[str, Any]:
        """Return the JSON-RPC ``error`` object for this error."""
        data = dict(self.data)
        data["mhs_code"] = self.code
        return {"code": self.jsonrpc, "message": self.message, "data": data}

    def to_dict(self) -> dict[str, Any]:
        """Return the receipt-style MHS error payload for this error."""
        payload = dict(self.data)
        payload["mhs_code"] = self.code
        payload["message"] = self.message
        return payload

    @classmethod
    def from_error_object(cls, obj: Mapping[str, Any]) -> "MHSError":
        """Build an :class:`MHSError` from a JSON-RPC ``error`` object."""
        if not isinstance(obj, Mapping):
            return cls("MHS.PROTOCOL.INVALID_REQUEST", f"invalid error object: {obj!r}")
        data = dict(obj.get("data") or {})
        code = data.pop("mhs_code", None) or obj.get("mhs_code")
        message = obj.get("message") or data.pop("message", None)
        if not isinstance(code, str):
            code = _code_from_jsonrpc(obj.get("code"))
        jsonrpc = obj.get("code") if isinstance(obj.get("code"), int) else None
        return cls(code, message, data, jsonrpc=jsonrpc)

    @classmethod
    def from_dict(cls, obj: Mapping[str, Any]) -> "MHSError":
        """Build an :class:`MHSError` from an MHS receipt-error payload."""
        if not isinstance(obj, Mapping):
            return cls("MHS.PROTOCOL.INVALID_REQUEST", f"invalid error payload: {obj!r}")
        data = dict(obj)
        code = data.pop("mhs_code", None) or "MHS.INTERNAL.ERROR"
        message = data.pop("message", None)
        return cls(code, message, data)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        """Return a compact debugging representation."""
        return f"MHSError({self.code!r}, {self.message!r})"

    def __str__(self) -> str:
        """Return ``CODE: message`` for logs and CLI output."""
        return f"{self.code}: {self.message}"


def _code_from_jsonrpc(value: Any) -> str:
    """Map a bare JSON-RPC integer code to the closest normative code."""
    standard = {
        PARSE_ERROR: "MHS.PROTOCOL.PARSE_ERROR",
        INVALID_REQUEST: "MHS.PROTOCOL.INVALID_REQUEST",
        METHOD_NOT_FOUND: "MHS.PROTOCOL.METHOD_NOT_FOUND",
        INVALID_PARAMS: "MHS.PROTOCOL.INVALID_PARAMS",
        INTERNAL_ERROR: "MHS.INTERNAL.ERROR",
    }
    if isinstance(value, int) and value in standard:
        return standard[value]
    if isinstance(value, int):
        for spec in MHS_ERROR_CODES.values():
            if spec.jsonrpc == value:
                return spec.code
    return "MHS.INTERNAL.ERROR"


def error_to_json(error: MHSError | Mapping[str, Any] | BaseException) -> dict[str, Any]:
    """Return the JSON-RPC ``error`` object for ``error``."""
    if isinstance(error, MHSError):
        return error.to_error_object()
    if isinstance(error, Mapping):
        if "code" in error and "data" in error and "mhs_code" not in error:
            return dict(error)
        return MHSError.from_dict(error).to_error_object()
    return MHSError("MHS.INTERNAL.ERROR", str(error) or type(error).__name__).to_error_object()


def error_from_json(obj: Mapping[str, Any]) -> MHSError:
    """Build an :class:`MHSError` from a JSON-RPC error or MHS payload."""
    if isinstance(obj, Mapping) and ("jsonrpc" in obj or ("code" in obj and "message" in obj)):
        return MHSError.from_error_object(obj)
    return MHSError.from_dict(obj)
