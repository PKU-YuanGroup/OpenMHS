#!/usr/bin/env python3
"""Produce ``MHS/sdk/docs/e2e-transcript.txt`` from a live conveyor endpoint.

Run with the SDK on the path::

    PYTHONPATH=MHS/sdk/src python3 MHS/sdk/tests/core/_e2e_transcript.py

The script drives the deterministic conveyor endpoint over both bindings:

* stdio: hello, devices.list, session.open, resource.read, world.step, the
  same command_id again (idempotent replay), e-stop + rejected command + reset,
  and evidence export/verify;
* stdio with ``--test-profile``: open the simulated safety door and show the
  interlock rejection;
* HTTP on 127.0.0.1:7400: hello, devices.list, session, step, plus the ``mhs``
  CLI ``devices`` command.

It writes a human-readable transcript, cleans up every child process, and exits
non-zero if the contract checks fail.  The transcript never contains absolute
paths: the interpreter is shown as ``python3`` and the checkout as ``<repo>``.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
SDK = REPO / "MHS" / "sdk"
OUT = SDK / "docs" / "e2e-transcript.txt"
PYTHON = sys.executable
PYTHONPATH = str(SDK / "src")

if PYTHONPATH not in sys.path:
    sys.path.insert(0, PYTHONPATH)

from mhs import connect  # noqa: E402
from mhs.canonical import ulid  # noqa: E402
from mhs.errors import MHSError  # noqa: E402

LINES: list[str] = []
FAILURES: list[str] = []


def _shown(argv: list[str]) -> str:
    """A command line as a reader would type it (no interpreter path)."""
    return " ".join("python3" if part == PYTHON else part for part in argv)


def _scrub(text: str) -> str:
    """Remove machine-specific absolute paths, and source line numbers, from the transcript text.

    A captured warning names ``<file>.py:<line>``; the line moves with every
    edit of that file, so it is shown as ``<file>.py:<line>`` literally.
    """
    replacements = [(str(REPO), "<repo>"), (PYTHON, "python3"),
                    (os.path.realpath(PYTHON), "python3"), (str(Path.home()), "~")]
    for old, new in sorted(replacements, key=lambda item: -len(item[0])):
        if old:
            text = text.replace(old, new)
    return re.sub(r"(\.py):\d+:", r"\1:<line>:", text)


def record(title: str, payload: Any) -> None:
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    LINES.append(f"\n### {title}   [{stamp}]\n")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    LINES.append(text + "\n")
    print(f"--- {title}")


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        LINES.append(f"\n!! CHECK FAILED: {message}\n")
        print(f"CHECK FAILED: {message}", file=sys.stderr)


def _invoke(client: Any, capability: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Invoke and return a receipt; protocol/session errors are transcript entries."""
    try:
        return client.invoke(capability, payload, **kwargs)
    except MHSError as exc:
        return {"status": "error", "error": {"mhs_code": exc.code, "message": exc.message}}


def _stdio_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = PYTHONPATH + os.pathsep + env.get("PYTHONPATH", "")
    return env


