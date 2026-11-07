"""Bounded static scan of the local repo clones (stdlib only, deterministic).

This module is used by ``build_registry.py``.  It walks each
``labs/<owner>/<repo>`` and ``robots/<owner>/<repo>`` clone to a maximum depth
of three directory levels, skipping VCS/metadata/dependency directories, and
extracts *evidence that a file exists*, never claims about behaviour:

* file count and top-level inventory,
* build-system files (pyproject.toml, setup.py, Cargo.toml, package.xml,
  CMakeLists.txt, package.json, Dockerfile, ...),
* license/README presence (README head is read, max 16 KiB),
* dependency / interface marker hits from build files and README head,
* *entry-point evidence* with file:line strings: console scripts, package
  mains, executables, ROS package names, README ``import``/``python -m`` lines.

Everything here is a bounded, read-only heuristic.  Nothing is executed.
"""

from __future__ import annotations

import os
import re

# Directories that are never useful for adapter evidence and can be enormous.
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".github", ".gitlab", ".idea", ".vscode",
    "node_modules", "__pycache__", ".venv", "venv", "env", ".env",
    "build", "dist", "target", ".tox", ".eggs", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".cache", "site-packages",
    "third_party", "third-party", "vendor", "external", ".dart_tool",
    ".gradle", ".next", "coverage", ".conda", "pkgs", ".snakemake",
    "wandb", "runs", "outputs", ".ipynb_checkpoints", "htmlcov",
}

MAX_DEPTH = 3              # depth of directories to descend into (root = 0)
MAX_FILES = 60000          # hard cap per repo so a pathological clone stays bounded
MAX_BUILD_FILE_BYTES = 32768
MAX_BUILD_FILES_READ = 8
MAX_README_BYTES = 16384
MAX_ENTRY_EVIDENCE = 8

BUILD_FILENAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "requirements-dev.txt", "package.json", "cargo.toml", "cmakelists.txt",
    "package.xml", "dockerfile", "pixi.toml", "environment.yml",
    "environment.yaml", "project.toml", "makefile", "meson.build",
    "build.bazel", "workspace", "pom.xml", "build.gradle", "build.gradle.kts",
    "renv.lock", "description", "manifest.toml", "configure.ac",
    "docker-compose.yml", "docker-compose.yaml", "earthfile", "justfile",
}
BUILD_SUFFIXES = (".csproj", ".sln", ".uproject", ".gemspec", ".cabal")
LICENSE_NAMES = {"license", "license.txt", "license.md", "licence",
                 "licence.txt", "copying", "copying.txt", "copyright"}

