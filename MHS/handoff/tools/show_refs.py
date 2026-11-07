#!/usr/bin/env python3
"""Print every place a driver package cites in the upstream clone, with the cited lines.  Standard library only.

    python3 MHS/handoff/tools/show_refs.py MHS/drivers/labs/tiagocoutinho__julabo
    python3 MHS/handoff/tools/show_refs.py <dir> --context 1        # one extra line either side

Gate G4 only checks that a cited ``path:LINE`` exists (it warns when the line lacks a bound's number).  A reviewer has to
read every Limit and Fact against its line ([REVIEW.md](../REVIEW.md), checklist 2 and 4); this prints them next to the
place in driver.py that cites them, so that is one screen per package.  It reads the clone with plain file reads and
never imports anything from it.  Exit code 1 when a citation names a missing file or a line beyond the end of the file.

Companion sources (``task.json`` ``companions``, REVIEW.md item 13): a citation ``companion:<alias>/<path>:<LINE>`` is
read from that companion's clone, and so are the ``source_ref``, ``type_ref`` and ``state_ref`` of a binding that
cites one.  Each companion gets a header with its pinned commit and the HEAD read from its ``.git`` files (no git
command), then its version evidence with the cited lines.  ``!! HEAD differs``, ``!! undeclared companion alias``,
``!! token not shown`` and a missing file or line count as bad citations.  The HEAD shown is the checkout's: the gate
reads the pinned commit from the object store and fails (G1 COMPANION_HEAD) when they differ.  ``task.json`` is the
package's own file: the companions are read from the registry card ``MHS/registry/tasks/<track>/<dir>.json``, and a
``task.json`` that differs from it, or declares companions without one, is reported (``!!``) and counted as bad.
A fetched companion (``lock``, a clone under ``work/companions`` listed in its ``LOCK.json``) is read from the
directory of its local path, or from ``--companions-root DIR`` (``DIR/LOCK.json`` and ``DIR/<clone>``); its header
also prints the LOCK.json entry, and ``!! LOCK mismatch``, ``!! writable work tree`` and ``!! clone missing`` count
as bad citations (the gate fails G1 COMPANION_LOCK, COMPANION_WRITABLE and NO_COMPANION_CLONE).

A citation inside a git submodule (a path under a ``path`` of the clone's ``.gitmodules``) is read as the gate reads
it: by the SDK's ``mhs.driver.upstream.UpstreamTree`` (``MHS/sdk/src`` of this checkout), at the commit the pinned
tree's gitlink records, from the submodule's own object store, and only when the submodule is checked out at exactly
that commit.  It prints which submodule and commit it read; a submodule that is absent, empty or at another commit is a
bad citation with the reason.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent.parent.parent
REF = re.compile(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")
COMPANION = re.compile(r"^companion:(?P<alias>[a-z][a-z0-9_-]{1,39})/(?P<rest>.+)$")
BINDING_REFS = ("source_ref", "type_ref", "state_ref")
GITMODULES_PATH = re.compile(r'^\s*path\s*=\s*"?([^"\n]*?)"?\s*$', re.MULTILINE | re.IGNORECASE)


def show_submodule(tree, inside: str, ref: str, context: int) -> tuple[list[str], bool]:
    """The cited lines of a ``path:LINE[-END]`` inside the git submodule ``inside`` of the package clone, read by the
    SDK's tree at the gitlink commit of the pinned tree (``tree``; None when the SDK cannot be imported), and whether
    the citation is bad (sdk-gaps-a's submodule reading inside p3-companion's ``show`` structure)."""
    match = REF.match(ref)
    text = tree.read_text(match["path"]) if tree is not None else None
    if text is None:
        reason = (tree.refusal_for(match["path"]) if tree is not None else None) or (
            "no such file at the submodule's gitlink commit" if tree is not None
            else "the SDK (MHS/sdk/src) that reads git submodules cannot be imported")
        return [f"  !! inside the git submodule {inside}: {reason}"], True
    out = []
    record = next((item for path, item in sorted(tree.submodules.items(), key=lambda pair: -len(pair[0]))
                   if match["path"].startswith(path + "/")), None)
    if record is not None:
        out.append(f"  (git submodule {record.path} at {record.commit[:12]}, the gitlink of the pinned commit; "
                   f"read from {record.git_dir})")
    lines = text.splitlines()
    start, end = int(match["start"]), int(match["end"] or match["start"])
    if end > len(lines) or start < 1:
        return out + [f"  !! the file has {len(lines)} lines"], True
    for number in range(max(1, start - context), min(len(lines), end + context) + 1):
        mark = ">" if start <= number <= end else " "
        out.append(f"  {mark}{number:>5}  {lines[number - 1].rstrip()[:160]}")
    return out, False


def submodule_paths(clone: Path) -> list[str]:
    """The paths the clone's ``.gitmodules`` declares (a plain read; the SDK checks each against the pinned tree)."""
    try:
        text = (clone / ".gitmodules").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return sorted({item.strip().strip("/") for item in GITMODULES_PATH.findall(text) if item.strip().strip("/")})


