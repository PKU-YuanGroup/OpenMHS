#!/usr/bin/env python3
"""Re-run the gate for finished driver packages and summarise the results.  Standard library only.

    python3 MHS/handoff/tools/collect.py                               # every package under MHS/drivers/
    python3 MHS/handoff/tools/collect.py MHS/drivers/labs/a__b ...     # chosen packages
    python3 MHS/handoff/tools/collect.py --out summary.json            # also write the summary as JSON
    python3 MHS/handoff/tools/collect.py MHS/drivers/labs/a__b --strict    # CI: a warning fails too

Never trust a package's own RESULT.json: this tool runs ``python3 -m mhs.driver check <dir> --backend fake --json
--no-report`` itself and compares the outcome with what RESULT.json claims.  It prints these as ``warning:`` lines
(and fails with --strict):

* ``RESULT_UNTRUSTED``: RESULT.json says ``pass`` but the gate fails, or the other way round;
* ``RESULT_SCHEMA``: RESULT.json is not valid against ``MHS/schema/driver-result.schema.json`` (the gate reads only its status
  and digest; the registry validator would reject the file later);
* ``RESULT_DIGEST_STALE``: RESULT.json is a pass whose ``gate.digest`` is not the digest of this gate run: the package
  changed after the last gate run the author recorded, or the digest was not copied from the gate's output;
* ``EXEMPLAR_RESIDUE``: the package still mentions an exemplar's repository, class or model names (``mhs.driver new
  --like`` copies the exemplar's code files; leftover facts of another repository are the commonest model mistake);
* ``UNSOURCED_LIMIT_GATE_WARNING``: gate G4 warned that a cited line does not show the number: a reviewer must read it;
* ``UNVERIFIABLE_CITATION``: a citation points into a binary file (a PDF manual); G4 cannot check the page, a reviewer
  must open it.

and these as ``note:`` lines, which never fail anything: the gate's other warning codes, and ``DECISION_DEVIATION`` when
a ``family-config`` card was written as a direct ``Driver`` or as another family (a legitimate result, for example a
framed binary protocol that a command table cannot express: a maintainer then decides on an override for the card).
``SUBMODULE_SOURCE`` names each git submodule the gate read evidence from (gate finding ``G1.SUBMODULE_SOURCE``: the
submodule's path, name, the gitlink commit it was read at and its object store; its licence is its own).
``FACTS_LIMITS_REVIEW`` flags explicit source/ref clauses in a facts.md Limits paragraph that are absent from the
reference's step action bounds. It is a bounded prose advisory, not a numeric/provenance check or an acceptance of
any citation warning; unrecognized prose receives no assessment. ``COMPANION_SOURCE`` names each companion source
the card declares (``companions``, REVIEW.md item 13) and how many of the package's citations read it: a reading
list for ``show_refs.py``. Every companion defect is a gate error, so no warning here needs a signature. A fetched
companion (``lock``, a clone under ``work/companions``) is named with its LOCK.json alias; when its clone is missing
(an export: ``work/`` does not travel) the note says where and how to fetch it (``tools/fetch_companions.py``), and the
verdict stays the gate's (it fails G1 NO_COMPANION_CLONE / COMPANION_LOCK). ``--companions-root DIR`` is passed to the
gate (and used for the residue scan) when the fetched clones live elsewhere.

A package whose ``driver.lock.json`` carries ``reviewed_by`` has its last two kinds listed as ``accepted by <reviewer>``
instead of warnings: signing is the act of reading them (MHS/handoff/REVIEW.md).

Exit code: 0 when every package passes the gate (and, with --strict, has no warnings), 1 otherwise, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# A standalone tool must not leave bytecode beside its helper modules, including
# when the caller has not set PYTHONDONTWRITEBYTECODE.
sys.dont_write_bytecode = True
from facts_limits import facts_limits_notes

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[2]

#: Family and helper vocabulary: it names a kind of driver, not an exemplar's identity, so it is never residue.
#: ``RobotEnv`` is the generic robot-environment class name of gym-style libraries (``MujocoRobotEnv``, robel's
#: ``RobotEnv``) that the star-sim exemplar's native class happens to share; its module root ``star_sim`` stays residue.
GENERIC_TERMS = frozenset({"gymnasium", "mujoco", "serial", "pyserial", "scpi", "visa", "pyvisa", "python-object", "ros", "ros1", "ros2", "rosbridge",
                           "robotenv"})
#: Files that are generated, copied from the registry or written as prose: not scanned for residue.
NOT_SCANNED = frozenset({"task.json", "driver.lock.json", "reference.json", "REFERENCE.md", "RESULT.json", "check-report.json"})
TEXT_SUFFIXES = frozenset({".py", ".md", ".json", ".jsonl", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini"})
FAMILY_HELPERS = ("PythonObjectDriver", "SerialDriver", "ScpiDriver", "GymnasiumDriver", "MujocoDriver", "RosDriver",
                  "QcodesDriver", "OphydDriver", "McpClientDriver", "PyLabRobotDriver", "TagDriver", "Sila2Driver")


def package_dirs(root: Path) -> list[Path]:
    drivers = root / "MHS" / "drivers"
    return sorted(path.parent for path in drivers.glob("*/*/task.json"))


def run_gate(root: Path, directory: Path, companions_root: Path | None = None) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root / "MHS" / "sdk" / "src"))
    command = [sys.executable, "-m", "mhs.driver", "check", str(directory), "--backend", "fake", "--json", "--no-report"]
    if companions_root is not None:
        command += ["--companions-root", str(companions_root)]
    proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, check=False, timeout=1200)
    report = None
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        pass
    return {"exit_code": proc.returncode, "report": report, "stderr": proc.stderr.strip()[-400:]}


def stable_digest_of(root: Path, report: dict) -> str | None:
    """The digest that RESULT.json ``gate.digest`` records (the report without its clock), from the SDK of this checkout."""
    sys.dont_write_bytecode = True
    source = str(root / "MHS" / "sdk" / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from mhs.driver.check import stable_digest
    return stable_digest(report)


def schema_problems(root: Path, document, schema: str) -> list[str]:
    """What ``MHS/schema/<schema>`` says is wrong with ``document`` (the SDK of this checkout); empty if valid."""
    sys.dont_write_bytecode = True
    source = str(root / "MHS" / "sdk" / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from mhs.schema import default_store
    return [str(item) for item in default_store().validate(document, schema)]


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def identity_words(driver_py: Path) -> set[str]:
    """What names an exemplar's device in its driver: environment id, device id, native class and model."""
    words: set[str] = set()
    try:
        text = driver_py.read_text(encoding="utf-8")
    except OSError:
        return words
    for pattern in (r'^\s*(?:env_id|device_id)\s*=\s*"([^"]+)"', r'^\s*vendor,\s*model\s*=\s*"[^"]*",\s*"([^"]+)"',
                    r'^\s*native\s*=\s*"[^":]*:([^"]+)"'):
        words.update(match.group(1) for match in re.finditer(pattern, text, re.MULTILINE))
    return words