# ---------------------------------------------------------------------------
# Marker vocabulary: (marker-id, regex).  Matched against build-file text,
# README head, file/dir names and the catalog's backend_family /
# integration_interfaces strings.  A hit is only "text mentions X"; the
# generator scores it, it never turns a hit into a capability claim.
# ---------------------------------------------------------------------------
MARKERS = {
    "ros2": r"\b(ros2|ros 2|rclpy|rclcpp|rosbridge|nav2|moveit2|ros2_control|ament|colcon|launch_ros|gz_ros|ros_gz)\b",
    "ros1": r"\b(roscpp|rospy|roslaunch|catkin|ros 1|ros-1|ros1)\b",
    "gazebo": r"\b(gazebo|gz-sim|gazebosim|gz_transport|gazebo_ros)\b",
    "mujoco": r"\b(mujoco|mjcf|mujoco-py|mjwarp)\b",
    "pybullet": r"\b(pybullet|pybullet_envs|bullet3)\b",
    "gymnasium": r"\b(gymnasium|gym\.|gym-|gym_|openai gym|farama)\b",
    "dm_env": r"\b(dm_env|dm-control|dm_control)\b",
    "isaac_sim": r"\b(isaac sim|isaac-sim|isaacsim|omniverse|omni\.isaac)\b",
    "isaac_lab": r"\b(isaac lab|isaaclab|omniisaacgym)\b",
    "isaac_gym": r"\b(isaac gym|isaacgym|isaac-gym)\b",
    "webots": r"\b(webots|webots_ros)\b",
    "unity": r"\b(unity3d|unity engine|unity)\b",
    "unreal": r"\b(unreal engine|unreal)\b",
    "airsim": r"\b(airsim|airsim-ros)\b",
    "sapien": r"\b(sapien|mani_skill|maniskill2?)\b",
    "drake": r"\b(pydrake|drake)\b",
    "brax_mjx": r"\b(brax|mjx|mujoco mjx)\b",
    "habitat": r"\b(habitat[-_ ]sim|habitat-lab|habitat)\b",
    "opentrons": r"\b(opentrons|ot-2|ot2|flex)\b",
    "pylabrobot": r"\b(pylabrobot|py-lab-robot)\b",
    "flowchem": r"\b(flowchem)\b",
    "madsci": r"\b(madsci)\b",
    "sila2": r"\b(sila ?2|sila2)\b",
    "mcp": r"\b(mcp|model context protocol|fastmcp|mcp-server|mcp server)\b",
    "scpi_visa": r"\b(pyvisa|visa|scpi|pymeasure|instrumentkit|labscript|qcodes)\b",
    "qcodes": r"\b(qcodes)\b",
    "bluesky_ophyd": r"\b(ophyd|bluesky|runengine|queueserver)\b",
    "micromanager": r"\b(micro-manager|micromanager|pymmcore|mmcore|mmcoreplus)\b",
    "http": r"\b(fastapi|flask|tornado|aiohttp|rest api|http api|json[- ]rpc|grpc|openapi|websocket)\b",
    "serial": r"\b(pyserial|serial port|serial communication|rs-?232|uart|modbus)\b",
    "mqtt": r"\b(mqtt|paho|hivemq|mosquitto)\b",
    "zeromq": r"\b(zmq|zeromq|0mq)\b",
    "opcua": r"\b(opc ?ua|opcua|open62541|asyncua)\b",
    "epics": r"\b(epics|caproto|pyepics|pvaccess)\b",
    "tango": r"\b(tango controls|pytango|tango device)\b",
    "mavlink": r"\b(mavlink|pixhawk|px4|ardupilot|arducopter|sitl)\b",
    "docker": r"\b(docker|containerfile|docker-compose)\b",
    "replay": r"\b(mcap|rosbag|foxglove|rerun|replay)\b",
    "lerobot": r"\b(lerobot)\b",
    "cli": r"\b(command[- ]line|cli|console script|entry_points)\b",
    "gpu": r"\b(cuda|gpu|nvidia|vulkan|optix|renderer)\b",
    "camera": r"\b(camera|webcam|realsense|opencv|image sensor)\b",
    "lidar": r"\b(lidar|point ?cloud|depth camera|rgbd)\b",
    "force_torque": r"\b(force[- /]?torque|ft sensor|wrench)\b",
    "imu": r"\b(imu|inertial measurement|accelerometer|gyroscope)\b",
    "laser": r"\b(laser|class 3b|class 4 laser)\b",
    "high_voltage": r"\b(high[- ]voltage|hv supply|kilovolt|kv supply)\b",
    "liquid_handling": r"\b(pipett|aspirat|dispens|liquid handl|syringe pump)\b",
    "thermal": r"\b(thermocycler|heater|hotplate|temperature controller|thermal)\b",
    "microscopy": r"\b(microscop|objective|fluorescence|confocal|stage)\b",
    "spectrometer": r"\b(spectrometer|spectrum|spectra|wavelength)\b",
    "balance": r"\b(balance|scale|mass measurement|weigh)\b",
}
MARKERS = {k: re.compile(v, re.IGNORECASE) for k, v in MARKERS.items()}