def pinned_tree(root: Path, clone: Path, commit: str):
    """The SDK's read-only tree of the clone at ``commit`` (None when the SDK of this checkout cannot be imported)."""
    sys.dont_write_bytecode = True
    source = str(root / "MHS" / "sdk" / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    try:
        from mhs.driver.upstream import UpstreamTree
    except Exception:  # noqa: BLE001 - reported as a bad citation by the caller
        return None
    return UpstreamTree(clone, commit)


def module_constants(tree: ast.Module) -> dict[str, object]:
    consts: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
    return consts


def evaluate(node: ast.AST, consts: dict[str, object]) -> str | None:
    """A ref string: a literal, or an f-string over module-level string constants."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = ""
        for part in node.values:
            if isinstance(part, ast.Constant):
                out += str(part.value)
            elif isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name) and part.value.id in consts:
                out += str(consts[part.value.id])
            else:
                return None
        return out
    return None


def string_value(node: ast.AST, consts: dict[str, object]) -> str | None:
    """A literal, an f-string over module constants, a module constant, or ``a + b`` of those."""
    value = evaluate(node, consts)
    if value is not None:
        return value
    if isinstance(node, ast.Name) and isinstance(consts.get(node.id), str):
        return str(consts[node.id])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = string_value(node.left, consts), string_value(node.right, consts)
        return left + right if left is not None and right is not None else None
    return None


def _parameters(function: ast.FunctionDef) -> list[str]:
    return [item.arg for item in function.args.posonlyargs + function.args.args]


def helper_call_value(node: ast.AST, consts: dict[str, object], functions: dict[str, ast.FunctionDef]) -> str | None:
    """``_source("263")``: a call of a module function whose body is one ``return`` of a string expression, with
    literal arguments (``def _source(ref): return f"{CLONE}:{ref}"``)."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions):
        return None
    function = functions[node.func.id]
    body = [item for item in function.body if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant))]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return None
    local = dict(consts)
    names = _parameters(function)
    for name, argument in [*zip(names, node.args), *((item.arg, item.value) for item in node.keywords)]:
        try:
            local[name] = str(ast.literal_eval(argument))
        except (ValueError, SyntaxError):
            return None
    return string_value(body[0].value, local)


