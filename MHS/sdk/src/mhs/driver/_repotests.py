"""Gate G9 child process: run a package's ``test_driver.py`` with the network and device files disabled.

``python -m mhs.driver._repotests <test_driver.py> [--result <file>]``
refuses every socket connection, datagram and name lookup that is not
loopback (``127.0.0.0/8``, ``::1``, ``localhost``) or a Unix socket, and
every open of a device file under ``/dev`` (serial ports, USB nodes; not
``/dev/null``, ``/dev/urandom``, ``/dev/tty`` or the standard streams), then
loads the file and runs its ``unittest`` cases.  Exit status 0 means at least
one test ran and all passed.  With ``--result`` the outcome is also written
to ``<file>`` as JSON (``{"ok", "tests_run", "failures", "errors", "skipped"}``)
after the cases ran, and the process ends with :func:`os._exit` (no
``atexit`` hook or leftover thread of the package runs after it): the gate
requires that file, so a ``test_driver.py`` that exits the interpreter early
(``SystemExit``, ``os._exit``) never passes.  The gate sets
``MHS_DRIVER_GATE_INNER`` so the file's own ``mhs.testing.check_driver`` call
skips G9 (no recursion).

:func:`guard_process` (network and device guard) is also applied by the
gate's own child process (:mod:`mhs.driver._gate`).
"""

from __future__ import annotations

import builtins
import errno
import importlib.util
import io
import json
import os
import socket
import sys
import traceback
import unittest
from typing import Any

_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"})
#: Device files a test process may open (everything else under /dev is refused while the gate runs).
_DEVICE_ALLOWED = frozenset({"/dev/null", "/dev/zero", "/dev/full", "/dev/random", "/dev/urandom", "/dev/tty",
                             "/dev/stdin", "/dev/stdout", "/dev/stderr"})
_DEVICE_ALLOWED_PREFIXES = ("/dev/fd/", "/dev/shm/")


def _loopback(host: Any) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    host = host.strip("[]").lower()
    return host in _LOOPBACK_NAMES or host.startswith("127.") or host in ("::1", "0:0:0:0:0:0:0:1")


def _check(address: Any) -> None:
    if isinstance(address, (str, bytes)):
        return  # AF_UNIX path
    if isinstance(address, tuple) and address and _loopback(address[0]):
        return
    raise OSError(errno.ENETUNREACH, f"network access is disabled while the acceptance gate runs test_driver.py "
                                     f"(G9): {address!r}")


def disable_network() -> None:
    """Patch :mod:`socket` so only loopback and Unix sockets work in this process."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo

    def connect(self: socket.socket, address: Any) -> Any:
        _check(address)
        return original_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> Any:
        _check(address)
        return original_connect_ex(self, address)

    def sendto(self: socket.socket, data: Any, *args: Any) -> Any:
        _check(args[-1] if args else None)
        return original_sendto(self, data, *args)

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host is not None and not _loopback(host):
            raise socket.gaierror(socket.EAI_NONAME, f"name lookup is disabled during the acceptance gate (G9): {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = sendto  # type: ignore[method-assign]
    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]


def _device_path(path: Any) -> str | None:
    """The real path of ``path`` when it is a device file the gate refuses, else ``None``."""
    if isinstance(path, int):
        return None  # an already open descriptor
    try:
        text = os.fsdecode(os.fspath(path))
    except TypeError:
        return None
    if not text:
        return None
    real = os.path.realpath(text)
    for candidate in (text, real):
        if candidate.startswith("/dev/") and candidate not in _DEVICE_ALLOWED \
                and not candidate.startswith(_DEVICE_ALLOWED_PREFIXES):
            return candidate
    return None


def _refuse_device(path: str) -> OSError:
    return PermissionError(errno.EACCES, "device files are not opened while the acceptance gate runs (the fake "
                                         "backend never touches hardware)", path)


def disable_devices() -> None:
    """Patch :func:`open` / :func:`io.open` / :func:`os.open` so device files under ``/dev`` cannot be opened."""
    original_open = builtins.open
    original_os_open = os.open

    def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        device = _device_path(file)
        if device is not None:
            raise _refuse_device(device)
        return original_open(file, *args, **kwargs)

    def guarded_os_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        device = _device_path(path)
        if device is not None:
            raise _refuse_device(device)
        return original_os_open(path, *args, **kwargs)

    builtins.open = guarded_open  # type: ignore[assignment]
    io.open = guarded_open  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    # Python 3.10's pathlib bound io.open when it was imported (Path.open goes through its accessor).
    import pathlib

    accessor = getattr(pathlib, "_NormalAccessor", None)
    if accessor is not None and getattr(accessor, "open", None) is original_open:
        accessor.open = staticmethod(guarded_open)  # type: ignore[attr-defined]


#: True once :func:`guard_process` ran in this process.
GUARDED = False


def guard_process() -> None:
    """The process guard of the gate's child processes: no network, no device files, no bytecode.

    It also sets ``MHS_PROCESS_GUARDED=1`` for the processes this one starts: an isolated simulator host
    (:mod:`mhs.bridge.sim_host`) started under the gate applies this same guard before it imports package code, or
    refuses to start.
    """
    global GUARDED
    sys.dont_write_bytecode = True
    disable_network()
    disable_devices()
    os.environ["MHS_PROCESS_GUARDED"] = "1"
    GUARDED = True


def _describe(exc: BaseException) -> str:
    if isinstance(exc, SystemExit):
        return (f"SystemExit({exc.code!r}): package code exited the interpreter (sys.exit/exit/raise SystemExit); "
                "a test never ends the process")
    return f"{type(exc).__name__}: {exc}"


def _run(path: str) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("mhs_gate_test_driver", path)
    if spec is None or spec.loader is None:
        return {"ok": False, "error": f"cannot load {path}"}
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001 - SystemExit at import is a failure, never a pass
        return {"ok": False, "error": f"{path} cannot be imported: {_describe(exc)}"}
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # noqa: BLE001 - a fixture that exits the interpreter fails the run
        traceback.print_exc(file=sys.stderr)
        return {"ok": False, "error": f"the test run did not complete: {_describe(exc)}"}
    outcome = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped)}
    if result.testsRun == 0:
        return {"ok": False, "error": "test_driver.py defines no test", **outcome}
    return {"ok": bool(result.wasSuccessful()), **outcome}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    result_path = None
    if len(args) == 3 and args[1] == "--result":
        result_path = args[2]
        args = args[:1]
    if len(args) != 1:
        print("usage: python -m mhs.driver._repotests <test_driver.py> [--result <file>]", file=sys.stderr)
        return 2
    guard_process()
    outcome = _run(args[0])
    if outcome.get("error"):
        print(outcome["error"], file=sys.stderr)
    code = 0 if outcome.get("ok") else 1
    if result_path is None:
        return code
    try:
        with open(result_path, "w", encoding="utf-8") as handle:
            json.dump(outcome, handle)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    raise SystemExit(main())
