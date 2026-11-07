"""Copies of the tutorial package with seeded defects, for the acceptance gate tests (stdlib only)."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from mhs.driver.check import run_check
from mhs.driver.package import write_reference

SDK = Path(__file__).resolve().parents[2]
SRC = SDK / "src"
TUTORIAL = SDK / "examples" / "thermostat"
#: Every gate but G9 (G9 runs test_driver.py in a child process; a few tests run it).
NO_REPO_TESTS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")


def temp_root(test: Any) -> Path:
    holder = tempfile.TemporaryDirectory(prefix="mhs-gate-test-")
    test.addCleanup(holder.cleanup)
    return Path(holder.name)


def copy_tutorial(test: Any, name: str = "thermostat", *, parent: Path | None = None) -> Path:
    """A copy of ``MHS/sdk/examples/thermostat`` (without check-report.json or caches)."""
    base = parent if parent is not None else temp_root(test)
    target = base / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TUTORIAL, target, ignore=shutil.ignore_patterns("__pycache__", "check-report.json"))
    return target


def broken_copy(test: Any, edits: Iterable[tuple[str, str, str]], *, regen: bool = True) -> Path:
    """A tutorial copy with ``(file, old, new)`` edits applied (and the reference file regenerated)."""
    directory = copy_tutorial(test)
    for file, old, new in edits:
        edit(directory, file, old, new)
    if regen:
        regenerate(directory)
    return directory


def edit(directory: Path, file: str, old: str, new: str, *, count: int = 1) -> None:
    path = directory / file
    text = path.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise AssertionError(f"{file}: expected {count} occurrence(s) of {old!r}, found {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def edit_json(directory: Path, file: str, **changes: Any) -> dict[str, Any]:
    path = directory / file
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update(changes)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def regenerate(directory: Path) -> None:
    write_reference(directory)


def check(directory: Path, gates: Sequence[str] | None = NO_REPO_TESTS, **options: Any) -> dict[str, Any]:
    options.setdefault("write_report", False)
    return run_check(directory, gates=list(gates) if gates is not None else None, **options)


def findings(report: Mapping[str, Any], gate: str | None = None, *, severity: str | None = "error") -> list[str]:
    out = []
    for item in report["gates"]:
        if gate is not None and item["id"] != gate:
            continue
        for finding in item["findings"]:
            if severity is None or finding.get("severity") == severity:
                out.append(finding["code"])
    return out


def coded(report: Mapping[str, Any], gate: str) -> list[tuple[str, str | None]]:
    """``(code, path)`` of every finding of ``gate`` (errors and warnings)."""
    return [(finding["code"], finding.get("path")) for item in report["gates"] if item["id"] == gate
            for finding in item["findings"]]


def statuses(report: Mapping[str, Any]) -> dict[str, str]:
    return {item["id"]: item["status"] for item in report["gates"]}


def reverse_methods(directory: Path) -> None:
    """Rewrite driver.py with the methods of the Driver class in reverse order (same behaviour)."""
    path = directory / "driver.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
            others = [item for item in node.body if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
            node.body = others + list(reversed(methods))
    path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")


def run_cli(*args: str, cwd: Path | None = None, timeout: float = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SRC)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("MHS_DRIVER_GATE_INNER", None)
    return subprocess.run([sys.executable, "-m", "mhs.driver", *args], capture_output=True, text=True,
                          timeout=timeout, cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.DEVNULL)


def real_package(test: Any, *, commit: str = "a" * 40) -> tuple[Path, Path]:
    """``(root, driver dir)``: the tutorial as a non-synthetic package with a plain-directory clone.

    The root holds ``MHS/sdk``, ``MHS/drivers/labs/acme__th1`` and the clone
    ``labs/acme/th1`` (a copy of the tutorial's ``vendor/``, not a git checkout).
    """
    root = temp_root(test)
    (root / "MHS" / "sdk").mkdir(parents=True)
    directory = copy_tutorial(test, "acme__th1", parent=root / "MHS" / "drivers" / "labs")
    clone = root / "labs" / "acme" / "th1"
    shutil.copytree(directory / "vendor", clone)
    shutil.rmtree(directory / "vendor")
    upstream = {"repo_url": "https://github.com/acme/th1", "commit": commit, "license_spdx": "MIT",
                "license_class": "permissive"}
    card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    for key in ("synthetic", "notes"):
        card.pop(key, None)
    card.update({"package_id": "gh.acme/th1", "upstream": upstream, "local_path": "labs/acme/th1",
                 "driver_dir": "MHS/drivers/labs/acme__th1",
                 "acceptance": "python3 -m mhs.driver check MHS/drivers/labs/acme__th1 --backend fake"})
    (directory / "task.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    edit_json(directory, "driver.lock.json", package_id="gh.acme/th1",
              upstream={key: upstream[key] for key in ("repo_url", "commit", "license_spdx")})
    edit(directory, "driver.py", "x-cap.openmhs-tutorial.heater_off.v1", "x-cap.acme.heater_off.v1")
    regenerate(directory)
    return root, directory


def names(items: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(item.get("id")) for item in items]


#: Package code that exits the interpreter in a way the static scan cannot see (the runtime guards must hold):
#: ``getattr`` itself is aliased, so the scan's getattr rule does not apply.
EVADE_EXIT = "import sys as _s\n_ga = getattr\n_ga(_s, 'ex' + 'it')(0)\n"
EVADE_OS_EXIT = "import os as _o\n_ga = getattr\n_ga(_o, '_ex' + 'it')(0)\n"
DRIVER_IMPORT = "from mhs.driver import"
ESTOP_BLOCK = "    @estop\n    def stop(self):\n        self.native.emergency_off()\n"


def indent(code: str, spaces: int = 8) -> str:
    return "".join(" " * spaces + line + "\n" for line in code.splitlines())


def git(path: Path, *args: str) -> str:
    """Run git in ``path`` with no user or system configuration (test repositories only)."""
    env = dict(os.environ)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "HOME": str(path),
                "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    settings = ["user.name=gate-test", "user.email=gate-test@invalid", "commit.gpgsign=false",
                "init.defaultBranch=main", f"core.hooksPath={os.devnull}"]
    options = [item for setting in settings for item in ("-c", setting)]
    done = subprocess.run(["git", *options, *args], cwd=str(path), env=env, capture_output=True, text=True,
                          timeout=60, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout.strip()


def git_package(test: Any) -> tuple[Path, Path, Path, str]:
    """``(root, driver dir, clone, commit)``: :func:`real_package` whose clone is a git repository pinned at HEAD."""
    root, directory = real_package(test)
    clone = root / "labs" / "acme" / "th1"
    git(clone, "init", "-q")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "TH-1 SDK")
    commit = git(clone, "rev-parse", "HEAD")
    pin(directory, commit)
    return root, directory, clone, commit


def pin(directory: Path, commit: str) -> None:
    """Pin ``commit`` in task.json and driver.lock.json and regenerate the reference file."""
    card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    card["upstream"]["commit"] = commit
    (directory / "task.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    lock = json.loads((directory / "driver.lock.json").read_text(encoding="utf-8"))
    lock["upstream"]["commit"] = commit
    (directory / "driver.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    regenerate(directory)