def parameter_values(tree: ast.Module, consts: dict[str, object], function: ast.FunctionDef, parameter: str,
                     parents: dict[ast.AST, ast.AST], assigned: dict[str, ast.AST]) -> list[tuple[int, str, str | None]]:
    """``(line, label, ref)`` of each value the module passes to ``parameter`` of the module function ``function``:
    an argument the reader resolves, or a comprehension variable unpacked from a module-level tuple of tuples (one
    value per row, with the row's line).  ``ref`` is ``None`` where the value cannot be read."""
    out: list[tuple[int, str, str | None]] = []
    names = _parameters(function)
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == function.name):
            continue
        argument = dict(zip(names, call.args)).get(parameter)
        argument = next((item.value for item in call.keywords if item.arg == parameter), argument)
        if argument is None:
            continue
        value = string_value(argument, consts)
        if value is not None or not isinstance(argument, ast.Name):
            out.append((call.lineno, f"{function.name}()", value))
            continue
        rows = None
        node = call
        while rows is None and node in parents:
            node = parents[node]
            if not isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                continue
            for generator in node.generators:
                target, source = generator.target, assigned.get(getattr(generator.iter, "id", ""))
                if isinstance(target, ast.Tuple) and isinstance(source, (ast.Tuple, ast.List)):
                    index = next((i for i, item in enumerate(target.elts)
                                  if isinstance(item, ast.Name) and item.id == argument.id), None)
                    if index is not None:
                        rows = [(row, index) for row in source.elts]
        if rows is None:
            out.append((call.lineno, f"{function.name}()", None))
            continue
        for row, index in rows:
            items = row.elts if isinstance(row, (ast.Tuple, ast.List)) else []
            first = items[0].value if items and isinstance(items[0], ast.Constant) else ""
            value = string_value(items[index], consts) if index < len(items) else None
            out.append((row.lineno, f"{function.name}({first!r})", value))
    return out


def citations(driver_py: Path) -> list[tuple[int, str, str]]:
    """(line in driver.py, what cites, ref) for every ``ref=`` argument and every ``estop_physical_ref`` and
    ``action_space_ref`` attribute (a literal, an f-string, a module string constant or a sum of those), plus every
    ``source_ref``/``type_ref``/``state_ref`` of a dict literal that cites a companion source (``companion:...``),
    and a sensed-confirmation stop's ``fill_refs`` values and declared ``history`` ``ref`` (a dict with
    ``durability`` and ``ref``),
    and the ``ref`` of every operator bridge (a dict literal with a string ``args``, E3).
    A ``ref=`` built by a module helper is followed too: a call of a one-``return`` helper with literal arguments
    (``ref=_source("263")``), and a parameter of the enclosing helper, listed once per value its callers pass
    (``ref=limit_ref`` in ``_action(..., limit_ref)``, called over the rows of a module-level tuple)."""
    tree = ast.parse(driver_py.read_text(encoding="utf-8"))
    consts = module_constants(tree)
    for node in tree.body:  # string constants built from others (_API + ":492-498")
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = string_value(node.value, consts)
            if value is not None:
                consts.setdefault(node.targets[0].id, value)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assigned = {node.targets[0].id: node.value for node in tree.body
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    owner = {node: function for function in functions.values() for node in ast.walk(function)}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {key.value: value for key, value in zip(node.keys, node.values) if isinstance(key, ast.Constant)}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in BINDING_REFS:
                    ref = string_value(value, consts)
                    if ref is not None and ref.startswith("companion:"):
                        found.append((value.lineno, f"binding {key.value}", ref))
            # A sensed-confirmation stop (SAFE-049): every fill_refs line of a source, and the line a ROS 2 source's
            # declared publisher history cites (REVIEW.md item 5 asks for both).
            fills = keys.get("fill_refs")
            if isinstance(fills, ast.Dict):
                for key, value in zip(fills.keys, fills.values):
                    if isinstance(key, ast.Constant):
                        ref = string_value(value, consts)
                        found.append((value.lineno, f"sensed fill_ref {key.value}",
                                      ref if ref is not None else "<not a constant>"))
            if "durability" in keys and "ref" in keys:
                ref = string_value(keys["ref"], consts)
                found.append((keys["ref"].lineno, "sensed history", ref if ref is not None else "<not a constant>"))
            bridge = keys.get("args")
            if "ref" in keys and isinstance(bridge, ast.Constant) and isinstance(bridge.value, str):
                # An operator bridge (RosDriver.operator_bridges, E3): its citation must show the bridge's ROS type.
                ref = string_value(keys["ref"], consts)
                found.append((keys["ref"].lineno, f"operator bridge {bridge.value[:70]!r}",
                              ref if ref is not None else "<not a constant>"))
            continue
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "call")
            subject = ""
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                subject = node.args[0].value[:70]
            for keyword in node.keywords:
                if keyword.arg == "ref":
                    ref = string_value(keyword.value, consts)
                    if ref is None:
                        ref = helper_call_value(keyword.value, consts, functions)
                    function = owner.get(node)
                    if (ref is None and isinstance(keyword.value, ast.Name) and function is not None
                            and keyword.value.id in _parameters(function)):
                        values = parameter_values(tree, consts, function, keyword.value.id, parents, assigned)
                        found.extend((line, f"{name} via {label}", value if value is not None else "<not a constant>")
                                     for line, label, value in values)
                        if values:
                            continue
                    found.append((node.lineno, f"{name}({subject!r})" if subject else name, ref if ref is not None else "<not a constant>"))
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", "") in (
                "estop_physical_ref", "action_space_ref"):
            ref = string_value(node.value, consts)
            found.append((node.lineno, node.targets[0].id, ref if ref is not None else "<not a constant>"))
    return sorted(found)


