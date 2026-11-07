"""The gate's child process: ``python -m mhs.driver check`` runs the gates here, never in its own process.

``python -m mhs.driver._gate --result <file> --progress <file> --backend <b>
[--root <dir>] [--clone <dir>] [--companions-root <dir>] <driver dir>`` disables the network and device
files (:func:`mhs.driver._repotests.guard_process`), runs
:func:`mhs.driver.check.run_check` without writing a report, appends one JSON
line per stage to ``--progress`` (``{"stage": "G6"}`` when a gate starts,
``{"gate": {...}}`` when it ends, ``{"tampered": [...]}`` when an ``mhs``
module changed), writes the report to ``--result`` and ends
with :func:`os._exit` (no ``atexit`` hook or leftover thread of the package
runs after the report is written).  The parent (:func:`mhs.driver.check.run_check_isolated`)
exits 0 only for a schema-valid passing report whose digest checks out, so
package code that exits the interpreter (``SystemExit``, ``os._exit``) or
crashes it can never make the gate pass.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any


def _parse(argv: list[str]) -> dict[str, Any] | None:
    options: dict[str, Any] = {"root": None, "clone": None, "backend": "fake", "companions_root": None}
    positional: list[str] = []
    keys = {"--result": "result", "--progress": "progress", "--backend": "backend", "--root": "root",
            "--clone": "clone", "--companions-root": "companions_root"}
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in keys:
            if index + 1 >= len(argv):
                return None
            options[keys[item]] = argv[index + 1]
            index += 2
            continue
        positional.append(item)
        index += 1
    if len(positional) != 1 or not options.get("result") or not options.get("progress"):
        return None
    options["directory"] = positional[0]
    return options


def _write(path: str, document: Any) -> None:
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(document, handle, sort_keys=True)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    options = _parse(list(sys.argv[1:] if argv is None else argv))
    if options is None:
        print("usage: python -m mhs.driver._gate --result <file> --progress <file> [--backend fake|sim] "
              "[--root <dir>] [--clone <dir>] [--companions-root <dir>] <driver dir>", file=sys.stderr)
        return 2
    from ._repotests import guard_process

    guard_process()
    from .check import CheckUsageError, run_check

    progress_path = options["progress"]

    def progress(event: dict[str, Any]) -> None:
        with open(progress_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    code = 0
    try:
        try:
            report = run_check(options["directory"], backend=options["backend"], root=options["root"],
                               clone=options["clone"], write_report=False, progress=progress,
                               companions_root=options["companions_root"])
        except CheckUsageError as exc:
            _write(options["result"], {"usage_error": str(exc)})
        else:
            _write(options["result"], {"report": report})
    except BaseException:  # noqa: BLE001 - the parent reports a gate that ended without a report
        traceback.print_exc(file=sys.stderr)
        code = 3
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code  # pragma: no cover - os._exit never returns


if __name__ == "__main__":
    raise SystemExit(main())