def residue_terms(root: Path, own: Path) -> dict[str, list[str]]:
    """Distinctive words of every exemplar other than ``own``: repository name, native module root, device identity."""
    listing = root / "MHS" / "drivers" / "EXEMPLARS.txt"
    terms: dict[str, list[str]] = {}
    if not listing.exists():
        return terms
    for line in listing.read_text(encoding="utf-8").split():
        exemplar = root / line.strip()
        if exemplar.resolve() == own.resolve() or not (exemplar / "task.json").exists():
            continue
        card = json.loads((exemplar / "task.json").read_text(encoding="utf-8"))
        repo = card["package_id"].split("/", 1)[1]
        words = {repo}
        for symbol in card.get("entry_symbols", [])[:1]:
            words.add(symbol["symbol"].split(":")[0].split(".")[0])
        words |= identity_words(exemplar / "driver.py")
        terms[card["package_id"]] = sorted(w for w in words if len(w) >= 5 and w.lower() not in GENERIC_TERMS)
    return terms


def scanned_files(directory: Path) -> list[Path]:
    out = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if (not path.is_file() or path.is_symlink() or "__pycache__" in relative.parts or relative.name in NOT_SCANNED
                or path.suffix not in TEXT_SUFFIXES):
            continue
        out.append(path)
    return out