def git_head(clone: Path) -> str | None:
    """The commit the clone's HEAD names, read from ``.git/HEAD``, the ref file or ``packed-refs`` (no git command)."""
    git = clone / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if re.fullmatch(r"[0-9a-f]{40}", head):
        return head
    if not head.startswith("ref: "):
        return None
    ref = head[len("ref: "):].strip()
    if ".." in ref.split("/"):
        return None
    try:
        value = (git / ref).read_text(encoding="utf-8").strip()
        return value if re.fullmatch(r"[0-9a-f]{40}", value) else None
    except OSError:
        pass
    try:
        for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
                return parts[0]
    except OSError:
        pass
    return None


def show(clone: Path, ref: str, context: int, token: str | None = None) -> tuple[list[str], bool]:
    """The cited lines of ``path:LINE[-END]`` in ``clone`` (plain reads) and whether the citation is bad."""
    match = REF.match(ref)
    if not match:
        return ["  !! not a path:LINE reference"], True
    target = (clone / match["path"]).resolve()
    if clone.resolve() not in target.parents or not target.is_file():
        return ["  !! no such file in the clone"], True
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = int(match["start"]), int(match["end"] or match["start"])
    if end > len(lines) or start < 1:
        return [f"  !! the file has {len(lines)} lines"], True
    out = []
    for number in range(max(1, start - context), min(len(lines), end + context) + 1):
        mark = ">" if start <= number <= end else " "
        out.append(f"  {mark}{number:>5}  {lines[number - 1].rstrip()[:160]}")
    if token is not None and token.lower() not in "\n".join(lines[start - 1:end]).lower():
        out.append(f"  !! token not shown: {token!r}")
        return out, True
    return out, False


