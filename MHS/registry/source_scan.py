#!/usr/bin/env python3
"""Bounded, read-only source scan of one upstream clone (stdlib only).

The scan never imports, installs or executes upstream code.  Python files are
parsed with :mod:`ast`; every other file is either only listed or read as text
with a size cap.  The result is a small JSON-serialisable dict of *facts* that
:mod:`triage` (strategy rules) and the task-card generator (entry symbols)
consume:

``tree``            sorted relative file paths (capped at ``MAX_TREE``), used
                    for duplicate detection by file-tree similarity
``counts``          file counts by kind (python, other source code, notebooks,
                    executables and archives, docs)
``readme``          README facts: size, first heading, download call-to-action
                    links, lure vocabulary, curated-list and tutorial wording,
                    MHS mentions
``python``          imported top-level modules (``imports_core``: the ones
                    package code imports unconditionally), ``gym``/``gymnasium``
                    env registrations of the package (keyword, positional,
                    class-object and decorator forms, with the registered
                    class's ``class_file`` and ``class_line``, followed through
                    package re-exports, and ``module_in_repo``; registrations in
                    examples, tests, docs and vendored copies are only counted
                    in ``gym_ids_aux``), ``Env`` subclasses (``env_entries``:
                    ranked environment classes, robosuite and LIBERO style
                    included), parse failures
``entry_classes``   ranked device-like classes ``{symbol, file, line, score,
                    bases, methods, transport, microcontroller, generated,
                    composes}`` (``file:line`` at the scanned commit; module
                    paths follow the packaging metadata's package roots, then
                    ``src`` layouts, also inside monorepos)
``markers``         structural markers: ROS ``package.xml``, launch files,
                    MJCF models (``mjcf_main``: loadable scene and robot models
                    with actuators, ranked; object and fixture assets,
                    fragments, templates and copies under examples, tests or
                    vendored trees are never main models), URDF, Unity/Unreal
                    projects, root build files, test directories
``license``         root licence files and the SPDX id their title names
                    (:func:`licenses.detect_files`)
``install``         ``requires-python`` / ``python_requires`` and console
                    scripts declared in the root build files
``mocks``           upstream simulators, mocks and fakes: classes and modules
                    named Sim/Mock/Fake/Dummy/Emulator/Virtual, pyvisa-sim YAML
``limit_hints``     numeric MIN/MAX/LIMIT/RANGE constants with ``file:line``

The last four feed the task cards (``taskcards.py``) only; triage does not
read them.

Every list is sorted and every cap is a constant, so the same commit always
produces the same facts.  ``SCAN_VERSION`` changes whenever the fact format or
a heuristic changes, so cached facts can be invalidated.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import warnings
from typing import Any, Mapping

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import licenses as LIC  # noqa: E402  (same-directory module; stdlib only)
from ros_build import scan_ros_build  # noqa: E402 (pinned root build evidence only)

SCAN_VERSION = 11

MAX_TREE = 20000          # file paths kept for tree similarity
MAX_PY_FILES = 1500       # Python files parsed per repo
MAX_PY_BYTES = 400_000    # larger Python files are skipped
MAX_XML_HEADS = 300       # .xml/.mjcf files whose head is read for <mujoco (the repo's own files first)
MJCF_BYTES = 262_144      # MJCF text read to classify a model (actuators, includes, worldbody)
MAX_MJCF_MAIN = 10        # ranked main-model candidates kept
MAX_ENV_ENTRIES = 8       # ranked environment classes kept
README_BYTES = 65536
MAX_ENTRY_CLASSES = 12
MAX_ENTRY_MORE = 48       # further ranked classes kept for the task cards (API variants skipped)
MAX_API_METHODS = 150     # device-API method names kept per ranked class (task-card hints)
MAX_EXPORTED_NAMES = 300
MAX_GYM_ENTRIES = 50
MAX_MOCKS = 12
MAX_LIMIT_HINTS = 20
LICENSE_BYTES = 65536
BUILD_FILE_BYTES = 65536

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", "site-packages", ".idea", ".vscode",
    ".eggs", "build", "dist", "_build", ".ipynb_checkpoints", "bower_components",
}
#: directories whose Python classes are never entry points (they may still
#: contribute imports and env registrations)
NON_ENTRY_DIRS = {
    "test", "tests", "testing", "unittests", "unit_tests", "doc", "docs",
    "example", "examples", "demo", "demos", "sample", "samples", "tutorial",
    "tutorials", "notebook", "notebooks", "benchmark", "benchmarks", "scripts",
    "script", "tools", "tool", "third_party", "thirdparty", "third_parties", "vendor", "external",
    "extern", "deps", "legacy", "old", "archive", "contrib_examples",
}
#: vendored third-party code: listed in the tree, never scanned as the repo's own code
VENDORED_DIRS = {"third_party", "thirdparty", "third_parties", "thirdparties", "third-party", "3rdparty",
                 "3rd_party", "3rd-party", "vendor", "vendored", "_vendor", "external", "extern", "deps",
                 "submodules"}
#: directories whose env registrations and MJCF files are examples, tests, docs, fixtures or vendored
#: copies: they never make the repo a simulator (rule 9 markers) and never name its entry or model
AUX_DIRS = NON_ENTRY_DIRS | VENDORED_DIRS | {"fixtures", "fixture", "test_data", "testdata", "unit_tests"}
PY_EXT = {".py", ".pyw"}
CODE_EXT = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".cs", ".java",
    ".kt", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".rs", ".go", ".m", ".jl",
    ".rb", ".lua", ".swift", ".scala", ".vb", ".bas", ".pas", ".f", ".f90",
    ".r", ".vi", ".lvproj", ".ino", ".pde", ".sh", ".ps1", ".tcl", ".php",
    ".dart", ".zig", ".nim", ".ml", ".hs", ".erl", ".ex", ".exs", ".clj",
    ".groovy", ".v", ".sv", ".vhd", ".vhdl", ".cu", ".cl", ".glsl", ".hlsl",
}
NOTEBOOK_EXT = {".ipynb"}
EXECUTABLE_EXT = {
    ".exe", ".msi", ".dmg", ".pkg", ".apk", ".appimage", ".deb", ".rpm", ".dll",
    ".so", ".dylib", ".app", ".jar", ".scr", ".com",
}
INSTALLER_EXT = {".exe", ".msi", ".dmg", ".pkg", ".apk", ".appimage", ".deb", ".rpm", ".scr"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".iso"}
DOC_EXT = {".md", ".rst", ".txt", ".html", ".htm", ".pdf", ".adoc", ".tex"}
ROOT_BUILD_FILES = (
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "environment.yml",
    "environment.yaml", "Pipfile", "package.json", "CMakeLists.txt", "Cargo.toml",
    "go.mod", "Makefile", "package.xml", "Dockerfile", "conda.yaml", "meta.yaml",
)

#: methods that indicate a class talks to a device (exact names)
DEVICE_METHODS = {
    "connect", "disconnect", "open", "close", "initialize", "initialise", "init",
    "home", "homing", "stop", "abort", "halt", "emergency_stop", "estop", "e_stop",
    "reset", "query", "ask", "read", "write", "send", "send_command", "command",
    "cmd", "move", "move_to", "move_abs", "move_rel", "move_absolute",
    "move_relative", "goto", "jog", "measure", "acquire", "snap", "snap_image",
    "capture", "grab", "trigger", "start", "pause", "resume", "aspirate",
    "dispense", "pick_up_tips", "drop_tips", "transfer", "heat", "cool",
    "enable", "disable", "power_on", "power_off", "turn_on", "turn_off", "arm",
    "disarm", "takeoff", "land", "identify", "idn", "calibrate", "status",
    "get_status", "is_busy", "is_moving", "wait_until_done", "wait_for_motion",
    "set_output", "get_output", "on", "off", "run", "shutdown",
}
#: method-name prefixes that indicate a device API
DEVICE_PREFIXES = (
    "set_", "get_", "read_", "write_", "move_", "measure_", "acquire_", "query_",
    "start_", "stop_", "enable_", "disable_", "open_", "close_", "send_",
)
DEVICE_BASES = {
    "instrument", "visainstrument", "scpiinstrument", "messagebasedinstrument",
    "device", "basedevice", "driver", "basedriver", "serialdevice", "serialinstrument",
    "motor", "camera", "sensor", "robot", "robotarm", "arm", "gripper", "controller",
    "stage", "pump", "laser", "spectrometer", "detector", "liquidhandlerbackend",
    "machinebackend", "backend", "instrumentbase", "hardware", "hardwareobject",
    "baseinstrument", "abstractinstrument", "hardwarecomponent", "module",
}
NON_ENTRY_BASES = {
    "exception", "error", "testcase", "enum", "intenum", "strenum", "namedtuple",
    "typeddict", "protocol", "qwidget", "qmainwindow", "qdialog", "qobject",
    "qthread", "basemodel", "dataclass", "env", "gymenv", "wrapper",
}
NON_ENTRY_NAME = re.compile(
    r"(?:Error|Exception|Test|Tests|Mixin|Config|Settings|Enum|Widget|Window|Dialog|"
    r"Gui|GUI|Plot|Plotter|View|Viewer|Tab|Panel|Thread|Worker|Logger|Parser|Handler|"
    r"Exporter|Writer|Reader|Builder|Factory|Schema|Message|Msg|Packet|Frame|Struct|"
    r"Result|Response|Request|State|Status|Type|Mode|Unit|Units|Constants?)$")
INIT_ADDRESS_PARAMS = {
    "port", "address", "addr", "ip", "ip_address", "host", "hostname", "resource",
    "resource_name", "visa_address", "visa_resource", "serial_port", "com", "com_port",
    "comport", "baudrate", "baud", "baud_rate", "url", "uri", "device", "dev",
    "device_path", "serial_number", "serial", "connection", "conn", "transport",
    "adapter", "interface", "bus", "channel", "unit_id", "slave", "socket", "tty",
}
TRANSPORT_IMPORTS = {
    "serial", "pyvisa", "visa", "socket", "usb", "ctypes", "requests", "websocket",
    "websockets", "minimalmodbus", "pymodbus", "telnetlib", "can", "hid", "ftd2xx",
    "pyftdi", "bluetooth", "bleak", "zmq", "grpc", "paho", "nidaqmx", "pydaqmx",
    "serialio", "sockio", "connio", "pyserial", "httpx", "aiohttp", "asyncua",
    "opcua", "pyads", "snap7", "pylablib", "instrumentkit", "pymeasure", "vxi11",
    "usbtmc", "pyusb", "smbus", "smbus2", "spidev", "rpi", "gpiozero", "pigpio",
    "picamera", "picamera2", "libcamera", "clr", "pythonnet", "win32com", "comtypes",
    "xarm", "urx", "rtde_control", "rtde_receive", "frankx", "franky", "panda_py",
    "dynamixel_sdk", "pyrealsense2", "harvesters", "pypylon", "pyueye", "pycromanager",
    "pymmcore", "pymmcore_plus", "pylabrobot", "opentrons", "sila2", "qcodes",
    "ophyd", "epics", "tango", "alpaca", "pymavlink", "mavsdk", "dronekit", "cflib",
    "autoscript_sdb_microscope_client", "tescanautomation",
}

#: imports of code that runs on a microcontroller (MicroPython, CircuitPython), not on the host
MICROCONTROLLER_IMPORTS = {"micropython", "utime", "ustruct", "uasyncio", "ubinascii", "rp2", "esp", "esp32", "pyb",
                           "busio", "digitalio", "analogio", "microcontroller", "adafruit_bus_device", "framebuf",
                           "uos", "usocket", "umqtt", "ujson"}
#: names imported from MicroPython's ``machine`` module (``from machine import Pin, I2C``)
MICROCONTROLLER_MACHINE_NAMES = {"Pin", "I2C", "SPI", "UART", "PWM", "ADC", "SoftI2C", "SoftSPI", "Timer", "RTC", "WDT"}
#: names only MicroPython's ``time`` module has (``from time import sleep_ms``)
MICROCONTROLLER_TIME_NAMES = {"sleep_ms", "sleep_us", "ticks_ms", "ticks_us", "ticks_diff", "ticks_add"}
#: imports of generated serialisation code (FlatBuffers, protobuf message classes)
GENERATED_IMPORTS = {"flatbuffers"}

_GYM_ID = re.compile(r"^[A-Za-z0-9_./:-]+-v\d+$")
_DOWNLOAD_CTA = re.compile(
    r"\[!\[[^\]]*download[^\]]*\]\([^)]*\)\]\((https?://[^)\s]+)\)"
    r"|\[[^\]\[]*\bdownload\b[^\]\[]*\]\((https?://[^)\s]+)\)", re.IGNORECASE)
_LURE_WORDS = re.compile(
    r"\b(?:cracked|crack download|keygen|key ?generator|activation (?:key|code) generator|"
    r"serial key|product key|free download|pre-?activated|torrent|warez)\b", re.IGNORECASE)
_CURATED_LIST = re.compile(
    r"\b(?:awesome[- ]list|a curated list|curated list of|list of awesome|"
    r"collection of (?:resources|papers|links)|paper list|reading list)\b", re.IGNORECASE)
_TUTORIAL = re.compile(
    r"\b(?:tutorials?|course|lecture notes?|lectures|homework|assignments?|"
    r"workshop materials?|class notes|lessons?|bootcamp|cheat ?sheet)\b", re.IGNORECASE)
_MHS = re.compile(r"model[ -]hardware[ -]standard|\bopen-?mhs\b|\bmhs\b", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,3}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_IMPORT_LINE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_README_IMPORT = re.compile(r"^\s*(?:>>>\s*)?from\s+([A-Za-z_][\w.]*)\s+import\s+\(?([\w ,]+)\)?", re.MULTILINE)
_README_CALL = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\s*\(")
#: README instructions to fetch artifacts the clone does not hold before anything runs: an asset or
#: model download script or command, multi-gigabyte assets, Git LFS objects
_ARTIFACT_DOWNLOAD = re.compile(
    r"\bdownload[_-](?:\w+[_-])?(?:assets?|meshes|scenes?|models?|checkpoints?|weights)\b"
    r"|\b(?:assets?|meshes|scenes?|models?|checkpoints?|weights)\b[^.\n]{0,60}?\b\d+(?:\.\d+)?\s?[GT]B\b"
    r"|\bgit[ -]lfs (?:pull|fetch|install)\b"
    # prose: "download and extract the assets", "download the pretrained models" (a dataset is training data)
    r"|\bdownload(?:\s+and\s+(?:extract|unzip|untar|unpack))?\s+(?:the\s+|our\s+|all\s+)?(?:pre-?trained\s+)?"
    r"(?:assets?|meshes|scenes?|models?|checkpoints?|weights)\b"
    # wget/curl of an asset archive
    r"|\b(?:wget|curl)\b[^\n]{0,160}?(?:assets?|meshes|scenes?|models?|checkpoints?|weights)"
    r"[^\n\s]{0,80}?\.(?:zip|tar\.gz|tgz|tar|7z)\b", re.IGNORECASE)
#: file-sharing hosts and commands for assets (gdown, Google Drive files and folders, Hugging Face datasets); they
#: count only on a line that also names assets, models, scenes, meshes or checkpoints (a dataset of demonstrations,
#: an embedded image or a video link does not)
_ARTIFACT_HOST = re.compile(
    r"\bgdown\s+\S+|\bdrive\.google\.com/(?:file/d/|drive/(?:u/\d+/)?folders/|uc\?(?:export=download&)?id=|"
    r"open\?id=)\S*|\bhuggingface\.co/datasets/\S+", re.IGNORECASE)
_ASSET_WORD = re.compile(r"\b(?:assets?|meshes|scenes?|models?|checkpoints?|weights|textures)\b", re.IGNORECASE)
#: README prerequisites that state (not merely mention) a GPU: "requires a GPU", "needs an NVIDIA GPU",
#: "GPU is required", a prerequisites or requirements line that names a GPU, a requirement bullet that starts with
#: an NVIDIA GPU, and a Vulkan setup step (rendering through Vulkan needs a GPU driver)
_README_GPU = re.compile(
    r"\b(?:requires?|required|needs?)\s+(?:an?\s+)?(?:(?:NVIDIA|CUDA)(?:[- ](?:capable|enabled|compatible))?\s+)?"
    r"(?:GPU|graphics card)\b"
    r"|\bGPU\s+(?:is\s+)?(?:required|needed|mandatory)\b"
    r"|^\W*(?:prerequisites?|requirements?|hardware requirements?)\b[^.\n]{0,40}?\b(?:GPU|CUDA)\b"
    r"|^\s*[-*]\s+(?:an?\s+)?NVIDIA\s+GPU\b"
    r"|\b(?:requires?|needs?|set\s?up|setup|install)\b[^.\n]{0,30}?\bVulkan\b", re.IGNORECASE | re.MULTILINE)
_README_GPU_NEGATIVE = re.compile(
    r"\b(?:optional(?:ly)?|recommended|if (?:you have|available)|not required|no gpu|without (?:a )?gpu|cpu[- ]only|"
    r"(?:also )?runs? on (?:the )?cpu|does not (?:need|require)|only for|train(?:ing)?|accelerated)\b", re.IGNORECASE)
#: file-sharing and link-shortener hosts a download lure points to
_LINK_HOSTS = re.compile(
    r"bit\.ly|tinyurl|mediafire|mega\.nz|drive\.google|dropbox|anonfiles|gofile|"
    r"gestyy|adf\.ly|shorte\.st|ouo\.io|linkvertise|"
    r"\.(?:exe|msi|dmg|apk|scr)(?:$|[?#])", re.IGNORECASE)


def _ext(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".tar.gz"):
        return ".tgz"
    return os.path.splitext(lower)[1]


def list_tree(root: str, limit: int = MAX_TREE) -> tuple[list[str], int, bool]:
    """Return (sorted relative paths capped at ``limit``, total seen, truncated).

    Directories are walked in sorted order and :data:`SKIP_DIRS` are pruned, so
    the capped prefix is deterministic for a given commit.
    """
    paths: list[str] = []
    total = 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/") + "/"
        for name in sorted(filenames):
            total += 1
            if len(paths) < limit:
                paths.append(rel_dir + name)
            else:
                truncated = True
        if total > limit * 10:
            truncated = True
            break
    paths.sort()
    return paths, total, truncated


def _read_text(path: str, limit: int) -> str:
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _find_readme(root: str, tree: list[str]) -> str | None:
    candidates = [p for p in tree if "/" not in p and p.lower().startswith("readme")]
    if not candidates:
        return None
    order = {".md": 0, ".rst": 1, ".txt": 2, "": 3}
    candidates.sort(key=lambda p: (order.get(_ext(p), 4), p))
    full = os.path.join(root, candidates[0])
    return candidates[0] if os.path.isfile(full) else None


def readme_facts(text: str, owner: str = "", repo: str = "") -> dict[str, Any]:
    """Facts from README text: heading, download call-to-action, lure wording."""
    heading = None
    match = _HEADING.search(text)
    if match:
        heading = re.sub(r"[`*_\[\]]", "", match.group(1)).strip()[:160]
    cta_links = []
    for m in _DOWNLOAD_CTA.finditer(text):
        url = m.group(1) or m.group(2)
        if url and url not in cta_links:
            cta_links.append(url)
    external_cta = []
    own_page = f"{owner.lower()}.github.io" if owner else None
    for url in cta_links:
        low = url.lower()
        if "pypi.org" in low or "anaconda.org" in low or "readthedocs" in low:
            continue
        if re.search(r"github\.com/[^/]+/[^/]+/(?:releases|archive)", low):
            continue
        if _LINK_HOSTS.search(low) or (own_page and own_page in low):
            external_cta.append(url)
    head = text[:4000]
    return {
        "bytes": len(text.encode("utf-8", errors="replace")),
        "heading": heading,
        "download_cta": sorted(external_cta)[:5],
        "lure_words": sorted({m.group(0).lower() for m in _LURE_WORDS.finditer(text)})[:8],
        "curated_list": bool(_CURATED_LIST.search(head)),
        "tutorial_words": sorted({m.group(0).lower() for m in _TUTORIAL.finditer(head)})[:8],
        "mhs_mentions": len(_MHS.findall(text)),
        "mhs_title": bool(heading and _MHS.search(heading)),
        "code_names": readme_code_names(text),
        "artifact_downloads": readme_artifact_downloads(text),
        "gpu_required": readme_gpu_lines(text),
    }


def readme_artifact_downloads(text: str) -> list[str]:
    """Asset, model, scene or checkpoint downloads a README asks for before anything runs (at most four)."""
    hits = {re.sub(r"\s+", " ", m.group(0)).strip()[:80] for m in _ARTIFACT_DOWNLOAD.finditer(text)}
    for line in text.splitlines():
        host = _ARTIFACT_HOST.search(line)
        if host and _ASSET_WORD.search(line):
            hits.add(re.sub(r"\s+", " ", host.group(0)).strip()[:80])
    return sorted(hits)[:4]


def readme_gpu_lines(text: str) -> list[str]:
    """README lines that state a GPU (or CUDA, Vulkan) requirement; lines that call it optional do not count."""
    out: list[str] = []
    for line in text.splitlines():
        if _README_GPU.search(line) and not _README_GPU_NEGATIVE.search(line):
            excerpt = re.sub(r"\s+", " ", line).strip()[:120]
            if excerpt and excerpt not in out:
                out.append(excerpt)
        if len(out) >= 3:
            break
    return out


def readme_code_names(text: str) -> list[str]:
    """Class-like names a README imports or calls (``from pkg import Name``, ``Name(``)."""
    names: set[str] = set()
    for match in _README_IMPORT.finditer(text):
        for name in match.group(2).split(","):
            name = name.strip().split(" as ")[0].strip()
            if name.isidentifier():
                names.add(name)
    for match in _README_CALL.finditer(text):
        names.add(match.group(1))
    return sorted(names)[:80]


def is_aux_path(rel: str) -> bool:
    """An example, test, docs, fixture, build-script or vendored file (see :data:`AUX_DIRS`)."""
    parts = rel.split("/")
    name = parts[-1].lower()
    if name in ("conftest.py", "setup.py", "noxfile.py", "fabfile.py", "conf.py") or name.startswith("test_") \
            or name.endswith("_test.py"):
        return True
    return any(p.lower() in AUX_DIRS for p in parts[:-1])


def _module_path(rel_file: str, roots: tuple[str, ...] = ()) -> str | None:
    """Dotted module path of a Python file.

    ``roots`` are the package directories the packaging metadata declares
    (poetry ``from``, setuptools ``package_dir``/``where``): a file below one
    of them is importable without that prefix (``generated/nidaqmx/task.py``
    is ``nidaqmx.task`` when pyproject.toml says ``from = "generated"``).
    """
    parts = rel_file[:-3].split("/") if rel_file.endswith(".py") else rel_file.split("/")
    for root in roots:
        prefix = root.split("/")
        if parts[:len(prefix)] == prefix and len(parts) > len(prefix):
            parts = parts[len(prefix):]
            break
    else:
        parts = _layout_parts(parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    return ".".join(parts)


def _layout_parts(parts: list[str]) -> list[str]:
    """Strip a ``src`` (also inside a monorepo) or ``lib``/``python``/``py`` prefix."""
    if "src" in parts[:-1]:
        # a src layout, also inside a monorepo (python/<dist>/src/<package>/...)
        last = len(parts) - 1 - parts[::-1].index("src")
        return parts[last + 1:]
    if parts and parts[0] in ("lib", "python", "py") and len(parts) > 1:
        return parts[1:]
    return parts


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    if isinstance(node, ast.Call):
        return _base_name(node.func)
    return ""


def _string(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _static_text(node: ast.expr | None) -> str | None:
    """A string constant, or an id template: an f-string or ``"...".format(...)`` with each
    interpolation shown as ``{}``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            parts.append(value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else "{}")
        return "".join(parts)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"
            and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str)):
        return re.sub(r"\{[^{}]*\}", "{}", node.func.value.value)
    return None