# Build-system identification by file name.  First match wins for the primary
# list, but all detected files are reported.
BUILD_SYSTEM_MAP = [
    ("pyproject.toml", "python"), ("setup.py", "python"), ("setup.cfg", "python"),
    ("requirements.txt", "python"), ("requirements-dev.txt", "python"),
    ("environment.yml", "conda"), ("environment.yaml", "conda"),
    ("pixi.toml", "pixi"), ("package.json", "node"), ("Cargo.toml", "cargo"),
    ("CMakeLists.txt", "cmake"), ("package.xml", "ros"), ("Makefile", "make"),
    ("meson.build", "meson"), ("BUILD.bazel", "bazel"), ("WORKSPACE", "bazel"),
    ("pom.xml", "maven"), ("build.gradle", "gradle"), ("build.gradle.kts", "gradle"),
    ("Dockerfile", "docker"), ("docker-compose.yml", "docker"),
    ("docker-compose.yaml", "docker"), ("Project.toml", "julia"),
    ("Manifest.toml", "julia"), ("renv.lock", "r"), ("DESCRIPTION", "r"),
    ("configure.ac", "autotools"), ("earthfile", "earthly"), ("Justfile", "just"),
]
EXT_SUFFIX_MAP = [
    (".csproj", "dotnet"), (".sln", "dotnet"), (".uproject", "unreal"),
    (".gemspec", "ruby"), (".cabal", "haskell"),
]

EXT_LANGUAGE = {
    ".py": "Python", ".pyx": "Cython", ".ipynb": "Jupyter Notebook",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".h": "C", ".c": "C", ".cu": "Cuda", ".cuh": "Cuda", ".rs": "Rust",
    ".cs": "C#", ".java": "Java", ".kt": "Kotlin", ".js": "JavaScript",
    ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rb": "Ruby", ".jl": "Julia", ".m": "MATLAB",
    ".lua": "Lua", ".swift": "Swift", ".scala": "Scala", ".r": "R",
    ".sh": "Shell", ".ps1": "PowerShell", ".f90": "Fortran", ".f": "Fortran",
    ".dart": "Dart", ".sol": "Solidity", ".ino": "Arduino",
}

README_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]*)")
README_PYSCRIPT_RE = re.compile(
    r"^\s*(?:\$ )?(?:python[0-9.]*\s+-m\s+([A-Za-z_][A-Za-z0-9_.]*))")
README_INSTALL_RE = re.compile(
    r"^\s*(?:\$ )?pip[0-9]*\s+install\s+([A-Za-z0-9_.\-\[\]]+)")
SCRIPT_TARGET_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)\s*=\s*['\"]([A-Za-z0-9_.]+:[A-Za-z0-9_.]+)['\"]")
SCRIPT_TARGET_SPACE_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)\s*=\s*([A-Za-z0-9_.]+:[A-Za-z0-9_.]+)\s*$")


def _is_skipped_dir(name: str) -> bool:
    return name.lower() in SKIP_DIRS or name.startswith(".git")