def github_package_id(repo_url: object) -> str | None:
    """``gh.<owner>/<repo>`` (lower case) of a ``https://github.com/<owner>/<repo>[.git]`` URL."""
    match = re.match(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", str(repo_url))
    return f"gh.{match.group(1)}/{match.group(2)}".lower() if match else None


def writable_entries(clone: Path, limit: int = 5) -> list[str]:
    """Up to ``limit`` work-tree entries of ``clone`` with a write bit (``.git`` excluded, symlinks not followed)."""
    found = ["."] if stat.S_IMODE(os.lstat(clone).st_mode) & 0o222 else []
    for directory, dirs, names in os.walk(clone):
        if Path(directory) == clone:
            dirs[:] = [item for item in dirs if item != ".git"]
        dirs.sort()
        for name in sorted(dirs) + sorted(names):
            info = os.lstat(os.path.join(directory, name))
            if not stat.S_ISLNK(info.st_mode) and stat.S_IMODE(info.st_mode) & 0o222:
                found.append(os.path.relpath(os.path.join(directory, name), clone))
            if len(found) >= limit:
                return found
    return found


def lock_entry(lock_root: Path, item: dict, package_id: object) -> tuple[dict | None, list[str]]:
    """The LOCK.json entry of a fetched companion and what differs from the card (as gate G1 COMPANION_LOCK)."""
    try:
        document = json.loads((lock_root / "LOCK.json").read_text(encoding="utf-8"))
        entries = {entry.get("alias"): entry for entry in document.get("clones") or [] if isinstance(entry, dict)}
    except (OSError, ValueError, AttributeError) as exc:
        return None, [f"{lock_root / 'LOCK.json'} cannot be read ({type(exc).__name__})"]
    entry = entries.get(item.get("lock"))
    if entry is None:
        return None, [f"LOCK.json has no entry {item.get('lock')!r}"]
    wrong = [f"{key} {entry.get(key)!r} != card {value!r}" for key, value in
             (("commit", item.get("commit")), ("path", item.get("local_path")), ("profile", item.get("profile")),
              ("ref", item.get("ref"))) if entry.get(key) != value]
    if github_package_id(entry.get("repo_url")) != item.get("package_id"):
        wrong.append(f"repo_url {entry.get('repo_url')!r} does not name {item.get('package_id')!r}")
    needed = entry.get("needed_by")
    if not isinstance(needed, list):
        wrong.append(f"needed_by {needed!r} is not a list (as gate G1 COMPANION_LOCK refuses)")
    elif package_id not in needed:
        wrong.append(f"{package_id} is not in needed_by")
    return entry, wrong


def companion_headers(root: Path, card: dict, context: int,
                      companions_root: Path | None = None) -> tuple[dict[str, Path], int]:
    """Print each declared companion and its version evidence; return {alias: clone} and the bad count."""
    clones: dict[str, Path] = {}
    bad = 0
    for item in card.get("companions") or []:
        alias = item.get("alias")
        lock_root = None
        if "lock" in item:
            lock_root = companions_root or (root / str(item.get("local_path"))).parent
            clone = lock_root / Path(str(item.get("local_path"))).name
        else:
            clone = root / str(item.get("local_path"))
        clones[str(alias)] = clone
        head = git_head(clone)
        print(f"\ncompanion {alias}: {item.get('package_id')} at {item.get('local_path')}")
        print(f"  pinned {item.get('commit')}  profile {item.get('profile')}  licence {item.get('license_spdx')}"
              + (f" ({item.get('licence_note')})" if item.get("licence_note") else ""))
        if lock_root is not None:
            entry, wrong = lock_entry(lock_root, item, card.get("package_id"))
            print(f"  lock   {item.get('lock')} (ref {item.get('ref')}) in {lock_root / 'LOCK.json'}")
            if entry is not None:
                print(f"  LOCK   {entry.get('repo_url')} {entry.get('ref_type', 'ref')} {entry.get('ref')} fetched "
                      f"{entry.get('fetched_utc')}, licence {entry.get('licence')}, needed_by {entry.get('needed_by')}")
            if wrong:
                print("  !! LOCK mismatch: " + "; ".join(wrong))
                bad += 1
            if not clone.is_dir():
                print(f"  !! clone missing: {clone} (fetch it with tools/fetch_companions.py)")
                bad += 1
            else:
                writable = writable_entries(clone)
                if writable:
                    print(f"  !! writable work tree: {writable}")
                    bad += 1
        print(f"  HEAD   {head}")
        if head != item.get("commit"):
            print("  !! HEAD differs from the pinned commit (or cannot be read)")
            bad += 1
        print(f"  reason: {item.get('reason')}")
    package_clone = root / card["local_path"]
    for item in card.get("companions") or []:
        for proof in item.get("version_evidence") or []:
            side = proof.get("side")
            target = package_clone if side == "package" else clones.get(
                item.get("alias") if side == "companion" else str(side)[len("companion:"):])
            print(f"\nversion evidence of {item.get('alias')}: {side} {proof.get('ref')} shows {proof.get('token')!r}")
            if target is None:
                print("  !! undeclared companion alias")
                bad += 1
                continue
            lines, wrong = show(target, str(proof.get("ref")), context, str(proof.get("token")))
            print("\n".join(lines))
            bad += wrong
    return clones, bad


def registry_check(root: Path, directory: Path, card: dict) -> tuple[dict, int]:
    """``(card to read, bad count)``: ``task.json`` must equal the registry card ``MHS/registry/tasks/<track>/<dir>.json``
    (gate G1 ``CARD_EDITED``), and a card that declares companions must have one (G1 ``COMPANION_CARD``).  When the
    two differ, the registry card is the one read below (it holds the reviewed companions)."""
    track = card.get("track")
    path = root / "MHS" / "registry" / "tasks" / str(track) / f"{directory.name}.json"
    if not (isinstance(track, str) and re.fullmatch(r"[A-Za-z0-9_-]+", track) and path.is_file()):
        if card.get("companions"):
            print(f"!! no registry card MHS/registry/tasks/{track}/{directory.name}.json confirms the companions of "
                  "task.json (the gate fails G1 COMPANION_CARD)")
            return card, 1
        return card, 0
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"!! the registry card MHS/registry/tasks/{track}/{directory.name}.json cannot be read")
        return card, 1
    if registry != card:
        print(f"!! task.json differs from the registry card MHS/registry/tasks/{track}/{directory.name}.json (the gate "
              "fails G1 CARD_EDITED); the companions and the clone below are the registry card's")
        return registry, 1
    return card, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("directory", type=Path, help="a driver package directory")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    parser.add_argument("--context", type=int, default=0, help="extra lines to show either side of a cited range")
    parser.add_argument("--companions-root", type=Path,
                        help="the directory of fetched companion clones and their LOCK.json (default: work/companions)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    directory = args.directory if args.directory.is_absolute() else root / args.directory
    try:
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
        cites = citations(directory / "driver.py")
    except (OSError, ValueError, SyntaxError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    card, bad = registry_check(root, directory, card)
    clone = root / card["local_path"]
    print(f"{card['package_id']}: {len(cites)} citation(s) in driver.py against {card['local_path']} at {card['upstream']['commit'][:12]}")
    companions_root = args.companions_root.resolve() if args.companions_root else None
    clones, wrong = (companion_headers(root, card, args.context, companions_root) if card.get("companions")
                     else ({}, 0))
    bad += wrong
    submodules = submodule_paths(clone)
    tree = None
    for line, what, ref in cites:
        print(f"\ndriver.py:{line}  {what}\n  cites {ref}")
        companion = COMPANION.match(ref)
        if ref.startswith("companion:"):
            if companion is None or companion["alias"] not in clones:
                print("  !! undeclared companion alias" if companion is not None else "  !! not a companion:<alias>/path:LINE reference")
                bad += 1
                continue
            lines, wrong = show(clones[companion["alias"]], companion["rest"], args.context)
        else:
            match = REF.match(ref)
            inside = next((item for item in submodules if match and match["path"].startswith(item + "/")), None)
            if inside is not None:
                # A git submodule: read at the gitlink commit of the pinned tree, as the gate reads it, never the checkout.
                tree = tree or pinned_tree(root, clone, card["upstream"]["commit"])
                lines, wrong = show_submodule(tree, inside, ref, args.context)
            else:
                lines, wrong = show(clone, ref, args.context)
        print("\n".join(lines))
        bad += wrong
    print(f"\n{bad} bad citation(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