def section_stdio() -> None:
    LINES.append("\n" + "=" * 78 + "\n=== A. stdio transport: mhs.reference conveyor --stdio\n" + "=" * 78 + "\n")
    argv = [PYTHON, "-m", "mhs.reference", "conveyor", "--stdio"]
    LINES.append("$ " + _shown(argv) + "\n")
    client = connect(argv, env=_stdio_env())
    try:
        hello = client.hello()
        record(
            "A1 mhs.hello",
            {
                "server": hello.get("server"),
                "implementation": hello.get("implementation"),
                "spec_version": hello.get("spec_version"),
                "mhs_version": hello.get("mhs_version"),
                "endpoint_id": hello.get("endpoint_id"),
                "features": hello.get("features"),
                "device_ids": [d.get("device_id") for d in hello.get("devices") or []],
            },
        )
        check(hello.get("mhs_version") == "1.0", "hello.mhs_version is 1.0")
        check("MHS.SAFETY.NOT_CERTIFIED" in (hello.get("features") or []), "hello discloses NOT_CERTIFIED")

        devices = client.devices()
        record("A2 mhs.devices.list", [{"device_id": d.get("device_id"), "mode": d.get("mode"),
                                        "capabilities": [c.get("capability_id") for c in d.get("capabilities") or []]}
                                       for d in devices])
        check(len(devices) == 1, "one device is listed")
        device_id = devices[0]["device_id"]
        check(devices[0].get("mode") == "simulated", "device mode is simulated")

        session = client.open_session([device_id], capabilities=None, mode="simulated", ttl_s=600)
        record(
            "A3 mhs.session.open",
            {k: session.get(k) for k in ("session_id", "mode", "expires_at", "granted")},
        )
        check(str(session.get("session_id", "")).startswith("mhs_s_"), "session id is mhs_s_…")

        before = client.read("workcell", device_id=device_id)
        record(
            "A4 mhs.resource.read (before)",
            {"revision": before.get("revision"), "state_hash": before.get("state_hash"),
             "state": {k: before.get("state", {}).get(k) for k in ("tick", "drive", "gate", "door", "estop")}},
        )
        check(before.get("state_hash", "").startswith("sha256:"), "read returns a state_hash")

        command_id = ulid()
        first = _invoke(client, "cap.world.step.v1", {"ticks": 5}, device_id=device_id, command_id=command_id)
        record(
            "A5 mhs.command cap.world.step.v1 {ticks: 5}",
            {k: first.get(k) for k in ("receipt_id", "command_id", "status", "state_revision_before",
                                        "state_revision_after", "state_hash_after", "replayed", "error")},
        )
        check(first.get("status") == "completed", "step command completed")
        check(first.get("state_revision_after") == (before.get("revision") or 0) + 1,
              "accepted mutation advances the device revision by one")

        second = _invoke(client, "cap.world.step.v1", {"ticks": 5}, device_id=device_id, command_id=command_id)
        record(
            "A6 same command_id again (idempotent replay)",
            {k: second.get(k) for k in ("receipt_id", "command_id", "status", "replayed",
                                        "state_revision_after", "error")},
        )
        check(second.get("replayed") is True, "identical replay is marked replayed=true")
        check(second.get("receipt_id") == first.get("receipt_id"), "identical replay returns the retained receipt")
        check(second.get("state_revision_after") == first.get("state_revision_after"),
              "identical replay does not advance the revision")

        estop = _invoke(client, "cap.world.step.v1", {}, device_id=device_id)  # ignored; keep session warm
        estop = client.estop("e2e transcript: emergency stop", device_id=device_id)
        record(
            "A7 mhs.safety.estop",
            {k: estop.get(k) for k in ("receipt_id", "command_id", "status", "output", "effects", "error")},
        )
        check(estop.get("status") == "completed", "e-stop receipt is completed")
        status = client.safety_status(device_id)
        record("A8 mhs.safety.status", {"estop": status.get("estop"), "interlocks": status.get("interlocks"),
                                         "safe_state": status.get("safe_state")})
        check((status.get("estop") or {}).get("engaged") is True, "safety.status reports the e-stop engaged")

        blocked = _invoke(client, "cap.world.step.v1", {"ticks": 1}, device_id=device_id, command_id=ulid())
        code = (blocked.get("error") or {}).get("mhs_code")
        record(
            "A9 command while e-stop is engaged (must be rejected, never executed)",
            {"status": blocked.get("status"), "error": blocked.get("error")},
        )
        check(blocked.get("status") == "rejected", "command under e-stop returns a rejected receipt")
        check(code in ("MHS.SAFETY.ESTOP_ENGAGED", "MHS.SAFETY.INTERLOCK_OPEN"),
              f"e-stop rejection carries a safety code (got {code!r})")

        reset = client.reset(device_id=device_id)
        record("A10 mhs.safety.reset", {k: reset.get(k) for k in ("status", "output", "error")})
        check(reset.get("status") == "completed", "reset completed")

        recovered = _invoke(client, "cap.world.step.v1", {"ticks": 1}, device_id=device_id, command_id=ulid())
        record("A11 command after reset", {"status": recovered.get("status"),
                                            "state_revision_after": recovered.get("state_revision_after")})
        check(recovered.get("status") == "completed", "commands work again after reset")

        bundle = client.export_evidence()
        verification = client.verify_evidence(bundle)
        record(
            "A12 mhs.evidence.export + mhs.evidence.verify",
            {
                "receipts": len(bundle.get("receipts") or []),
                "head_digest": bundle.get("head_digest"),
                "valid": verification.get("valid"),
                "checked": verification.get("checked"),
                "errors": verification.get("errors"),
            },
        )
        check(verification.get("valid") is True, "exported evidence bundle verifies offline")
    finally:
        client.close()
        LINES.append("\n(stdio child process closed)\n")


