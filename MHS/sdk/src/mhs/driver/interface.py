"""The generated interface contract, ``MHS/sdk/INTERFACE.md`` (``python -m mhs.driver --print-interface``).

The text is built from the code (signatures, ``__all__`` lists, the gate
table, the command-line parser), so it cannot drift: CI regenerates it and
diffs it against the committed file.
"""

from __future__ import annotations

import inspect
import os
import re
from typing import Any, Callable, Iterable

from .. import _ids

__all__ = ["interface_text"]

_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")


def _default(value: Any) -> str:
    text = repr(value)
    if _ADDRESS.search(text) or len(text) > 60:
        return "<default>"
    return text


def signature(fn: Callable[..., Any], *, skip_self: bool = False) -> str:
    """``(a, b=1, *, c=None)`` without annotations, with stable defaults."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return "(...)"
    parts: list[str] = []
    star = False
    for index, param in enumerate(sig.parameters.values()):
        if skip_self and index == 0 and param.name in ("self", "cls"):
            continue
        if param.kind is param.VAR_POSITIONAL:
            parts.append(f"*{param.name}")
            star = True
            continue
        if param.kind is param.VAR_KEYWORD:
            parts.append(f"**{param.name}")
            continue
        if param.kind is param.KEYWORD_ONLY and not star:
            parts.append("*")
            star = True
        text = param.name
        if param.default is not param.empty:
            text += f"={_default(param.default)}"
        parts.append(text)
    return "(" + ", ".join(parts) + ")"


def _summary(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    first = doc.strip().split("\n\n", 1)[0].replace("\n", " ").strip()
    return first.replace("|", "\\|")


def _rows(module: Any, names: Iterable[str]) -> list[str]:
    lines = ["| Name | Signature | Summary |", "|---|---|---|"]
    for name in names:
        obj = getattr(module, name)
        if inspect.isclass(obj):
            sig = signature(obj)
            kind = "class"
        elif callable(obj):
            sig = signature(obj)
            kind = "function"
        else:
            sig, kind = "", "constant"
        summary = _summary(obj) if kind != "constant" else f"`{_default(obj)}`"
        lines.append(f"| `{name}` | `{sig}` | {summary} |" if sig else f"| `{name}` | {kind} | {summary} |")
    return lines


def _cli_section() -> list[str]:
    from .__main__ import build_parser

    # argparse wraps at the terminal width and may colour its output: fix both so the text is stable.
    saved = {key: os.environ.get(key) for key in ("COLUMNS", "NO_COLOR", "FORCE_COLOR", "PYTHON_COLORS")}
    os.environ.update({"COLUMNS": "200", "NO_COLOR": "1", "PYTHON_COLORS": "0"})
    os.environ.pop("FORCE_COLOR", None)
    try:
        return _usage_lines(build_parser())
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _usage_lines(parser: Any) -> list[str]:
    lines = ["```text", parser.format_usage().strip()]
    for action in parser._actions:  # noqa: SLF001 - argparse has no public accessor for subparsers
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            for name, sub in choices.items():
                lines.append(sub.format_usage().strip())
                for inner in sub._actions:  # noqa: SLF001
                    nested = getattr(inner, "choices", None)
                    if isinstance(nested, dict):
                        for nested_parser in nested.values():
                            lines.append(nested_parser.format_usage().strip())
    lines.append("```")
    return [line.replace("usage: ", "") for line in lines]


def interface_text() -> str:
    """The full text of ``MHS/sdk/INTERFACE.md``."""
    import mhs.adapter as adapter
    import mhs.driver as driver
    import mhs.testing as testing
    import mhs.server as server
    from mhs.client import MHSClient

    from .check import GATES, REPO_TEST_TIMEOUT_S, TOOL_LIMIT_BYTES

    gate_text = {
        "G1": "required files, task.json names this directory (and equals the registry card), "
              "no symlink out of the package, the clone exists and is unmodified",
        "G2": "driver.lock.json validates and pins the card's package id, commit, repository and licence",
        "G3": "catalogue classes and kinds, no drift or widening, limit paths resolve, the card's expected mode and "
              "risk floor, hardware R1+ has @estop, safe_state and limits on every numeric input, every Limit cites "
              "source+ref; "
              "a hardware driver's fake is not the upstream native class; package code never exits, patches or "
              "reaches into the interpreter, the runtime or the gate",
        "G4": "every Limit/Fact ref path:LINE exists in the clone at the pinned commit",
        "G5": "reference.json and REFERENCE.md equal a fresh `reference` output",
        "G6": "on fresh in-process endpoints: reads, in-range writes and actions reach the fake, every "
              "bound/element/leaf is refused ENVELOPE_VIOLATION with zero native calls, e-stop cancels a running "
              "action and calls the native stop, latched refusals, agent reset refused on hardware, native failure "
              "gives failed, operator_required gives LIMITS_UNSET, outputs validate",
        "G7": "attributes the fake defines or the driver touches exist on the native class (AST of "
              "the pinned clone, never imported); serial/SCPI: command mnemonics occur in the clone; "
              "ROS: pinned endpoint/type evidence, generated action wire types and exact cancellation scope",
        "G8": f"in-process conformance MHS-Sim CL3; MCP projection builds; inputs have a "
              f"description and a unit; tool description and driver-owned tool part <= {TOOL_LIMIT_BYTES} bytes",
        "G9": f"test_driver.py keeps the check_driver call and passes in <= {REPO_TEST_TIMEOUT_S} s "
              "with the network disabled",
    }
    client_methods = ["hello", "devices", "inspect", "open_session", "read", "invoke", "subscribe", "events",
                      "cancel", "snapshot", "restore", "safety_status", "estop", "reset", "permit",
                      "export_evidence", "close"]
    server_names = ["MHSServer", "Device", "Resource", "Capability", "SafetyEnvelope"]
    missing = [name for name in client_methods if not callable(getattr(MHSClient, name, None))]
    missing += [name for name in server_names if not hasattr(server, name)]
    if missing:
        raise RuntimeError(f"the frozen client/server names {missing} are gone; the interface contract is broken")
    lines: list[str] = [
        _ids.NON_AFFILIATION,
        "",
        f"# {_ids.PROJECT_NAME} SDK interface contract (generated)",
        "",
        "Generated by `python3 -m mhs.driver --print-interface` from the code; do not edit by hand. "
        f"Distribution `{_ids.DIST_NAME}` {_ids.SDK_VERSION}, import name `mhs`, specification {_ids.SPEC_VERSION}, "
        f"wire revision `mhs_version: \"{_ids.WIRE_VERSION}\"`. Python 3.10+, standard library only.",
        "",
        "## Driver package layout",
        "",
        "One directory per upstream repository: `MHS/drivers/<track>/<owner>__<repo>/`.",
        "",
        "| File | Content |",
        "|---|---|",
        "| `task.json` | the task card (input; never edited) |",
        "| `driver.py` | one `mhs.driver.Driver` subclass (or a family config subclass) |",
        "| `fake.py` and/or `fixtures/` | the fake backend (only attributes of the upstream class), transcripts, "
        "`fixtures/conformance.json` |",
        "| `native.py` | the hardware backend factory (never imported by the gate) |",
        "| `facts.md` | tags and facts with source and `path:LINE` |",
        "| `test_driver.py` | calls `mhs.testing.check_driver(HERE)`; cases may be added, never removed |",
        "| `driver.lock.json` | pinned upstream, install, backends, `authored_by`, `reviewed_by` |",
        "| `reference.json`, `REFERENCE.md` | generated by `python3 -m mhs.driver reference <dir>` |",
        "| `site-limits.example.json` | optional narrow-only operator overlay |",
        "| `RESULT.json` | `pass`, `blocked` or `skip-proposed` with codes |",
        "",
        "## Driver API (`mhs.driver`)",
        "",
        *_rows(driver, driver.__all__),
        "",
        "## Loader (`mhs.adapter`)",
        "",
        *_rows(adapter, adapter.__all__),
        "",
        f"`LoadError.reason` is one of {', '.join(f'`{item}`' for item in adapter.LoadError.REASONS)}.",
        "",
        "## Acceptance gate (`python3 -m mhs.driver check <dir> --backend fake`)",
        "",
        "Exit status 0 pass, 1 fail (the failing gate ids are printed), 2 usage error. Writes `check-report.json` "
        "(`check-report.schema.json`). A pass on a fake or sim backend is evidence `contract_checked`, never an "
        "MHS-Device level. The command never imports the package: the gates run in a child process with the "
        "network and device files disabled, and only a schema-valid passing report from it exits 0.",
        "",
        "| Gate | Name | Checks |",
        "|---|---|---|",
        *[f"| {gate_id} | {name} | {gate_text[gate_id]} |" for gate_id, name in GATES],
        "",
        "## Command line (`python3 -m mhs.driver`)",
        "",
        *_cli_section(),
        "",
        "## Test helpers (`mhs.testing`)",
        "",
        *_rows(testing, testing.__all__),
        "",
        "## Client, server and conformance surface",
        "",
        "Names only (their signatures belong to the modules that define them; add names, never change one):",
        "",
        "- `mhs.connect(endpoint)` returns an `MHSClient` with " + ", ".join(f"`{name}()`" for name in client_methods)
        + ".",
        "- `mhs.server`: " + ", ".join(f"`{name}`" for name in server_names) + ".",
        "- `mhs.conformance.run_suite(client, profile, level)` and "
        "`mhs.conformance.inprocess.run_suite_inprocess(factory, profile, level)` return a conformance report.",
        "",
        "`client.invoke()` returns a receipt for rejected, failed and unknown outcomes and raises `MHSError` only "
        "for transport, protocol and session failures: a refused physical action is evidence, not an exception.",
        "",
    ]
    return "\n".join(lines)