def companion_clone(root: Path, item: dict, companions_root: Path | None = None) -> Path:
    """Where a companion's clone is read: a corpus one at ``root/<local_path>``, a fetched (``lock``) one in the
    directory of its local path or ``companions_root``."""
    if "lock" in item and companions_root is not None:
        return companions_root / Path(str(item.get("local_path"))).name
    return root / str(item.get("local_path"))


def cited_lines(root: Path, directory: Path, card: dict, companions_root: Path | None = None) -> str:
    """The upstream lines that the package's reference.json cites (facts and limits), read at the pinned commit."""
    refs: list[str] = []
    stack = [read_json(directory / "reference.json")]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("ref"), str):
                refs.append(node["ref"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    if not refs or not card.get("local_path"):
        return ""
    sys.dont_write_bytecode = True
    source = str(root / "MHS" / "sdk" / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    try:
        from mhs.driver.upstream import UpstreamTree, parse_ref
    except Exception:  # noqa: BLE001 - a missing or broken SDK is the gate's finding, not this tool's
        return ""
    tree = UpstreamTree(root / card["local_path"], (card.get("upstream") or {}).get("commit"))
    companions = {str(item.get("alias")): item for item in card.get("companions") or [] if isinstance(item, dict)}
    trees = {}
    lines: list[str] = []
    for text in sorted(set(refs)):
        ref = parse_ref(text)
        source = tree
        match = re.match(r"^companion:([a-z][a-z0-9_-]{1,39})/(.+)$", text)
        if match is not None and match.group(1) in companions:
            # A declared companion source (task.json companions) is read at its own pinned commit.
            item = companions[match.group(1)]
            if match.group(1) not in trees:
                trees[match.group(1)] = UpstreamTree(companion_clone(root, item, companions_root), item.get("commit"))
            source, ref = trees[match.group(1)], parse_ref(match.group(2))
        content = source.read_text(ref.path) if ref is not None else None
        if content is not None:
            lines.extend(content.splitlines()[ref.line - 1:ref.end])
    return "\n".join(lines)


def companion_notes(root: Path, directory: Path, card: dict, companions_root: Path | None = None) -> list[str]:
    """``COMPANION_SOURCE`` notes: each companion the card declares and how many reference.json facts cite it; a
    fetched companion whose clone is missing gets where and how to fetch it instead."""
    reference = read_json(directory / "reference.json")
    facts = reference.get("facts") if isinstance(reference, dict) and isinstance(reference.get("facts"), list) else []
    notes = []
    for item in card.get("companions") or []:
        if not isinstance(item, dict):
            continue
        alias = str(item.get("alias"))
        if "lock" in item:
            clone = companion_clone(root, item, companions_root)
            if not clone.is_dir():
                notes.append(f"COMPANION_SOURCE: {alias} = {item.get('lock')}@{str(item.get('commit'))[:12]} "
                             f"({item.get('profile')}): clone missing at {clone}; fetch with "
                             f"tools/fetch_companions.py {directory.relative_to(root).as_posix()} [--from DIR]")
                continue
        cited = sum(1 for fact in facts if isinstance(fact, dict)
                    and str(fact.get("ref", "")).startswith(f"companion:{alias}/"))
        named = item.get("lock") if "lock" in item else item.get("package_id")
        notes.append(f"COMPANION_SOURCE: {alias} = {named}@{str(item.get('commit'))[:12]} "
                     f"({item.get('profile')}): {cited} fact citation(s); read them, the stop's binding citations "
                     "and the version evidence with show_refs.py (REVIEW.md item 13)")
    return notes


def residue(root: Path, directory: Path, card: dict, companions_root: Path | None = None) -> list[str]:
    """Names of another exemplar left in any text file of the package (code, facts, fixtures, the site-limits example).

    A name of the repository's own card, or one that an upstream line the package cites shows (robust-gymnasium
    registers its own ``CartPole-v1``), is the upstream's and not residue."""
    found = []
    own_text = json.dumps([card.get(key) for key in ("package_id", "entry_symbols", "helper", "family", "models", "local_path")],
                          default=str).lower()
    files = [(path, path.read_text(encoding="utf-8", errors="replace")) for path in scanned_files(directory)]
    terms = residue_terms(root, directory)
    cited = cited_lines(root, directory, card, companions_root).lower() if any(terms.values()) else ""
    for pid, words in terms.items():
        patterns = [(word, re.compile(re.escape(word), re.IGNORECASE)) for word in words
                    if word.lower() not in own_text and word.lower() not in cited]
        for path, text in files:
            hits = [word for word, pattern in patterns if pattern.search(text)]
            if hits:
                found.append(f"{path.relative_to(directory).as_posix()} mentions {', '.join(repr(w) for w in hits)} (exemplar {pid})")
    return found


def driver_base(directory: Path) -> str | None:
    """The family helper the package's driver class derives from, else ``Driver``; None if driver.py cannot be read."""
    try:
        tree = ast.parse((directory / "driver.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    names = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                names.append(base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", ""))
    helper = next((name for name in names if name in FAMILY_HELPERS), None)
    return helper or ("Driver" if "Driver" in names else None)


def summarise(root: Path, directory: Path, companions_root: Path | None = None) -> dict:
    card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    # The two-argument call is kept when no companions root is given (callers and test doubles of run_gate).
    gate = run_gate(root, directory) if companions_root is None else run_gate(root, directory, companions_root)
    report = gate["report"] or {}
    failed = report.get("failed") or []
    passed = gate["exit_code"] == 0 and report.get("passed") is True
    result_doc = read_json(directory / "RESULT.json") if (directory / "RESULT.json").exists() else None
    claimed = None
    if (directory / "RESULT.json").exists():
        claimed = result_doc.get("status") if isinstance(result_doc, dict) else "unreadable"
    lock = read_json(directory / "driver.lock.json")
    reviewer = None
    if isinstance(lock, dict) and isinstance(lock.get("reviewed_by"), dict):
        reviewer = lock["reviewed_by"].get("reviewer")
    expected_digest = stable_digest_of(root, report) if passed else None

    warnings: list[str] = []
    accepted: list[str] = []
    notes: list[str] = []
    if isinstance(result_doc, dict):
        problems = schema_problems(root, result_doc, "driver-result.schema.json")
        if problems:
            warnings.append("RESULT_SCHEMA: RESULT.json is not valid against driver-result.schema.json: " + "; ".join(problems[:3]))
    if claimed == "pass" and not passed:
        warnings.append("RESULT_UNTRUSTED: RESULT.json says pass but the gate fails")
    if claimed in (None, "blocked", "skip-proposed", "unreadable") and passed:
        warnings.append(f"RESULT_UNTRUSTED: the gate passes but RESULT.json says {claimed!r}")
    if claimed == "pass" and passed and expected_digest:
        recorded = ((result_doc or {}).get("gate") or {}).get("digest")
        if recorded != expected_digest:
            warnings.append(f"RESULT_DIGEST_STALE: RESULT.json gate.digest is {recorded!r}, this gate run gives "
                            f"{expected_digest}; run the gate after your last edit and copy the digest line it prints")
    for note in residue(root, directory, card, companions_root):
        warnings.append("EXEMPLAR_RESIDUE: " + note)
    other_warnings: dict[str, int] = {}
    for gate_result in report.get("gates", []):
        for finding in gate_result.get("findings", []):
            code = finding.get("code")
            if code == "G4.REF_VALUE":
                line = f"UNSOURCED_LIMIT_GATE_WARNING: {finding.get('path')}: a reviewer must read {finding.get('ref')}"
            elif code == "G4.REF_BINARY":
                line = (f"UNVERIFIABLE_CITATION: {finding.get('path')}: {finding.get('ref')} is in a binary file (a PDF page?); "
                        "a reviewer must open it")
            elif code == "G1.SUBMODULE_SOURCE":
                notes.append(f"SUBMODULE_SOURCE: {finding.get('message')}")
                continue
            else:
                if finding.get("severity") == "warning":
                    other_warnings[str(code)] = other_warnings.get(str(code), 0) + 1
                continue
            (accepted if reviewer else warnings).append(line)
    if other_warnings:
        notes.append("gate warnings: " + ", ".join(code if n == 1 else f"{code} x{n}" for code, n in sorted(other_warnings.items()))
                     + " (python3 -m mhs.driver check <dir> --backend fake --verbose prints the messages)")
    actual = driver_base(directory)
    if card.get("decision") == "family-config" and actual is not None and actual != card.get("helper"):
        notes.append(f"DECISION_DEVIATION: the card says family-config / {card.get('helper')}, the driver derives from {actual}; "
                     "a maintainer decides whether the card needs an override (MHS/registry/overrides/README.md)")
    notes.extend(facts_limits_notes(directory))
    notes.extend(companion_notes(root, directory, card, companions_root))
    return {
        "package_id": card["package_id"],
        "driver_dir": str(directory.relative_to(root)),
        "gate_exit_code": gate["exit_code"],
        "gate_passed": passed,
        "failed": failed,
        "report_digest": report.get("report_digest"),
        "gate_digest": expected_digest,
        "result_json_status": claimed,
        "reviewer": reviewer,
        "warnings": warnings,
        "accepted_by_reviewer": accepted,
        "notes": notes,
        "gate_stderr": "" if passed else gate["stderr"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("directories", nargs="*", type=Path, help="driver package directories (default: all under MHS/drivers)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    parser.add_argument("--out", type=Path, help="write the summary as JSON here")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings too (CI uses it)")
    parser.add_argument("--companions-root", type=Path,
                        help="the directory of fetched companion clones and their LOCK.json, passed to the gate "
                             "(default: work/companions under the root)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    directories = [d if d.is_absolute() else root / d for d in args.directories] or package_dirs(root)
    if not directories:
        print("no driver packages found", file=sys.stderr)
        return 2
    rows = []
    for directory in directories:
        if not (directory / "task.json").exists():
            print(f"error: {directory} has no task.json", file=sys.stderr)
            return 2
        rows.append(summarise(root, directory.resolve(),
                              args.companions_root.resolve() if args.companions_root else None))
    for row in rows:
        mark = "PASS" if row["gate_passed"] else "FAIL " + ",".join(row["failed"] or ["?"])
        print(f"{mark:<28} {row['package_id']:<46} RESULT.json={row['result_json_status']}")
        for warning in row["warnings"]:
            print("    warning:", warning)
        for line in row["accepted_by_reviewer"]:
            print(f"    accepted by {row['reviewer']}:", line)
        for note in row["notes"]:
            print("    note:", note)
    passed = sum(row["gate_passed"] for row in rows)
    print(f"-- {passed} of {len(rows)} package(s) pass the gate; {sum(bool(r['warnings']) for r in rows)} with warnings")
    if args.out:
        args.out.write_text(json.dumps({"summary": {"packages": len(rows), "passed": passed}, "packages": rows}, indent=1) + "\n",
                            encoding="utf-8")
    bad = passed != len(rows) or (args.strict and any(row["warnings"] for row in rows))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