def section_interlock() -> None:
    LINES.append("\n" + "=" * 78 + "\n=== B. interlock case: conveyor --stdio --test-profile\n" + "=" * 78 + "\n")
    argv = [PYTHON, "-m", "mhs.reference", "conveyor", "--stdio", "--test-profile"]
    LINES.append("$ " + _shown(argv) + "\n")
    client = connect(argv, env=_stdio_env())
    try:
        device_id = client.devices()[0]["device_id"]
        client.open_session([device_id], capabilities=None, mode="simulated", ttl_s=600)
        opened = _invoke(client, "x-cap.mhs-test.set_door.v1", {"state": "open"}, device_id=device_id,
                         command_id=ulid())
        record("B1 open the simulated safety door", {"status": opened.get("status"),
                                                      "error": opened.get("error")})
        # Plan 3.6: the permit (step 10) is checked before the interlocks
        # (step 11), so the permit-gated valve move carries a valid permit and
        # only the open door can refuse it.
        try:
            permit = client.permit(
                "cap.actuation.valve.v1", {"gate": "main"}, device_id=device_id,
                resource=client.capability_resource("cap.actuation.valve.v1", device_id=device_id),
            )
        except MHSError as exc:
            permit = {"error": {"mhs_code": exc.code, "message": exc.message}}
        record("B2 permit for the diverter move (mhs.safety.permit.request)",
               {"granted": bool(permit.get("permit_id")), "error": permit.get("error")})
        check(bool(permit.get("permit_id")), "the valve permit is granted")
        valve = _invoke(client, "cap.actuation.valve.v1", {"gate": "main"}, device_id=device_id,
                        command_id=ulid(), permit_id=permit.get("permit_id"))
        code = (valve.get("error") or {}).get("mhs_code")
        record(
            "B3 diverter move with the door open (must be rejected by the interlock)",
            {"status": valve.get("status"), "error": valve.get("error")},
        )
        check(valve.get("status") == "rejected", "open interlock produces a rejected receipt")
        check(code == "MHS.SAFETY.INTERLOCK_OPEN",
              f"interlock rejection carries MHS.SAFETY.INTERLOCK_OPEN (got {code!r})")
        closed = _invoke(client, "x-cap.mhs-test.set_door.v1", {"state": "closed"}, device_id=device_id,
                         command_id=ulid())
        record("B4 close the safety door", {"status": closed.get("status")})
    finally:
        client.close()
        LINES.append("\n(test-profile stdio child process closed)\n")


def _wait_for_ready(proc: subprocess.Popen[str], timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout is not None else ""
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"server exited with {proc.returncode}")
            time.sleep(0.05)
            continue
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("mhs_ready"):
            return payload
    raise RuntimeError("HTTP endpoint did not announce readiness")