#: calls that register a gym/gymnasium (or ManiSkill-style) environment
REGISTER_CALLS = ("register", "register_env", "register_envs", "registry_register")


def _gym_ids(tree: ast.AST) -> list[str]:
    """Env ids passed to ``register``/``register_env`` (``-vN`` ids, or any id with an entry point)."""
    return [entry["id"] for entry in _gym_registrations(tree)]


def _imported_symbols(module: ast.AST, modpath: str | None, is_package: bool) -> dict[str, tuple[str, str]]:
    """Local name -> ("module", dotted module) or ("symbol", "module:Name") from the module's imports and classes."""
    out: dict[str, tuple[str, str]] = {}
    if not isinstance(module, ast.Module):
        return out
    package = (modpath or "") if is_package else (modpath or "").rpartition(".")[0]
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    out[alias.asname] = ("module", alias.name)
                else:
                    out[alias.name.split(".")[0]] = ("module", alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package
                for _ in range(node.level - 1):
                    base = base.rpartition(".")[0]
                mod = ".".join(x for x in (base, node.module or "") if x)
            else:
                mod = node.module or ""
            if not mod:
                continue
            for alias in node.names:
                if alias.name != "*":
                    out[alias.asname or alias.name] = ("symbol", f"{mod}:{alias.name}")
    for node in module.body:
        if isinstance(node, ast.ClassDef) and modpath:
            out[node.name] = ("symbol", f"{modpath}:{node.name}")
    return out


def _symbol_of(node: ast.expr | None, names: Mapping[str, tuple[str, str]]) -> str | None:
    """``module:Class`` for an entry point given as a class object (``ReachPosEnv``, ``envs.ReachPosEnv``)."""
    chain: list[str] = []
    while isinstance(node, ast.Attribute):
        chain.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id not in names:
        return None
    kind, target = names[node.id]
    chain.reverse()
    if not chain:
        return target if kind == "symbol" else None
    if kind == "symbol":
        mod, _, name = target.partition(":")
        module = f"{mod}.{name}"
    else:
        module = target
    if len(chain) > 1:
        module += "." + ".".join(chain[:-1])
    return f"{module}:{chain[-1]}"


def _registration_id(node: ast.Call) -> str | None:
    keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
    value = _static_text(node.args[0]) if node.args else None
    if value is None:
        for key in ("id", "env_id", "uid", "name"):
            if key in keywords:
                value = _static_text(keywords[key])
                break
    return value or None


def _gym_registrations(tree: ast.AST, modpath: str | None = None, is_package: bool = False) -> list[dict[str, Any]]:
    """``{id, entry_point, line, form, template}`` of every gym registration (see :func:`_gym_ids`).

    Forms: ``call`` (``register(id=..., entry_point="pkg.mod:Env")``, also a
    positional entry point or a class object such as
    ``vector_entry_point=ReachPosEnv``, resolved through the module's imports)
    and ``decorator`` (``@register_env("PushCube-v1")`` on a class: the entry
    point is that class and ``line`` its ``class`` line).  ``template`` marks an
    id built at run time (an f-string or ``str.format``; the interpolations are
    shown as ``{}``).
    """
    names = _imported_symbols(tree, modpath, is_package)
    out: list[dict[str, Any]] = []
    decorators: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and _call_name(dec) in REGISTER_CALLS:
                decorators.add(id(dec))
                value = _registration_id(dec)
                if value and _GYM_ID.match(value):
                    out.append({"id": value, "entry_point": f"{modpath}:{node.name}" if modpath else None,
                                "line": node.lineno, "form": "decorator", "template": "{}" in value})
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in decorators or _call_name(node) not in REGISTER_CALLS:
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        value = _registration_id(node)
        if not value:
            continue
        has_entry = "entry_point" in keywords or "vector_entry_point" in keywords
        if _GYM_ID.match(value) or (has_entry and re.match(r"^[A-Za-z0-9_./:{}-]+$", value)):
            entry_point = None
            for key in ("entry_point", "vector_entry_point"):
                if key in keywords:
                    entry_point = _string(keywords[key]) or _symbol_of(keywords[key], names)
                    if entry_point:
                        break
            if entry_point is None and len(node.args) > 1:
                entry_point = _string(node.args[1]) or _symbol_of(node.args[1], names)
            out.append({"id": value, "entry_point": entry_point, "line": node.lineno, "form": "call",
                        "template": "{}" in value})
    return out


def _imports(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0].lower())
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                out.add(node.module.split(".")[0].lower())
    return out


