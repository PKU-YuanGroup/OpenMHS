#!/usr/bin/env python3
"""Per-repo task cards: ``MHS/registry/tasks/<track>/<owner>__<repo>.json`` (stdlib only).

One card per registry record, validated by ``schema/taskcard.schema.json``.
A card is the only input a driver author (human or model) gets for one repo.
Every field is derived from the triage decision (``triage.py``), the corpus
lock (``corpus.lock.jsonl``), the licence facts (``licenses.py``) and the
bounded AST/file scan of the clone (``source_scan.py``):

``entry_symbols``   AST classes only, typed ``{symbol, file, line,
                    confidence}``: the package's gym/gymnasium registrations
                    (then its ranked environment classes, robosuite and LIBERO
                    style included) for simulator cards, ranked device classes
                    otherwise (simulators, mocks and dummies of the device are
                    left to ``mock_strategy``).  ``ast`` when the class
                    definition was found in the clone (a registration's class
                    is followed through re-exports); ``recon`` for a
                    registration whose class is not defined in the clone (an
                    engine's generic env class) or was not found, with the
                    registration's file and line.  Never README lines or
                    ``__init__.py:1`` package markers.
``models``          MuJoCo scene and robot models a MujocoDriver can load,
                    ranked (``{file, line, kind}``; the first is the main
                    model): loadable MJCF files with actuators, never object
                    or fixture assets, fragments, templates or example copies.
``install``         commands only when a root file backs them (``pip install .``
                    for a buildable pyproject.toml or setup.py, ``pip install -r
                    requirements.txt``; root ROS packages need explicit Catkin
                    or ament evidence before selecting their workspace build);
                    ``system_deps`` names software pip does not install that
                    package code imports (mujoco-py's MuJoCo 2.1 binaries).
``mock_strategy``   upstream simulators, mocks and fakes the scan found; the
                    environment itself for simulators; a transcript for SCPI
                    and serial command maps without one; a recording fake
                    otherwise.
``hints``           reads, writes and actions of the entry classes, and the
                    stable catalogue classes their method and attribute names
                    suggest (setters without a better class map to
                    ``cap.device.configure.v1``).  Suggestions, not a
                    specification.  An override's ``capability_classes``
                    (a reviewer's reading of the source) replace the
                    suggested classes, and the risk floor follows them.
``needs_recon``     what the scan could not derive: ``decision``,
                    ``entry_symbol``, ``model`` (a MuJoCo card without a main
                    model), ``install``, ``capabilities``, ``limit_sources``,
                    ``license``, ``artifacts`` (the README downloads assets,
                    models or LFS objects the clone does not hold),
                    ``motion`` (a robot hardware card whose motion API was not
                    found, and no reviewer named its classes) and ``mode`` (a
                    recon card of a simulation repo
                    whose code also drives hardware: the recon decides which
                    mode the driver serves).
``safety``          ``expected_mode`` is the record's first mode (hardware first;
                    null for a never-dispatched card of a record without
                    modes; an override's reviewed ``modes`` set the
                    record's modes); ``risk_floor`` is the highest catalogue
                    ``risk_class`` of the candidate classes
                    (``catalog_view.risk_floor``); ``limit_hints`` are numeric
                    MIN/MAX/LIMIT/RANGE constants with ``file:line`` on
                    hardware-mode cards (error codes, counters, protocol and
                    network sizes, training settings and ML, script and
                    example modules dropped).
``helper``          from the pilot helper table (``triage.FAMILIES``); a missing
                    helper is a ``helper:<name>`` entry in ``blocked_on``; a
                    python-object card with neither an entry symbol nor
                    candidate classes (a serial or SCPI card: nor an install
                    file) is blocked on ``recon:entry_symbol``
                    (:func:`recon_first`).
``package_status``  the driver package's state from ``MHS/drivers/**``: none,
                    in_progress (a directory without RESULT.json), pass,
                    blocked or skip-proposed.  A passing package is not
                    dispatched again.
``wave``/``rank``   the published rollout waves and rank formula (below).

Waves: 0 exemplars (curated); 1 pilot pool (``tasks/pilot-candidates.json``);
2 strict-ready dispatchable cards (Python, a pip install backed by a root file
with no system dependency such as mujoco-py's MuJoCo 2.1 binaries, no GPU,
licence known, an AST entry symbol or, for MuJoCo, a main model, candidate
classes, no artifact download); 3 the other dispatchable cards;
4 recon-only cards (``untriaged``, and dispatchable cards blocked on
``recon:entry_symbol``); 5 cards waiting for a post-pilot helper; 6 cards that
need a GPU, Windows or a helper-less external engine (Isaac, Unity, Unreal,
Habitat, AirSim, CARLA, Gazebo); 9 cards that are never dispatched as a repo
task (``skip``, ``reference`` and ``bridge-runtime``).

Rank within a wave (deterministic, 1 = first)::

    rank_score = 40*partner + 20*hardware_mode + 10*helper_available + 8*has_tests
                 + 5*log10(stars + 1) - 15*gpu - 20*license_unknown

sorted by descending score, ties broken by ``package_id``.

Run:  python3 MHS/registry/taskcards.py [--jobs N] [--cache DIR] [--check]
      regenerates every card from the committed records and a scan of the
      corpus.  ``build_registry.py`` calls the same functions in-process.
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict
from typing import Any, Iterable, Mapping, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import catalog_view as CV  # noqa: E402
import family_data as FD  # noqa: E402
import licenses as LIC  # noqa: E402
import triage as T  # noqa: E402

CARD_VERSION = "0.9"
TASKS_DIR = os.path.join(HERE, "tasks")
PILOT_PATH = os.path.join(TASKS_DIR, "pilot-candidates.json")
sys.path.insert(0, os.path.join(WORKSPACE, "MHS", "sdk", "src"))
from mhs import _ids  # noqa: E402  (identifiers: SCHEMA_BASE, REGISTRY_ID)

CARD_SCHEMA = _ids.SCHEMA_BASE + "taskcard.schema.json"
TRACKS = ("labs", "robots")

WAVE_EXEMPLAR, WAVE_PILOT, WAVE_STRICT, WAVE_CORE, WAVE_RECON, WAVE_HELPER, WAVE_LAST, WAVE_NEVER = 0, 1, 2, 3, 4, 5, 6, 9
WAVES = OrderedDict((
    (WAVE_EXEMPLAR, "exemplars, done before the handoff (curated overrides)"),
    (WAVE_PILOT, "pilot pool: the non-exemplar cards of tasks/pilot-candidates.json (MHS/handoff/pilot-20.json "
                 "dispatches 20 of them)"),
    (WAVE_STRICT, "strict-ready: Python, pip install backed by a root file with no system dependency, no GPU, "
                  "licence known, AST entry symbol (or, for MuJoCo, a main scene or robot model), candidate classes, "
                  "no artifact download"),
    (WAVE_CORE, "other dispatchable cards with an available helper"),
    (WAVE_RECON, "recon-only cards (decision untriaged, or a dispatchable card blocked on recon:entry_symbol): "
                 "confirm an entry symbol and a decision"),
    (WAVE_HELPER, "family members waiting for a post-pilot helper (blocked_on helper:<name>)"),
    (WAVE_LAST, "cards that need a GPU, Windows or an external engine without a helper (Isaac, Unity, Unreal, "
                "Habitat, AirSim, CARLA, Gazebo)"),
    (WAVE_NEVER, "never dispatched as a repo task: skip, reference and bridge-runtime cards"),
))
RANK_FORMULA = ("rank_score = 40*partner + 20*hardware_mode + 10*helper_available + 8*has_tests "
                "+ 5*log10(stars+1) - 15*gpu - 20*license_unknown; sorted by descending score, "
                "ties by package_id")
PILOT_SIZE = 40
PILOT_BUCKETS = OrderedDict((
    ("direct-python-instrument", "direct Python instrument drivers (python-object, labs track)"),
    ("serial-scpi", "serial and SCPI command maps (SerialDriver, ScpiDriver)"),
    ("gymnasium-mujoco", "gymnasium and MuJoCo simulators (GymnasiumDriver, MujocoDriver)"),
    ("robot-sdk", "robot SDK drivers on fakes (python-object, robots track)"),
))

MAX_ENTRY_SYMBOLS = 5
MAX_HINTS = 12
MAX_CLASSES = 8
MAX_LIMIT_HINTS = 8
#: blocked_on entry of a dispatchable card that has neither an entry symbol nor candidate classes
RECON_BLOCK = "recon:entry_symbol"
PACKAGE_STATUSES = ("none", "in_progress", "pass", "blocked", "skip-proposed")

CJK_RE = re.compile(r"[　-〿㐀-鿿豈-﫿＀-￯]")


# ---------------------------------------------------------------------------
# English text
# ---------------------------------------------------------------------------

def english(text: str, limit: int = 300) -> str:
    """Render triage evidence in English: glossary-translate quoted catalogue values, drop what stays CJK."""
    text = str(text or "")
    if CJK_RE.search(text):
        def repl(match: "re.Match[str]") -> str:
            inner = match.group(2)
            rendered = re.sub(r"\s*\[zh\]\s*$", "", FD.translate_zh(inner)).strip()
            return repr(rendered) if rendered and not CJK_RE.search(rendered) else "(catalogue text)"
        text = re.sub(r"(['\"])([^'\"]*?[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef][^'\"]*?)\1", repl, text)
        text = CJK_RE.sub("", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return text


# ---------------------------------------------------------------------------
# entry symbols
# ---------------------------------------------------------------------------

_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")
_REL = re.compile(r"^(?!/)(?!.*(^|/)\.\.(/|$))[A-Za-z0-9._@+/-]+$")
#: directories that wrap a device for another framework (a server, GUI or CLI front end)
WRAPPER_DIRS = {"server", "servers", "tango", "gui", "ui", "qt", "web", "webapp", "widgets", "cli", "dashboard",
                "frontend", "app", "apps", "viewer", "viewers", "rpc"}
#: directories of a GUI front end: their classes are widgets and views, never a card's entry symbol
GUI_DIRS = {"gui", "ui", "qt", "widgets", "views", "frontend"}
#: directories and modules of the transport layer below the device classes
TRANSPORT_DIRS = {"interface", "interfaces", "transport", "transports", "adapter", "adapters", "comm", "comms",
                  "communication", "connection", "connections", "protocol", "protocols", "bus"}
#: directories of optional or contributed code beside the package
EXTRA_DIRS = {"extra", "extras", "contrib", "demo", "demos", "sample", "samples", "example", "examples", "legacy"}
#: directories of a lab framework's plugins around the device's own wrapper (PyMoDAQ's ``daq_move_plugins`` and
#: ``daq_viewer_plugins`` call the classes under ``hardware/``)
PLUGIN_DIRS = {"daq_move_plugins", "daq_viewer_plugins"}
#: top-level packages of reinforcement-learning libraries that robot-learning repos vendor (a copy of
#: ``stable_baselines3/`` beside the package): never a device entry
VENDORED_DIRS = {"stable_baselines3", "baselines", "rl_games", "rsl_rl", "skrl", "tianshou"}
#: base classes of a Qt front end (``QObject``, ``QThread``, ``QWidget``, dvg's ``QDeviceIO`` worker wrapper)
_QT_BASE = re.compile(r"^Q(?:Object|Thread|Runnable|Timer|Widget|MainWindow|Dialog|Frame|GroupBox|DockWidget|"
                      r"GraphicsView|GraphicsObject|GraphicsWidget|Abstract\w+Model|DeviceIO)$")
#: class names of front ends that build the device class as a member (never the facade the card prefers)
_FRONT_END_NAME = re.compile(r"(?:Server|Service|App|Application|Node|Bridge|Proxy|Plugin|Ui|Tool|Cli|Shell)$")
#: class names of transport and protocol layers below the device class
_TRANSPORT_NAME = re.compile(r"(?:Interface|Transport|Port|Connection|Adapter|Protocol|Socket|Bus|Link|Cmd\w*|"
                             r"Comm|Communication|Serial|Tcp|Udp|Uart)$")


def _symbol_ok(symbol: Any, file: Any, line: Any) -> bool:
    return T.entry_shape(symbol, file, line)


#: class names that name a physical device (the card prefers them as the entry point)
_DEVICE_NOUN = re.compile(
    r"(?:Robot|Arm|Camera|Stage|Motor|Pump|Laser|Gripper|Spectrometer|Spectrophotometer|Oscilloscope|Multimeter|"
    r"PowerSupply|Lockin|LockIn|Picomotor|Actuator|Shutter|FilterWheel|Thermostat|Hotplate|Stirrer|Syringe|"
    r"Detector|Positioner|Chiller|Circulator|Balance|Microscope|Goniometer|Monochromator|Potentiostat|Centrifuge|"
    r"Incubator|Shaker|Drone|Rover|Hand|Bath|Lidar)$")
#: names of constant tables and value types, rarely the entry point
_TABLE_NAME = re.compile(r"(?:Types|Markers|Names|Events|Codes|Constants|Durations|Kinds|Ids|Flags|Modes|Sides|"
                         r"Errors|Units|Keys|Values)$")
_VALUE_NAME = re.compile(r"^(?:Matrix|Vector|Vec|Quaternion|Quat|Point|Transform|Pose2D|Color|Rect)\d*[A-Za-z]?$")
#: modules of helpers and value types
_UTIL_STEMS = {"util", "utils", "helpers", "helper", "common", "math", "mathutils", "geometry", "transformations",
               "types", "datatypes", "structs"}
#: transports and base classes of an instrument command map (preferred on scpi and serial cards)
_COMMAND_MAP_TRANSPORTS = {"pyvisa", "visa", "serial", "pyserial", "serialio", "vxi11", "usbtmc", "pymeasure"}
_COMMAND_MAP_BASES = {"messagebaseddriver", "messagebased", "instrument", "scpiinstrument", "visainstrument",
                      "serialdevice", "serialinstrument"}


def ranked_classes(facts: T.RepoFacts, family: str | None = None) -> list[dict[str, Any]]:
    """AST device classes re-ranked for a card: exported public device classes first.

    Up: classes the README constructs (+3), re-exported classes (+2), class
    names that name a device (+4), facades that build another ranked class as
    a member (+3) and, on scpi and serial cards, classes that use a VISA or
    serial transport or an instrument base class (+3).  Down: transport and
    protocol layers (by class name, directory or module, -4 each), server,
    GUI, viewer, RPC and CLI front ends (-4, and -4 more when a core class
    outside those directories has the same name), optional, contributed or demo
    code beside the package (-3), a lab framework's plugins around the device
    wrapper (PyMoDAQ ``daq_move_plugins``, -4), vendored reinforcement-learning
    libraries (-4), Qt objects, threads and widgets (a Qt base class, -4),
    feature components (-3), member objects of a facade (-2),
    simulators, mocks and dummies of the device (by class or module name,
    -5; :func:`entry_symbols` lists them only when nothing else is ranked),
    base classes of other ranked classes (-4, unless only mocks subclass
    them), constant tables
    (attributes only -6, an enum base -8, a table-like name -4), value types
    and helper modules (-4) and generated serialisation code (-6).  Code that
    runs on a microcontroller (MicroPython, CircuitPython), test classes and
    classes of debugging scripts (``debug_*.py``) are never listed, and copies
    of the same class (same name and API) are listed once.
    """
    py = facts.python
    exported = set(py.get("exported_names") or [])
    readme = set((facts.readme or {}).get("code_names") or [])
    items = list(py.get("entry_classes") or []) + list(py.get("entry_more") or [])
    names = {str(cls.get("symbol") or "").rsplit(":", 1)[-1] for cls in items}
    subclassed = {str(b) for cls in items for b in cls.get("bases") or [] if not T.is_mock_class(cls, names)}
    # facades: a class that builds another ranked class as a member (``self._arm = XArm(...)``) wraps it
    composed = {c["class"] for cls in items for c in cls.get("composes") or [] if c.get("class") in names}
    # names of classes outside server, GUI and CLI directories: a same-named class in such a directory (a Tango
    # device server's CryoCon beside the core cryocon.cryocon:CryoCon) is a front end of that device class
    core_names = {str(cls.get("symbol") or "").rsplit(":", 1)[-1] for cls in items
                  if not {p.lower() for p in str(cls.get("file") or "").split("/")[:-1]} & WRAPPER_DIRS}
    scored = []
    for cls in items:
        if not _symbol_ok(cls.get("symbol"), cls.get("file"), cls.get("line")):
            continue
        name = cls["symbol"].rsplit(":", 1)[1]
        bases = {str(b).lower() for b in cls.get("bases") or []}
        methods = list(cls.get("api_methods") or []) + list(cls.get("methods") or [])
        stem = cls["file"].rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
        score = int(cls.get("score", 0))
        if name in readme:
            score += 3      # the README imports or constructs it: the public entry point
        if name in exported:
            score += 2      # re-exported by a package __init__
        if _DEVICE_NOUN.search(name) and methods and name not in composed:
            score += 4      # named after the device it drives (a facade's member object is not the entry)
        if family in ("scpi", "serial") and (set(cls.get("transport") or []) & _COMMAND_MAP_TRANSPORTS
                                             or bases & _COMMAND_MAP_BASES):
            score += 3      # the instrument class of a command map
        if _TRANSPORT_NAME.search(name):
            score -= 4      # a transport or protocol layer, not the device
        if name.endswith("Feature"):
            score -= 3      # a component of a device class
        if name in subclassed:
            score -= 4      # a base class: its device subclasses are the entry points
        if T.is_mock_class(cls, names):
            score -= 5      # a simulator, mock or fake of the device (mock_strategy lists it)
        if any(c.get("class") in names and c.get("class") != name for c in cls.get("composes") or []) \
                and not _FRONT_END_NAME.search(name):
            score += 3      # a facade over other ranked classes: the public entry point
        if name in composed:
            score -= 2      # a member object of a facade
        if not methods:
            score -= 6      # attributes only: a constant table or a component, rarely the entry point
        if any("enum" in b or b in ("flag", "intflag") for b in bases):
            score -= 8      # an enumeration
        if _TABLE_NAME.search(name):
            score -= 4
        if _VALUE_NAME.match(name) or stem in _UTIL_STEMS:
            score -= 4      # a value type or a helper module
        if cls.get("generated"):
            score -= 6      # generated serialisation code (FlatBuffers, protobuf)
        if cls.get("microcontroller"):
            continue        # MicroPython or CircuitPython code runs on the board, never the host-side entry
        if name.startswith("Test") or any("test" in p.lower() for p in cls["file"].split("/")[:-1]):
            continue        # a test case or a test helper
        if stem == "debug" or stem.startswith("debug_"):
            continue        # a debugging script or a debug stand-in (``debug_Alia_qdev.py``, ``debug_gpib.py``)
        dirs = {p.lower() for p in cls["file"].split("/")[:-1]}
        if dirs & WRAPPER_DIRS:
            score -= 4      # a server, GUI or CLI front end around the device
            if name in core_names:
                score -= 4  # ... that shares its name with the core device class it serves
        if dirs & TRANSPORT_DIRS or stem in TRANSPORT_DIRS:
            score -= 4      # the transport layer below the device classes
        if dirs & EXTRA_DIRS:
            score -= 3      # optional, contributed or demo code beside the package
        if dirs & PLUGIN_DIRS:
            score -= 4      # a lab framework's plugin around the device wrapper (PyMoDAQ calls hardware/)
        if dirs & VENDORED_DIRS:
            score -= 4      # a vendored copy of a reinforcement-learning library
        if _qt_class(cls):
            score -= 4      # a Qt object, thread or widget around the device class (its signals are not device API)
        scored.append((score, cls))
    scored.sort(key=lambda sc: (-sc[0], -int(sc[1].get("api", 0)), sc[1]["file"], sc[1]["line"]))
    out, seen, copies = [], set(), set()
    for score, cls in scored:
        name = cls["symbol"].rsplit(":", 1)[1]
        copy_key = (name, tuple(cls.get("methods") or []), tuple(cls.get("members") or []))
        if cls["symbol"] in seen or copy_key in copies:
            continue
        seen.add(cls["symbol"])
        copies.add(copy_key)
        out.append(dict(cls, card_score=score, mock=T.is_mock_class(cls, names)))
    return out


def gym_entries(facts: T.RepoFacts) -> list[dict[str, Any]]:
    """The package's gym/gymnasium registrations whose entry point is a ``module:Class`` symbol, located
    classes first (registrations in examples, tests and docs are not scanned as entries)."""
    out, seen = [], set()
    for reg in facts.python.get("gym_entries") or []:
        entry = reg.get("entry_point")
        if not isinstance(entry, str) or not _SYMBOL.match(entry):
            continue
        if entry in seen:
            continue
        seen.add(entry)
        out.append(reg)
    # located classes first, template and example envs last (stable: registration order within each group)
    out.sort(key=lambda reg: (not reg.get("class_file"), _is_template(reg)))
    return out


def _is_template(reg: Mapping[str, Any]) -> bool:
    return bool(_TEMPLATE_ENV.search(str(reg.get("file") or "").rsplit("/", 1)[-1])
                or _TEMPLATE_ENV.search(str(reg.get("entry_point") or "")))


def registrations(facts: T.RepoFacts) -> list[dict[str, Any]]:
    """Every registration of the package (for hints), starter templates last."""
    return sorted(facts.python.get("gym_entries") or [], key=_is_template)


#: registrations of a starter template (ManiSkill's ``envs/template.py`` ``CustomEnv``), not an environment
_TEMPLATE_ENV = re.compile(r"(?:^|[_.:])(?:minimal_)?templates?(?:[_.]|$)|:Custom\w*Env$|:Template\w*$", re.IGNORECASE)


def entry_symbols(facts: T.RepoFacts, decision: T.Decision) -> list[dict[str, Any]]:
    """Typed entry symbols from the AST scan (never README lines or package markers).

    A registration whose class the scan located in the clone is ``ast`` with
    the class's file and line; one whose class is not defined in the clone
    (``module_in_repo`` false, an engine's generic env class) or was not found
    is ``recon`` with the registration's file and line.  An override's
    ``entry_symbols`` (a recon proposal a maintainer accepted) replace the
    scan's and are ``override``.
    """
    out: list[dict[str, Any]] = []
    if decision.entry_symbols:
        # a maintainer confirmed these in the clone (a checked recon proposal): they replace the scan's guesses
        return [{"symbol": s["symbol"], "file": s["file"], "line": int(s["line"]), "confidence": "override"}
                for s in decision.entry_symbols[:MAX_ENTRY_SYMBOLS]]
    if facts.scan is None:
        return out
    simulator = decision.family in ("gymnasium", "mujoco") or decision.role == "sim-env"
    if simulator or facts.python.get("gym_entries"):
        for reg in gym_entries(facts):
            located = bool(reg.get("class_file") and reg.get("class_line"))
            file, line = (reg["class_file"], reg["class_line"]) if located else (reg["file"], reg["line"])
            if _symbol_ok(reg["entry_point"], file, line) and all(e["symbol"] != reg["entry_point"] for e in out):
                out.append({"symbol": reg["entry_point"], "file": file, "line": int(line),
                            "confidence": "ast" if located else "recon"})
            if len(out) >= MAX_ENTRY_SYMBOLS:
                return out
        if not out and simulator and decision.role == "sim-env":
            # no usable registration: the package's environment classes (a robosuite or LIBERO env API,
            # a MujocoEnv subclass) are the entry; a twin candidate's entry is its model (``models``)
            for env in facts.python.get("env_entries") or []:
                if _symbol_ok(env.get("symbol"), env.get("file"), env.get("line")):
                    out.append({"symbol": env["symbol"], "file": env["file"], "line": int(env["line"]),
                                "confidence": "ast"})
                if len(out) >= MAX_ENTRY_SYMBOLS:
                    break
        if out or simulator:
            # a simulator's entry is an env registration or environment class (or, for MuJoCo, the main
            # model in ``models``); device-style classes of a simulator repo are not its entry
            return out
    ranked = device_classes(facts, decision.family)
    real = [cls for cls in ranked if not cls["mock"]]
    if not real:
        # only simulators or dummies are ranked: the same-named class of the real module comes first
        for cls in ranked:
            twin = cls.get("real_twin") or {}
            if _symbol_ok(twin.get("symbol"), twin.get("file"), twin.get("line")) and \
                    all(e["symbol"] != twin["symbol"] for e in out):
                out.append({"symbol": twin["symbol"], "file": twin["file"], "line": int(twin["line"]),
                            "confidence": "ast"})
    for cls in (real or ranked)[:MAX_ENTRY_SYMBOLS]:
        if len(out) < MAX_ENTRY_SYMBOLS and all(e["symbol"] != cls["symbol"] for e in out):
            out.append({"symbol": cls["symbol"], "file": cls["file"], "line": int(cls["line"]), "confidence": "ast"})
    return out


def device_classes(facts: T.RepoFacts, family: str | None = None) -> list[dict[str, Any]]:
    """:func:`ranked_classes` without GUI front-end classes (widgets, views): those are never a device entry
    nor the source of its hints, even when nothing else is ranked."""
    return [cls for cls in ranked_classes(facts, family)
            if not {p.lower() for p in cls["file"].split("/")[:-1]} & GUI_DIRS]


def sim_models(facts: T.RepoFacts, decision: T.Decision) -> list[dict[str, Any]]:
    """Main MuJoCo models for a simulator card (``source_scan.classify_mjcf``; empty for other cards)."""
    if facts.scan is None or decision.strategy in ("skip", "reference"):
        return []
    if not (decision.family in ("mujoco", "gymnasium") or decision.role in ("sim-env", "twin-candidate")):
        return []
    out = []
    for model in T.mjcf_main(facts)[:MAX_ENTRY_SYMBOLS]:
        if isinstance(model.get("file"), str) and _REL.match(model["file"]) and int(model.get("line") or 0) >= 1:
            out.append(OrderedDict((("file", model["file"]), ("line", int(model["line"])), ("kind", model["kind"]))))
    return out


# ---------------------------------------------------------------------------
# hints and candidate classes
# ---------------------------------------------------------------------------

LIFECYCLE = {"connect", "disconnect", "open", "close", "init", "initialize", "initialise", "shutdown", "reconnect",
             "release_connection", "__enter__", "__exit__", "cleanup", "dispose", "terminate", "quit", "exit",
             "delete_device", "init_device"}
RAW_IO = {"read", "write", "query", "ask", "send", "send_command", "command", "cmd", "write_readline", "readline",
          "read_until", "flush", "write_raw", "read_raw", "query_raw", "read_bytes", "write_bytes", "recv", "send_cmd",
          "read_message", "send_message", "read_response", "parse_response"}
READ_PREFIX = ("get_", "read_", "measure_", "query_", "is_", "has_", "fetch_")
WRITE_PREFIX = ("set_", "write_", "configure_", "config_")
#: the same verbs as the first token of a camelCase or PascalCase name (getStartSpeed, setTemperature, ReadAIN)
READ_FIRST = {"get", "read", "measure", "query", "is", "has", "fetch"}
WRITE_FIRST = {"set", "write", "configure", "config"}
#: tokens of a setter that sets a reference point, not a target (set_zero_position, setHomePosition)
REFERENCE_TOKENS = {"zero", "home", "homing", "origin", "offset", "offsets", "limit", "limits", "reference", "ref"}
#: control_<mode> methods of a motor or joint controller (controlMIT, control_Pos_Vel, control_Vel)
CONTROL_MODES = {"pos", "position", "vel", "velocity", "torque", "mit", "speed", "current"}
STOP_WORDS = {"stop", "halt", "abort", "pause"}


def _tokens(name: str) -> list[str]:
    parts = []
    for chunk in re.split(r"[_\W]+", name):
        parts.extend(re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", chunk))
    return [p.lower() for p in parts if p]


def method_kind(name: str) -> str | None:
    """``read``, ``write``, ``action`` or None (lifecycle, raw I/O and private names)."""
    low = name.lower()
    if low.startswith("_") or low in LIFECYCLE or low in RAW_IO:
        return None
    if low.startswith(READ_PREFIX) or low in ("status", "get_status", "idn", "identify", "identification"):
        return "read"
    if low.startswith(WRITE_PREFIX):
        return "write"
    seq = _tokens(name)
    if len(seq) > 1 and seq[0] in READ_FIRST:
        return "read"
    if len(seq) > 1 and seq[0] in WRITE_FIRST:
        return "write"
    if len(seq) > 1 and seq[0] == "control" and set(seq[1:]) & CONTROL_MODES:
        return "action"
    tokens = set(seq)
    if low in SS_DEVICE_METHODS or tokens & {"move", "mov", "servo", "goto", "jog", "home", "homing", "start", "stop",
                                              "abort", "halt",
                                              "aspirate", "dispense", "transfer", "grasp", "grip", "release", "trigger",
                                              "acquire", "capture", "snap", "calibrate", "focus", "autofocus", "heat",
                                              "cool", "enable", "disable", "arm", "disarm", "takeoff", "land", "run",
                                              "pause", "resume", "reset", "emergency", "estop", "fire", "pump", "spin",
                                              "centrifuge", "incubate", "mix", "wash", "dose", "inject"}:
        return "action"
    return None


try:  # the scan's device verbs, so a card and triage agree on what a device method is
    from source_scan import DEVICE_METHODS as SS_DEVICE_METHODS  # noqa: E402
except ImportError:  # pragma: no cover
    SS_DEVICE_METHODS = set()

MEASURE_NOUNS = (
    (("temperature", "temp", "celsius", "kelvin"), "cap.measure.temperature.v1"),
    (("voltage", "volt", "volts"), "cap.measure.voltage.v1"),
    (("resistance", "ohm", "ohms", "impedance"), "cap.measure.resistance.v1"),
    (("pressure",), "cap.measure.pressure.v1"),
    (("flow", "flowrate"), "cap.measure.flow.v1"),
    (("mass", "weight"), "cap.measure.mass.v1"),
    (("spectrum", "spectra", "spectral", "spectrometer"), "cap.measure.spectrum.v1"),
    (("intensity",), "cap.measure.intensity.v1"),
)


def class_for(name: str, kind: str, track: str, context: set[str]) -> str | None:
    """The stable catalogue class a native name suggests (None when nothing fits).

    ``kind`` is read, write, action or attribute (a class-level descriptor
    whose direction is unknown).  ``context`` is every token of the class's
    API, so a bare ``set_point`` in a temperature controller is a thermal
    setpoint.
    """
    t = _tokens(name)
    ts = set(t)
    if ts & {"emergency", "estop"} or name.lower() in ("e_stop", "estop"):
        return None   # the e-stop is mhs.safety.estop, not a capability
    setpoint = "setpoint" in ts or ("set" in ts and "point" in ts) or ({"target", "working"} & ts and ts & {"temperature", "temp"})
    thermal_ctx = bool(context & {"temperature", "temp", "heater", "heating", "bath", "circulator", "chiller", "thermostat"})
    if kind in ("write", "attribute") and setpoint and (thermal_ctx or ts & {"temperature", "temp"}):
        return "cap.thermal.setpoint.v1"
    if kind == "write" and ts & {"temperature", "temp"}:
        return "cap.thermal.setpoint.v1"
    if kind in ("read", "attribute"):
        for nouns, cap in MEASURE_NOUNS:
            if ts & set(nouns) and not ts & {"limit", "limits", "max", "min", "range", "setpoint", "unit", "units"}:
                return cap
        if t and (t[-1] == "current" or "amps" in ts or "amperage" in ts):
            return "cap.measure.current.v1"
    if kind in ("read", "action") and ts & {"spectrum", "spectra"}:
        return "cap.measure.spectrum.v1"
    if kind == "action" and ts & {"image", "frame", "snap", "capture", "grab", "picture", "photo"}:
        return "cap.sensing.image.v1"
    if kind in ("write", "action"):
        if ts & {"gripper", "grasp", "grip"} and not ts & {"open", "release"}:
            return "cap.manipulation.grasp.v1"
        if ts & {"aspirate"}:
            return "cap.fluid.aspirate.v1"
        if ts & {"dispense"}:
            return "cap.fluid.dispense.v1"
        if ts & {"valve"}:
            return "cap.actuation.valve.v1"
        if ts & {"pump"} and not ts & {"pressure"}:
            return "cap.actuation.pump.v1"
        if ts & {"gpio", "relay", "ttl", "digital"}:
            return "cap.actuation.gpio.v1"
        if ts & {"focus", "autofocus"}:
            return "cap.imaging.focus.v1"
        if ts & {"illumination", "led", "lamp"} and kind == "write":
            return "cap.imaging.illumination.v1"
        if ts & {"centrifuge"}:
            return "cap.sample.centrifuge.v1"
        if ts & {"incubate", "incubation", "incubator"}:
            return "cap.sample.incubate.v1"
        if kind == "action" and t[0] == "control" and ts & CONTROL_MODES:
            # a motor controller's control commands (controlMIT, control_Pos_Vel, control_Vel); a setter that picks
            # a control mode (set_pos_control) is configuration
            if ts & {"pos", "position", "mit"}:
                return "cap.motion.joint_position.v1"
            if ts & {"vel", "velocity", "speed"}:
                return "cap.motion.joint_velocity.v1"
            if ts & {"torque", "current"}:
                return "cap.motion.joint_torque.v1"
        if kind == "write" and ts & REFERENCE_TOKENS:
            # setting a zero, home or offset reference is configuration, not a motion target
            return "cap.device.configure.v1"
        if ts & {"joint", "joints", "servo", "angle", "angles"}:
            return "cap.motion.joint_position.v1"
        if track == "robots" and ts & {"pose", "cartesian", "tcp", "position", "xyz"}:
            return "cap.motion.cartesian_pose.v1"
        if ts & {"move", "mov", "goto", "jog", "position"} and not ts & {"gripper"}:
            return "cap.motion.joint_position.v1"
        if ts & {"calibrate", "calibration"} and kind == "action":
            return "cap.device.calibrate.v1"
        if ts & {"selftest"} or ("self" in ts and "test" in ts):
            return "cap.device.self_test.v1"
    if kind == "write":
        return "cap.device.configure.v1"
    if kind == "read":
        return "cap.sensing.read.v1"
    return None


def _stable(cap: str) -> bool:
    entry = CV.catalog().get(cap)
    return isinstance(entry, dict) and entry.get("status") in ("stable", "active")


def _in_dirs(cls: Mapping[str, Any], dirs: set[str]) -> bool:
    return bool({p.lower() for p in str(cls.get("file") or "").split("/")[:-1]} & dirs)


def _qt_class(cls: Mapping[str, Any]) -> bool:
    return any(_QT_BASE.match(str(b).rsplit(".", 1)[-1]) for b in cls.get("bases") or [])


def device_hints(facts: T.RepoFacts, track: str, classes: Sequence[Mapping[str, Any]]) -> tuple[dict, list[str]]:
    """(hints, candidate classes) from the API of the top entry classes.

    A facade's member objects count as its API (``DobotRobot.motion.MovJ`` for
    ``self.motion = Motion(...)``); simulators, mocks and dummies of the device
    are not read when a real class is ranked, nor are a lab framework's plugins
    (``PLUGIN_DIRS``) and Qt wrappers (a Qt base class) when another class is.
    A server, GUI or CLI front end named after a class already read (a Tango
    device server's ``CryoCon`` beside the core ``cryocon.cryocon:CryoCon``)
    is skipped: its members are the server's attributes, not the device's.
    """
    reads: list[str] = []
    writes: list[str] = []
    actions: list[str] = []
    caps: Counter[str] = Counter()
    motion = False
    stops = False
    real = [cls for cls in classes if not cls.get("mock")]
    # a framework plugin's API (PyMoDAQ ``move_Abs`` on a spectrometer or a DAQ card) and a Qt wrapper's signals are
    # not the device's when the device class they call is ranked
    real = [cls for cls in real if not (_in_dirs(cls, PLUGIN_DIRS) or _qt_class(cls))] or real
    hinted: set[str] = set()
    for cls in (real or list(classes))[:3]:
        cname = cls["symbol"].rsplit(":", 1)[1]
        if cname in hinted and _in_dirs(cls, WRAPPER_DIRS):
            continue    # a server front end named after a class already read (a Tango server's CryoCon)
        hinted.add(cname)
        own = sorted(set(cls.get("api_methods") or []) | set(cls.get("methods") or []))
        # a member object's API the facade does not already expose itself, public members first
        extra = sorted((m for m in cls.get("composed_methods") or [] if m.rsplit(".", 1)[-1] not in set(own)),
                       key=lambda m: (m.startswith("_"), m))
        methods = own + extra
        members = list(cls.get("members") or [])
        context = {tok for n in methods + members for tok in _tokens(n)}
        for qualified in methods:
            name = qualified.rsplit(".", 1)[-1]
            kind = method_kind(name)
            if kind is None:
                continue
            label = f"{cname}.{qualified}"
            target = {"read": reads, "write": writes, "action": actions}[kind]
            if label not in target:
                target.append(label)
            if set(_tokens(name)) & STOP_WORDS:
                stops = True
            cap = class_for(name, kind, track, context)
            if cap:
                caps[cap] += 1
                motion = motion or cap.startswith("cap.motion.")
        for name in members:
            label = f"{cname}.{name} (attribute)"
            if label not in reads:
                reads.append(label)
            cap = class_for(name, "attribute", track, context)
            if cap:
                caps[cap] += 1
    if motion and stops:
        caps["cap.motion.stop.v1"] += 1
    ordered = [cap for cap, _n in sorted(caps.items(), key=lambda kv: (-kv[1], kv[0])) if _stable(cap)]
    hints = {"reads": reads[:MAX_HINTS], "writes": writes[:MAX_HINTS], "actions": actions[:MAX_HINTS],
             "candidate_classes": ordered[:MAX_CLASSES]}
    return hints, hints["candidate_classes"]


SIM_CLASSES = ["cap.world.reset.v1", "cap.world.step.v1", "cap.world.seed.v1"]
MUJOCO_CLASSES = ["cap.world.reset.v1", "cap.world.step.v1"]


def _gym_hint(reg: Mapping[str, Any]) -> str:
    template = " (id template, built at run time)" if reg.get("template") else ""
    return f"gym env {reg['id']}{template} registered at {reg['file']}:{reg['line']}"


def sim_hints(facts: T.RepoFacts, family: str | None) -> tuple[dict, list[str]]:
    """Hints for a simulator card: the package's env registrations or main MJCF models, and the world classes
    the helper serves."""
    actions: list[str] = []
    for reg in registrations(facts)[:MAX_HINTS]:
        actions.append(_gym_hint(reg))
    if not actions:
        for model in T.mjcf_main(facts)[:MAX_HINTS]:
            actions.append(f"MJCF {model['kind']} model {model['file']}:{model['line']}")
    caps = MUJOCO_CLASSES if family == "mujoco" else SIM_CLASSES
    return {"reads": [], "writes": [], "actions": actions[:MAX_HINTS], "candidate_classes": list(caps)}, list(caps)


#: limit-like constants that are really error codes, counters, protocol sizes, network settings or
#: training and evaluation settings (gradient clipping, epochs, rewards, episodes)
_NOT_A_LIMIT = re.compile(r"ERR|CODE|(?:^|_)ID(?:_|$)|NUM|LEN|COUNT|SIZE|RETR|TIMEOUT|LEVEL|VERSION|INDEX|IDX|BUF|"
                          r"BYTES|PORT|BAUD|ADDR|TRANSACTION|CHANNELS|TRACES|LOG|(?:^|_)GRAD|EPOCH|REWARD|REDIRECT|"
                          r"SOCKET|EPISODE|BATCH|LEARNING|(?:^|_)LR(?:_|$)|LOSS|(?:^|_)ITER|SEED|WORKERS|THREADS|"
                          r"CONNECTIONS|CACHE|QUEUE|HISTORY|PROMOTION|SHORTFALL|SCORE|(?:^|_)NORM(?:_|$)|TRIES|ATTEMPTS",
                          re.IGNORECASE)


#: modules that hold error and status codes, not limits
_CODE_MODULE = re.compile(r"(?:^|_)(?:codes?|errors?|errs?|exceptions?|status|ret|returns?|consts?)$")
#: machine-learning, training and evaluation modules: their bounds are hyperparameters, not device limits
_ML_PATH = re.compile(r"(?:^|/|_)(?:train(?:er|ing)?|learn(?:er|ing)?|rl|ppo|sac|td3|ddpg|dqn|agents?|policy|policies|"
                      r"algos?|algorithms?|networks?|nets?|optim\w*|hyper\w*|evaluat\w*|benchmarks?|"
                      r"experiments?|scripts?|examples?|notebooks?|baselines?)(?:/|_|\.py$|$)", re.IGNORECASE)


def limit_hints(facts: T.RepoFacts) -> list[str]:
    out = []
    for item in (facts.scan or {}).get("limit_hints") or []:
        stem = item["file"].rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
        if (_NOT_A_LIMIT.search(item["name"]) or _CODE_MODULE.search(stem) or _is_test_path(item["file"])
                or _ML_PATH.search(item["file"])):
            continue
        out.append(f"{item['file']}:{item['line']} {item['name']} = {item['value']}"[:300])
        if len(out) >= MAX_LIMIT_HINTS:
            break
    return out


# ---------------------------------------------------------------------------
# install, platform, GPU, mocks
# ---------------------------------------------------------------------------

_PY_SPEC = re.compile(r"^[<>=!~]{1,2}[0-9][0-9.]*(,[<>=!~]{1,2}[0-9][0-9.]*)*$")
GPU_IMPORTS = frozenset({"isaacgym", "isaaclab", "isaacsim", "omni", "omni_isaac", "isaacgymenvs", "warp", "cupy",
                         "pycuda", "tensorrt", "genesis", "brax", "mujoco_warp", "taichi", "nvidia"})
#: COM, .NET and Win32 bindings: the code path that uses them runs on Windows only.  ``msvcrt`` and
#: ``winreg`` are left out: cross-platform code imports them behind a platform check (keyboard
#: polling, registry lookups of a driver path)
WINDOWS_IMPORTS = frozenset({"win32com", "win32api", "win32con", "win32gui", "pywintypes", "pythoncom", "wmi",
                             "comtypes", "clr"})
LINUX_IMPORTS = frozenset({"rclpy", "rospy", "fcntl_linux", "evdev", "spidev", "smbus", "smbus2", "rpi", "gpiozero",
                           "pigpio", "picamera", "picamera2", "libcamera"})
EXTERNAL_ENGINE_IMPORTS = frozenset({"isaacgym", "isaaclab", "isaacsim", "omni", "omni_isaac", "isaacgymenvs",
                                     "mlagents", "mlagents_envs", "unrealcv", "habitat", "habitat_sim", "airsim",
                                     "carla", "omnigibson", "newton", "tdw", "unity_simulator", "virtualhome",
                                     "pyflex", "agx", "agxSDK"})
#: a catalogue runtime requirement that states (not merely mentions) a GPU; the
#: Chinese words are 需要/需/要求/必须 (needs, requires, must) and the negations
#: 无需/不需要/可选/无 (not needed, optional, none)
_GPU_POSITIVE = re.compile(r"(?:需要|需|要求|必须|requires?|required|needs?)\s*(?:an?\s+)?(?:NVIDIA\s*)?(?:GPU|CUDA|RTX)",
                           re.IGNORECASE)
_GPU_NEGATIVE = re.compile(r"无需|不需要|不需|可选|optional|not required|no\s+gpu|无\s*GPU|cpu[- ]only|CPU\s*即可",
                           re.IGNORECASE)


def python_spec(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", "", str(value)).replace(".*", "")
    if re.match(r"^[0-9][0-9.]*$", text):
        text = ">=" + text
    return text if _PY_SPEC.match(text) and len(text) <= 40 else None


#: package imports that need software pip does not install (``install.system_deps``)
SYSTEM_DEP_IMPORTS = (
    ("mujoco_py", "MuJoCo 2.1 binaries and a C compiler for mujoco-py"),
)


def install_block(facts: T.RepoFacts, gpu: bool, platform: str) -> dict[str, Any]:
    scan = facts.scan or {}
    root = set((scan.get("markers") or {}).get("root_build_files") or [])
    inst = scan.get("install") or {}
    commands: list[str] = []
    ros = inst.get("ros_build") or {}
    status = ros.get("status")
    if ros:
        # The three ROS-sensitive root files come from the selected pin; a
        # modified/untracked checkout must not override that install decision.
        root = (set(root) - {"setup.py", "package.xml", "CMakeLists.txt"}) | set(ros.get("root_files") or [])
    if status == "catkin":
        commands.append("catkin_make")
    elif status == "ament":
        commands.append("colcon build")
    elif status in ("ambiguous", "unknown", "unavailable") or "package.xml" in root:
        pass  # No guessed ROS/Python build: the empty recipe retains install recon.
    elif "setup.py" in root or ("pyproject.toml" in root and inst.get("pyproject_buildable", True)):
        commands.append("pip install .")
    elif "requirements.txt" in root:
        commands.append("pip install -r requirements.txt")
    python = python_spec(inst.get("python_requires"))
    core = facts.python.get("imports_core")
    imports = frozenset(core) if core is not None else facts.imports
    system_deps = [text for module, text in SYSTEM_DEP_IMPORTS if module in imports]
    if status == "catkin":
        system_deps.append("Catkin workspace with this package in src; run catkin_make from the workspace root")
    elif status == "ament":
        system_deps.append("ament/colcon workspace and the ROS dependencies declared in package.xml")
    elif status in ("ambiguous", "unknown", "unavailable") or "package.xml" in root:
        system_deps.append("Resolve the root ROS build tooling from pinned package.xml/CMakeLists.txt before installation")
    return {"python": python, "commands": commands, "system_deps": system_deps, "gpu": gpu, "platform": platform}


def needs_gpu(facts: T.RepoFacts, catalog_runtime: str) -> bool:
    """A GPU-only import in package code outside ``try``/``if`` blocks (``source_scan`` ``imports_core``;
    optional CUDA paths and test or benchmark scripts do not count), a README prerequisite that states a GPU
    (``source_scan.readme_gpu_lines``: "requires a GPU", "CUDA GPU", Vulkan), or a catalogue requirement that
    states one."""
    core = facts.python.get("imports_core")
    if (frozenset(core) if core is not None else facts.imports) & GPU_IMPORTS:
        return True
    if facts.readme.get("gpu_required"):
        return True
    text = catalog_runtime or ""
    return bool(_GPU_POSITIVE.search(text)) and not _GPU_NEGATIVE.search(text)


def platform_for(facts: T.RepoFacts, family: str | None) -> str:
    imports = facts.all_imports
    if imports & WINDOWS_IMPORTS and not imports & LINUX_IMPORTS:
        return "windows"
    if family == "ros" or imports & {"rclpy", "rospy"}:
        return "linux"
    return "any"


def _is_test_path(path: str) -> bool:
    return any(part in ("test", "tests", "testing") for part in path.split("/")[:-1]) or \
        path.rsplit("/", 1)[-1].startswith("test_")


#: directories whose simulations are GUI tasks, plots or examples, not a device simulator
_NOT_DEVICE_SIM_DIRS = {"tasks", "task", "gui", "ui", "plots", "plot", "widgets", "examples", "example", "demo", "demos",
                        "docs", "doc", "notebooks", "scripts", "benchmarks"}


def _device_mock(mock: Mapping[str, Any]) -> bool:
    """A simulator, mock or fake of the device itself (pyvisa-sim files count; test and GUI helpers do not)."""
    if mock["kind"] == "pyvisa-sim":
        return True
    parts = {p.lower() for p in mock["file"].split("/")[:-1]}
    return not _is_test_path(mock["file"]) and not parts & _NOT_DEVICE_SIM_DIRS


def mock_block(facts: T.RepoFacts, family: str | None, role: str, omit_sim_contract: bool = False) -> dict[str, Any]:
    scan = facts.scan or {}
    mocks = [m for m in scan.get("mocks") or [] if _REL.match(m.get("file") or "")]
    mocks.sort(key=lambda m: (_is_test_path(m["file"]), {"pyvisa-sim": 0, "class": 1, "module": 2}.get(m["kind"], 3),
                              m["file"].count("/"), m["file"], m["line"]))
    tests = (scan.get("markers") or {}).get("test_dirs") or []
    upstream_tests = tests[0] if tests and _REL.match(tests[0]) else None
    hints = []
    for m in [m for m in mocks if _device_mock(m)][:6]:
        hint = f"{m['file']}:{m['line']}"
        if m.get("symbol"):
            hint += f" {m['symbol'].rsplit(':', 1)[1]}"
        elif m["kind"] == "pyvisa-sim":
            hint += " pyvisa-sim device file"
        hints.append(hint)
    if not omit_sim_contract and (family in ("gymnasium", "mujoco") or role in ("sim-env", "twin-candidate")):
        # the simulator is its own backend: its registrations, main models or environment classes; device
        # mocks and vector-env workers (``DummyVectorEnv``) are not a simulator's fake
        preferred = "upstream-sim"
        hints = [f"{reg['file']}:{reg['line']} gym env {reg['id']}" for reg in registrations(facts)[:4]]
        if not hints:
            # the main model first: the scene or robot a MujocoDriver loads
            hints = [f"{m['file']}:{m['line']} MJCF {m['kind']} model" for m in T.mjcf_main(facts)[:4]]
        if not hints:
            hints = [f"{e['file']}:{e['line']} {e['symbol'].rsplit(':', 1)[1]} environment class"
                     for e in (facts.python.get("env_entries") or [])[:4]]
    elif any(_device_mock(m) for m in mocks):
        preferred = "upstream-sim"
    elif family in ("scpi", "serial"):
        preferred = "transcript"
    else:
        preferred = "fake"
    return {"preferred": preferred, "hints": hints, "upstream_tests": upstream_tests}


# ---------------------------------------------------------------------------
# cards
# ---------------------------------------------------------------------------

def card_relpath(track: str, owner: str, repo: str) -> str:
    """Card path relative to MHS/registry."""
    return f"tasks/{track}/{owner}__{repo}.json"


def card_path_for(card: Mapping[str, Any]) -> str:
    """Card path relative to the repository root."""
    return f"MHS/registry/tasks/{card['track']}/{card['driver_dir'].rsplit('/', 1)[1]}.json"


def driver_dir(track: str, owner: str, repo: str) -> str:
    return f"MHS/drivers/{track}/{owner}__{repo}"


def expected_mode(record: Mapping[str, Any], decision: T.Decision) -> str | None:
    """The mode the driver serves.

    A reviewed ``served_mode`` of ``simulated`` serves the simulated form of a
    dual-mode record and leaves hardware on the record: hardware stays first,
    and ``simulated`` is also present.  Otherwise the driver serves the
    record's first mode (hardware first for dual-mode records).

    A record without modes (tier D or X: not a device) has a mode only when
    its card is a driver or recon task; then the role decides (simulators and
    twins simulated, device roles hardware).  Never-dispatched cards of such
    records (skip, reference, bridge-runtime) have none (null).
    """
    modes = list(record.get("modes") or [])
    if modes:
        if (getattr(decision, "served_mode", None) == "simulated" and modes[0] == "hardware"
                and "simulated" in modes):
            return "simulated"
        return "hardware" if modes[0] in ("hardware", "hybrid") else "simulated"
    if decision.strategy not in T.DISPATCHABLE + ("untriaged",):
        return None
    if decision.family in ("gymnasium", "mujoco") or decision.role in ("sim-env", "twin-candidate"):
        return "simulated"
    if decision.role in T.DEVICE_ROLES:
        return "hardware"
    return None


def recon_first(family: str | None, symbols: Sequence[Mapping[str, Any]], classes: Sequence[str],
                install: Mapping[str, Any]) -> bool:
    """A dispatchable card a driver cannot be written from yet (``blocked_on: recon:entry_symbol``).

    A python-object card needs an entry class: without an entry symbol and
    without candidate classes it goes to recon.  A serial or SCPI command map
    can be written from command scripts, so it goes to recon only when it also
    has no install file.  Other families integrate through their own structure
    (a ROS package, an MJCF model, a framework's configuration) and are never
    routed here.
    """
    if symbols or classes:
        return False
    if family == "python-object":
        return True
    return family in ("serial", "scpi") and not install["commands"]


def skip_reason(decision: T.Decision) -> str | None:
    if decision.strategy != "skip":
        return None
    evidence = [e for e in decision.evidence if not e.startswith("rules alone:")]
    text = evidence[0] if evidence else decision.reason_code
    if decision.variant_of and decision.variant_of not in text:
        text = f"duplicate of {decision.variant_of}: {text}"
    return english(text, 300) or decision.reason_code


def build_card(record: Mapping[str, Any], decision: T.Decision, facts: T.RepoFacts,
               lock: Mapping[str, Any] | None, license_info: Mapping[str, Any],
               overlay_blocked: Iterable[str] = (), catalog_runtime: str = "",
               package_status: str = "none") -> "OrderedDict[str, Any]":
    """One task card (wave and rank are filled in by :func:`assign_waves`).

    ``overlay_blocked`` are the codes of a blocked or skip-proposed
    RESULT.json and ``package_status`` the driver package's state
    (:data:`PACKAGE_STATUSES`).
    """
    track, owner, repo = str(record["local_path"]).split("/")[:3]
    family = decision.family
    dispatchable = decision.strategy in T.DISPATCHABLE
    gpu = needs_gpu(facts, catalog_runtime)
    platform = platform_for(facts, family)
    symbols = entry_symbols(facts, decision) if decision.strategy in T.DISPATCHABLE + ("untriaged", "bridge-runtime") else []
    # omit_sim_contract: a reviewer confirmed the scan's gym, environment or MJCF world is not the served
    # contract. capability_classes cannot say that (it needs 1 to 8 catalogue ids, and it does not drop models).
    models = [] if decision.omit_sim_contract else (
        sim_models(facts, decision) if decision.strategy in T.DISPATCHABLE + ("untriaged",) else [])
    sim_contract = (not decision.omit_sim_contract) and (
        family in ("gymnasium", "mujoco") or (decision.role == "sim-env" and (
            facts.python.get("gym_entries") or T.mjcf_models(facts) or facts.python.get("env_entries"))))
    if decision.strategy in ("skip", "reference", "bridge-runtime"):
        hints, classes = {"reads": [], "writes": [], "actions": [], "candidate_classes": []}, []
    elif sim_contract:
        hints, classes = sim_hints(facts, family)
    else:
        hints, classes = device_hints(facts, track, device_classes(facts, family))
    if decision.capability_classes and dispatchable:
        # a reviewer named the device's classes (an override): they replace the scan's guesses, the floor follows
        classes = reviewed_classes(decision)
        hints = dict(hints, candidate_classes=list(classes))
    mode = expected_mode(record, decision)
    blocked = set(decision.blocked_on) | set(overlay_blocked)
    install = install_block(facts, gpu, platform)
    if dispatchable and recon_first(family, symbols, classes, install):
        blocked.add(RECON_BLOCK)    # nothing to write a driver from: a recon pass names the entry first
    blocked = sorted(blocked)
    lock = lock or {}
    repo_url = lock.get("repo_url") or record.get("repo_url")
    if not isinstance(repo_url, str) or not repo_url.startswith("https://"):
        repo_url = f"https://github.com/{owner}/{repo}"
    needs = []
    if decision.strategy == "untriaged":
        needs.append("decision")
        if decision.role == "sim-env" and mode == "hardware":
            # a simulation repo whose code also drives hardware: the recon decides which mode the driver serves
            needs.append("mode")
    if decision.strategy in T.DISPATCHABLE + ("untriaged",):
        if not symbols and not models:
            needs.append("entry_symbol")
        if family == "mujoco" and not models:
            needs.append("model")       # no loadable scene or robot model: recon names the model first
        if not install["commands"]:
            needs.append("install")
        if dispatchable and not classes:
            needs.append("capabilities")
        if mode == "hardware" and CV.RISK_ORDER.index(CV.risk_floor(classes)) >= 1 and not limit_hints(facts):
            needs.append("limit_sources")
        if license_info["license_class"] == "unknown":
            needs.append("license")
        if (facts.readme or {}).get("artifact_downloads"):
            needs.append("artifacts")   # assets, models or LFS objects the clone does not hold
        if (track == "robots" and mode == "hardware" and decision.role in T.DEVICE_ROLES
                and not decision.capability_classes and not any(c.startswith("cap.motion.") for c in classes)):
            needs.append("motion")      # a robot whose motion API the scan did not find
    timebox = {"direct-driver": 120 if decision.role == "driver-pack" else 90, "family-config": 60,
               "untriaged": 30}.get(decision.strategy, 15)
    card: "OrderedDict[str, Any]" = OrderedDict()
    card["$schema"] = CARD_SCHEMA
    card["card_version"] = CARD_VERSION
    card["package_id"] = record["package_id"]
    card["track"] = track
    card["local_path"] = record["local_path"]
    card["driver_dir"] = driver_dir(track, owner, repo)
    card["upstream"] = OrderedDict((
        ("repo_url", repo_url),
        ("commit", lock.get("commit")),
        ("license_spdx", license_info["license_spdx"]),
        ("license_class", license_info["license_class"]),
    ))
    card["decision"] = decision.strategy
    card["reason_code"] = decision.reason_code
    card["role"] = decision.role
    card["family"] = family
    card["helper"] = decision.helper
    card["helper_status"] = decision.helper_status
    card["blocked_on"] = blocked
    card["quarantine"] = bool(decision.quarantine)
    card["variant_of"] = decision.variant_of
    card["package_status"] = package_status if package_status in PACKAGE_STATUSES else "none"
    card["wave"] = WAVE_NEVER
    card["rank"] = 1
    card["exemplar"] = T.exemplar_for(family, track) if (dispatchable or decision.strategy == "untriaged") else None
    card["entry_symbols"] = symbols
    card["models"] = models
    card["install"] = install
    card["mock_strategy"] = mock_block(facts, family, decision.role, decision.omit_sim_contract)
    card["hints"] = hints
    card["safety"] = OrderedDict((
        ("expected_mode", mode),
        ("risk_floor", CV.risk_floor(classes)),
        # device limits only: a simulator's bounds come from its action and observation spaces
        ("limit_hints", limit_hints(facts) if decision.strategy in T.DISPATCHABLE + ("untriaged",)
         and mode == "hardware" else []),
    ))
    card["needs_recon"] = needs
    card["timebox_min"] = timebox
    card["acceptance"] = f"python3 -m mhs.driver check {card['driver_dir']} --backend fake"
    card["skip_reason"] = skip_reason(decision)
    card["publish_review"] = "required" if (license_info["license_class"] in LIC.REVIEW_CLASSES
                                            or license_info.get("review")
                                            or decision.publish_review == "required") else "not_required"
    return card


def reviewed_classes(decision: T.Decision) -> list[str]:
    """An override's ``capability_classes``: stable catalogue classes only (a typo or a deprecated class fails the
    build instead of reaching a card)."""
    wrong = [cap for cap in decision.capability_classes if not _stable(cap)]
    if wrong:
        raise ValueError(f"{decision.package_id}: override capability_classes {wrong} are not stable catalogue classes")
    return list(decision.capability_classes)[:MAX_CLASSES]


# ---------------------------------------------------------------------------
# waves and ranks
# ---------------------------------------------------------------------------

def dispatch_ready(card: Mapping[str, Any]) -> bool:
    """The card can be a driver task: dispatchable decision, available helper, nothing blocks it, not quarantined.

    This is the handoff kit's dispatch rule; waves and the pilot pool use it, so
    a card keeps its wave once its package passes.
    """
    return (card["decision"] in T.DISPATCHABLE and card["helper_status"] == "available"
            and not card["blocked_on"] and not card["quarantine"])


def dispatchable_now(card: Mapping[str, Any]) -> bool:
    """:func:`dispatch_ready` and the driver package has not passed and proposes no skip (``package_status``
    none or in_progress): the orchestrator dispatches exactly these cards."""
    return dispatch_ready(card) and card.get("package_status", "none") in ("none", "in_progress")


def has_entry(card: Mapping[str, Any]) -> bool:
    """What a driver is written from: a main model (``models``) for a MuJoCo card, which a MujocoDriver
    loads (an environment class alone does not do), an ``ast`` entry symbol otherwise."""
    if card["family"] == "mujoco":
        return bool(card.get("models"))
    return any(s["confidence"] == "ast" for s in card["entry_symbols"])


def strict_ready(card: Mapping[str, Any]) -> bool:
    """Python, a pip install backed by a root file and nothing pip does not install (no ``system_deps``), no
    GPU, licence known, an AST entry symbol (or, for MuJoCo, a main model), candidate classes and no artifact
    download."""
    inst = card["install"]
    return (dispatch_ready(card) and any(c.startswith("pip ") for c in inst["commands"]) and not inst["gpu"]
            and not inst["system_deps"]
            and inst["platform"] != "windows" and card["upstream"]["license_class"] != "unknown"
            and has_entry(card) and bool(card["hints"]["candidate_classes"])
            and "artifacts" not in card["needs_recon"])


def rank_components(card: Mapping[str, Any], partner: bool, stars: int, has_tests: bool) -> dict[str, Any]:
    comp = {
        "partner": int(bool(partner)),
        "hardware_mode": int(card["safety"]["expected_mode"] == "hardware"),
        "helper_available": int(card["helper_status"] == "available"),
        "has_tests": int(bool(has_tests)),
        "stars": int(stars or 0),
        "gpu": int(bool(card["install"]["gpu"])),
        "license_unknown": int(card["upstream"]["license_class"] == "unknown"),
    }
    score = (40 * comp["partner"] + 20 * comp["hardware_mode"] + 10 * comp["helper_available"] + 8 * comp["has_tests"]
             + 5 * math.log10(comp["stars"] + 1) - 15 * comp["gpu"] - 20 * comp["license_unknown"])
    comp["rank_score"] = round(score, 4)
    return comp


def pilot_ready(card: Mapping[str, Any]) -> bool:
    """A card a pilot run can finish: an AST entry symbol (or, for MuJoCo, a main model), candidate classes,
    no system dependency, no artifact download and, for a robot, a motion API."""
    return (has_entry(card) and bool(card["hints"]["candidate_classes"]) and not card["install"]["system_deps"]
            and not {"artifacts", "motion"} & set(card["needs_recon"]))


#: card score the first entry class of a device card needs for the pilot pool
PILOT_MIN_ENTRY_SCORE = 6


def pilot_entry_ok(card: Mapping[str, Any], facts: T.RepoFacts) -> bool:
    """The pilot's first entry class is a usable host-side driver class.

    A device card's first entry symbol needs a card score of at least
    ``PILOT_MIN_ENTRY_SCORE`` and must not reach its device only through
    ctypes (a vendor DLL a fake cannot stand in for at import time).
    Simulator cards need no class check.
    """
    if card["family"] in ("gymnasium", "mujoco") or not card["entry_symbols"]:
        return True
    first = card["entry_symbols"][0]["symbol"]
    for cls in ranked_classes(facts, card["family"]):
        if cls["symbol"] == first:
            transports = set(cls.get("transport") or [])
            return cls["card_score"] >= PILOT_MIN_ENTRY_SCORE and not (transports and transports <= {"ctypes"})
    return False


def pilot_bucket(card: Mapping[str, Any]) -> str | None:
    """The pilot bucket of a dispatchable card (exemplars always; licences that need a review, and cards
    without an entry symbol or candidate classes, never)."""
    if card["wave"] != WAVE_EXEMPLAR and (not dispatch_ready(card) or card["publish_review"] == "required"
                                          or card["wave"] not in (WAVE_STRICT, WAVE_CORE) or not pilot_ready(card)):
        return None
    family = card["family"]
    if family == "python-object":
        return "robot-sdk" if card["track"] == "robots" else "direct-python-instrument"
    if family in ("serial", "scpi"):
        return "serial-scpi"
    if family in ("gymnasium", "mujoco"):
        return "gymnasium-mujoco"
    return None


def base_wave(card: Mapping[str, Any], decision: T.Decision, facts: T.RepoFacts) -> int:
    if decision.wave is not None:
        return int(decision.wave)
    if card["decision"] in ("skip", "reference", "bridge-runtime"):
        return WAVE_NEVER
    if card["decision"] == "untriaged":
        markers = facts.markers
        if (facts.all_imports & EXTERNAL_ENGINE_IMPORTS or markers.get("unity_project") or markers.get("unreal_project")
                or T.gazebo_marker(facts)):
            return WAVE_LAST
        return WAVE_RECON
    if card["blocked_on"] == [RECON_BLOCK]:
        return WAVE_RECON
    if not dispatch_ready(card):
        return WAVE_HELPER
    if card["install"]["gpu"] or card["install"]["platform"] == "windows":
        return WAVE_LAST
    return WAVE_STRICT if strict_ready(card) else WAVE_CORE


def assign_waves(cards: Mapping[str, "OrderedDict[str, Any]"], decisions: Mapping[str, T.Decision],
                 facts: Mapping[str, T.RepoFacts], stars: Mapping[str, int],
                 pilot_size: int = PILOT_SIZE) -> dict[str, Any]:
    """Set ``wave`` and ``rank`` on every card; return the pilot-candidate selection."""
    components = {}
    for pid, card in cards.items():
        f = facts[pid]
        card["wave"] = base_wave(card, decisions[pid], f)
        components[pid] = rank_components(card, bool(decisions[pid].partner), stars.get(pid, 0),
                                          bool(f.markers.get("has_tests")))
    eligible = {pid for pid, card in cards.items()
                if card["wave"] == WAVE_EXEMPLAR or pilot_entry_ok(card, facts[pid])}
    pilot = select_pilot(cards, components, pilot_size, eligible)
    for item in pilot:
        if cards[item["package_id"]]["wave"] != WAVE_EXEMPLAR:
            cards[item["package_id"]]["wave"] = WAVE_PILOT
    by_wave: dict[int, list[str]] = {}
    for pid, card in cards.items():
        by_wave.setdefault(card["wave"], []).append(pid)
    for wave, pids in by_wave.items():
        pids.sort(key=lambda p: (-components[p]["rank_score"], p))
        for rank, pid in enumerate(pids, 1):
            cards[pid]["rank"] = rank
    for item in pilot:
        item["wave"] = cards[item["package_id"]]["wave"]
        item["rank"] = cards[item["package_id"]]["rank"]
    return {"components": components, "pilot": pilot}


def select_pilot(cards: Mapping[str, Mapping[str, Any]], components: Mapping[str, Mapping[str, Any]],
                 size: int = PILOT_SIZE, eligible: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """The ``size`` top-ranked cards within available helpers, an equal share per bucket.

    Every exemplar (wave 0) is kept in its bucket; the rest of each bucket is
    filled by strict-ready cards first, then by rank score, ties by package_id.
    A bucket served by two helpers (SerialDriver and ScpiDriver,
    GymnasiumDriver and MujocoDriver) takes its cards from the two families
    in turn, so the pilot exercises every helper.  ``eligible`` (default:
    every card) is the set :func:`pilot_entry_ok` admits.
    """
    per_bucket = size // len(PILOT_BUCKETS)
    allowed = set(cards) if eligible is None else set(eligible)
    pools: dict[str, list[str]] = {}
    for bucket in PILOT_BUCKETS:
        pool = [pid for pid, card in cards.items() if pid in allowed and pilot_bucket(card) == bucket]
        # simulators first in the simulator bucket: a model of a real robot (twin-candidate) comes after them
        pool.sort(key=lambda p: (cards[p]["wave"] != WAVE_EXEMPLAR, not strict_ready(cards[p]),
                                 bucket == "gymnasium-mujoco" and cards[p]["role"] != "sim-env",
                                 -components[p]["rank_score"], p))
        pools[bucket] = _alternate_families(pool, cards)
    taken = {bucket: min(per_bucket, len(pool)) for bucket, pool in pools.items()}
    # a bucket with too few cards leaves its slots to the others, one at a time in bucket order
    while sum(taken.values()) < size and any(taken[b] < len(pools[b]) for b in pools):
        for bucket in PILOT_BUCKETS:
            if sum(taken.values()) < size and taken[bucket] < len(pools[bucket]):
                taken[bucket] += 1
    chosen: list[dict[str, Any]] = []
    for bucket in PILOT_BUCKETS:
        for pid in pools[bucket][:taken[bucket]]:
            chosen.append({"package_id": pid, "bucket": bucket, "exemplar": cards[pid]["wave"] == WAVE_EXEMPLAR,
                           "strict_ready": strict_ready(cards[pid]), **{k: components[pid][k] for k in (
                               "rank_score", "partner", "hardware_mode", "helper_available", "has_tests", "stars",
                               "gpu", "license_unknown")}})
    return chosen


def _alternate_families(pool: list[str], cards: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Exemplars first, then the families of the pool in turn (each in its pool order; the family that comes
    first in the pool starts)."""
    head = [p for p in pool if cards[p]["wave"] == WAVE_EXEMPLAR]
    by_family: "OrderedDict[str, list[str]]" = OrderedDict()
    for pid in pool:
        if pid not in head:
            by_family.setdefault(str(cards[pid]["family"]), []).append(pid)
    queues = list(by_family.values())
    out = list(head)
    while any(queues):
        for queue in queues:
            if queue:
                out.append(queue.pop(0))
    return out


def pilot_document(pilot: Sequence[Mapping[str, Any]], cards: Mapping[str, Mapping[str, Any]],
                   generated_at: str) -> "OrderedDict[str, Any]":
    doc: "OrderedDict[str, Any]" = OrderedDict()
    doc["pilot_candidates_version"] = CARD_VERSION
    doc["generated_by"] = "MHS/registry/taskcards.py (via build_registry.py)"
    doc["generated_at"] = generated_at
    doc["description"] = ("The top-ranked task cards within the available pilot helpers (python-object, serial, "
                          "scpi, gymnasium, mujoco), an equal share per bucket, for MHS/handoff/pilot-20.json "
                          "(WP-11). Exemplars (wave 0) are listed in their bucket and are not pilot repos; every other "
                          "candidate is wave 1. Within a bucket strict-ready cards come first, then the rank score; a "
                          "bucket served by two helpers takes its cards from the two families in turn.")
    doc["rank_formula"] = RANK_FORMULA
    share = len(pilot) // len(PILOT_BUCKETS)
    doc["buckets"] = OrderedDict()
    for name, text in PILOT_BUCKETS.items():
        count = sum(1 for p in pilot if p["bucket"] == name)
        exemplars = sum(1 for p in pilot if p["bucket"] == name and p["exemplar"])
        bucket: "OrderedDict[str, Any]" = OrderedDict((("description", text), ("count", count)))
        if count < share:
            # select_pilot fills every bucket to its share first, so a short bucket has used every eligible card
            bucket["shortfall"] = (f"{share - count} of {share} slots unfilled: only {count} card(s), {exemplars} of "
                                   f"them exemplar(s), pass the pilot checks (dispatch-ready, no licence review, an "
                                   f"AST entry symbol or MuJoCo model, candidate classes, no system dependency or "
                                   f"asset download, a motion API for a robot); the other buckets took the slots")
        doc["buckets"][name] = bucket
    doc["count"] = len(pilot)
    doc["candidates"] = [OrderedDict((("bucket", p["bucket"]), ("package_id", p["package_id"]),
                                      ("exemplar", p["exemplar"]), ("strict_ready", p["strict_ready"]),
                                      ("wave", p["wave"]), ("rank", p["rank"]),
                                      ("rank_score", p["rank_score"]),
                                      ("components", OrderedDict((k, p[k]) for k in (
                                          "partner", "hardware_mode", "helper_available", "has_tests", "stars", "gpu",
                                          "license_unknown"))),
                                      ("card", card_path_for(cards[p["package_id"]])),
                                      ("task", cards[p["package_id"]])))
                         for p in pilot]
    return doc


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------

def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def write_cards(cards: Mapping[str, Mapping[str, Any]], out_dir: str = TASKS_DIR) -> int:
    """Write every card; remove card files of records that no longer exist (only under tasks/<track>/)."""
    wanted = set()
    for card in cards.values():
        owner_repo = card["driver_dir"].rsplit("/", 1)[1]
        path = os.path.join(out_dir, card["track"], owner_repo + ".json")
        wanted.add(os.path.abspath(path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = dumps(card)
        try:
            with open(path, encoding="utf-8") as fh:
                if fh.read() == text:
                    continue
        except OSError:
            pass
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    for track in TRACKS:
        for path in glob.glob(os.path.join(out_dir, track, "*.json")):
            if os.path.abspath(path) not in wanted:
                os.remove(path)
    return len(cards)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(obj))


def load_cards(out_dir: str = TASKS_DIR) -> dict[str, dict[str, Any]]:
    out = {}
    for track in TRACKS:
        for path in sorted(glob.glob(os.path.join(out_dir, track, "*.json"))):
            with open(path, encoding="utf-8") as fh:
                card = json.load(fh)
            out[card["package_id"]] = card
    return out


def summarize(cards: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cs = list(cards.values())
    return {
        "total": len(cs),
        "by_decision": dict(sorted(Counter(c["decision"] for c in cs).items())),
        "by_wave": dict(sorted(Counter(str(c["wave"]) for c in cs).items())),
        "dispatchable_now": sum(1 for c in cs if dispatchable_now(c)),
        "strict_ready": sum(1 for c in cs if strict_ready(c)),
        "publish_review_required": sum(1 for c in cs if c["publish_review"] == "required"),
        "with_entry_symbols": sum(1 for c in cs if c["entry_symbols"]),
        "with_ast_entry": sum(1 for c in cs if any(e["confidence"] == "ast" for e in c["entry_symbols"])),
        "recon_blocked": sum(1 for c in cs if RECON_BLOCK in c["blocked_on"]),
        "by_package_status": dict(sorted(Counter(c.get("package_status", "none") for c in cs).items())),
        "with_install": sum(1 for c in cs if c["install"]["commands"]),
        "by_risk_floor": dict(sorted(Counter(c["safety"]["risk_floor"] for c in cs).items())),
        "by_mock": dict(sorted(Counter(c["mock_strategy"]["preferred"] for c in cs).items())),
    }


def main(argv: list[str] | None = None) -> int:
    """Regenerate the records and cards (the build_registry.py pipeline without recipes and docs)."""
    import argparse

    parser = argparse.ArgumentParser(description="Regenerate MHS/registry/tasks/** (and the records they come from)")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--cache", default=os.environ.get("MHS_TRIAGE_CACHE"))
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a committed file differs")
    args = parser.parse_args(argv)
    import build_registry as BR  # noqa: E402  (full pipeline; needs the corpus)

    return BR.main(["--records-only", "--jobs", str(args.jobs)] + (["--check"] if args.check else [])
                   + (["--cache", args.cache] if args.cache else []))


if __name__ == "__main__":
    sys.exit(main())