def section_http() -> None:
    LINES.append("\n" + "=" * 78 + "\n=== C. HTTP transport: mhs.reference conveyor --port 7400 + mhs CLI\n" + "=" * 78 + "\n")
    argv = [PYTHON, "-m", "mhs.reference", "conveyor", "--port", "7400"]
    LINES.append("$ " + _shown(argv) + "\n")
    env = _stdio_env()
    proc = subprocess.Popen(
        argv,
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready = _wait_for_ready(proc)
        LINES.append("server ready: " + json.dumps(ready, sort_keys=True) + "\n")
        base = ready.get("url") or "http://127.0.0.1:7400"

        descriptor = json.loads(urllib.request.urlopen(base + "/.well-known/mhs.json", timeout=5).read())
        record("C1 GET /.well-known/mhs.json", descriptor)
        check(descriptor.get("mhs_version") == "1.0", "well-known descriptor has mhs_version")

        schema = json.loads(
            urllib.request.urlopen(base + "/mhs/v1/schema/device.schema.json", timeout=5).read()
        )
        record("C2 GET /mhs/v1/schema/device.schema.json", {"title": schema.get("title"),
                                                             "id": schema.get("$id")})
        check(str(schema.get("$id", "")).endswith("/device.schema.json"),
              "schema route serves the device schema")

        client = connect(base)
        try:
            hello = client.hello()
            record("C3 HTTP mhs.hello", {"mhs_version": hello.get("mhs_version"),
                                          "endpoint_id": hello.get("endpoint_id")})
            devices = client.devices()
            device_id = devices[0]["device_id"]
            record("C4 HTTP mhs.devices.list", [{"device_id": d.get("device_id"), "mode": d.get("mode")}
                                                 for d in devices])
            session = client.open_session([device_id], capabilities=None, mode="simulated", ttl_s=300)
            record("C5 HTTP mhs.session.open", {"session_id": session.get("session_id"),
                                                "expires_at": session.get("expires_at")})
            receipt = _invoke(client, "cap.world.step.v1", {"ticks": 2}, device_id=device_id, command_id=ulid())
            record("C6 HTTP mhs.command", {k: receipt.get(k) for k in ("status", "state_revision_after",
                                                                        "state_hash_after", "error")})
            check(receipt.get("status") == "completed", "HTTP command completed")
            bundle = client.export_evidence()
            verify = client.verify_evidence(bundle)
            record("C7 HTTP evidence export/verify", {"receipts": len(bundle.get("receipts") or []),
                                                       "valid": verify.get("valid")})
            check(verify.get("valid") is True, "HTTP evidence verifies")
        finally:
            client.close()

        cli_argv = [PYTHON, "-m", "mhs.cli", "devices", "--endpoint", base, "--json"]
        LINES.append("\n$ " + _shown(cli_argv) + "\n")
        cli = subprocess.run(cli_argv, cwd=str(REPO), env=env, capture_output=True, text=True, timeout=30)
        LINES.append(f"exit code: {cli.returncode}\n")
        if cli.stderr.strip():
            LINES.append("stderr:\n" + cli.stderr + "\n")
        try:
            parsed = json.loads(cli.stdout)
        except json.JSONDecodeError:
            parsed = cli.stdout
        record("C8 mhs CLI devices --json", parsed)
        check(cli.returncode == 0, "mhs CLI devices exits 0")
    finally:
        proc.terminate()
        try:
            _, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate(timeout=5)
        if stderr and stderr.strip():
            LINES.append("\n(server stderr)\n" + stderr.strip() + "\n")
        LINES.append(f"\n(HTTP server exited: {proc.returncode})\n")


def main() -> int:
    LINES.append(
        "OpenMHS SDK end-to-end transcript\n"
        f"generated: {datetime.now(timezone.utc).isoformat()}\n"
        f"python:    {sys.version.split()[0]}\n"
        f"platform:  {platform.system()} {platform.machine()}\n"
        f"generator: PYTHONPATH=MHS/sdk/src python3 MHS/sdk/tests/core/_e2e_transcript.py\n"
        f"commands:  PYTHONPATH=MHS/sdk/src python3 -m mhs.reference conveyor --stdio\n"
        f"           PYTHONPATH=MHS/sdk/src python3 -m mhs.reference conveyor --port 7400\n"
        f"           PYTHONPATH=MHS/sdk/src python3 -m mhs.cli devices --endpoint http://127.0.0.1:7400 --json\n"
    )
    starts = time.time()
    try:
        section_stdio()
        section_interlock()
        section_http()
    except BaseException as exc:  # noqa: BLE001 - transcript records the failure
        import traceback

        FAILURES.append(f"{type(exc).__name__}: {exc}")
        LINES.append("\n!! E2E ABORTED\n" + traceback.format_exc() + "\n")
        print(traceback.format_exc(), file=sys.stderr)
    duration = time.time() - starts
    if FAILURES:
        LINES.append("\nRESULT: FAIL\n")
        for failure in FAILURES:
            LINES.append(f" - {failure}\n")
    else:
        LINES.append("\nRESULT: PASS — all contract checks held over stdio and HTTP.\n")
    LINES.append(f"\nduration: {duration:.2f}s\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(_scrub("".join(LINES)), encoding="utf-8")
    print(f"wrote {OUT} ({'PASS' if not FAILURES else 'FAIL'})")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