def _is_entry_location(rel_file: str) -> bool:
    parts = rel_file.split("/")
    name = parts[-1].lower()
    if name in ("setup.py", "conftest.py", "noxfile.py", "fabfile.py", "conf.py") or name.startswith("test_") or name.endswith("_test.py"):
        return False
    return not any(p.lower() in NON_ENTRY_DIRS for p in parts[:-1])


def _all_names(module: ast.Module) -> set[str]:
    """Names listed in ``__all__`` or re-exported by ``from .x import Name``."""
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                names.update(v for v in (_string(e) for e in node.value.elts) if v)
        elif isinstance(node, ast.ImportFrom) and node.level >= 1:
            names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
    return names


MAX_COMPOSED = 12   # composed member objects kept per class
#: methods that build a class's member objects (``__init__``, ``_initialize``, ``setup``, ``connect`` ...)
_BUILDER_METHOD = re.compile(r"^_*(?:init\w*|initiali[sz]e\w*|setup\w*|connect\w*|open|start|build\w*)$")


def _composed(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str]]:
    """``(attribute, ClassName)`` for each ``self.<attribute> = ClassName(...)`` in a method body."""
    out = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        cls = _base_name(node.value.func)
        if not cls or not cls[:1].isupper():
            continue
        for target in node.targets:
            if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                    and target.value.id == "self"):
                out.append((target.attr, cls))
    return out