def _read_text(path: str, limit: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def _line_of(text: str, needle: str, start: int = 0) -> int:
    idx = text.find(needle, start)
    if idx < 0:
        return 1
    return text.count("\n", 0, idx) + 1


def scan_repo(repo_dir: str) -> dict:
    """Return a bounded feature dict for one clone.  Deterministic."""
    out = {
        "exists": os.path.isdir(repo_dir),
        "files": 0,
        "dirs": 0,
        "build_files": [],
        "build_systems": [],
        "languages": [],
        "license_file": None,
        "readme": None,
        "readme_size": 0,
        "readme_head": "",
        "top_dirs": [],
        "top_files": [],
        "markers": {},
        "entry_evidence": [],
        "has_python_package": False,
        "has_ros_package": False,
        "has_unity_project": False,
        "has_unreal_project": False,
        "has_dockerfile": False,
        "has_mhs_adapter_file": False,
        "ext_counts": {},
    }
    if not out["exists"]:
        out["missing"] = True
        return out

    build_paths = []
    readme_paths = []
    license_paths = []
    text_by_path = {}
    python_pkg_dirs = []
    ext_counts = {}
    stop = False
    for root, dirs, files in os.walk(repo_dir):
        rel = os.path.relpath(root, repo_dir)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = sorted(d for d in dirs if not _is_skipped_dir(d))
        if depth >= MAX_DEPTH:
            dirs[:] = []
        if depth == 0:
            out["top_dirs"] = list(dirs)
            out["top_files"] = sorted(files)
        for name in sorted(files):
            out["files"] += 1
            if out["files"] > MAX_FILES:
                stop = True
                break
            full = os.path.join(root, name)
            low = name.lower()
            ext = os.path.splitext(low)[1]
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            if depth <= 1:
                if low in BUILD_FILENAMES or low.endswith(BUILD_SUFFIXES):
                    build_paths.append(full)
            if depth == 0 and low.startswith("readme"):
                readme_paths.append(full)
            if depth == 0 and low in LICENSE_NAMES:
                license_paths.append(full)
            if low == "__init__.py" and depth <= 2:
                python_pkg_dirs.append(os.path.dirname(full))
            if low == "mhs-adapter.json" or (low == "adapter.json" and "mhs" in rel.lower()):
                out["has_mhs_adapter_file"] = True
        if stop:
            break

    out["dirs"] = len(out["top_dirs"])
    out["top_dirs"] = out["top_dirs"][:40]
    out["top_files"] = out["top_files"][:40]

    # --- read the bounded text evidence -----------------------------------
    build_paths.sort(key=lambda p: (p.count(os.sep), p))
    build_rel = []
    build_text = []
    for path in build_paths[:MAX_BUILD_FILES_READ]:
        relpath = os.path.relpath(path, repo_dir)
        build_rel.append(relpath)
        build_text.append((relpath, _read_text(path, MAX_BUILD_FILE_BYTES)))
    out["build_files"] = build_rel
    out["build_systems"] = _build_systems(out["build_files"])
    # a Dockerfile anywhere at depth <= 1 still counts
    if any(os.path.basename(p).lower().startswith("dockerfile") for p in build_rel):
        out["has_dockerfile"] = True

    if readme_paths:
        readme_path = sorted(readme_paths)[0]
        try:
            out["readme_size"] = os.path.getsize(readme_path)
        except OSError:
            out["readme_size"] = 0
        out["readme"] = os.path.relpath(readme_path, repo_dir)
        out["readme_head"] = _read_text(readme_path, MAX_README_BYTES)
    if license_paths:
        out["license_file"] = os.path.relpath(sorted(license_paths)[0], repo_dir)

    # --- languages -------------------------------------------------------
    langs = []
    for ext, count in ext_counts.items():
        lang = EXT_LANGUAGE.get(ext)
        if lang and count >= 1:
            langs.append((count, lang))
    seen = set()
    for _, lang in sorted(langs, key=lambda t: (-t[0], t[1])):
        if lang not in seen:
            seen.add(lang)
            langs_out = out["languages"]
            langs_out.append(lang)
    out["languages"] = out["languages"][:8]
    out["ext_counts"] = {k: v for k, v in sorted(ext_counts.items()) if v >= 2}

    # --- marker hits -----------------------------------------------------
    haystacks = {
        "build": "\n".join(t for _, t in build_text),
        "readme": out["readme_head"],
        "names": " ".join(
            list(out["top_dirs"]) + list(out["top_files"])
        ),
    }
    hits = {}
    for marker, rx in MARKERS.items():
        count = 0
        for slot in ("build", "readme", "names"):
            count += len(rx.findall(haystacks[slot] or ""))
        if count:
            hits[marker] = count
    out["markers"] = dict(sorted(hits.items()))

    # --- entry point evidence -------------------------------------------
    evidence = []

    def add_evidence(text: str) -> None:
        if text and text not in evidence and len(evidence) < MAX_ENTRY_EVIDENCE:
            evidence.append(text)

    for relpath, text in build_text:
        if not text:
            continue
        low = os.path.basename(relpath).lower()
        if low in ("pyproject.toml", "setup.cfg"):
            for m in re.finditer(r"\[[^\]]*scripts[^\]]*\]", text):
                section = text[m.end():]
                nxt = re.search(r"^\s*\[", section, re.MULTILINE)
                if nxt:
                    section = section[: nxt.start()]
                for line in section.splitlines():
                    if not line.strip() or line.strip().startswith("#"):
                        continue
                    line_no = _line_of(text, line.strip(), m.end())
                    add_evidence(f"{relpath}:{line_no}: {line.strip()[:160]}")
        elif low == "setup.py":
            for line_no, line in enumerate(text.splitlines(), 1):
                if ("console_scripts" in line or "entry_points" in line) and "=" in line:
                    add_evidence(f"{relpath}:{line_no}: {line.strip()[:160]}")
        elif low == "package.json":
            for line_no, line in enumerate(text.splitlines(), 1):
                if re.search(r'"(main|bin|module)"\s*:', line):
                    add_evidence(f"{relpath}:{line_no}: {line.strip()[:160]}")
        elif low == "cargo.toml":
            for line_no, line in enumerate(text.splitlines(), 1):
                if re.match(r"^\s*(name|path|\[\[bin\]\]|\[lib\])", line):
                    add_evidence(f"{relpath}:{line_no}: {line.strip()[:160]}")
        elif low == "cmakelists.txt":
            for line_no, line in enumerate(text.splitlines(), 1):
                if re.search(r"add_(executable|library)\s*\(", line, re.IGNORECASE):
                    add_evidence(f"{relpath}:{line_no}: {line.strip()[:160]}")
        elif low == "package.xml":
            m = re.search(r"<name>\s*([^<]+?)\s*</name>", text)
            if m:
                line_no = _line_of(text, m.group(0))
                add_evidence(f"{relpath}:{line_no}: ROS package <name>{m.group(1)}")

    # Python package directories (depth <= 2) give module-path evidence.
    for pkg_dir in sorted(python_pkg_dirs)[:4]:
        rel = os.path.relpath(pkg_dir, repo_dir)
        if rel == ".":
            continue
        init = os.path.join(pkg_dir, "__init__.py")
        try:
            size = os.path.getsize(init)
        except OSError:
            size = 0
        add_evidence(f"{os.path.join(rel, '__init__.py')}:1: python package ({size} bytes)")

    # README usage lines (line numbers are real).
    readme_text = out["readme_head"]
    if readme_text and out["readme"]:
        found = 0
        for line_no, line in enumerate(readme_text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or len(stripped) > 200:
                continue
            m = README_IMPORT_RE.match(stripped)
            if m:
                add_evidence(f"{out['readme']}:{line_no}: {stripped[:120]}")
                found += 1
            else:
                m = README_PYSCRIPT_RE.match(stripped)
                if m:
                    add_evidence(f"{out['readme']}:{line_no}: {stripped[:120]}")
                    found += 1
                else:
                    m = README_INSTALL_RE.match(stripped)
                    if m and found < 3:
                        add_evidence(f"{out['readme']}:{line_no}: {stripped[:120]}")
                        found += 1
            if len(evidence) >= MAX_ENTRY_EVIDENCE:
                break

    out["entry_evidence"] = evidence
    out["has_python_package"] = bool(python_pkg_dirs) or "python" in out["build_systems"]
    out["has_ros_package"] = any(
        os.path.basename(p) == "package.xml" for p in build_rel)
    out["has_unity_project"] = any(
        f.endswith(".uproject") or f == "ProjectSettings" for f in out["top_dirs"] + out["top_files"])
    out["has_unreal_project"] = any(f.endswith(".uproject") for f in out["top_files"])
    return out


def _build_systems(build_files: list[str]) -> list[str]:
    found = []
    for relpath in build_files:
        base = os.path.basename(relpath)
        low = base.lower()
        for name, system in BUILD_SYSTEM_MAP:
            if low == name.lower() and system not in found:
                found.append(system)
        for suffix, system in EXT_SUFFIX_MAP:
            if low.endswith(suffix) and system not in found:
                found.append(system)
    return found


def scan_corpus(workspace_root: str, tracks=("labs", "robots")) -> dict:
    """Scan every clone.  Returns {(track, owner, repo): features} sorted."""
    result = {}
    for track in tracks:
        track_dir = os.path.join(workspace_root, track)
        if not os.path.isdir(track_dir):
            continue
        for owner in sorted(os.listdir(track_dir)):
            owner_dir = os.path.join(track_dir, owner)
            if not os.path.isdir(owner_dir):
                continue
            for repo in sorted(os.listdir(owner_dir)):
                repo_dir = os.path.join(owner_dir, repo)
                if not os.path.isdir(repo_dir):
                    continue
                result[(track, owner, repo)] = scan_repo(repo_dir)
    return result


if __name__ == "__main__":  # ad-hoc inspection helper
    import json
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    feats = scan_corpus(root)
    stats = {"repos": len(feats), "empty": 0}
    stats["empty"] = sum(1 for f in feats.values() if f["files"] == 0)
    print(json.dumps(stats, indent=2))
