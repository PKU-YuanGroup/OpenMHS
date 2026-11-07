"""Conservative root ROS build evidence; never imports or executes upstream code.

Only a pinned regular blob (or a regular synthetic fixture file) is read. The
result identifies build tooling, not a ROS distribution, Python ABI, complete
dependency installation, or proof that the build succeeds.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "src"))
from mhs.driver.source_surface import regular_source
from mhs.driver.upstream import UpstreamTree

FILES = ("package.xml", "CMakeLists.txt", "setup.py")
MAX_BYTES = 65536
_FAMILY = {"catkin": "catkin", "ament_cmake": "ament", "ament_python": "ament"}


def _blank(match):
    return "".join("\n" if char == "\n" else " " for char in match.group())


def _xml(text, evidence, problems):
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        problems.append("package.xml: declarations/entities are unsupported")
        return
    try:
        package = ET.fromstring(text)
    except ET.ParseError:
        problems.append("package.xml: malformed XML")
        return
    if package.tag != "package":
        problems.append("package.xml: expected a package element")
        return
    clean = re.sub(r"<!--[\s\S]*?-->", _blank, text)
    candidates = [(child, False) for child in package if child.tag == "buildtool_depend"]
    candidates += [(child, "condition" in parent.attrib) for parent in package if parent.tag == "export"
                   for child in parent if child.tag == "build_type"]
    positions = {}
    for child, parent_condition in candidates:
        marker = (child.text or "").strip()
        if marker not in _FAMILY:
            if child.tag == "build_type":
                problems.append("package.xml: unsupported explicit build_type")
            continue
        pattern = rf"<{child.tag}\b[^>]*>\s*({re.escape(marker)})\s*</{child.tag}\s*>"
        matches = list(re.finditer(pattern, clean))
        index = positions.get((child.tag, marker), 0)
        positions[(child.tag, marker)] = index + 1
        line = clean.count("\n", 0, matches[index].start(1)) + 1 if index < len(matches) else 1
        evidence.append({"file": "package.xml", "line": line, "marker": marker,
                         "kind": child.tag, "family": _FAMILY[marker],
                         "conditional": parent_condition or "condition" in child.attrib})


def _cmake(text, evidence):
    # Preserve line locations while ignoring comments and quoted message text.
    clean = re.sub(r"#\[(=*)\[[\s\S]*?\]\1\]", _blank, text)
    clean = re.sub(r"\[(=*)\[[\s\S]*?\]\1\]", _blank, clean)
    clean = re.sub(r'"(?:\\.|[^"\\])*"', _blank, clean)
    clean = re.sub(r"#[^\n]*", _blank, clean)
    stack = []
    starters = {"if", "foreach", "while", "function", "macro", "block"}
    enders = {"endif", "endforeach", "endwhile", "endfunction", "endmacro", "endblock"}
    for match in re.finditer(r"(?m)^[ \t]*([A-Za-z_][A-Za-z_0-9]*)\s*\(([^)]*)\)", clean):
        command, args = match.group(1).lower(), match.group(2).strip()
        if command in enders:
            if stack:
                stack.pop()
            continue
        if command in starters:
            stack.append(command)
            continue
        first = args.split()[0] if args else ""
        marker = first if command == "find_package" and first in ("catkin", "ament_cmake") else None
        if command in ("catkin_package", "catkin_python_setup", "ament_package"):
            marker = "catkin" if command.startswith("catkin") else "ament_cmake"
        if marker:
            evidence.append({"file": "CMakeLists.txt", "line": clean.count("\n", 0, match.start(1)) + 1,
                             "marker": marker, "kind": command, "family": _FAMILY[marker],
                             "conditional": bool(stack)})


def _setup(text, evidence, problems):
    try:
        module = ast.parse(text)
    except (SyntaxError, ValueError):
        # An unparseable setup cannot establish that pip is safe for a ROS root.
        problems.append("setup.py: cannot statically parse packaging imports")
        return
    def walk(node, conditional=False):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            conditional = True
        if isinstance(node, ast.ImportFrom):
            found = node.module == "catkin_pkg.python_setup"
        elif isinstance(node, ast.Import):
            found = any(alias.name == "catkin_pkg.python_setup" for alias in node.names)
        else:
            found = False
        if found:
            evidence.append({"file": "setup.py", "line": node.lineno, "marker": "catkin_pkg.python_setup",
                             "kind": "import", "family": "catkin", "conditional": conditional})
        for child in ast.iter_child_nodes(node):
            walk(child, conditional or isinstance(node, (ast.If, ast.Try, getattr(ast, "TryStar", ast.Try), ast.For, ast.AsyncFor,
                                                        ast.While, ast.With, ast.AsyncWith, ast.Match)))
    walk(module)


def scan_ros_build(root, commit=None):
    """Root build classification with cited evidence from an exact source pin.

    Missing or invalid supplied commits never fall back to checkout contents.
    Nested packages are deliberately outside this root-install decision.
    """
    tree = UpstreamTree(Path(root), commit)
    if tree.is_git and commit is None:
        tree.commit = tree.head()
    out = {"status": "none", "commit": tree.commit, "source": "pinned" if tree.commit else "fixture",
           "root_files": [], "evidence": [], "problems": []}
    if (tree.commit or tree.is_git) and not tree.pinned:
        out["status"] = "unavailable"
        out["problems"].append("pinned root build evidence is unavailable; no worktree fallback")
        return out
    if tree.pinned:
        listing = tree._run("ls-tree", "-z", str(tree.commit), "--", *FILES)
        if listing is None:
            out["status"] = "unavailable"
            out["problems"].append("cannot list pinned root build files")
            return out
        present = {entry.partition("\t")[2] for entry in listing.split("\0") if "\t" in entry}
    else:
        present = {name for name in FILES if os.path.lexists(Path(root) / name)}
    out["root_files"] = sorted(present)
    texts = {}
    for name in FILES:
        if name not in present:
            continue
        try:
            text = regular_source(tree, name)
            if len(text.encode("utf-8")) > MAX_BYTES:
                raise ValueError("exceeds bounded root build scan")
            texts[name] = text
        except ValueError as exc:
            out["problems"].append(f"{name}: {exc}")
    if len(texts) != len(present):
        out["status"] = "unavailable"
        return out
    if "package.xml" in texts:
        _xml(texts["package.xml"], out["evidence"], out["problems"])
    if "CMakeLists.txt" in texts:
        _cmake(texts["CMakeLists.txt"], out["evidence"])
    if "setup.py" in texts:
        _setup(texts["setup.py"], out["evidence"], out["problems"])
    evidence = out["evidence"]
    families = {item["family"] for item in evidence}
    definite = {item["family"] for item in evidence if not item["conditional"]
                and item["kind"] in ("buildtool_depend", "build_type", "find_package", "import")}
    if len(families) > 1:
        out["status"] = "ambiguous"
    elif "package.xml" in present or evidence:
        out["status"] = next(iter(definite)) if len(definite) == 1 and not out["problems"] \
            and "package.xml" in present else "unknown"
    return out