def _class_info(node: ast.ClassDef) -> dict[str, Any]:
    methods: list[str] = []
    members: list[str] = []
    init_params: list[str] = []
    composes: list[tuple[str, str]] = []
    has_async = False
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(item.name)
            has_async = has_async or isinstance(item, ast.AsyncFunctionDef)
            if _BUILDER_METHOD.match(item.name):
                for pair in _composed(item):
                    if pair not in composes:
                        composes.append(pair)
            if item.name == "__init__":
                args = item.args
                init_params = [a.arg.lower() for a in (args.posonlyargs + args.args + args.kwonlyargs)]
        elif isinstance(item, (ast.Assign, ast.AnnAssign)) and isinstance(item.value, ast.Call):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_") and not target.id.isupper():
                    members.append(target.id)
    return {
        "name": node.name,
        "line": node.lineno,
        "bases": sorted({_base_name(b) for b in node.bases if _base_name(b)}),
        "methods": methods,
        "members": members,
        "init_params": init_params,
        "async": has_async,
        "composes": composes[:MAX_COMPOSED],
        "decorated_register": any(_env_decorator(d) for d in node.decorator_list),
    }


def _env_decorator(dec: ast.expr) -> bool:
    """An environment registration decorator: ``@register_env(...)``, LIBERO's ``@register_problem`` or a
    ``@register("Name-v0")`` with a gym-style id (a plugin registry's ``@Registry.register("step")`` is not)."""
    if isinstance(dec, ast.Name):
        return dec.id in ("register_problem", "register_env")
    if not isinstance(dec, ast.Call):
        return False
    name = _call_name(dec)
    if name in ("register_env", "register_envs", "register_problem"):
        return True
    value = _registration_id(dec) if name == "register" else None
    return bool(value and _GYM_ID.match(value))


def _is_device_method(name: str) -> bool:
    low = name.lower()
    return low in DEVICE_METHODS or low.startswith(DEVICE_PREFIXES)


