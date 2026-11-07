"""Code files: chain device commands in a plain Python script, with a ledger.

A code file is an ordinary Python script that drives devices through the
client API (explore with the agent, freeze the steps, loop them without
per-step reasoning; ``MHS/sdk/docs/code-files.md``)::

    from mhs.run import lab

    with lab("http://127.0.0.1:7401") as bench:                   # every device of that endpoint
        bench["liquid-handler"].invoke("cap.fluid.transfer.v1",
                                       {"source_well": "A1", "destination_well": "B1", "volume_ul": 50})
        bench["sample-mover"].invoke("cap.sample.move.v1", {"plate_id": "plate-001", "to": "reader"})
        spectrum = bench["plate-reader"].invoke("cap.measure.spectrum.v1",
                                                {"plate_id": "plate-001", "wavelengths_nm": [562]})

:func:`lab` connects to each endpoint once and gives every device its own
:class:`~mhs.client.DeviceHandle` (its own session, opened on first use in
the device's own mode).  With ``check=True`` (the default) any outcome other
than ``completed`` (or work still running) raises
:class:`~mhs.client.MHSRejected` carrying the receipt, so a code file stops
at the first refusal instead of carrying on.  The endpoint still enforces
every limit, interlock and permit: a code file has no more authority than the
same calls made one by one.

Every run writes a ledger, ``.mhs-run/<run id>.json``: the script's SHA-256,
the endpoints, every receipt id (with command id, device, capability and
status), commands whose response was lost, the start and end time and the
outcome.  ``mhs run script.py`` runs a script under one ledger that records
every client of the process; a :func:`lab` used outside ``mhs run`` writes
its own ledger for its own clients when it is closed.  :func:`verify_ledger`
checks the ledger's receipts against an endpoint's evidence bundle.

Targets of :func:`lab` are endpoints (``http(s)://...``, ``mhs://host:port``,
``stdio:<command>``, an argv list, an :class:`mhs.server.MHSServer` in this
process, an open :class:`~mhs.client.MHSClient`) -- every device they serve
gets a handle -- or device ids.  A device id is looked up in the configured
endpoints (:func:`mhs.discovery.discover`); an ``mhs://host:port/...`` id
whose endpoint is not configured is reached at ``http://host:port``.  A
discovered endpoint is a claim: it gets only its own endpoints-file
``token_file`` (never ``lab(token=...)``), and a device two discovered
endpoints list is ambiguous.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import runpy
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import _ids, canonical
from .client import DeviceHandle, MHSClient, MHSRejected, Receipt, add_observer, connect, transport_target
from .errors import MHSError

__all__ = [
    "LEDGER_DIR",
    "LEDGER_VERSION",
    "Lab",
    "Ledger",
    "active_ledger",
    "lab",
    "run_script",
    "verify_ledger",
]

#: Directory (relative to the working directory) the ledgers are written to.
LEDGER_DIR = ".mhs-run"
LEDGER_VERSION = 1
#: Receipt statuses an endpoint's evidence must hold once the command ended.
_FINAL = ("completed", "failed", "rejected", "cancelled")

_ACTIVE: list["Ledger"] = []
_ACTIVE_LOCK = threading.Lock()
#: Labs with their own ledger that are not closed yet (their ledgers are written at interpreter exit).
_OPEN_LABS: "set[Lab]" = set()


def active_ledger() -> "Ledger | None":
    """The ledger of the ``mhs run`` in progress, if any."""
    with _ACTIVE_LOCK:
        return _ACTIVE[-1] if _ACTIVE else None


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# ledger
# ---------------------------------------------------------------------------


class Ledger:
    """Records the endpoints, receipts and lost responses of a code-file run.

    It observes every client of the process (:func:`mhs.client.add_observer`),
    or only the clients passed to :meth:`track` when ``only_tracked`` is true.
    :meth:`close` writes ``<directory>/<run_id>.json`` atomically.
    """

    def __init__(self, *, script: str | os.PathLike[str] | None = None, argv: Sequence[str] | None = None,
                 directory: str | os.PathLike[str] = LEDGER_DIR, only_tracked: bool = False) -> None:
        self.run_id = canonical.ulid()
        # Absolute from the start: a script that calls os.chdir() does not move its ledger.
        self.directory = Path(os.path.abspath(os.path.expanduser(os.fspath(directory))))
        self.script = str(script) if script is not None else None
        self.script_sha256 = _sha256_file(Path(script)) if script is not None else None
        self.argv = [str(item) for item in argv] if argv is not None else None
        self.started_at = canonical.now_rfc3339()
        self.only_tracked = bool(only_tracked)
        self.path: Path | None = None
        self._lock = threading.Lock()
        self._tracked: set[int] = set()
        self._endpoints: dict[int, dict[str, Any]] = {}
        self._receipts: dict[str, dict[str, Any]] = {}
        self._lost: list[dict[str, Any]] = []
        self._remove = add_observer(self._observe)

    # -- observation --------------------------------------------------
    def track(self, client: Any) -> None:
        with self._lock:
            self._tracked.add(id(client))
        self._endpoint(client)

    def _endpoint(self, client: Any) -> dict[str, Any]:
        with self._lock:
            entry = self._endpoints.get(id(client))
            if entry is None:
                transport = getattr(client, "transport", None)
                entry = {"endpoint_id": getattr(client, "endpoint_id", None),
                         "transport": str(getattr(transport, "kind", "") or "unknown"),
                         "target": transport_target(transport)}
                self._endpoints[id(client)] = entry
            elif entry.get("endpoint_id") is None and getattr(client, "endpoint_id", None):
                entry["endpoint_id"] = client.endpoint_id
            return entry

    def _observe(self, event: str, client: Any, payload: Mapping[str, Any]) -> None:
        if self.only_tracked and id(client) not in self._tracked:
            return
        endpoint = self._endpoint(client)
        if event == "receipt":
            receipt_id = str(payload.get("receipt_id"))
            error = payload.get("error") if isinstance(payload.get("error"), Mapping) else {}
            entry = {
                "receipt_id": receipt_id,
                "command_id": payload.get("command_id"),
                "endpoint_id": payload.get("endpoint_id") or endpoint.get("endpoint_id"),
                "device_id": payload.get("device_id"),
                "capability_id": payload.get("capability_id"),
                "status": payload.get("status"),
            }
            if payload.get("operation_id"):
                entry["operation_id"] = payload.get("operation_id")
            if error.get("mhs_code"):
                entry["error_code"] = error.get("mhs_code")
            with self._lock:
                # A polled operation updates its entry; the first sighting keeps its place.
                self._receipts.setdefault(receipt_id, {}).update({k: v for k, v in entry.items() if v is not None})
        elif event == "lost":
            entry = {key: payload.get(key) for key in ("method", "code", "command_id", "command_ids",
                                                       "may_have_effect") if payload.get(key) is not None}
            if endpoint.get("endpoint_id"):
                entry["endpoint_id"] = endpoint["endpoint_id"]
            with self._lock:
                self._lost.append(entry)

    # -- results ------------------------------------------------------
    @property
    def receipt_ids(self) -> list[str]:
        with self._lock:
            return list(self._receipts)

    def document(self, *, outcome: str, error: Mapping[str, Any] | None = None,
                 exit_code: int | None = None) -> dict[str, Any]:
        with self._lock:
            endpoints = []
            seen: set[tuple[Any, Any]] = set()
            for entry in self._endpoints.values():
                key = (entry.get("endpoint_id"), entry.get("target"))
                if key not in seen:
                    seen.add(key)
                    endpoints.append({k: v for k, v in entry.items() if v is not None})
            receipts = [dict(item) for item in self._receipts.values()]
            lost = [dict(item) for item in self._lost]
        document: dict[str, Any] = {
            "ledger_version": LEDGER_VERSION,
            "run_id": self.run_id,
            "script": self.script,
            "script_sha256": self.script_sha256,
            "argv": self.argv,
            "endpoints": endpoints,
            "receipt_ids": [item["receipt_id"] for item in receipts],
            "receipts": receipts,
            "lost": lost,
            "started_at": self.started_at,
            "ended_at": canonical.now_rfc3339(),
            "outcome": outcome,
            "sdk": {"name": _ids.DIST_NAME, "version": _ids.SDK_VERSION, "spec": _ids.SPEC_VERSION},
        }
        if exit_code is not None:
            document["exit_code"] = int(exit_code)
        if error:
            document["error"] = dict(error)
        return document

    def close(self, *, outcome: str = "completed", error: Mapping[str, Any] | None = None,
              exit_code: int | None = None) -> Path:
        """Stop observing and write the ledger (once); returns its path."""
        self._remove()
        if self.path is not None:
            return self.path
        document = self.document(outcome=outcome, error=error, exit_code=exit_code)
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{self.run_id}.json"
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        self.path = target
        return target


def _error_record(exc: BaseException) -> dict[str, Any]:
    record: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)[:500]}
    code = getattr(exc, "code", None)
    if isinstance(exc, MHSError) and code:
        record["code"] = code
    if isinstance(exc, MHSRejected):
        record["receipt_id"] = exc.receipt.get("receipt_id")
        record["status"] = exc.status
    return record


def _outcome(exc: BaseException | None) -> str:
    if exc is None:
        return "completed"
    if isinstance(exc, MHSRejected):
        return exc.status
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted"
    return "error"


# ---------------------------------------------------------------------------
# lab
# ---------------------------------------------------------------------------


def _segments(device_id: str) -> list[str]:
    text = device_id.split("://", 1)[-1]
    return [part for part in text.split("/") if part]


def _is_endpoint_text(text: str) -> bool:
    if text.startswith(("http://", "https://", "stdio:", "mhs+stdio://")):
        return True
    if text.startswith("mhs://"):
        return not [part for part in text[len("mhs://"):].split("/")[1:] if part]
    return False


class Lab:
    """Handles on the devices of one or more endpoints (:func:`lab`)."""

    def __init__(self, *, check: bool = True, mode: str | None = None, ttl_s: int = 600,
                 principal: Mapping[str, Any] | None = None, ledger: Ledger | None = None) -> None:
        self.check = bool(check)
        self.mode = mode
        self.ttl_s = int(ttl_s)
        self.principal = dict(principal) if principal is not None else None
        self.ledger = ledger
        self.ledger_path: Path | None = None
        #: device id -> handle, in the order the devices were found.
        self.devices: dict[str, DeviceHandle] = {}
        #: Every client the lab talks through (one per endpoint).
        self.clients: list[MHSClient] = []
        self._owned: list[MHSClient] = []
        self._closed = False

    # -- construction -------------------------------------------------
    def _add_client(self, client: MHSClient, *, owned: bool) -> MHSClient:
        if all(client is not known for known in self.clients):
            self.clients.append(client)
            if owned:
                self._owned.append(client)
            if self.ledger is not None:
                self.ledger.track(client)
        return client

    def _add_devices(self, client: MHSClient, wanted: str | None = None) -> None:
        served = [str(item.get("device_id")) for item in client.devices()]
        chosen = served if wanted is None else [item for item in served if item == wanted]
        if wanted is not None and not chosen:
            raise MHSError("MHS.DEVICE.UNKNOWN", f"{client.endpoint_id or 'the endpoint'} does not serve {wanted}",
                           {"device_id": wanted, "served": served[:20]})
        for device_id in chosen:
            if device_id not in self.devices:
                self.devices[device_id] = client.device(device_id, mode=self.mode, ttl_s=self.ttl_s,
                                                        principal=self.principal, check=self.check)

    # -- access -------------------------------------------------------
    def device(self, name: str) -> DeviceHandle:
        """The handle of a device: its full id, or a unique segment of it (``"sample-mover"``)."""
        if name in self.devices:
            return self.devices[name]
        matches = [device_id for device_id in self.devices if name in _segments(device_id)]
        if len(matches) == 1:
            return self.devices[matches[0]]
        if matches:
            raise MHSError("MHS.HOST.DEVICE_AMBIGUOUS", f"{name!r} names several devices; use the full id",
                           {"candidates": matches})
        raise MHSError("MHS.DEVICE.UNKNOWN", f"no device {name!r} in this lab",
                       {"devices": list(self.devices)})

    __getitem__ = device

    def __iter__(self) -> Iterator[DeviceHandle]:
        return iter(list(self.devices.values()))

    def __len__(self) -> int:
        return len(self.devices)

    def __contains__(self, name: object) -> bool:
        try:
            self.device(str(name))
        except MHSError:
            return False
        return True

    @property
    def receipts(self) -> list[Receipt]:
        """Every receipt the handles returned, per device in lab order."""
        return [receipt for handle in self.devices.values() for receipt in handle.receipts]

    def estop(self, reason: str = "code file requested an emergency stop") -> list[Receipt]:
        """Engage the e-stop of every device (no session needed) and return the receipts.

        A refused stop is returned as its receipt, never raised.  A device
        whose stop raises (transport, authentication) never keeps the others
        from being stopped: every device is attempted first, then the first
        error is raised again with ``data["errors"]`` (``{device_id,
        mhs_code, message}`` per device) and ``data["receipts"]`` (the stops
        that were answered).
        """
        receipts: list[Receipt] = []
        failed: list[tuple[str, MHSError]] = []
        for device_id, handle in list(self.devices.items()):
            try:
                receipts.append(handle.estop(reason))
            except MHSError as exc:
                failed.append((device_id, exc))
        if failed:
            first = failed[0][1]
            errors = [{"device_id": device_id, "mhs_code": exc.code, "message": exc.message}
                      for device_id, exc in failed]
            raise MHSError(first.code,
                           f"e-stop not confirmed for {len(failed)} of {len(self.devices)} device(s): "
                           + "; ".join(f"{item['device_id']}: {item['mhs_code']}" for item in errors),
                           {"errors": errors, "receipts": [dict(item) for item in receipts]},
                           retryable=bool(first.retryable))
        return receipts

    # -- lifecycle ----------------------------------------------------
    def close(self, *, outcome: str = "completed", error: Mapping[str, Any] | None = None) -> Path | None:
        """Close every session and every client the lab opened; write its own ledger."""
        if self._closed:
            return self.ledger_path
        self._closed = True
        with _ACTIVE_LOCK:
            _OPEN_LABS.discard(self)
        for handle in list(self.devices.values()):
            handle.close()
        for client in self._owned:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - closing must never raise
                pass
        if self.ledger is not None:
            self.ledger_path = self.ledger.close(outcome=outcome, error=error)
        return self.ledger_path

    def __enter__(self) -> "Lab":
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> None:
        self.close(outcome=_outcome(exc), error=_error_record(exc) if exc is not None else None)

    def __repr__(self) -> str:
        return f"Lab({list(self.devices)!r})"


def lab(*targets: Any, check: bool = True, ledger: bool | str | os.PathLike[str] = True, mode: str | None = None,
        ttl_s: int = 600, token: str | None = None, principal: Mapping[str, Any] | None = None) -> Lab:
    """Connect to endpoints (or find devices) and return a :class:`Lab` of per-device handles.

    ``check=True`` makes every receipt-returning handle call raise
    :class:`~mhs.client.MHSRejected` unless the outcome is ``completed`` (or
    the work is still running).  ``ledger`` is ``True`` (write
    ``.mhs-run/<run id>.json`` on close), ``False`` or a directory; inside
    ``mhs run`` the run's ledger records everything instead.  ``mode`` is the
    session mode (default: each device's own).  ``token`` is the bearer token
    for the HTTP endpoints named in this call (an endpoint string, an
    in-process server, or the ``host:port`` of an ``mhs://`` device id that
    discovery does not list).  It is never sent to a discovered endpoint:
    discovery is a claim, so a device found through ``MHS_ENDPOINTS`` or the
    endpoints file is reached with that entry's own ``token_file`` only.
    A device that two discovered endpoints list raises
    ``MHS.HOST.DEVICE_AMBIGUOUS``; pass its endpoint instead.
    """
    if not targets:
        raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "lab() needs at least one endpoint or device id")
    own: Ledger | None = None
    if ledger is not False and active_ledger() is None:
        directory = LEDGER_DIR if ledger is True else ledger
        script = sys.argv[0] if sys.argv and sys.argv[0] and Path(sys.argv[0]).is_file() else None
        own = Ledger(script=script, argv=list(sys.argv) if script else None, directory=directory,
                     only_tracked=True)
    result = Lab(check=check, mode=mode, ttl_s=ttl_s, principal=principal, ledger=own)
    try:
        _resolve(result, targets, token=token)
    except BaseException as exc:
        result.close(outcome=_outcome(exc), error=_error_record(exc))
        raise
    if own is not None:
        with _ACTIVE_LOCK:
            _OPEN_LABS.add(result)
    return result


def _flush_at_exit() -> None:
    # A lab that was never closed still leaves its ledger (no network at exit).
    with _ACTIVE_LOCK:
        pending = list(_OPEN_LABS)
    for result in pending:
        if not result._closed and result.ledger is not None:  # noqa: SLF001
            try:
                result.ledger_path = result.ledger.close(outcome="unclosed")
            except Exception:  # noqa: BLE001 - nothing to report at interpreter exit
                pass


atexit.register(_flush_at_exit)


def _resolve(result: Lab, targets: Sequence[Any], *, token: str | None) -> None:
    by_target: dict[str, MHSClient] = {}
    discovered: list[Any] | None = None

    def connect_to(target: Any, key: str, *, auth: str | None, cwd: str | None = None) -> MHSClient:
        if key not in by_target:
            kwargs: dict[str, Any] = {"token": auth} if auth else {}
            if cwd:
                kwargs["cwd"] = cwd  # a stdio entry's working directory (endpoints.schema.json ``cwd``)
            by_target[key] = result._add_client(connect(target, **kwargs), owned=True)  # noqa: SLF001
        return by_target[key]

    for target in targets:
        if isinstance(target, MHSClient):
            result._add_devices(result._add_client(target, owned=False))  # noqa: SLF001
            continue
        if isinstance(target, (list, tuple)):
            client = connect_to(list(target), " ".join(str(part) for part in target), auth=None)
            result._add_devices(client)  # noqa: SLF001
            continue
        if not isinstance(target, str):
            if callable(getattr(target, "handle", None)):
                client = connect_to(target, f"inprocess:{id(target)}", auth=token)
                result._add_devices(client)  # noqa: SLF001
                continue
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", f"lab() cannot use {target!r} as an endpoint")
        if _is_endpoint_text(target):
            from .discovery import parse_target

            transport, url, command = parse_target(target)
            client = connect_to(url if transport == "http" else command, url or " ".join(command or []),
                                auth=token if transport == "http" else None)
            result._add_devices(client)  # noqa: SLF001
            continue
        # A device id or device name: one an endpoint named in this call already serves needs no lookup.
        if _device_id_for(target, list(result.devices)) is not None:
            continue
        if discovered is None:
            from .discovery import discover

            discovered = discover()
        endpoint = _endpoint_for(target, discovered)
        if endpoint is not None:
            from .discovery import token_of

            # Discovered is not trusted: only the entry's own token_file, never the caller's token.
            client = connect_to(endpoint.target, endpoint.key, auth=token_of(endpoint),
                                cwd=endpoint.cwd if endpoint.transport == "stdio" else None)
            result._add_devices(client, _device_id_for(target, endpoint.devices))  # noqa: SLF001
            continue
        if target.startswith("mhs://"):
            from .discovery import parse_target

            _transport, url, _command = parse_target(target)
            authority = target[len("mhs://"):].split("/", 1)[0]
            if ":" in authority.rsplit("]", 1)[-1]:
                client = connect_to(url, str(url), auth=token)
                result._add_devices(client, target)  # noqa: SLF001
                continue
        raise MHSError(
            "MHS.DEVICE.UNKNOWN",
            f"no configured endpoint serves device {target!r}: pass its endpoint (http://..., stdio:...) or list "
            "the endpoint in MHS_ENDPOINTS or ~/.mhs/endpoints.json",
            {"device_id": target},
        )


def _endpoint_for(name: str, endpoints: Sequence[Any]) -> Any:
    """The one discovered endpoint that lists ``name``; ``None``; ambiguous when several claim it."""
    claims = [endpoint for endpoint in endpoints if _device_id_for(name, endpoint.devices) is not None]
    if len(claims) > 1:
        raise MHSError("MHS.HOST.DEVICE_AMBIGUOUS",
                       f"{name!r} is listed by {len(claims)} discovered endpoints "
                       f"({', '.join(item.key for item in claims)}); pass the endpoint to lab() instead",
                       {"device_id": name, "endpoints": [item.key for item in claims]})
    return claims[0] if claims else None


def _device_id_for(name: str, devices: Sequence[str]) -> str | None:
    if name in devices:
        return name
    matches = [device_id for device_id in devices if name in _segments(device_id)]
    return matches[0] if len(matches) == 1 else None


# ---------------------------------------------------------------------------
# mhs run
# ---------------------------------------------------------------------------


def run_script(script: str | os.PathLike[str], args: Sequence[str] = (), *,
               ledger_dir: str | os.PathLike[str] = LEDGER_DIR) -> tuple[int, Path]:
    """Run a Python code file as ``__main__`` under one ledger; ``(exit code, ledger path)``.

    The exit code follows the CLI table: 0 the script finished, 1 a receipt
    was not ``completed`` (:class:`~mhs.client.MHSRejected`) or the script
    raised, 3 a transport error, 4 an authentication error (also a receipt
    refused with ``MHS.AUTH.*``), the script's own ``sys.exit`` code
    otherwise, 130 an interrupt.  The ledger is written in every case, to
    ``ledger_dir`` resolved against the working directory at the start (a
    script that changes directory does not move it; the working directory is
    restored afterwards).  ``FileNotFoundError`` when the script does not
    exist.
    """
    from .cli import exit_code_for

    path = Path(script)
    if not path.is_file():
        raise FileNotFoundError(f"{script}: no such code file")
    argv = [str(path), *[str(item) for item in args]]
    ledger = Ledger(script=path, argv=argv, directory=ledger_dir)
    saved_argv = list(sys.argv)
    saved_path = list(sys.path)
    saved_cwd = os.getcwd()
    sys.argv = argv
    sys.path.insert(0, str(path.resolve().parent))
    with _ACTIVE_LOCK:
        _ACTIVE.append(ledger)
    code = 0
    failure: BaseException | None = None
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            code = 0
        elif isinstance(exc.code, int):
            code = exc.code
        else:
            sys.stderr.write(f"{exc.code}\n")
            code = 1
    except KeyboardInterrupt as exc:
        failure, code = exc, 130
    except MHSRejected as exc:
        failure, code = exc, exit_code_for(exc)
        sys.stderr.write(f"mhs run: {exc.status} receipt {exc.receipt.get('receipt_id')}: {exc.code}: "
                         f"{exc.message}\n")
    except MHSError as exc:
        failure, code = exc, exit_code_for(exc)
        sys.stderr.write(f"mhs run: {exc.code}: {exc.message}\n")
    except BaseException as exc:  # noqa: BLE001 - the script's own failure is reported, never swallowed
        failure, code = exc, 1
        traceback.print_exc()
    finally:
        sys.argv = saved_argv
        sys.path[:] = saved_path
        try:
            os.chdir(saved_cwd)
        except OSError:  # pragma: no cover - the directory was removed by the script
            pass
        with _ACTIVE_LOCK:
            if ledger in _ACTIVE:
                _ACTIVE.remove(ledger)
    if failure is None and code not in (0, None):
        outcome = "exited"
    else:
        outcome = _outcome(failure)
    target = ledger.close(outcome=outcome, error=_error_record(failure) if failure is not None else None,
                          exit_code=code)
    return code, target


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------


def verify_ledger(ledger: Mapping[str, Any] | str | os.PathLike[str], bundle: Mapping[str, Any], *,
                  endpoint_id: str | None = None) -> dict[str, Any]:
    """Check a ledger's receipts against one endpoint's evidence bundle.

    The bundle's hash chain is verified offline (:func:`mhs.evidence.verify_bundle`);
    then every ledger receipt of that endpoint (``endpoint_id``, default the
    bundle's) with a final status must be in the bundle with the same command
    id, device, capability and status.  Receipts of other endpoints are not
    checked here; receipts still ``running``/``accepted``/``unknown`` in the
    ledger are listed as ``pending``.

    ``valid`` is false, with ``reasons``, when the chain does not verify
    (``chain_invalid``), a receipt is missing or differs
    (``missing_receipts``, ``mismatched_receipts``), the bundle's endpoint is
    not among the ledger's ``endpoints`` (``endpoint_not_in_ledger``), or the
    ledger has final receipts but none of them belongs to this endpoint
    (``no_receipts_for_endpoint``): a check against the wrong endpoint never
    passes by checking nothing.  Returns ``{valid, reasons, endpoint_id,
    chain, checked, missing, mismatched, pending}``.
    """
    from .evidence import verify_bundle

    document = ledger if isinstance(ledger, Mapping) else json.loads(Path(ledger).read_text(encoding="utf-8"))
    chain = verify_bundle(bundle)
    receipts = [item for item in bundle.get("receipts") or [] if isinstance(item, Mapping)]
    owner = endpoint_id or _bundle_endpoint(bundle)
    by_id = {str(item.get("receipt_id")): item for item in receipts}
    checked = 0
    missing: list[str] = []
    mismatched: list[dict[str, Any]] = []
    pending: list[str] = []
    finals = 0
    for entry in document.get("receipts") or []:
        if entry.get("status") in _FINAL:
            finals += 1
        if owner is not None and entry.get("endpoint_id") not in (None, owner):
            continue
        receipt_id = str(entry.get("receipt_id"))
        if entry.get("status") not in _FINAL:
            pending.append(receipt_id)
            continue
        checked += 1
        found = by_id.get(receipt_id)
        if found is None:
            missing.append(receipt_id)
            continue
        for key in ("command_id", "device_id", "capability_id", "status"):
            if entry.get(key) is not None and found.get(key) != entry.get(key):
                mismatched.append({"receipt_id": receipt_id, "field": key, "ledger": entry.get(key),
                                   "evidence": found.get(key)})
    reasons: list[str] = []
    if not chain.get("valid"):
        reasons.append("chain_invalid")
    if missing:
        reasons.append("missing_receipts")
    if mismatched:
        reasons.append("mismatched_receipts")
    listed = {str(item.get("endpoint_id")) for item in document.get("endpoints") or []
              if isinstance(item, Mapping) and item.get("endpoint_id")}
    if owner is not None and listed and owner not in listed:
        reasons.append("endpoint_not_in_ledger")
    if finals and not checked:
        reasons.append("no_receipts_for_endpoint")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "endpoint_id": owner,
        "chain": {"valid": bool(chain.get("valid")), "checked": chain.get("checked"),
                  "head_digest": chain.get("head_digest"), "errors": list(chain.get("errors") or [])[:5]},
        "checked": checked,
        "missing": missing,
        "mismatched": mismatched,
        "pending": pending,
    }


def _bundle_endpoint(bundle: Mapping[str, Any]) -> str | None:
    info = bundle.get("endpoint_info") if isinstance(bundle.get("endpoint_info"), Mapping) else {}
    genesis = bundle.get("genesis") if isinstance(bundle.get("genesis"), Mapping) else {}
    document = genesis.get("genesis_document") if isinstance(genesis.get("genesis_document"), Mapping) else {}
    value = bundle.get("endpoint") or info.get("endpoint_id") or document.get("endpoint_id")
    return str(value) if value else None