def rank_entry_classes(classes: list[dict[str, Any]], readme_names: set[str]) -> list[dict[str, Any]]:
    """Score device-like classes; in-repo base classes contribute their API."""
    by_name: dict[str, list[dict[str, Any]]] = {}
    for info in classes:
        by_name.setdefault(info["name"], []).append(info)
    has_subclass = {b for info in classes for b in info["bases"]}

    def ancestors(info: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        queue = [info]
        seen = {id(info)}
        while queue and len(out) < 8:
            current = queue.pop(0)
            for base in current["bases"]:
                for cand in by_name.get(base, []):
                    if cand["file"] == current["file"] or len(by_name[base]) == 1:
                        if id(cand) not in seen:
                            seen.add(id(cand))
                            out.append(cand)
                            queue.append(cand)
                        break
        return out

    ranked: list[dict[str, Any]] = []
    for info in classes:
        if not info["entry_ok"]:
            continue
        lineage = [info] + ancestors(info)
        external_bases = {b.lower() for item in lineage for b in item["bases"] if b not in by_name}
        if external_bases & NON_ENTRY_BASES or NON_ENTRY_NAME.search(info["name"]) or info["name"].startswith("_"):
            continue
        methods = sorted({m for item in lineage for m in item["methods"] if not m.startswith("_")})
        members = sorted({m for item in lineage for m in item["members"]})
        api = [m for m in methods if _is_device_method(m)] + members
        if len(methods) + len(members) < 2:
            continue
        init_params = next((item["init_params"] for item in lineage if item["init_params"]), [])
        imports = set().union(*(item["module_imports"] for item in lineage))
        score = min(len(api), 10)
        if external_bases & DEVICE_BASES or any(b.lower() in DEVICE_BASES for item in lineage for b in item["bases"]):
            score += 3
        if set(init_params) & INIT_ADDRESS_PARAMS:
            score += 2
        if imports & TRANSPORT_IMPORTS:
            score += 2
        exported = info["exported"] or info["name"] in readme_names
        if exported:
            score += 3
        if re.match(r"^(?:Base|Abstract|Generic|_)", info["name"]) or info["name"] in has_subclass:
            score -= 2
        if score < 4:
            continue
        composes, composed_methods = [], []
        for attr, cname in (pair for item in lineage for pair in item.get("composes") or []):
            targets = by_name.get(cname, [])
            if not targets or cname == info["name"] or any(c["class"] == cname for c in composes):
                continue
            target = next((t for t in targets if t["file"].rsplit("/", 1)[0] == info["file"].rsplit("/", 1)[0]),
                          targets[0])
            composes.append({"attr": attr, "class": cname})
            composed_methods.extend(f"{attr}.{m}" for m in target["methods"] if not m.startswith("_"))
            if len(composes) >= MAX_COMPOSED:
                break
        ranked.append({
            "symbol": info["symbol"],
            "file": info["file"],
            "line": info["line"],
            "score": score,
            "bases": info["bases"][:6],
            "methods": methods[:40],
            "members": members[:40],
            "api_methods": [m for m in methods if _is_device_method(m)][:MAX_API_METHODS],
            "api": len(api),
            "exported": exported,
            "async": any(item["async"] for item in lineage),
            "transport": sorted(imports & TRANSPORT_IMPORTS)[:6],
            "microcontroller": bool(info.get("microcontroller")),
            # generated serialisation code (a "generated" directory can hold the real package)
            "generated": bool(info["module_imports"] & GENERATED_IMPORTS) or info["file"].endswith(
                ("_pb2.py", "_pb2_grpc.py")),
            # member objects the class builds (``self.motion = Motion(...)``): a facade's device API lives there
            "composes": composes,
            "composed_methods": composed_methods[:MAX_API_METHODS],
            # a simulator or dummy module's class: the same-named class of a real module (pyzaber's
            # dummy_linear_slides.multiaxis_linear_slides beside linear_slides.multiaxis_linear_slides)
            "real_twin": _real_twin(info, by_name),
        })
    ranked.sort(key=lambda c: (-c["score"], -c["api"], c["file"], c["line"]))
    return ranked


def _imports_unguarded(tree: ast.AST) -> set[str]:
    """Top-level modules imported outside ``try``/``if`` blocks (an optional or flag-guarded import is not)."""
    out: set[str] = set()
    stack: list[tuple[ast.AST, bool]] = [(tree, False)]
    while stack:
        node, guarded = stack.pop()
        if not guarded:
            if isinstance(node, ast.Import):
                out.update(alias.name.split(".")[0].lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                out.add(node.module.split(".")[0].lower())
        inner = guarded or isinstance(node, (ast.Try, ast.If)) or type(node).__name__ == "TryStar"
        stack.extend((child, inner) for child in ast.iter_child_nodes(node))
    return out


#: directory names of test, benchmark and study scripts beside the package (not its runtime imports)
_NOT_CORE_DIR = re.compile(r"test|timeit|bench|stud(?:y|ies)|profil|sandbox|playground|experiment", re.IGNORECASE)


def _is_core_location(rel: str) -> bool:
    """Package code: an entry location outside test, benchmark and study directories."""
    return _is_entry_location(rel) and not any(_NOT_CORE_DIR.search(p) for p in rel.split("/")[:-1])


#: base classes of simulation environments (gym/gymnasium, MuJoCo, robosuite, Isaac Lab, dm_env)
ENV_BASES = {"env", "gymenv", "mujocoenv", "vecenv", "directrlenv", "managerbasedrlenv", "baseenv", "robotenv",
             "dm_env", "environment", "manipulationenv", "singlearmenv", "twoarmenv", "goalenv", "mujocorobotenv",
             "mujocopyenv", "mujocoenvbase", "sapienenv"}
#: environment classes that are plumbing, not an environment: vector envs, wrappers, workers
_ENV_PLUMBING = re.compile(r"(?:Vector\w*Env|VecEnv\w*|Wrapper|Worker|Pool|Runner|Buffer|Registry)$|^(?:Dummy|Fake|Mock)")


def env_entries(classes: list[dict[str, Any]], readme_names: set[str]) -> list[dict[str, Any]]:
    """Ranked environment classes of the package (the entry of a simulator without a gym registration).

    A class is an environment when its base is an environment base
    (:data:`ENV_BASES`, robosuite's ``ManipulationEnv``/``SingleArmEnv``
    included), when it is registered by a decorator (``@register_env``,
    LIBERO's ``@register_problem``), when it defines ``step`` and ``reset`` and
    is named ``...Env``, or when an in-repo base class is one.  Vector envs,
    wrappers and workers are plumbing, not entries.  Up: README-named (+3),
    re-exported (+2), registered (+2); down: abstract bases and classes other
    environments subclass (-3).
    """
    env: set[int] = set()
    for info in classes:
        bases = {b.lower() for b in info["bases"]}
        if bases & ENV_BASES or info.get("decorated_register") or (
                info["name"].endswith(("Env", "Environment")) and {"step", "reset"} <= set(info["methods"])):
            env.add(id(info))
    for _ in range(4):   # subclasses of in-repo environment classes (by base-class name)
        names = {info["name"] for info in classes if id(info) in env}
        grown = {id(info) for info in classes if set(info["bases"]) & names} - env
        if not grown:
            break
        env |= grown
    subclassed = {b for info in classes for b in info["bases"]}
    out = []
    for info in classes:
        name = info["name"]
        if id(info) not in env or not info["entry_ok"] or not info.get("symbol") or _ENV_PLUMBING.search(name) \
                or name.startswith("_") or NON_ENTRY_NAME.search(name) and not name.endswith(("Env", "Environment")):
            continue
        score = 0
        score += 3 if name in readme_names else 0
        score += 2 if info["exported"] else 0
        score += 2 if info.get("decorated_register") else 0
        if re.match(r"^(?:Base|Abstract|Generic)", name) or name in subclassed:
            score -= 3
        out.append({"symbol": info["symbol"], "file": info["file"], "line": info["line"], "score": score,
                    "bases": info["bases"][:4]})
    out.sort(key=lambda e: (-e["score"], e["file"].count("/"), e["file"], e["line"]))
    return out[:MAX_ENV_ENTRIES]


def _real_twin(info: dict[str, Any], by_name: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    module = str(info.get("symbol") or "").rpartition(":")[0]
    if not _MOCK_MODULE.search(module.rsplit(".", 1)[-1].lower()):
        return None
    for cand in sorted(by_name.get(info["name"], []), key=lambda c: (c["file"].count("/"), c["file"], c["line"])):
        cmod = str(cand.get("symbol") or "").rpartition(":")[0]
        if cand is not info and cand.get("entry_ok") and cmod and not _MOCK_MODULE.search(cmod.rsplit(".", 1)[-1].lower()):
            return {"symbol": cand["symbol"], "file": cand["file"], "line": cand["line"]}
    return None


def scan_python(root: str, tree: list[str], readme_names: set[str] | None = None,
                roots: tuple[str, ...] = ()) -> dict[str, Any]:
    py_files = [p for p in tree if _ext(p) in PY_EXT
                and not any(part.lower() in VENDORED_DIRS for part in p.split("/")[:-1])]
    # shallow files first, then alphabetical: package code is preferred over
    # deep test/data trees when the cap applies
    py_files.sort(key=lambda p: (p.count("/"), p))
    imports: set[str] = set()
    imports_core: set[str] = set()
    gym_ids: set[str] = set()
    gym_ids_aux: set[str] = set()
    env_classes = 0
    parsed = failed = skipped = 0
    classes: list[dict[str, Any]] = []
    package_exports: dict[str, set[str]] = {}
    unparsed_imports: set[str] = set()
    registrations: list[dict[str, Any]] = []
    mocks: list[dict[str, Any]] = []
    limit_hints: list[dict[str, Any]] = []
    for rel in py_files[:MAX_PY_FILES]:
        full = os.path.join(root, rel)
        try:
            size = os.path.getsize(full)
        except OSError:
            skipped += 1
            continue
        if size > MAX_PY_BYTES:
            skipped += 1
            continue
        source = _read_text(full, MAX_PY_BYTES)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                module = ast.parse(source, filename=rel)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            failed += 1
            unparsed_imports.update(m.group(1).lower() for m in _IMPORT_LINE.finditer(source))
            continue
        parsed += 1
        module_imports = _imports(module)
        imports |= module_imports
        if _is_core_location(rel):
            imports_core |= _imports_unguarded(module)
        micro = bool(module_imports & MICROCONTROLLER_IMPORTS) or _micropython_time(module)
        modpath = _module_path(rel, roots)
        aux = is_aux_path(rel)
        for reg in _gym_registrations(module, modpath, rel.endswith("__init__.py")):
            if aux:
                gym_ids_aux.add(reg["id"])      # an example's, test's or docs' env is not the package's
            else:
                gym_ids.add(reg["id"])
                registrations.append(dict(reg, file=rel))
        exported_here = _all_names(module)
        if rel.endswith("__init__.py"):
            package_exports[rel.rsplit("/", 1)[0] if "/" in rel else ""] = exported_here
        entry_ok = _is_entry_location(rel)
        mocks.extend(_mock_classes(module, rel, modpath))
        if entry_ok:
            limit_hints.extend(_limit_constants(module, rel))
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {_base_name(b).lower() for b in node.bases}
            info = _class_info(node)
            if base_names & {"env", "gymenv", "mujocoenv", "vecenv", "directrlenv",
                             "managerbasedrlenv", "baseenv", "robotenv", "dm_env", "environment"} or (
                    node.name.endswith(("Env", "Environment")) and {"step", "reset"} <= set(info["methods"])):
                env_classes += 1
            info.update(file=rel, module_imports=module_imports, entry_ok=bool(entry_ok and modpath),
                        microcontroller=micro,
                        symbol=f"{modpath}:{node.name}" if modpath else None,
                        exported=node.name in exported_here)
            classes.append(info)
    for info in classes:
        package = info["file"].rsplit("/", 1)[0] if "/" in info["file"] else ""
        if info["name"] in package_exports.get(package, set()):
            info["exported"] = True
    ranked = rank_entry_classes(classes, readme_names or set())
    exported_names = sorted({name for names in package_exports.values() for name in names})
    by_symbol = {info["symbol"]: info for info in classes if info.get("symbol")}
    by_class: dict[str, list[dict[str, Any]]] = {}
    for info in classes:
        if info.get("symbol"):
            by_class.setdefault(info["name"], []).append(info)
    modules = {m for m in (_module_path(p, roots) for p in py_files) if m}
    for reg in registrations:
        _locate_registration(reg, by_symbol, by_class, modules)
    registrations.sort(key=lambda r: (r["file"].count("/"), r["file"], r["line"], r["id"]))
    for path in py_files:
        stem = path.rsplit("/", 1)[-1][:-3].lower() if path.endswith(".py") else ""
        if _MOCK_MODULE.search(stem):
            mocks.append({"kind": "module", "file": path, "line": 1, "symbol": None})
    mocks = _dedupe_sorted(mocks, ("file", "line"))
    limit_hints = _dedupe_sorted(limit_hints, ("file", "line", "name"))
    return {
        "files": len(py_files),
        "parsed": parsed,
        "failed": failed,
        "skipped": skipped + max(0, len(py_files) - MAX_PY_FILES),
        "imports": sorted(imports),
        "imports_unparsed": sorted(unparsed_imports - imports)[:200],
        "imports_core": sorted(imports_core),
        "gym_ids": sorted(gym_ids)[:50],
        "gym_id_count": len(gym_ids),
        "gym_ids_aux": sorted(gym_ids_aux - gym_ids)[:10],
        "gym_entries": registrations[:MAX_GYM_ENTRIES],
        "env_classes": env_classes,
        "env_entries": env_entries(classes, readme_names or set()),
        "classes": len(classes),
        "entry_classes": ranked[:MAX_ENTRY_CLASSES],
        "entry_more": [_light(c) for c in _distinct_more(ranked)],
        "exported_names": exported_names[:MAX_EXPORTED_NAMES],
        "mocks": mocks[:MAX_MOCKS],
        "limit_hints": limit_hints[:MAX_LIMIT_HINTS],
    }


def _micropython_time(module: ast.Module) -> bool:
    """MicroPython-only imports at module level: ``from time import sleep_ms``, ``from machine import Pin``."""
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            names = {alias.name for alias in node.names}
            if node.module in ("time", "utime") and names & MICROCONTROLLER_TIME_NAMES:
                return True
            if node.module == "machine" and names & MICROCONTROLLER_MACHINE_NAMES:
                return True
    return False


def _module_matches(found: str, module: str) -> bool:
    """``found`` is ``module`` itself or the same module below a path prefix (``examples.pkg.envs`` for ``pkg.envs``)."""
    return found == module or found.endswith("." + module)


def _locate_registration(reg: dict[str, Any], by_symbol: dict[str, dict[str, Any]],
                         by_class: dict[str, list[dict[str, Any]]], modules: set[str]) -> None:
    """Find the class a gym registration names: ``class_file``/``class_line`` and how it was found.

    ``class_resolved`` is ``defined`` (the entry-point module defines the
    class) or ``reexport`` (exactly one class of that name is defined below the
    entry-point package, or in the same top-level package, which re-exports
    it); it is absent when the class was not found.  ``module_in_repo`` is
    False when no module of this repo is the entry-point module or below it
    (an engine's generic env class such as ``isaaclab.envs:ManagerBasedRLEnv``).
    """
    entry = reg.get("entry_point") or ""
    if ":" not in entry:
        return
    module, name = entry.split(":", 1)
    reg["module_in_repo"] = any(_module_matches(m, module) or m.startswith(module + ".") or ("." + module + ".") in m
                                for m in modules)
    target = by_symbol.get(entry)
    how = "defined" if target is not None else None
    if target is None:
        named = by_class.get(name, [])
        same = [i for i in named if _module_matches(i["symbol"].split(":")[0], module)]
        below = [i for i in named if i["symbol"].split(":")[0].startswith(module + ".")
                 or ("." + module + ".") in i["symbol"].split(":")[0]]
        top = module.split(".")[0]
        package = [i for i in named if top in i["symbol"].split(":")[0].split(".")]
        for candidates, kind in ((same, "defined"), (below, "reexport"), (package, "reexport")):
            if len(candidates) == 1:
                target, how = candidates[0], kind
                break
            if candidates:
                break
    if target is not None:
        reg["class_file"], reg["class_line"], reg["class_resolved"] = target["file"], target["line"], how


def _distinct_more(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ranked classes after the first MAX_ENTRY_CLASSES, skipping variants whose API repeats an earlier class."""
    seen = {(c["symbol"].rsplit(":", 1)[-1], tuple(c["methods"]), tuple(c["members"])) for c in ranked[:MAX_ENTRY_CLASSES]}
    apis = {(tuple(c["methods"]), tuple(c["members"])) for c in ranked[:MAX_ENTRY_CLASSES]}
    out = []
    for cls in ranked[MAX_ENTRY_CLASSES:]:
        api = (tuple(cls["methods"]), tuple(cls["members"]))
        key = (cls["symbol"].rsplit(":", 1)[-1],) + api
        if key in seen or (api in apis and api != ((), ())):
            continue
        seen.add(key)
        apis.add(api)
        out.append(cls)
        if len(out) >= MAX_ENTRY_MORE:
            break
    return out


def _light(cls: dict[str, Any]) -> dict[str, Any]:
    """A ranked class without the long method lists (cards only need a few)."""
    out = dict(cls)
    out["methods"] = cls["methods"][:20]
    out["members"] = cls["members"][:20]
    out["api_methods"] = cls["api_methods"][:60]
    out["composed_methods"] = list(cls.get("composed_methods") or [])[:60]
    return out


def _dedupe_sorted(items: list[dict[str, Any]], key: tuple[str, ...]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in sorted(items, key=lambda i: (str(i["file"]).count("/"),) + tuple(str(i[k]) if k != "line" else
                                                                                  f"{int(i[k]):08d}" for k in key)):
        marker = tuple(item[k] for k in key)
        if marker not in seen:
            seen.add(marker)
            out.append(item)
    return out


#: class and module names of upstream simulators, mocks and fakes (mock_strategy hints)
_MOCK_NAME = re.compile(r"(?:^|(?<=[a-z0-9_]))(?:Sim|Simulated|Simulator|Simulation|Mock|Mocked|Fake|Dummy|"
                        r"Emulator|Emulated|Virtual|Loopback)(?=[A-Z0-9_]|$)")
_MOCK_MODULE = re.compile(r"(?:^|_)(?:sim|simulat\w*|mock\w*|fake\w*|dummy|emulat\w*|virtual)(?:_|$)")
#: constants that look like device limits: MAX_TEMP, TEMP_MIN, SPEED_LIMIT, VOLTAGE_RANGE, LIMITS ...
_LIMIT_NAME = re.compile(r"^(?:MAX|MIN|MAXIMUM|MINIMUM)_|_(?:MAX|MIN|MAXIMUM|MINIMUM|LIMITS?|RANGES?|BOUNDS?)$|"
                         r"^(?:LIMITS?|RANGES?|BOUNDS?)$|^(?:max|min)_[a-z0-9_]+$|^[a-z0-9_]+_(?:max|min|limits?|range)$")


def _mock_classes(module: ast.Module, rel: str, modpath: str | None) -> list[dict[str, Any]]:
    out = []
    for node in module.body:
        if isinstance(node, ast.ClassDef) and _MOCK_NAME.search(node.name) and not node.name.startswith("_"):
            if NON_ENTRY_NAME.search(node.name) and not re.search(r"(?:Sim|Mock|Fake|Dummy)", node.name):
                continue
            out.append({"kind": "class", "file": rel, "line": node.lineno,
                        "symbol": f"{modpath}:{node.name}" if modpath else None})
    return out


def _numeric(node: ast.expr | None) -> Any:
    """A number, a negated number, or a short list/tuple of numbers (else None)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _numeric(node.operand)
        if isinstance(inner, (int, float)):
            return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, (ast.Tuple, ast.List)) and 0 < len(node.elts) <= 8:
        values = [_numeric(e) for e in node.elts]
        if all(isinstance(v, (int, float)) for v in values):
            return values
    return None


def _limit_constants(module: ast.Module, rel: str) -> list[dict[str, Any]]:
    """Module- and class-level numeric constants whose names read like limits."""
    out = []
    bodies = [module.body] + [n.body for n in module.body if isinstance(n, ast.ClassDef)]
    for body in bodies:
        for node in body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target, value = node.target, node.value
            else:
                continue
            if not isinstance(target, ast.Name) or not _LIMIT_NAME.search(target.id):
                continue
            number = _numeric(value)
            if number is None:
                continue
            text = repr(number)
            if len(text) > 80:
                continue
            out.append({"file": rel, "line": node.lineno, "name": target.id, "value": text})
    return out


_XML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_MJ_ACTUATOR = re.compile(r"<actuator\b[^>]*>(.*?)</actuator>", re.DOTALL)
_MJ_ACTUATOR_CHILD = re.compile(r"<(?:motor|position|velocity|intvelocity|general|cylinder|muscle|adhesion|damper|"
                                r"plugin)\b")
_MJ_INCLUDE = re.compile(r"<include\b[^>]*\bfile\s*=\s*[\"']([^\"']+)[\"']")
_MJ_MODEL = re.compile(r"<mujoco\b[^>]*\bmodel\s*=\s*[\"']([^\"']*)[\"']")
#: directories of component libraries: a gripper, object, fixture or mount is a part another model includes,
#: never the main model (robosuite-style robots get their actuators at run time, so only their grippers are
#: actuated in the clone)
MJCF_COMPONENT_DIRS = {"grippers", "gripper", "end_effectors", "objects", "object", "articulated_objects", "fixtures",
                       "fixture", "props", "furniture", "mounts", "mount", "bases", "accessories", "items", "textures",
                       "meshes", "sensors", "cameras"}
#: path components that mark a model as unsupported, deprecated or a backup (robopal's ``vx300s(not_support_now)``)
_MJCF_UNSUPPORTED = re.compile(r"not[_ -]?support|unsupported|deprecated|obsolete|broken|backup|(?:^|[_.-])old(?:$|[_.-])",
                               re.IGNORECASE)
#: MJCF file names of a scene (a world with a floor, lights and the robot included)
_SCENE_STEM = re.compile(r"(?:^|[_.-])(?:scene|world|arena|env|environment|task|playground)s?(?:$|[_.-]|\d)",
                         re.IGNORECASE)


def mjcf_facts(text: str) -> dict[str, Any]:
    """Facts of one MJCF file: the ``<mujoco`` line, model name, actuators, worldbody and includes."""
    line = text[: text.find("<mujoco")].count("\n") + 1 if "<mujoco" in text else 1
    body = _XML_COMMENT.sub("", text)
    model = _MJ_MODEL.search(body)
    return {
        "line": line,
        "model": model.group(1)[:80] if model else None,
        # actuators directly, or an <include> inside <actuator> (a file of bare <motor .../> elements)
        "actuated": any(_MJ_ACTUATOR_CHILD.search(m.group(1)) or "<include" in m.group(1)
                        for m in _MJ_ACTUATOR.finditer(body)),
        "worldbody": "<worldbody" in body,
        "includes": [m.group(1) for m in _MJ_INCLUDE.finditer(body)][:20],
    }


def _resolve_include(rel: str, target: str, known: set[str]) -> str | None:
    """The tree path an ``<include file=...>`` names: relative to the including file's directory or any
    directory above it (MuJoCo resolves includes against the top-level model's directory).  A path that
    climbs out of the clone (``../unitree_sim/basic_scene.xml`` inside the ``unitree_sim`` clone) is matched
    by its trailing components."""
    if "{" in target or target.startswith("/") or "://" in target:
        return None
    parts = rel.split("/")[:-1]
    for depth in range(len(parts), -1, -1):
        candidate = os.path.normpath("/".join(parts[:depth] + [target])).replace(os.sep, "/")
        if candidate in known:
            return candidate
    if target.startswith("../"):
        tail = [p for p in target.split("/") if p not in ("..", ".", "")]
        for k in range(len(tail)):
            if "/".join(tail[k:]) in known:
                return "/".join(tail[k:])
    return None


def classify_mjcf(files: Mapping[str, Mapping[str, Any]], tree: list[str], repo: str = "") -> list[dict[str, Any]]:
    """Ranked main-model candidates among the MJCF files read (``{file, line, kind}``).

    A main model is loadable on its own and models something that moves: it
    has a worldbody and actuators, directly or through files it includes
    (followed within the repo).  Kinds: ``scene`` (a scene-named file, or one
    that includes others) and ``robot``.  Never main: object and fixture
    assets (no actuators), fragments (no worldbody), templates or files whose
    includes are not in the clone, copies under examples, tests, docs or
    vendored trees (:data:`AUX_DIRS`), parts in component-library
    directories (:data:`MJCF_COMPONENT_DIRS`: grippers, objects, fixtures,
    mounts ...) and paths marked unsupported, deprecated or a backup.
    Order: scenes, then robots; files under ``_``-prefixed (private)
    directories last; a file or model name that shares a word with the repo
    name first; shallow paths first.
    """
    known = set(tree)
    resolved: dict[str, list[str | None]] = {
        rel: [_resolve_include(rel, inc, known) for inc in facts["includes"]] for rel, facts in files.items()}

    def closure(rel: str, key: str, seen: set[str]) -> bool:
        if rel in seen or rel not in files:
            return False
        seen.add(rel)
        return bool(files[rel][key]) or any(closure(inc, key, seen) for inc in resolved[rel] if inc)

    repo_words = {w for w in re.split(r"[^a-z0-9]+", repo.lower()) if len(w) >= 3}
    out = []
    for rel, facts in files.items():
        if is_aux_path(rel) or any(inc is None for inc in resolved[rel]) \
                or {p.lower() for p in rel.split("/")[:-1]} & MJCF_COMPONENT_DIRS or _MJCF_UNSUPPORTED.search(rel):
            continue
        if not (closure(rel, "actuated", set()) and closure(rel, "worldbody", set())):
            continue
        stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        kind = "scene" if _SCENE_STEM.search(stem) or facts["includes"] else "robot"
        words = {w for w in re.split(r"[^a-z0-9]+", f"{stem} {facts.get('model') or ''}".lower()) if len(w) >= 3}
        private = any(p.startswith("_") for p in rel.split("/")[:-1])     # a vendored or private part (``_robotiq/``)
        out.append({"file": rel, "line": int(facts["line"]), "kind": kind,
                    "_key": (kind != "scene", private, not (words & repo_words), rel.count("/"), rel)})
    out.sort(key=lambda m: m.pop("_key"))
    return out[:MAX_MJCF_MAIN]


def scan_markers(root: str, tree: list[str], repo: str = "") -> dict[str, Any]:
    package_xml = [p for p in tree if p.rsplit("/", 1)[-1] == "package.xml"]
    launch = [p for p in tree if p.endswith((".launch", ".launch.py", ".launch.xml"))]
    urdf = [p for p in tree if p.lower().endswith((".urdf", ".urdf.xacro", ".xacro"))]
    mjcf = []
    xml_files = [p for p in tree if p.lower().endswith((".xml", ".mjcf")) and p.rsplit("/", 1)[-1] != "package.xml"]
    # the repo's own files before example, test and vendored copies when the cap applies
    xml_files.sort(key=lambda p: (is_aux_path(p), p.count("/"), p))
    mjcf_text: dict[str, dict[str, Any]] = {}
    for rel in xml_files[:MAX_XML_HEADS]:
        head = _read_text(os.path.join(root, rel), 2048)
        if "<mujoco" in head:
            mjcf.append(rel)
            mjcf_text[rel] = mjcf_facts(_read_text(os.path.join(root, rel), MJCF_BYTES))
    mjcf.sort()
    unity = any(p.startswith("ProjectSettings/") or "/ProjectSettings/ProjectVersion.txt" in p for p in tree) or any(
        p.endswith(".unity") for p in tree)
    unreal = any(p.endswith(".uproject") or p.endswith(".uplugin") for p in tree)
    root_files = sorted(p for p in tree if "/" not in p and p in ROOT_BUILD_FILES)
    has_tests = any(part in ("test", "tests") for p in tree for part in p.split("/")[:-1]) or any(
        p.rsplit("/", 1)[-1].startswith("test_") and p.endswith(".py") for p in tree)
    test_dirs: set[str] = set()
    for p in tree:
        parts = p.split("/")[:-1]
        for i, part in enumerate(parts):
            if part in ("test", "tests"):
                test_dirs.add("/".join(parts[:i + 1]))
                break
    return {
        "package_xml": len(package_xml),
        "package_xml_paths": package_xml[:10],
        "launch_files": len(launch),
        "urdf": len(urdf),
        "mjcf": len(mjcf),
        "mjcf_aux": sum(1 for p in mjcf if is_aux_path(p)),
        "mjcf_paths": [p for p in mjcf if not is_aux_path(p)][:10],
        "mjcf_main": classify_mjcf(mjcf_text, tree, repo),
        "unity_project": unity,
        "unreal_project": unreal,
        "root_build_files": root_files,
        "has_tests": has_tests,
        "test_dirs": sorted(test_dirs, key=lambda d: (d.count("/"), d))[:5],
    }


def count_kinds(tree: list[str]) -> dict[str, int]:
    counts = {"files": len(tree), "python": 0, "code": 0, "notebooks": 0,
              "executables": 0, "installers": 0, "archives": 0, "docs": 0}
    for path in tree:
        ext = _ext(path)
        if ext in PY_EXT:
            counts["python"] += 1
        elif ext in CODE_EXT:
            counts["code"] += 1
        elif ext in NOTEBOOK_EXT:
            counts["notebooks"] += 1
        elif ext in EXECUTABLE_EXT:
            counts["executables"] += 1
            if ext in INSTALLER_EXT:
                counts["installers"] += 1
        elif ext in ARCHIVE_EXT:
            counts["archives"] += 1
        elif ext in DOC_EXT:
            counts["docs"] += 1
    return counts


def scan_license(root: str, tree: list[str]) -> dict[str, Any]:
    """Root licence files and the SPDX id of their text (``licenses.detect_files``)."""
    files = LIC.license_files(p for p in tree if "/" not in p)
    texts = {name: _read_text(os.path.join(root, name), LICENSE_BYTES) for name in files[:4]}
    spdx, used = LIC.detect_files(texts)
    return {"files": files[:8], "spdx": spdx, "file": used}


_REQUIRES_PYTHON = (
    ("pyproject.toml", re.compile(r"^\s*requires-python\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)),
    ("setup.cfg", re.compile(r"^\s*python_requires\s*=\s*([^\s#;]+(?:\s*,\s*[^\s#;]+)*)", re.MULTILINE)),
    ("setup.py", re.compile(r"python_requires\s*=\s*['\"]([^'\"]+)['\"]")),
)
_SCRIPT_ENTRY = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_][\w.]*$")
#: licence declared in packaging metadata: ``license = "MIT"`` (pyproject, setup.cfg),
#: ``license={text = "..."}``, ``license="..."`` (setup.py) and ``License ::`` trove classifiers
_DECLARED_LICENSE = re.compile(
    r"^\s*license\s*=\s*(?:\{\s*text\s*=\s*)?['\"]([^'\"\n]+)['\"]"
    r"|^\s*license\s*=\s*([A-Za-z0-9][^\n#;]*?)\s*$"
    r"|['\"]License :: (?:OSI Approved :: )?([^'\"\n]+)['\"]", re.MULTILINE)


#: package directories in packaging metadata: poetry ``packages = [{include = "x", from = "dir"}]``,
#: setuptools ``package_dir = {"": "dir"}`` / ``package-dir`` / ``where = ["dir"]`` and setup.cfg ``package_dir = =dir``
_PACKAGE_ROOTS = (
    re.compile(r"\{[^{}\n]*\binclude\s*=\s*[\"'][^\"']+[\"'][^{}\n]*\bfrom\s*=\s*[\"']([^\"']+)[\"']"),
    re.compile(r"package[_-]dir\s*=\s*\{\s*[\"'][\"']\s*:\s*[\"']([^\"']+)[\"']"),
    re.compile(r"^\s*[\"'][\"']\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE),
    re.compile(r"\bwhere\s*=\s*\[?\s*[\"']([^\"']+)[\"']"),
    re.compile(r"^\s*package_dir\s*=\s*\n?\s*=\s*([\w./-]+)\s*$", re.MULTILINE),
)


def package_roots(root: str, tree: list[str]) -> list[str]:
    """Package directories declared by the root build files (see :func:`_module_path`)."""
    root_files = {p for p in tree if "/" not in p}
    found: set[str] = set()
    for name in ("pyproject.toml", "setup.cfg", "setup.py"):
        if name not in root_files:
            continue
        text = _read_text(os.path.join(root, name), BUILD_FILE_BYTES)
        for pattern in _PACKAGE_ROOTS:
            if pattern.pattern.startswith("^\\s*[") and "package-dir" not in text and "package_dir" not in text:
                continue    # a bare '"" = "dir"' line counts only inside a package-dir table
            for match in pattern.finditer(text):
                value = match.group(1).strip().strip("/").removeprefix("./")
                if value and value != "." and re.match(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$", value) \
                        and any(p.startswith(value + "/") for p in tree):
                    found.add(value)
    return sorted(found, key=lambda v: (-v.count("/"), v))[:4]


def scan_install(root: str, tree: list[str], commit: str | None = None) -> dict[str, Any]:
    """``requires-python`` and console scripts from the root build files (text only)."""
    root_files = {p for p in tree if "/" not in p}
    python_requires = None
    for name, pattern in _REQUIRES_PYTHON:
        if name in root_files:
            match = pattern.search(_read_text(os.path.join(root, name), BUILD_FILE_BYTES))
            if match:
                python_requires = re.sub(r"\s+", "", match.group(1))[:40]
                break
    scripts: list[str] = []
    if "pyproject.toml" in root_files:
        text = _read_text(os.path.join(root, "pyproject.toml"), BUILD_FILE_BYTES)
        section = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL)
        if section:
            for match in re.finditer(r"^\s*['\"]?([\w.-]+)['\"]?\s*=\s*['\"]([^'\"]+)['\"]", section.group(1),
                                     re.MULTILINE):
                scripts.append(f"{match.group(1)}={match.group(2).strip()}")
    for name in ("setup.py", "setup.cfg"):
        if name in root_files:
            text = _read_text(os.path.join(root, name), BUILD_FILE_BYTES)
            for match in re.finditer(r"['\"]?([\w.-]+)\s*=\s*([A-Za-z_][\w.]*:[A-Za-z_][\w.]*)['\"]?", text):
                if "console_scripts" in text or "gui_scripts" in text:
                    scripts.append(f"{match.group(1)}={match.group(2)}")
    scripts = sorted({s for s in scripts if _SCRIPT_ENTRY.match(s.split("=", 1)[1])})
    requirements = sorted(p for p in root_files if re.match(r"^requirements[\w.-]*\.txt$", p))
    declared: list[str] = []
    for name in ("pyproject.toml", "setup.cfg", "setup.py"):
        if name not in root_files:
            continue
        text = _read_text(os.path.join(root, name), BUILD_FILE_BYTES)
        for match in _DECLARED_LICENSE.finditer(text):
            value = (match.group(1) or match.group(2) or match.group(3) or "").strip()
            if value and len(value) <= 120 and value not in declared:
                declared.append(value)
    buildable = None
    if "pyproject.toml" in root_files:
        text = _read_text(os.path.join(root, "pyproject.toml"), BUILD_FILE_BYTES)
        buildable = bool(re.search(r"^\[(?:build-system|project|tool\.poetry)\]", text, re.MULTILINE))
    return {"python_requires": python_requires, "console_scripts": scripts[:20], "requirements": requirements[:6],
            "pyproject_buildable": buildable, "declared_license": declared[:4],
            "package_roots": package_roots(root, tree), "ros_build": scan_ros_build(root, commit)}


def pyvisa_sim_files(root: str, tree: list[str]) -> list[str]:
    """YAML files with pyvisa-sim ``devices:`` and ``dialogues:`` sections (a SCPI simulator)."""
    out = []
    for rel in [p for p in tree if p.lower().endswith((".yaml", ".yml"))][:MAX_XML_HEADS]:
        head = _read_text(os.path.join(root, rel), 4096)
        if re.search(r"^devices:", head, re.MULTILINE) and "dialogues:" in head:
            out.append(rel)
    return out[:MAX_MOCKS]


def scan_repo(root: str, owner: str = "", repo: str = "", commit: str | None = None) -> dict[str, Any]:
    """Scan one clone. Root ROS build evidence uses ``commit``; other facts retain the existing worktree scan."""
    tree, total, truncated = list_tree(root)
    readme_path = _find_readme(root, tree)
    readme = readme_facts(_read_text(os.path.join(root, readme_path), README_BYTES), owner, repo) if readme_path else None
    if readme is not None:
        readme["path"] = readme_path
    counts = count_kinds(tree)
    counts["total"] = total
    install = scan_install(root, tree, commit)
    python = scan_python(root, tree, set((readme or {}).get("code_names") or []),
                         tuple(install["package_roots"]))
    mocks = list(python.pop("mocks")) + [{"kind": "pyvisa-sim", "file": p, "line": 1, "symbol": None}
                                          for p in pyvisa_sim_files(root, tree)]
    limit_hints = python.pop("limit_hints")
    return {
        "scan_version": SCAN_VERSION,
        "tree": tree,
        "truncated": truncated,
        "counts": counts,
        "readme": readme,
        "python": python,
        "markers": scan_markers(root, tree, repo),
        "license": scan_license(root, tree),
        "install": install,
        "mocks": _dedupe_sorted(mocks, ("file", "line"))[:MAX_MOCKS],
        "limit_hints": limit_hints,
    }


if __name__ == "__main__":  # ad-hoc inspection: python3 source_scan.py <clone>
    import json
    import sys

    for arg in sys.argv[1:]:
        facts = scan_repo(arg, *os.path.normpath(arg).split(os.sep)[-2:])
        facts["tree"] = f"<{len(facts['tree'])} paths>"
        print(json.dumps(facts, indent=1, sort_keys=True))
