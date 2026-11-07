#!/usr/bin/env python3
"""Deterministic triage of every corpus repo into an integration strategy.

Each repo gets exactly one :class:`Decision`: ``strategy`` (the card's
``decision``), ``role``, ``reason_code``, ``quarantine``, ``variant_of`` and,
for integrable repos, the integration ``family`` and its ``helper``.  The rules
are the eleven ordered rules of the handoff kit; the first rule whose predicate
holds decides.  Curated overrides (``MHS/registry/overrides/*.json``) win over
every rule.

 1. tier X or empty clone                                -> skip:empty
 2. no source code (nor model files), an analyst docs-only or
    no-source flag the scan confirms, curated list, course
    or tutorial                                          -> skip:not-device
 3. download lure or binary-only installer               -> skip:quarantine (+ quarantine)
 4. prior-art MHS implementation                         -> reference:prior-art
 5. fork or duplicate of another corpus repo             -> skip:duplicate_of (+ variant_of)
 6. protocol stack, framework or engine a helper builds on -> bridge-runtime:<family|engine>
 7. orchestrator, host, MCP wrapper of a covered backend -> reference:host
    GUI, plotting or other tooling                       -> skip:tooling
 8. tier D (peripheral, not a device)                    -> skip:peripheral
    (a catalogue software row counts as tier D only when neither device evidence, a driver
    directory such as ``hal/`` or ``drivers/`` nor a device-named class shows in the code)
 9. family with a helper plus a structural marker        -> family:<family> (family-config)
    (gym envs that need an external simulator, including Gazebo, CoppeliaSim and Webots scenes,
    have no helper and fall through; registrations and MJCF files in examples, tests, docs and
    vendored copies are no marker; the MuJoCo marker is a loadable scene or robot model with
    actuators, never object or fixture assets alone; a GUI application without a device class
    takes no protocol family)
10. Python code with an AST-parsed device entry class    -> PY_SDK_WITH_ENTRY (direct-driver)
    (score >= 9 with three API members, or the transport-using class of a catalogue
    device SDK with score >= 4 and two API members; simulators, mocks and dummies of the
    device are never the entry class)
11. everything else                                      -> untriaged:<why> (recon-only card)

Device evidence (rules 8 to 10 and the inferred role) needs a class that
uses a hardware transport (serial, VISA, USB, fieldbus, a vendor SDK) when the
catalogue calls the repo a model or a simulation (measurement model, task
environment, direct simulation backend, digital twin): catalogue device
wording, a device-SDK name or a ctypes import alone never turns a simulator,
emulator or benchmark into a hardware driver.

``quarantine`` is the rule-3 predicate evaluated for *every* repo, so a lure
that an earlier rule already skips (for example a README-only lure, rule 2) is
still quarantined.  Simulator families only come from structural markers in
the code (an engine import, ``package.xml``, MJCF models, ``gym`` env
registrations); names and README words never select a family.

Inputs (all read-only): the committed registry records
(``MHS/registry/repos/**``), ``work/analysis/repo_profiles.jsonl`` (analyst
flags and the catalogue row), the catalogue CSV (fork and mirror notes),
``MHS/registry/corpus.lock.jsonl`` (git remote and HEAD read by
``corpus_lock.py``; ``clone_audit_2026-10-12/baseline.jsonl`` is the fallback
and the audit cross-check), and a bounded AST/file-tree scan of each clone
(``source_scan.py``).  No upstream code is imported or executed.

Run:  python3 MHS/registry/triage.py [--jobs 8] [--cache DIR] [--out FILE.jsonl]
      prints the distribution of decisions per strategy, role, rule and family.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WORKSPACE, "MHS", "sdk", "src"))

from mhs.driver.source_selector import entry_shape  # noqa: E402 (stdlib-only source metadata)

import source_scan as SS  # noqa: E402  (same-directory module; stdlib only)

TRIAGE_VERSION = "0.9.4"
REPOS_DIR = os.path.join(HERE, "repos")
OVERRIDES_DIR = os.path.join(HERE, "overrides")
LOCK_PATH = os.path.join(HERE, "corpus.lock.jsonl")
CATALOG_CSV = os.path.join(WORKSPACE, "openai4s_backend_catalog_all_sources", "openai4s_backend_catalog.csv")
CLONE_AUDIT = os.path.join(WORKSPACE, "clone_audit_2026-10-12", "baseline.jsonl")

STRATEGIES = ("direct-driver", "family-config", "bridge-runtime", "reference", "skip", "untriaged")
ROLES = ("device-driver", "driver-pack", "sim-env", "twin-candidate", "framework", "transport",
         "tooling", "host", "prior-art", "docs", "not-device")
DISPATCHABLE = ("direct-driver", "family-config")


# ---------------------------------------------------------------------------
# integration families and helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Family:
    """An integration family: the SDK helper a family-config subclasses."""

    name: str
    helper: str | None          # Driver helper class, None until the helper exists
    prerequisite: str | None    # blocked_on entry while the helper is missing
    exemplar: str | None        # driver package to copy structurally


#: Pilot helpers are available (plan 3.12); every post-pilot helper is a
#: ``helper:<name>`` prerequisite that clears when the helper lands.
FAMILIES: "OrderedDict[str, Family]" = OrderedDict((f.name, f) for f in (
    Family("python-object", "PythonObjectDriver", None, "MHS/drivers/labs/tiagocoutinho__julabo"),
    Family("serial", "SerialDriver", None, "MHS/drivers/labs/thinksrs__srsinst.sr860"),
    Family("scpi", "ScpiDriver", None, "MHS/drivers/labs/thinksrs__srsinst.sr860"),
    Family("gymnasium", "GymnasiumDriver", None, "MHS/drivers/robots/farama-foundation__gymnasium"),
    Family("mujoco", "MujocoDriver", None, "MHS/drivers/robots/farama-foundation__gymnasium"),
    Family("ros", "RosDriver", None, "MHS/drivers/robots/avidbots__flatland"),
    Family("http", None, "helper:http", None),
    Family("pylabrobot", "PyLabRobotDriver", None, "MHS/drivers/labs/oelemento__star-sim"),  # PyLabRobot helper (plr-liquid-handler-v1)
    # w1-waiting-routing (2026-11-05): Sila2Driver with the sila-testing Phenix exemplar (one pinned source profile).
    Family("sila2", "Sila2Driver", None, "MHS/drivers/labs/anguyen-23__sila-testing"),
    # --- exemplars-pyobj (2026-11-04): QCoDeS and Ophyd helpers with their exemplar packages ---
    Family("qcodes", "QcodesDriver", None, "MHS/drivers/labs/qcodes__qcodes_contrib_drivers"),
    Family("ophyd", "OphydDriver", None, "MHS/drivers/labs/bcda-aps__apstools"),
    # --- end exemplars-pyobj ---
    Family("pymmcore-plus", None, "helper:pymmcore-plus", None),
    Family("lerobot", None, "helper:lerobot", None),
    Family("mavlink", None, "helper:mavlink", None),
    Family("tag-bridge", "TagDriver", None, "MHS/drivers/labs/josuablejeru__labmastro"),  # tag-bridge helper (2026-11-04)
    # exemplars-service (2026-11-04): McpClientDriver with the Rigol DHO MCP exemplar.
    Family("mcp-client", "McpClientDriver", None, "MHS/drivers/labs/mattjax16__rigol-dho-mcp"),
))
#: SerialDriver command maps copy the ScpiDriver command-map exemplar (sr860); the
#: MuJoCo helper has no exemplar of its own yet and copies the Gymnasium one.
#: Robot SDK direct drivers copy the xArm exemplar (per-joint arrays, return codes).
ROBOT_SDK_EXEMPLAR = "MHS/drivers/robots/xarm-developer__xarm-python-sdk"


def exemplar_for(family: str | None, track: str | None) -> str | None:
    """Exemplar driver package for a family (robot-track direct drivers use xArm)."""
    if family == "python-object" and track == "robots":
        return ROBOT_SDK_EXEMPLAR
    fam = FAMILIES.get(family or "")
    return fam.exemplar if fam else None


# ---------------------------------------------------------------------------
# rule data
# ---------------------------------------------------------------------------

#: Rule 6: protocol stacks, frameworks and engines that a helper or bridge builds
#: on (only repos present in the corpus).  They become SDK bridge tasks, never
#: repo tasks.  package_id -> (family or None for an engine without a helper, role).
BRIDGE_RUNTIME: dict[str, tuple[str | None, str]] = {
    # VISA / SCPI transports
    "gh.pyvisa/pyvisa": ("scpi", "transport"),
    "gh.pyvisa/pyvisa-py": ("scpi", "transport"),
    "gh.pyvisa/pyvisa-sim": ("scpi", "transport"),
    "gh.python-ivi/python-vxi11": ("scpi", "transport"),
    "gh.python-ivi/python-usbtmc": ("scpi", "transport"),
    "gh.microsoft/pyvisa-mock": ("scpi", "transport"),
    # Modbus, OPC UA, EPICS, Tango, ASCOM Alpaca (tag bridge transports)
    "gh.pymodbus-dev/pymodbus": ("tag-bridge", "transport"),
    "gh.sourceperl/pymodbustcp": ("tag-bridge", "transport"),
    "gh.freeopcua/opcua-asyncio": ("tag-bridge", "transport"),
    "gh.freeopcua/python-opcua": ("tag-bridge", "transport"),
    "gh.node-opcua/node-opcua": ("tag-bridge", "transport"),
    "gh.opcfoundation/ua-.netstandard": ("tag-bridge", "transport"),
    "gh.caproto/caproto": ("tag-bridge", "transport"),
    "gh.pyepics/pyepics": ("tag-bridge", "transport"),
    "gh.epics-base/epics-base": ("tag-bridge", "transport"),
    "gh.tango-controls/pytango": ("tag-bridge", "transport"),
    "gh.ascominitiative/alpyca": ("tag-bridge", "transport"),
    # ROS / DDS / rosbridge
    "gh.ros2/rclpy": ("ros", "transport"),
    "gh.ros2/rclcpp": ("ros", "transport"),
    "gh.ros2/ros2": ("ros", "framework"),
    "gh.ros2/rosidl_dds": ("ros", "transport"),
    "gh.eprosima/fast-dds": ("ros", "transport"),
    "gh.eclipse-cyclonedds/cyclonedds": ("ros", "transport"),
    "gh.eclipse-zenoh/zenoh-plugin-ros2dds": ("ros", "transport"),
    "gh.robotwebtools/rosbridge_suite": ("ros", "transport"),
    "gh.robotwebtools/roslibpy": ("ros", "transport"),
    "gh.robotwebtools/rclnodejs": ("ros", "transport"),
    "gh.roslibrust/roslibrust": ("ros", "transport"),
    "gh.micro-ros/micro-ros-agent": ("ros", "transport"),
    "gh.ros-controls/ros2_control": ("ros", "framework"),
    "gh.ros-controls/ros2_controllers": ("ros", "framework"),
    "gh.ros-controls/gazebo_ros2_control": ("ros", "framework"),
    "gh.ros-controls/gz_ros2_control": ("ros", "framework"),
    "gh.ros-controls/mujoco_ros2_control": ("ros", "framework"),
    "gh.ros-simulation/gazebo_ros_pkgs": ("ros", "framework"),
    "gh.ros2/rcl": ("ros", "transport"),
    "gh.ros2/rclc": ("ros", "transport"),
    "gh.ros2/rcl_interfaces": ("ros", "transport"),
    "gh.ros2/common_interfaces": ("ros", "transport"),
    "gh.ros2/rosidl": ("ros", "transport"),
    "gh.ros2/rmw": ("ros", "transport"),
    "gh.ros2/rmw_connext": ("ros", "transport"),
    "gh.ros2/rmw_dps": ("ros", "transport"),
    "gh.ros2/rmw_fastrtps": ("ros", "transport"),
    "gh.ros2/rmw_freertps": ("ros", "transport"),
    "gh.ros2/rmw_iceoryx": ("ros", "transport"),
    "gh.ros2/rmw_implementation": ("ros", "transport"),
    "gh.ros2/rmw_opensplice": ("ros", "transport"),
    "gh.ros2/freertps": ("ros", "transport"),
    "gh.gazebosim/ros_gz": ("ros", "transport"),
    "gh.robotwebtools/ros2-web-bridge": ("ros", "transport"),
    "gh.osrf/soss": ("ros", "transport"),
    "gh.unity-technologies/ros-tcp-connector": ("ros", "transport"),
    "gh.unity-technologies/ros-tcp-endpoint": ("ros", "transport"),
    "gh.coppeliarobotics/simros2": ("ros", "transport"),
    "gh.cyberbotics/webots_ros2": ("ros", "framework"),
    "gh.gazebosim/gz-sim": ("ros", "framework"),
    "gh.gazebosim/gz-transport": ("ros", "transport"),
    "gh.gazebosim/gazebo-classic": ("ros", "framework"),
    # simulation and RL cores
    "gh.farama-foundation/gymnasium": ("gymnasium", "framework"),
    "gh.openai/gym": ("gymnasium", "framework"),
    "gh.farama-foundation/shimmy": ("gymnasium", "framework"),
    "gh.google-deepmind/mujoco": ("mujoco", "framework"),
    "gh.google-deepmind/mujoco_warp": ("mujoco", "framework"),
    "gh.google-deepmind/dm_control": ("mujoco", "framework"),
    "gh.google-deepmind/dm_env": ("gymnasium", "framework"),
    "gh.openai/mujoco-py": ("mujoco", "framework"),
    "gh.google-deepmind/dm_env_rpc": ("gymnasium", "transport"),
    # simulation engines without a helper (future bridges; never repo tasks)
    "gh.bulletphysics/bullet3": (None, "framework"),
    "gh.robotlocomotion/drake": (None, "framework"),
    "gh.cyberbotics/webots": (None, "framework"),
    "gh.coppeliarobotics/coppeliasimlib": (None, "framework"),
    "gh.coppeliarobotics/zmqremoteapi": (None, "transport"),
    "gh.coppeliarobotics/simzmq": (None, "transport"),
    "gh.stepjam/pyrep": (None, "framework"),
    "gh.isaac-sim/isaacsim": (None, "framework"),
    "gh.isaac-sim/isaaclab": (None, "framework"),
    "gh.facebookresearch/habitat-sim": (None, "framework"),
    "gh.haosulab/sapien": (None, "framework"),
    "gh.genesis-embodied-ai/genesis-world": (None, "framework"),
    "gh.google/brax": (None, "framework"),
    "gh.nvidia/warp": (None, "framework"),
    "gh.newton-physics/newton": (None, "framework"),
    "gh.nvidia-omniverse/physx": (None, "framework"),
    "gh.projectchrono/chrono": (None, "framework"),
    "gh.raisimtech/raisimlib": (None, "framework"),
    "gh.raisimtech/raisim2lib": (None, "framework"),
    "gh.gazebosim/gz-physics": (None, "framework"),
    "gh.carla-simulator/carla": (None, "framework"),
    "gh.microsoft/airsim": (None, "framework"),
    "gh.unity-technologies/ml-agents": (None, "framework"),
    "gh.siconos/siconos": (None, "framework"),
    "gh.dimforge/nphysics": (None, "framework"),
    # lab automation frameworks behind post-pilot helpers
    "gh.microsoft/qcodes": ("qcodes", "framework"),
    "gh.bluesky/ophyd": ("ophyd", "framework"),
    "gh.bluesky/ophyd-async": ("ophyd", "framework"),
    "gh.pylabrobot/pylabrobot": ("pylabrobot", "framework"),
    "gh.pymmcore-plus/pymmcore-plus": ("pymmcore-plus", "framework"),
    "gh.micro-manager/pymmcore": ("pymmcore-plus", "framework"),
    "gh.micro-manager/mmcoreanddevices": ("pymmcore-plus", "framework"),
    "gh.micro-manager/pycro-manager": ("pymmcore-plus", "framework"),
    "gh.huggingface/lerobot": ("lerobot", "framework"),
    "gh.opentrons/opentrons": ("http", "framework"),
    "gh.ad-sdl/madsci": ("http", "framework"),
    "gh.automatedchemistry/flowchem": ("http", "framework"),
}

#: imports that make a structural family marker (rule 9), checked in order
LAB_FRAMEWORK_IMPORTS: tuple[tuple[str, frozenset[str]], ...] = (
    ("pylabrobot", frozenset({"pylabrobot"})),
    ("qcodes", frozenset({"qcodes"})),
    ("ophyd", frozenset({"ophyd", "ophyd_async"})),
    ("pymmcore-plus", frozenset({"pymmcore_plus", "pymmcore", "pycromanager"})),
    ("sila2", frozenset({"sila2", "sila_python", "unitelabs"})),
    ("http", frozenset({"madsci", "flowchem"})),
)
#: LeRobot is checked after the simulator markers: many benchmarks import it
#: only for datasets and policies
LEROBOT_IMPORTS = frozenset({"lerobot"})
GYM_IMPORTS = frozenset({"gym", "gymnasium"})
#: analyst/registry families for which a package.xml is the main structure
ROS_FAMILIES = ("ros1", "ros2", "gazebo")
#: a gym env that needs one of these external applications cannot run under
#: the pip-installed GymnasiumDriver; it has no helper yet
EXTERNAL_SIM_IMPORTS = frozenset({
    "isaacgym", "isaaclab", "isaacsim", "omni", "omni_isaac", "isaacgymenvs", "airsim",
    "carla", "mlagents", "mlagents_envs", "pyrep", "habitat_sim", "habitat", "vizdoom",
    "controller", "deepbots", "rospy", "rclpy", "gazebo_msgs", "unrealcv", "pyrfuniverse",
    "holoocean", "scenario", "gym_ignition", "raisimpy", "omnigibson", "pybullet_ros", "newton",
    "tdw", "unity_simulator", "virtualhome", "pyflex", "agx", "agxSDK",
})
#: GUI toolkits: an application built on one, with no device class of its own, is a host or a tool,
#: not a protocol command map (its VISA or serial import is the application's plumbing)
GUI_IMPORTS = frozenset({"pyqt4", "pyqt5", "pyqt6", "pyside", "pyside2", "pyside6", "qtpy", "tkinter", "wx",
                         "kivy", "dearpygui", "customtkinter", "flet", "toga", "pyqtgraph", "pysimplegui"})
#: transports that reach real hardware (serial, VISA, USB, fieldbus, DAQ and
#: GPIO buses, vendor camera and robot SDKs).  Generic networking (socket,
#: HTTP, websockets, ZeroMQ, gRPC) and ctypes are not on the list: emulators
#: serve sockets and simulators load native libraries through ctypes.
HARDWARE_TRANSPORTS = frozenset({
    "serial", "pyserial", "serialio", "serial_asyncio", "aioserial", "pyvisa", "visa", "vxi11", "usbtmc", "usb",
    "pyusb", "hid", "ftd2xx", "pyftdi", "can", "bluetooth", "bleak", "nidaqmx", "pydaqmx", "minimalmodbus",
    "pymodbus", "pyads", "snap7", "smbus", "smbus2", "spidev", "rpi", "gpiozero", "pigpio", "picamera",
    "picamera2", "libcamera", "pyrealsense2", "harvesters", "pypylon", "pyueye", "xarm", "urx", "rtde_control",
    "rtde_receive", "frankx", "franky", "panda_py", "dynamixel_sdk", "pymavlink", "mavsdk", "dronekit",
    "pylablib", "instrumentkit", "pymeasure", "clr", "pythonnet", "win32com", "comtypes", "sockio", "connio",
    "cflib", "autoscript_sdb_microscope_client", "tescanautomation",
})
#: directories of a transport layer (an entry class there is an interface, not the device)
TRANSPORT_LAYER_DIRS = frozenset({"interface", "interfaces", "transport", "transports", "adapters", "comm", "comms"})
#: directories of a GUI application's front end: a class there is a plugin, widget or view, not the driver
FRONT_END_DIRS = frozenset({"gui", "ui", "qt", "widgets", "plugins", "views", "frontend"})
#: external simulators that also rule out the ROS marker (ROS itself does not)
NON_ROS_EXTERNAL = EXTERNAL_SIM_IMPORTS - {"rospy", "rclpy", "gazebo_msgs", "pybullet_ros"}
MUJOCO_IMPORTS = frozenset({"mujoco", "dm_control", "mujoco_py"})
SCPI_IMPORTS = frozenset({"pyvisa", "visa", "vxi11", "usbtmc", "pyvisa_py", "pyvisa_sim", "pymeasure"})
TAG_IMPORTS = frozenset({"pymodbus", "pymodbustcp", "minimalmodbus", "umodbus", "asyncua", "opcua",
                         "epics", "caproto", "tango", "alpaca", "pyads", "snap7"})
MAVLINK_IMPORTS = frozenset({"pymavlink", "mavsdk", "dronekit"})
SERIAL_IMPORTS = frozenset({"serial", "serial_asyncio", "aioserial", "serialio"})
MCP_IMPORTS = frozenset({"mcp", "fastmcp"})
#: backends covered by a helper or bridge; an MCP server that only wraps one
#: of them is a host (rule 7)
COVERED_BACKEND_IMPORTS = frozenset({
    "rclpy", "rospy", "roslibpy", "pyvisa", "visa", "pylabrobot", "opentrons", "sila2", "qcodes",
    "ophyd", "ophyd_async", "bluesky", "pymmcore_plus", "pymmcore", "pycromanager", "lerobot",
    "isaacsim", "omni", "mujoco", "gymnasium", "gym", "pymavlink", "mavsdk", "dronekit", "pymodbus",
    "asyncua", "opcua", "epics", "caproto", "tango", "madsci", "flowchem", "gz", "gazebo",
})

#: catalogue adapter roles / categories (Chinese source vocabulary, matched as
#: substrings of the catalogue fields; English meaning in the comment)
CAT_HOST = ("编排调度",      # orchestration / scheduling
            "Agent框架",     # agent framework
            "实验编排",      # experiment orchestration
            "工作流")        # workflow
CAT_TOOL = ("辅助工具",)     # auxiliary tool
ROLE_TOOL = ("外围工具",)    # peripheral tool
CAT_NOT_DEVICE = ("策略/算法",  # policy / algorithm
                  "数据集")     # dataset
CAT_ASSET = ("模型资产", "场景资产")   # model / scene asset
ROLE_DEVICE = ("设备SDK", "设备 SDK", "仪器SDK")   # device SDK, instrument SDK
CAT_DEVICE = ("设备", "仪器", "SDK", "通用机器人平台")  # device, instrument, SDK, general robot platform
ROLE_SIM_BACKEND = ("直接模拟后端",)  # direct simulation backend
CAT_SIM = ("完整环境", "操作任务环境", "任务环境", "数字孪生")  # complete/manipulation task environment, digital twin
ROLE_SIM = ("任务环境",)            # task environment
CAT_ENGINE = ("物理引擎",)          # physics engine
ROLE_MODEL = ("测量模型",)          # measurement (numerical) model
#: catalogue rows that describe software, not a device, unless the scan finds
#: device or simulation evidence: policy/algorithm, dataset, control framework,
#: navigation, physics engine, model/scene asset
CAT_SOFTWARE = ("策略/算法", "数据集", "控制框架", "移动导航", "物理引擎", "模型资产", "场景资产")

_NAME_TUTORIAL = re.compile(
    r"(?:^|[-_.])(?:tutorials?|courses?|lectures?|lessons?|workshops?|cheat-?sheets?|homeworks?|"
    r"assignments?|bootcamp|notes|curriculum|summer-?school|textbook|book)(?:$|[-_.\d])", re.IGNORECASE)
_NAME_AWESOME = re.compile(r"(?:^|[-_.])(?:awesome|awsome)(?:$|[-_.])", re.IGNORECASE)
_NAME_MHS = re.compile(r"(?:^|[-_.])(?:open-?)?mhs(?:$|[-_.])|model[-_]?hardware[-_]?standard|fastmhs|mhsbench",
                       re.IGNORECASE)
_TOOLING_WORDS = re.compile(
    r"(?:^|[-_.\s])(?:gui|viewer|visuali[sz]\w*|plot\w*|dashboard|widgets?|napari|logger|"
    r"monitor\w*|converter|parser|cookiecutter|template|exporter|labell?ing|annotat\w*|"
    r"profiler|linter|formatter|editor|studio|inspector|browser|explorer)(?:$|[-_.\s])", re.IGNORECASE)
_HOST_WORDS = re.compile(
    r"(?:^|[-_.\s])(?:orchestrat\w*|scheduler|workflows?|agentic|copilot|assistant|chatbot|"
    r"mission-?control|ground-?station|gcs|queue-?server)(?:$|[-_.\s])", re.IGNORECASE)
_DEVICE_NAME = re.compile(
    r"(?:^|[-_.])(?:drivers?|hardware|hw|sdk|firmware|hal|bringup|instruments?|devices?)(?:$|[-_.])",
    re.IGNORECASE)
_SIM_NAME = re.compile(r"(?:^|[-_.])(?:sim|simulator|simulation|gazebo|gym|twin|emulator)(?:$|[-_.\d])",
                       re.IGNORECASE)
# Latin words are delimited by non-letters, not \b: the notes mix Chinese and
# English ("pymeasure/pymeasure的fork") and CJK characters count as word characters
_FORK_NOTE = re.compile(
    r"(?<![A-Za-z])fork(?:ed)?(?![A-Za-z])|的分叉|镜像|(?<![A-Za-z])mirror(?![A-Za-z])|副本|同源|"
    r"(?<![A-Za-z])copy of(?![A-Za-z])", re.IGNORECASE)   # fork, mirror, copy, same origin
_DIVERGENCE_NOTE = re.compile(
    r"hard fork|实质|substantive|非镜像|非未改动|新增|扩展|(?<![A-Za-z])extension|移植|(?<![A-Za-z])port(?![A-Za-z])|"
    r"ahead \d+|不是.{0,12}重复|独立|多个|(?<![A-Za-z])multiple", re.IGNORECASE)
# (substantive, not a mirror, not an unmodified fork, adds, extends, port, not a duplicate, independent, several)
_OWNER_REPO = re.compile(r"(?<![\w.-])([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)")
_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9 _.+-]{1,60}")
_NOTE_STOPWORDS = {"fork", "forked", "forkof", "mirror", "copy", "copyof", "readme", "github", "unknown",
                   "official", "upstream", "archived", "version"}

#: rule-10 thresholds for an AST entry class
ENTRY_MIN_SCORE = 9
ENTRY_MIN_API = 3
#: rule-10 thresholds for the transport-using class of a catalogue device SDK
SMALL_SDK_MIN_SCORE = 4
SMALL_SDK_MIN_API = 2
#: rule-9 serial / mcp members keep their own Python class when it is this strong
STRONG_ENTRY_SCORE = 12
#: rule-5 tree similarity
TREE_DUPLICATE = 0.9
TREE_FORK_CORROBORATION = 0.5


# ---------------------------------------------------------------------------
# facts and decisions
# ---------------------------------------------------------------------------

#: class names of a simulator, mock, fake or dummy of the device (the module stem is checked with
#: ``source_scan._MOCK_MODULE``: ``utils/cameras/sim.py``, ``pyzaber/dummy_linear_slides.py``)
_MOCK_CLASS = re.compile(r"^(?:Sim|Simulated|Mock|Mocked|Fake|Dummy|Emulated|Emulator)(?=[A-Z0-9_]|$)"
                         r"|(?<=[A-Za-z0-9_])(?:Sim|Simulator|Simulated|Mock|Fake|Dummy|Emulator)$")


def is_mock_class(cls: Mapping[str, Any], names: Iterable[str] = ()) -> bool:
    """A ranked class that simulates, mocks or fakes the device (by class name or module name).

    ``Virtual<Name>`` counts only when ``<Name>`` is another class in ``names``
    (``VirtualC3000Controller`` beside ``C3000Controller``; NI's VirtualBench is
    an instrument).
    """
    module, _, name = str(cls.get("symbol") or "").rpartition(":")
    stem = module.rsplit(".", 1)[-1].lower()
    if name.startswith("Virtual") and name[7:] in set(names):
        return True
    return bool(_MOCK_CLASS.search(name)) or bool(SS._MOCK_MODULE.search(stem))


@dataclass
class RepoFacts:
    """Everything triage knows about one clone (all values are plain data)."""

    package_id: str
    local_path: str
    track: str
    owner: str
    repo: str
    tier: str = "C"
    families: list[str] = field(default_factory=list)
    stars: int = 0
    archived: bool = False
    catalog: dict[str, str] = field(default_factory=dict)
    analyst: dict[str, Any] = field(default_factory=dict)
    git: dict[str, Any] = field(default_factory=dict)
    scan: dict[str, Any] | None = None

    # -- convenience views ---------------------------------------------------
    @property
    def counts(self) -> dict[str, int]:
        return (self.scan or {}).get("counts") or {}

    @property
    def source_files(self) -> int:
        c = self.counts
        return int(c.get("python", 0)) + int(c.get("code", 0))

    @property
    def python(self) -> dict[str, Any]:
        return (self.scan or {}).get("python") or {}

    @property
    def imports(self) -> frozenset[str]:
        return frozenset(self.python.get("imports") or [])

    @property
    def all_imports(self) -> frozenset[str]:
        """AST imports plus regex imports of files that do not parse (Python 2)."""
        return self.imports | frozenset(self.python.get("imports_unparsed") or [])

    @property
    def markers(self) -> dict[str, Any]:
        return (self.scan or {}).get("markers") or {}

    @property
    def readme(self) -> dict[str, Any]:
        return (self.scan or {}).get("readme") or {}

    def entry(self) -> dict[str, Any] | None:
        """The best ranked device class that is not a simulator, mock or dummy of the device."""
        classes = self.python.get("entry_classes") or []
        names = {str(c.get("symbol") or "").rsplit(":", 1)[-1] for c in classes}
        for cls in classes:
            if not is_mock_class(cls, names):
                return cls
        return None

    def cat(self, key: str) -> str:
        return str(self.catalog.get(key) or "")

    def has_cat(self, key: str, needles: Iterable[str]) -> bool:
        value = self.cat(key)
        return any(n in value for n in needles)

    def flags(self) -> set[str]:
        return set(self.analyst.get("flags") or [])


@dataclass
class Decision:
    """The triage outcome of one repo."""

    package_id: str
    strategy: str
    role: str
    reason_code: str
    rule: int | str
    quarantine: bool = False
    variant_of: str | None = None
    family: str | None = None
    helper: str | None = None
    helper_status: str | None = None
    blocked_on: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    justification: str | None = None
    partner: str | None = None
    flagship: bool = False
    wave: int | None = None
    #: an override's confirmed entry symbols ({symbol, file, line}); the card carries them, the decision record does not
    entry_symbols: list[dict[str, Any]] = field(default_factory=list)
    #: a reviewed override's capability classes: they replace the scan-derived candidate classes on the card, whose
    #: risk floor follows them (CAP-017); the card carries them, the decision record does not
    capability_classes: list[str] = field(default_factory=list)
    #: a reviewed override confirmed the scan's gym, environment or MJCF simulator contract is not what the
    #: driver serves; the card drops those models and world classes (taskcards.build_card)
    omit_sim_contract: bool = False
    #: "required" when a reviewed override found licence evidence the owner must decide on before publication
    publish_review: str | None = None
    #: a reviewed override's complete mode set (hardware first): it replaces the scan's modes on the record, and the
    #: card's expected mode follows; the record carries them, the decision record does not
    modes: list[str] = field(default_factory=list)
    #: a reviewed override's companion sources (user decision 2026-11-05): build_registry.py resolves them against
    #: the corpus lock and copies them onto the card; the decision record does not carry them
    companions: list[dict[str, Any]] = field(default_factory=list)
    #: "simulated" when a reviewed override serves the simulated form of a dual-mode record and leaves hardware
    #: on the record (the card's expected mode; the decision record does not carry it)
    served_mode: str | None = None

    def to_json(self) -> dict[str, Any]:
        out = OrderedDict()
        for key in ("package_id", "strategy", "role", "reason_code", "rule", "quarantine", "variant_of",
                    "family", "helper", "helper_status", "blocked_on", "partner", "flagship", "wave",
                    "justification", "evidence"):
            out[key] = getattr(self, key)
        return out


# ---------------------------------------------------------------------------
# predicates shared by several rules
# ---------------------------------------------------------------------------

def is_empty(f: RepoFacts) -> bool:
    if f.tier == "X":
        return True
    if f.scan is None:
        return False
    return int(f.counts.get("total", 0)) == 0


#: a lure may carry a stub script or two; real projects have more source than this
LURE_MAX_SOURCE_FILES = 2
#: committed installers (.exe, .msi ...) that, together with a README download call-to-action to a file host or
#: link shortener, quarantine a repo whatever its source count (triage rule 3: binary installer)
LURE_MIN_INSTALLERS = 3


def lure_signals(f: RepoFacts) -> list[str]:
    """Rule-3 predicate: download lure or binary-only installer (empty = not a lure).

    A lure is a README whose call to action is a download link to an external
    page or file host (or that uses crack/keygen-style wording) in a repo with
    at most two source files.  A binary installer repo ships executables or
    installers and no source code at all.
    """
    if f.scan is None:
        return []
    out = []
    if f.source_files <= LURE_MAX_SOURCE_FILES:
        cta = f.readme.get("download_cta") or []
        words = f.readme.get("lure_words") or []
        if cta:
            out.append(f"README download call-to-action to {cta[0]} with {f.source_files} source file(s)")
        if words:
            out.append(f"README lure wording ({', '.join(words[:3])}) with {f.source_files} source file(s)")
    if f.source_files == 0 and int(f.counts.get("executables", 0)) > 0:
        out.append(f"{f.counts.get('executables')} executable/installer file(s) and no source code")
    installers = int(f.counts.get("installers", 0))
    # a file host, link shortener or installer link; the owner's own github.io documentation page does not count
    hosted = [u for u in f.readme.get("download_cta") or [] if ".github.io" not in u.lower()]
    if f.source_files > LURE_MAX_SOURCE_FILES and installers >= LURE_MIN_INSTALLERS and hosted:
        # committed installers plus a README that sends the reader to a file host or link shortener
        out.append(f"{installers} committed installer file(s) and a README download call-to-action to {hosted[0]}")
    return out


def sim_catalogue(f: RepoFacts) -> str | None:
    """The catalogue calls the repo a model or a simulation: role measurement model, task environment or
    direct simulation backend, or category complete/manipulation task environment or digital twin."""
    if f.has_cat("adapter_role", ROLE_MODEL + ROLE_SIM + ROLE_SIM_BACKEND):
        return f"catalogue role {f.cat('adapter_role')!r}"
    if f.has_cat("category", CAT_SIM):
        return f"catalogue category {f.cat('category')!r}"
    return None


def hardware_transport(f: RepoFacts) -> str | None:
    """A ranked class with device API that imports a hardware transport (serial, VISA, USB, fieldbus ...)."""
    for cls in f.python.get("entry_classes") or []:
        hit = sorted(set(cls.get("transport") or []) & HARDWARE_TRANSPORTS)
        if hit and int(cls.get("api", 0)) >= 2 and not is_mock_class(cls):
            return f"class {cls['symbol']} uses the hardware transport {hit[0]}"
    return None


def device_evidence(f: RepoFacts) -> str | None:
    """Why the repo looks like it drives a device (None when nothing says so).

    When the catalogue calls the repo a model or a simulation
    (:func:`sim_catalogue`), the evidence also needs a class that uses a
    hardware transport: catalogue device wording, a device-SDK name or a
    ctypes import alone does not make a simulator, emulator or benchmark a
    hardware driver.
    """
    base = _device_evidence(f)
    if base and sim_catalogue(f):
        hardware = hardware_transport(f)
        return f"{base}; {hardware}" if hardware else None
    return base


def _device_evidence(f: RepoFacts) -> str | None:
    if f.has_cat("category", CAT_DEVICE):
        return f"catalogue category {f.cat('category')!r}"
    if f.has_cat("adapter_role", ROLE_DEVICE):
        return f"catalogue role {f.cat('adapter_role')!r}"
    if _DEVICE_NAME.search(f.repo):
        return f"repo name {f.repo!r}"
    entry = f.entry()
    if entry and entry["score"] >= STRONG_ENTRY_SCORE and entry.get("transport") and entry.get("exported"):
        return f"exported class {entry['symbol']} uses {entry['transport'][0]}"
    return None


#: directories that hold device drivers (a hardware abstraction layer, driver or device modules)
DRIVER_DIRS = frozenset({"hal", "drivers", "driver", "hardware", "devices", "instruments"})
DRIVER_DIR_MIN_FILES = 3


#: class names that name a device (the last word of the class name)
_DEVICE_CLASS = re.compile(
    r"(?:Camera|Stage|Motor|Pump|Laser|Gripper|Spectrometer|Oscilloscope|Multimeter|PowerSupply|Lockin|LockIn|"
    r"Picomotor|Actuator|Shutter|FilterWheel|Thermostat|Hotplate|Stirrer|Syringe|Detector|Positioner|"
    r"Nanopositioner|Chiller|Circulator|Balance|Microscope|Goniometer|Monochromator)$")


def device_class(f: RepoFacts) -> str | None:
    """Device evidence from the AST: a ranked class named after a device with two device API members.

    Like :func:`driver_directory`, it only keeps rule 8 from filing device
    wrappers as pure software; it selects no strategy on its own.
    """
    for cls in (f.python.get("entry_classes") or []):
        name = cls["symbol"].rsplit(":", 1)[-1]
        if _DEVICE_CLASS.search(name) and int(cls.get("api", 0)) >= 2 and not is_mock_class(cls):
            return f"class {cls['symbol']} names a device ({cls['api']} device API members)"
    return None


def driver_directory(f: RepoFacts) -> str | None:
    """Device evidence from the layout: at least three source files below a driver directory.

    This also sees drivers the AST scan cannot read (C++, C#, Rust).  It only
    keeps rule 8 from filing a hardware abstraction layer as pure software; it
    never selects a strategy, a family or a role on its own.
    """
    counts: Counter[str] = Counter()
    for path in (f.scan or {}).get("tree") or []:
        parts = path.split("/")
        if SS._ext(parts[-1]) not in SS.PY_EXT | SS.CODE_EXT:
            continue
        if any(p.lower() in SS.VENDORED_DIRS or p.lower() in ("test", "tests", "example", "examples", "docs")
               for p in parts[:-1]):
            continue
        for i, part in enumerate(parts[:-1]):
            if part.lower() in DRIVER_DIRS:
                counts["/".join(parts[:i + 1])] += 1
                break
    if not counts:
        return None
    where, n = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return f"{n} source files under {where}/" if n >= DRIVER_DIR_MIN_FILES else None


def mjcf_models(f: RepoFacts) -> int:
    """MJCF files of the repo itself: copies under examples, tests, fixtures, docs and vendored trees
    (``source_scan.AUX_DIRS``) do not count (an IK library's example robots do not make a simulator)."""
    return max(0, int(f.markers.get("mjcf", 0)) - int(f.markers.get("mjcf_aux", 0)))


def mjcf_main(f: RepoFacts) -> list[dict[str, Any]]:
    """Ranked loadable scene and robot models with actuators (``source_scan.classify_mjcf``)."""
    return list(f.markers.get("mjcf_main") or [])


def sim_evidence(f: RepoFacts) -> str | None:
    """Why the repo looks like a simulation environment or twin (None when nothing says so)."""
    gym_ids = f.python.get("gym_ids") or []
    if gym_ids:
        return f"registers gym env {gym_ids[0]}"
    if mjcf_models(f):
        return f"{mjcf_models(f)} MJCF model(s)"
    if int(f.python.get("env_classes", 0)) >= 1:
        return f"{f.python.get('env_classes')} environment class(es)"
    if f.has_cat("category", CAT_SIM) or f.has_cat("adapter_role", ROLE_SIM + ROLE_SIM_BACKEND):
        return f"catalogue {f.cat('category')!r}/{f.cat('adapter_role')!r}"
    if _SIM_NAME.search(f.repo):
        return f"repo name {f.repo!r}"
    return None


#: file-tree signs of a Gazebo simulation: world files and Gazebo plugin or asset directories
_GAZEBO_DIRS = frozenset({"gazebo", "gazebo_plugins", "gazebo_models", "gz_plugins"})


#: scene files of simulators that run as a separate application (no helper)
_ENGINE_SCENES = ((".world", "Gazebo world file"), (".ttt", "CoppeliaSim scene"), (".ttm", "CoppeliaSim model"),
                  (".wbt", "Webots world"))


def gazebo_marker(f: RepoFacts) -> str | None:
    """The clone runs its environments in an external simulator application: Gazebo (``.world`` files or a
    Gazebo plugin/asset directory), CoppeliaSim (``.ttt``/``.ttm`` scenes) or Webots (``.wbt`` worlds)."""
    tree = (f.scan or {}).get("tree") or []
    for ext, what in _ENGINE_SCENES:
        scenes = [p for p in tree if p.endswith(ext)]
        if scenes:
            return f"{what} {scenes[0]}"
    for path in tree:
        parts = path.split("/")
        hit = [p for p in parts[:-1] if p.lower() in _GAZEBO_DIRS]
        if hit and (SS._ext(parts[-1]) in SS.CODE_EXT or parts[-1] in ("CMakeLists.txt", "model.sdf", "model.config")):
            return f"Gazebo directory {'/'.join(parts[:parts.index(hit[0]) + 1])}/"
    return None


def structural_family(f: RepoFacts) -> tuple[str | None, str | None, list[str]]:
    """(family, marker, notes) from code structure only; names never pick a family.

    Order: lab-automation framework imports, gym env registrations, external
    simulators (no helper), ROS ``package.xml``, MJCF models, LeRobot, then the
    protocol families.  A driver pack never takes a protocol family (its
    instruments use several transports), and serial and MCP repos that already
    contain a strong Python device class are left to rule 10 (wrapping the
    upstream class is safer than re-implementing a vendor serial framing).
    """
    imports = f.all_imports
    notes: list[str] = []
    for family, names in LAB_FRAMEWORK_IMPORTS:
        hit = sorted(imports & names)
        if hit:
            return family, f"imports {hit[0]}", notes
    external = sorted(imports & EXTERNAL_SIM_IMPORTS)
    gym_ids = f.python.get("gym_ids") or []
    if gym_ids and imports & GYM_IMPORTS:
        gazebo = gazebo_marker(f)
        if external:
            notes.append(f"gym envs need the external simulator {external[0]} (no helper)")
        elif gazebo:
            notes.append(f"gym envs need an external simulator application ({gazebo}; no helper)")
        else:
            return "gymnasium", f"registers gym env {gym_ids[0]}", notes
    non_ros_external = sorted(imports & NON_ROS_EXTERNAL)
    if non_ros_external:
        notes.append(f"needs the external simulator {non_ros_external[0]} (no helper)")
        return None, None, notes
    if int(f.markers.get("package_xml", 0)) > 0:
        ros_family = f.analyst.get("family") in ROS_FAMILIES or bool(set(f.families[:1]) & set(ROS_FAMILIES))
        if ros_family:
            return "ros", f"ROS package.xml ({f.markers.get('package_xml')})", notes
        notes.append("ROS sub-package only (package.xml in a repo whose main family is not ROS)")
    mjcf = mjcf_models(f)
    main = mjcf_main(f)
    asset_only = f.source_files == 0 or (not f.python.get("files") and f.has_cat("category", CAT_ASSET))
    if mjcf and (imports & MUJOCO_IMPORTS or asset_only):
        if main:
            return "mujoco", f"MJCF {main[0]['kind']} model {main[0]['file']} ({mjcf} MJCF file(s))", notes
        # object or fixture assets, fragments and templates only: nothing a MujocoDriver can load and drive
        notes.append(f"{mjcf} MJCF file(s), but no loadable scene or robot model with actuators")
    if f.python.get("gym_ids_aux") and not gym_ids:
        notes.append(f"gym envs registered only in examples, tests or docs ({f.python['gym_ids_aux'][0]})")
    if imports & LEROBOT_IMPORTS and device_evidence(f) and not sim_evidence(f):
        return "lerobot", "imports lerobot", notes
    if _is_driver_pack(f):
        notes.append("driver pack: several vendor packages with strong device classes")
        return None, None, notes
    entry = f.entry()
    strong = bool(entry and entry["score"] >= STRONG_ENTRY_SCORE)
    gui = sorted(f.imports & GUI_IMPORTS)
    if gui and entry is None and imports & (SCPI_IMPORTS | TAG_IMPORTS | MAVLINK_IMPORTS | SERIAL_IMPORTS):
        # a GUI application with no device class: its VISA or serial calls are the application's plumbing
        notes.append(f"GUI application ({gui[0]}) with no device class; no protocol family")
        return None, None, notes
    hit = sorted(imports & SCPI_IMPORTS)
    if hit:
        own = set((entry or {}).get("transport") or []) & HARDWARE_TRANSPORTS
        small_sdk = bool(entry and f.has_cat("adapter_role", ROLE_DEVICE) and entry["score"] >= SMALL_SDK_MIN_SCORE
                         and entry.get("api", 0) >= SMALL_SDK_MIN_API)
        layer = bool(entry and {p.lower() for p in entry["file"].split("/")[:-1]} & TRANSPORT_LAYER_DIRS)
        if (strong or small_sdk) and own and not own & SCPI_IMPORTS and not layer:
            # a strong device class on its own transport (FTDI, USB, serial) is the driver; a VISA helper
            # module beside it does not make the repo a SCPI command map
            notes.append(f"VISA import {hit[0]}, but {entry['symbol']} is a usable Python class on {sorted(own)[0]}")
            return None, None, notes
        return "scpi", f"imports {hit[0]}", notes
    for family, names in (("tag-bridge", TAG_IMPORTS), ("mavlink", MAVLINK_IMPORTS)):
        hit = sorted(imports & names)
        if hit:
            return family, f"imports {hit[0]}", notes
    hit = sorted(imports & SERIAL_IMPORTS)
    if hit:
        if strong:
            notes.append(f"serial transport {hit[0]}, but {entry['symbol']} is a usable Python class")
            return None, None, notes
        return "serial", f"imports {hit[0]}", notes
    hit = sorted(imports & MCP_IMPORTS)
    if hit and is_mcp_wrapper(f) and not strong:
        return "mcp-client", f"MCP server (imports {hit[0]})", notes
    return None, None, notes


def is_mcp_wrapper(f: RepoFacts) -> bool:
    named = bool(re.search(r"(?:^|[-_.])mcp(?:$|[-_.])", f.repo, re.I)) or f.analyst.get("family") == "mcp-server"
    return named and bool(f.imports & MCP_IMPORTS or f.analyst.get("family") == "mcp-server")


def host_or_tooling(f: RepoFacts) -> tuple[str | None, str | None]:
    """Rule-7 predicate: ("host"|"tooling", evidence) or (None, None)."""
    device = f.has_cat("adapter_role", ROLE_DEVICE)
    envs = bool(f.python.get("gym_ids")) or int(f.python.get("env_classes", 0)) >= 3
    if is_mcp_wrapper(f):
        covered = sorted(f.imports & COVERED_BACKEND_IMPORTS)
        if covered:
            return "host", f"MCP server wrapping the covered backend {covered[0]}"
    if not device and not envs:
        if f.has_cat("category", CAT_HOST):
            return "host", f"catalogue category {f.cat('category')!r} (orchestration/agent)"
        if _HOST_WORDS.search(f.repo):
            return "host", f"repo name {f.repo!r} names an orchestrator/agent/host"
        if f.has_cat("category", CAT_TOOL) and f.has_cat("adapter_role", ROLE_TOOL):
            return "tooling", "catalogue category auxiliary tool, role peripheral tool"
        if _TOOLING_WORDS.search(f.repo):
            return "tooling", f"repo name {f.repo!r} names a GUI/plotting/tooling project"
    return None, None


def effective_tier(f: RepoFacts) -> tuple[str, str | None]:
    """Registry tier, demoted to D when the catalogue row describes software, not a device.

    A row whose catalogue category is policy/algorithm, dataset, control
    framework, navigation, physics engine or asset (or whose role is a
    measurement model) counts as tier D when the scan finds neither device nor
    simulation evidence.
    """
    if f.tier in ("D", "X"):
        return f.tier, None
    software = f.has_cat("category", CAT_SOFTWARE) or f.has_cat("adapter_role", ROLE_MODEL)
    device = bool(device_evidence(f) or driver_directory(f) or device_class(f))
    if software and not device and not sim_evidence(f):
        return "D", (f"catalogue {f.cat('category')!r}/{f.cat('adapter_role')!r} describes software "
                     "and the scan finds no device or simulation evidence")
    if f.has_cat("category", CAT_NOT_DEVICE) and not f.python.get("gym_ids") and not device:
        return "D", f"catalogue category {f.cat('category')!r} with no env registration or device evidence"
    return f.tier, None


def infer_role(f: RepoFacts, family: str | None = None) -> str:
    """Content role used when a rule does not fix the role itself."""
    device = device_evidence(f)
    if family == "gymnasium" or f.python.get("gym_ids"):
        return "sim-env"
    if f.has_cat("category", CAT_NOT_DEVICE) and not device:
        return "not-device"
    if (f.has_cat("category", CAT_ENGINE) or f.has_cat("adapter_role", CAT_ENGINE)) and not device:
        return "framework"
    if f.has_cat("category", CAT_ASSET) or f.has_cat("adapter_role", CAT_ASSET):
        return "twin-candidate" if mjcf_main(f) else "not-device"
    if family == "mujoco":
        return "sim-env" if int(f.python.get("env_classes", 0)) or f.has_cat("category", CAT_SIM) else "twin-candidate"
    if f.has_cat("adapter_role", ROLE_MODEL) and not device:
        return "not-device"
    if f.has_cat("adapter_role", ROLE_SIM_BACKEND) and device:
        return "twin-candidate"
    if device:
        return "driver-pack" if _is_driver_pack(f) else "device-driver"
    if sim_evidence(f):
        return "sim-env"
    if f.has_cat("category", CAT_HOST):
        return "host"
    if f.has_cat("category", CAT_TOOL) or f.has_cat("adapter_role", ROLE_TOOL):
        return "tooling"
    return "not-device"


def _is_driver_pack(f: RepoFacts) -> bool:
    """Many strong entry classes spread over several vendor sub-packages."""
    classes = [c for c in (f.python.get("entry_classes") or []) if c["score"] >= STRONG_ENTRY_SCORE]
    dirs = {c["file"].rsplit("/", 1)[0] for c in classes if "/" in c["file"]}
    return len(classes) >= 8 and len(dirs) >= 5


# ---------------------------------------------------------------------------
# duplicate index (rule 5)
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class DuplicateIndex:
    """Finds the canonical repo of forks and duplicates across the corpus."""

    def __init__(self, facts: Iterable[RepoFacts]):
        self.facts = {f.package_id: f for f in facts}
        self.by_name: dict[str, list[str]] = defaultdict(list)
        self.by_owner_repo: dict[str, str] = {}
        self.by_remote: dict[str, list[str]] = defaultdict(list)
        self.by_head: dict[str, list[str]] = defaultdict(list)
        for pid, f in sorted(self.facts.items()):
            self.by_name[_norm(f.repo)].append(pid)
            self.by_owner_repo[f"{f.owner.lower()}/{f.repo.lower()}"] = pid
            remote = (f.git.get("repo_url") or "").lower()
            if remote:
                self.by_remote[remote].append(pid)
            head = f.git.get("commit")
            if head:
                self.by_head[head].append(pid)
        self._cache: dict[str, tuple[str, str] | None] = {}

    def _tree(self, pid: str) -> list[str]:
        f = self.facts[pid]
        return list((f.scan or {}).get("tree") or [])

    def _canonical(self, pids: Iterable[str], prefer: str | None = None) -> str:
        pids = sorted(set(pids))
        if prefer in pids:
            return prefer
        return sorted(pids, key=lambda p: (self.facts[p].archived, -int(self.facts[p].stars or 0),
                                           self.facts[p].owner.lower() != self.facts[p].repo.lower(), p))[0]

    def upstream_candidates(self, f: RepoFacts, note: str) -> list[str]:
        """Corpus repos a catalogue fork/mirror note names (never ``f`` itself).

        ``owner/repo`` mentions win; otherwise the longest run of Latin words
        whose normalised form equals a corpus repo name ("QCoDeS contrib
        drivers" -> ``qcodes_contrib_drivers``).
        """
        out: list[str] = []
        for owner, repo in _OWNER_REPO.findall(note):
            pid = self.by_owner_repo.get(f"{owner.lower()}/{repo.lower().rstrip('.')}")
            if pid and pid != f.package_id and pid not in out:
                out.append(pid)
        if out:
            return out
        best: tuple[int, list[str]] = (0, [])
        for run in _LATIN_RUN.findall(note):
            words = [w for w in re.split(r"[\s]+", run.strip()) if w]
            for size in range(len(words), 0, -1):
                if size < best[0]:
                    break
                for start in range(0, len(words) - size + 1):
                    key = _norm("".join(words[start:start + size]))
                    if len(key) < 4 or key in _NOTE_STOPWORDS:
                        continue
                    hits = [p for p in self.by_name.get(key, []) if p != f.package_id]
                    if hits:
                        if size > best[0]:
                            best = (size, [])
                        best[1].extend(h for h in hits if h not in best[1])
        return best[1]

    def _raw(self, pid: str) -> tuple[str, str] | None:
        if pid not in self._cache:
            self._cache[pid] = self._lookup(self.facts[pid])
        return self._cache[pid]

    def lookup(self, f: RepoFacts) -> tuple[str, str] | None:
        """(canonical package_id, evidence) when ``f`` duplicates another corpus repo.

        Chains are followed to their root (a fork of a fork points at the
        upstream) and a cycle is broken by the same canonical order, so every
        cluster keeps exactly one repo that is not skipped.
        """
        if f.package_id not in self.facts:
            self.facts[f.package_id] = f
        first = self._raw(f.package_id)
        if first is None:
            return None
        chain = [f.package_id]
        current = first[0]
        while current not in chain:
            chain.append(current)
            step = self._raw(current) if current in self.facts else None
            if step is None:
                break
            current = step[0]
        else:
            cycle = chain[chain.index(current):]
            root = self._canonical(cycle)
            return None if root == f.package_id else (root, first[1] if root == first[0] else
                                                       f"{first[1]}; cluster root {root}")
        root = chain[-1]
        if root == f.package_id:
            return None
        return root, first[1] if root == first[0] else f"{first[1]}; upstream of that is {root}"

    def _lookup(self, f: RepoFacts) -> tuple[str, str] | None:
        me = f.package_id
        tree = self._tree(me)
        head = f.git.get("commit")
        if head and len(self.by_head.get(head, [])) > 1:
            group = self.by_head[head]
            canonical = self._canonical(group)
            if canonical != me:
                return canonical, f"same HEAD commit {head[:12]} as {canonical}"
        remote = (f.git.get("repo_url") or "").lower()
        if remote and len(self.by_remote.get(remote, [])) > 1:
            canonical = self._canonical(self.by_remote[remote])
            if canonical != me:
                return canonical, f"same git remote {remote} as {canonical}"
        note = " ".join(filter(None, [f.cat("relation_to_other_projects"), f.cat("limitations")]))
        if note and _FORK_NOTE.search(note) and not _DIVERGENCE_NOTE.search(note):
            ups = self.upstream_candidates(f, note)
            if len(ups) == 1:
                sim = jaccard(tree, self._tree(ups[0]))
                if sim >= TREE_FORK_CORROBORATION:
                    return ups[0], f"catalogue fork/mirror note names {ups[0]} (tree similarity {sim:.2f})"
        group = [p for p in self.by_name.get(_norm(f.repo), []) if p != me]
        similar = []
        for other in group:
            sim = jaccard(tree, self._tree(other))
            if sim > TREE_DUPLICATE:
                similar.append((other, sim))
        if similar:
            canonical = self._canonical([me] + [o for o, _ in similar])
            if canonical != me:
                sim = dict(similar).get(canonical, max(s for _, s in similar))
                return canonical, f"file tree {sim:.2f} similar to {canonical}"
        return None


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

class Context:
    """Corpus-wide state the rules need (duplicate index)."""

    def __init__(self, facts: Iterable[RepoFacts]):
        self.duplicates = DuplicateIndex(facts)


def _dec(f: RepoFacts, strategy: str, role: str, reason: str, rule: int, *evidence: str, **extra: Any) -> Decision:
    return Decision(package_id=f.package_id, strategy=strategy, role=role, reason_code=reason, rule=rule,
                    evidence=[e for e in evidence if e], **extra)


def rule_1_empty(f: RepoFacts, ctx: Context) -> Decision | None:
    if not is_empty(f):
        return None
    why = "registry tier X" if f.tier == "X" else "clone has no files"
    return _dec(f, "skip", "not-device", "skip:empty", 1, why)


def rule_2_not_device(f: RepoFacts, ctx: Context) -> Decision | None:
    flags = f.flags() & {"no_source_code", "clone_content_gap"}
    docs_only = f.analyst.get("family") == "docs-only"
    models = int(f.markers.get("mjcf", 0)) + int(f.markers.get("urdf", 0)) + int(f.markers.get("package_xml", 0))
    if f.scan is not None and f.source_files == 0 and models == 0:
        nb = int(f.counts.get("notebooks", 0))
        return _dec(f, "skip", "docs", "skip:not-device", 2,
                    "no source code in the clone" + (f" ({nb} notebook(s) only)" if nb else ""))
    if (flags or docs_only) and f.source_files <= 1 and structural_family(f)[0] is None and not f.entry():
        what = ", ".join(sorted(flags) + (["docs-only"] if docs_only else []))
        return _dec(f, "skip", "docs", "skip:not-device", 2,
                    f"analyst {what}, confirmed by the scan ({f.source_files} source file, no device class)")
    if _NAME_AWESOME.search(f.repo) or (f.readme.get("curated_list") and f.source_files <= 5):
        return _dec(f, "skip", "docs", "skip:not-device", 2, "curated list (awesome-style)")
    if _NAME_TUTORIAL.search(f.repo):
        return _dec(f, "skip", "docs", "skip:not-device", 2, f"repo name {f.repo!r} names a course/tutorial")
    return None


def rule_3_quarantine(f: RepoFacts, ctx: Context) -> Decision | None:
    signals = lure_signals(f)
    if not signals:
        return None
    return _dec(f, "skip", "not-device", "skip:quarantine", 3, *signals)


def rule_4_prior_art(f: RepoFacts, ctx: Context) -> Decision | None:
    readme = f.readme
    claim = f.analyst.get("mhs_claim")
    named = bool(_NAME_MHS.search(f.repo))
    titled = bool(readme.get("mhs_title"))
    mentions = int(readme.get("mhs_mentions", 0))
    if titled or (named and mentions >= 1) or (claim in ("claimed", "inspired_or_third_party") and mentions >= 5):
        why = "README title names MHS" if titled else ("repo name names MHS" if named else
                                                       f"analyst MHS claim {claim}, {mentions} mentions")
        return _dec(f, "reference", "prior-art", "reference:prior-art", 4, why)
    return None


def rule_5_duplicate(f: RepoFacts, ctx: Context) -> Decision | None:
    hit = ctx.duplicates.lookup(f)
    if not hit:
        return None
    canonical, why = hit
    return _dec(f, "skip", infer_role(f, structural_family(f)[0]), "skip:duplicate_of", 5, why, variant_of=canonical)


def rule_6_bridge_runtime(f: RepoFacts, ctx: Context) -> Decision | None:
    entry = BRIDGE_RUNTIME.get(f.package_id)
    if entry is None:
        return None
    family, role = entry
    reason = f"bridge-runtime:{family}" if family else "bridge-runtime:engine"
    return _dec(f, "bridge-runtime", role, reason, 6,
                f"protocol stack or framework behind the {family or 'SDK'} helper; an SDK bridge task, not a repo task",
                family=family)


def rule_7_host_tooling(f: RepoFacts, ctx: Context) -> Decision | None:
    kind, why = host_or_tooling(f)
    if kind == "host":
        return _dec(f, "reference", "host", "reference:host", 7, why)
    if kind == "tooling":
        return _dec(f, "skip", "tooling", "skip:tooling", 7, why)
    return None


def rule_8_peripheral(f: RepoFacts, ctx: Context) -> Decision | None:
    tier, why = effective_tier(f)
    if tier != "D":
        return None
    role = infer_role(f)
    if role in ("device-driver", "driver-pack", "sim-env", "twin-candidate", "framework"):
        role = "tooling" if f.has_cat("adapter_role", ROLE_TOOL) else "not-device"
    return _dec(f, "skip", role, "skip:peripheral", 8, why or "registry tier D (peripheral, not a device)")


def rule_9_family(f: RepoFacts, ctx: Context) -> Decision | None:
    family, marker, notes = structural_family(f)
    if family is None:
        return None
    role = infer_role(f, family)
    if role not in FAMILY_ROLES.get(family, DEVICE_ROLES):
        return None
    evidence = device_evidence(f) if role in ("device-driver", "driver-pack") else sim_evidence(f)
    return _dec(f, "family-config", role, f"family:{family}", 9, f"structural marker: {marker}",
                f"{role} evidence: {evidence}" if evidence else "", *notes, family=family)


def rule_10_direct(f: RepoFacts, ctx: Context) -> Decision | None:
    entry = f.entry()
    if not entry:
        return None
    strong = entry["score"] >= ENTRY_MIN_SCORE and entry.get("api", 0) >= ENTRY_MIN_API
    # a catalogue device SDK whose best class talks to its transport is a driver even when the class is
    # small (a single-file USB or serial driver); a ROS package beside it is not an external simulator
    small_sdk = (f.has_cat("adapter_role", ROLE_DEVICE) and bool(entry.get("transport"))
                 and entry["score"] >= SMALL_SDK_MIN_SCORE and entry.get("api", 0) >= SMALL_SDK_MIN_API)
    if not strong and not small_sdk:
        return None
    if f.imports & GUI_IMPORTS and {p.lower() for p in entry["file"].split("/")[:-1]} & FRONT_END_DIRS:
        return None     # a GUI application's plugin or widget class (pylablib-cam-control), not a device driver
    if f.imports & (EXTERNAL_SIM_IMPORTS if strong else NON_ROS_EXTERNAL):
        if not (small_sdk and not f.imports & NON_ROS_EXTERNAL):
            return None
    device = device_evidence(f)
    role = infer_role(f)
    if not device or role not in ("device-driver", "driver-pack", "twin-candidate"):
        return None
    if device.startswith("exported class") and not hardware_transport(f):
        # the only evidence is an exported client of generic networking (HTTP, gRPC, ZeroMQ, sockets): a
        # framework's client of its own server (labdaemon, jumpstarter), not a device driver
        return None
    why = (f"AST entry class {entry['symbol']} ({entry['file']}:{entry['line']}, score {entry['score']})" if strong else
           f"catalogue device SDK; AST class {entry['symbol']} ({entry['file']}:{entry['line']}, score "
           f"{entry['score']}) uses {entry['transport'][0]}")
    return _dec(f, "direct-driver", role, "PY_SDK_WITH_ENTRY", 10, why,
                f"device evidence: {device}", family="python-object")


def rule_11_untriaged(f: RepoFacts, ctx: Context) -> Decision:
    family, _marker, notes = structural_family(f)
    entry = f.entry()
    if f.scan is None:
        why = "untriaged:no_scan"
    elif not f.python.get("files"):
        why = "untriaged:non_python"
    elif entry is None:
        why = "untriaged:no_entry_class"
    else:
        why = "untriaged:weak_entry"
    evidence = list(notes)
    if entry:
        evidence.append(f"best AST class {entry['symbol']} score {entry['score']}")
    return _dec(f, "untriaged", infer_role(f, family), why, 11, *evidence)


DEVICE_ROLES = ("device-driver", "driver-pack", "twin-candidate")
#: roles a family-config can have per family; protocol families are devices only
FAMILY_ROLES = {
    "gymnasium": ("sim-env", "twin-candidate"),
    "mujoco": ("sim-env", "twin-candidate"),
    "ros": ("device-driver", "driver-pack", "sim-env", "twin-candidate"),
}


RULES: tuple[tuple[int, Callable[[RepoFacts, Context], Decision | None]], ...] = (
    (1, rule_1_empty),
    (2, rule_2_not_device),
    (3, rule_3_quarantine),
    (4, rule_4_prior_art),
    (5, rule_5_duplicate),
    (6, rule_6_bridge_runtime),
    (7, rule_7_host_tooling),
    (8, rule_8_peripheral),
    (9, rule_9_family),
    (10, rule_10_direct),
    (11, rule_11_untriaged),
)


# ---------------------------------------------------------------------------
# overrides
# ---------------------------------------------------------------------------

OVERRIDE_KEYS = {"package_id", "strategy", "role", "reason_code", "family", "quarantine", "variant_of",
                 "partner", "flagship", "wave", "entry_symbols", "capability_classes", "publish_review",
                 "modes", "companions", "omit_sim_contract", "served_mode", "justification"}
#: the modes an override may set, in the record's order (hardware first)
OVERRIDE_MODES = ("hardware", "simulated", "replay")
#: a catalogue capability class id (taskcards.py checks that it is a stable class of the catalogue)
OVERRIDE_CLASS_RE = re.compile(r"^cap\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")
#: at most as many reviewed classes as a card carries (taskcards.MAX_CLASSES)
OVERRIDE_MAX_CLASSES = 8
OVERRIDE_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")
OVERRIDE_FILE_RE = re.compile(r"^(?!/)(?!.*(^|/)\.\.(/|$))[A-Za-z0-9._@+/-]+$")  # defs.schema.json relPath
#: companion sources (user decision 2026-11-05): at most this many per card
OVERRIDE_MAX_COMPANIONS = 3
COMPANION_KEYS = ("alias", "package_id", "commit", "profile", "reason", "version_evidence")
#: the optional key of a companion fetched under work/companions: its LOCK.json alias (DESIGN-2, 2026-11-05)
COMPANION_LOCK_KEY = "lock"
COMPANION_LOCK_RE = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+@[A-Za-z0-9_.+-]+$")
#: the fetched companion clones and their bookkeeping, relative to the workspace root
COMPANIONS_DIR = os.path.join("work", "companions")
COMPANION_LOCK_FILE = "LOCK.json"
_GITHUB_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
COMPANION_ALIAS_RE = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
COMPANION_PROFILE_RE = re.compile(r"^ros[12]-[a-z]+-[a-z0-9.+-]+$")
#: A non-ROS profile of a user-authorized hardware stop (decision 4, 2026-11-05). A ROS profile never matches.
COMPANION_HARDWARE_STOP_KEY = "hardware_stop"
HARDWARE_STOP_PROFILE_RE = re.compile(r"^(?!ros[12]-)[a-z][a-z0-9.+-]{1,80}$")
_COMPANION_KEY_SETS = (set(COMPANION_KEYS), set(COMPANION_KEYS) | {COMPANION_LOCK_KEY},
                       set(COMPANION_KEYS) | {COMPANION_LOCK_KEY, COMPANION_HARDWARE_STOP_KEY})
COMPANION_SIDE_RE = re.compile(r"^(package|companion|companion:[a-z][a-z0-9_-]{1,39})$")
COMPANION_REF_RE = re.compile(r"^[^:\s][^:]*:[1-9][0-9]*(-[1-9][0-9]*)?$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PACKAGE_ID_RE = re.compile(r"^gh\.[a-z0-9_.-]+/[a-z0-9_.-]+$")


class OverrideError(ValueError):
    """An override file is malformed or contradicts itself."""


def load_overrides(directory: str = OVERRIDES_DIR) -> dict[str, dict[str, Any]]:
    """``{package_id: override}`` from every ``overrides/*.json`` (sorted, duplicates refused)."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        for item in doc.get("overrides") or []:
            check_override(item, path)
            pid = item["package_id"]
            if pid in out:
                raise OverrideError(f"{os.path.basename(path)}: {pid} is overridden twice")
            out[pid] = dict(item, _file=os.path.basename(path))
    return out


def check_override(item: Mapping[str, Any], where: str = "override") -> None:
    unknown = set(item) - OVERRIDE_KEYS
    if unknown:
        raise OverrideError(f"{where}: unknown override key(s) {sorted(unknown)}")
    for key in ("package_id", "strategy", "role", "justification"):
        if not item.get(key):
            raise OverrideError(f"{where}: override needs {key}")
    if item["strategy"] not in STRATEGIES:
        raise OverrideError(f"{where}: {item['package_id']}: unknown strategy {item['strategy']!r}")
    if item["role"] not in ROLES:
        raise OverrideError(f"{where}: {item['package_id']}: unknown role {item['role']!r}")
    family = item.get("family")
    if item["strategy"] in DISPATCHABLE and family not in FAMILIES:
        raise OverrideError(f"{where}: {item['package_id']}: {item['strategy']} needs a family from {list(FAMILIES)}")
    if item["strategy"] == "skip" and item.get("reason_code", "").startswith("skip:duplicate_of") and not item.get("variant_of"):
        raise OverrideError(f"{where}: {item['package_id']}: a duplicate override needs variant_of")
    if item.get("quarantine") and item["strategy"] in DISPATCHABLE:
        raise OverrideError(f"{where}: {item['package_id']}: a quarantined repo cannot be dispatched")
    symbols = item.get("entry_symbols")
    if symbols is not None:
        if item["strategy"] not in DISPATCHABLE:
            raise OverrideError(f"{where}: {item['package_id']}: entry_symbols are only for {'/'.join(DISPATCHABLE)}")
        if not isinstance(symbols, list) or not 1 <= len(symbols) <= 5 or not all(
                isinstance(s, dict) and sorted(s) == ["file", "line", "symbol"] and isinstance(s["symbol"], str)
                and entry_shape(s["symbol"], s["file"], s["line"]) for s in symbols):
            raise OverrideError(f"{where}: {item['package_id']}: entry_symbols must be 1 to 5 {{symbol, file, line}} "
                                f"items with a Python source selector and a safe relative source file path")
    classes = item.get("capability_classes")
    if classes is not None:
        if item["strategy"] not in DISPATCHABLE:
            raise OverrideError(f"{where}: {item['package_id']}: capability_classes are only for {'/'.join(DISPATCHABLE)}")
        if (not isinstance(classes, list) or not 1 <= len(classes) <= OVERRIDE_MAX_CLASSES
                or len(set(map(str, classes))) != len(classes)
                or not all(isinstance(c, str) and OVERRIDE_CLASS_RE.match(c) for c in classes)):
            raise OverrideError(f"{where}: {item['package_id']}: capability_classes must be 1 to "
                                f"{OVERRIDE_MAX_CLASSES} distinct catalogue class ids (cap.<area>.<name>.v<N>)")
    if "publish_review" in item and item["publish_review"] != "required":
        raise OverrideError(f"{where}: {item['package_id']}: publish_review can only be 'required' (an override adds "
                            f"a publication review, never waives one)")
    if "omit_sim_contract" in item:
        if item["strategy"] not in DISPATCHABLE:
            raise OverrideError(f"{where}: {item['package_id']}: omit_sim_contract is only for "
                                f"{'/'.join(DISPATCHABLE)}")
        if item["omit_sim_contract"] is not True:
            raise OverrideError(f"{where}: {item['package_id']}: omit_sim_contract can only be true (it drops the "
                                f"scan's simulator contract; it cannot be waived back on)")
    modes = item.get("modes")
    if modes is not None:
        if (not isinstance(modes, list) or not 1 <= len(modes) <= len(OVERRIDE_MODES)
                or not all(isinstance(mode, str) and mode in OVERRIDE_MODES for mode in modes)
                or len(set(modes)) != len(modes)
                or list(modes) != sorted(modes, key=OVERRIDE_MODES.index)):
            raise OverrideError(f"{where}: {item['package_id']}: modes must be 1 to {len(OVERRIDE_MODES)} distinct "
                                f"modes of {list(OVERRIDE_MODES)} in that order (hardware first)")
    companions = item.get("companions")
    if companions is not None:
        check_companions(item, companions, where)
    if "served_mode" in item:
        if item["strategy"] not in DISPATCHABLE:
            raise OverrideError(f"{where}: {item['package_id']}: served_mode is only for {'/'.join(DISPATCHABLE)}")
        if item["served_mode"] != "simulated":
            raise OverrideError(f"{where}: {item['package_id']}: served_mode can only be 'simulated' (the card serves "
                                "the simulated form; hardware stays on the record and is not served)")
    text = str(item["justification"])
    if "\n" in text or len(text) > 240:
        raise OverrideError(f"{where}: {item['package_id']}: justification must be one line of at most 240 characters")


def check_companions(item: Mapping[str, Any], companions: Any, where: str) -> None:
    """The shape of an override's ``companions`` (user decision 2026-11-05); the corpus rules are build_registry's."""
    pid = item["package_id"]
    if item["strategy"] not in DISPATCHABLE:
        raise OverrideError(f"{where}: {pid}: companions are only for {'/'.join(DISPATCHABLE)}")
    if not isinstance(companions, list) or not 1 <= len(companions) <= OVERRIDE_MAX_COMPANIONS:
        raise OverrideError(f"{where}: {pid}: companions must be 1 to {OVERRIDE_MAX_COMPANIONS} entries")
    aliases: set[str] = set()
    for index, entry in enumerate(companions):
        label = f"{where}: {pid}: companions[{index}]"
        if not isinstance(entry, dict) or set(entry) not in _COMPANION_KEY_SETS:
            raise OverrideError(f"{label} must have exactly the keys {list(COMPANION_KEYS)}, and optionally "
                                f"{COMPANION_LOCK_KEY!r} (a work/companions/LOCK.json alias)"
                                f" and {COMPANION_HARDWARE_STOP_KEY!r} (exactly true, and only with lock)")
        if COMPANION_HARDWARE_STOP_KEY in entry and entry[COMPANION_HARDWARE_STOP_KEY] is not True:
            raise OverrideError(f"{label}: hardware_stop must be exactly true, or be omitted")
        if COMPANION_LOCK_KEY in entry and (not isinstance(entry[COMPANION_LOCK_KEY], str)
                                            or not COMPANION_LOCK_RE.match(entry[COMPANION_LOCK_KEY])):
            raise OverrideError(f"{label}: lock must be a LOCK.json alias matching {COMPANION_LOCK_RE.pattern}")
        if not isinstance(entry["alias"], str) or not COMPANION_ALIAS_RE.match(entry["alias"]):
            raise OverrideError(f"{label}: alias must match {COMPANION_ALIAS_RE.pattern}")
        if entry["alias"] in aliases:
            raise OverrideError(f"{label}: alias {entry['alias']!r} is declared twice")
        aliases.add(entry["alias"])
        if not isinstance(entry["package_id"], str) or not PACKAGE_ID_RE.match(entry["package_id"]):
            raise OverrideError(f"{label}: package_id must be a corpus package id (gh.owner/repo)")
        if entry["package_id"] == pid:
            raise OverrideError(f"{label}: a repository is never its own companion")
        if not isinstance(entry["commit"], str) or not COMMIT_RE.match(entry["commit"]):
            raise OverrideError(f"{label}: commit must be a 40-hex commit")
        if entry.get(COMPANION_HARDWARE_STOP_KEY) is True:
            if item.get("family") not in ("direct", "python-object"):
                raise OverrideError(f"{label}: hardware_stop is only for a direct or python-object family")
            if not isinstance(entry["profile"], str) or not HARDWARE_STOP_PROFILE_RE.match(entry["profile"]):
                raise OverrideError(f"{label}: profile must match {HARDWARE_STOP_PROFILE_RE.pattern} "
                                    "(a non-ROS hardware-stop profile)")
        elif not isinstance(entry["profile"], str) or not COMPANION_PROFILE_RE.match(entry["profile"]):
            raise OverrideError(f"{label}: profile must match {COMPANION_PROFILE_RE.pattern}")
        reason = entry["reason"]
        if not isinstance(reason, str) or "\n" in reason or not 10 <= len(reason) <= 240:
            raise OverrideError(f"{label}: reason must be one line of 10 to 240 characters")
        evidence = entry["version_evidence"]
        if not isinstance(evidence, list) or not 2 <= len(evidence) <= 12:
            raise OverrideError(f"{label}: version_evidence must be 2 to 12 items")
        for number, proof in enumerate(evidence):
            if (not isinstance(proof, dict) or set(proof) != {"side", "ref", "token"}
                    or not isinstance(proof["side"], str) or not COMPANION_SIDE_RE.match(proof["side"])
                    or not isinstance(proof["ref"], str) or not COMPANION_REF_RE.match(proof["ref"])
                    or ".." in proof["ref"].split(":")[0].split("/")
                    or not isinstance(proof["token"], str) or not 2 <= len(proof["token"]) <= 80):
                raise OverrideError(f"{label}: version_evidence[{number}] must be {{side, ref, token}}: side package, "
                                    "companion or companion:<alias>, a relative path:LINE ref and a token of 2 to 80 "
                                    "characters")
        sides = {proof["side"] for proof in evidence}
        if "package" not in sides or not any(side.startswith("companion") for side in sides):
            raise OverrideError(f"{label}: version_evidence needs a package-side and a companion-side item")
    for entry in companions:
        for proof in entry["version_evidence"]:
            other = proof["side"][len("companion:"):] if proof["side"].startswith("companion:") else None
            if other is not None and other not in aliases:
                raise OverrideError(f"{where}: {pid}: version_evidence side {proof['side']!r} names an undeclared "
                                    "companion")


def clone_head(path):
    """The commit a clone's HEAD names, read from its ``.git`` files (no git command); None when unknown."""
    git = os.path.join(path, ".git")
    try:
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as fh:
            head = fh.read().strip()
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
        with open(os.path.join(git, *ref.split("/")), encoding="utf-8") as fh:
            value = fh.read().strip()
        return value if re.fullmatch(r"[0-9a-f]{40}", value) else None
    except OSError:
        pass
    try:
        with open(os.path.join(git, "packed-refs"), encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
                    return parts[0]
    except OSError:
        pass
    return None


def evidence_shown(clone, ref, token):
    """True when ``path:LINE[-END]`` of the working tree of ``clone`` exists and shows ``token`` (case-insensitive)."""
    match = re.fullmatch(r"([^:\s][^:]*):([1-9][0-9]*)(?:-([1-9][0-9]*))?", str(ref))
    if match is None or ".." in match.group(1).split("/") or match.group(1).startswith("/"):
        return False
    first = int(match.group(2))
    last = int(match.group(3) or first)
    try:
        with open(os.path.join(clone, *match.group(1).split("/")), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return False
    if last < first or last > len(lines):
        return False
    return str(token).lower() in "\n".join(lines[first - 1:last]).lower()


def lock_package_id(repo_url):
    """``gh.<owner>/<repo>`` (lower case) of a ``https://github.com/<owner>/<repo>[.git]`` URL, else None."""
    match = _GITHUB_URL_RE.match(repo_url) if isinstance(repo_url, str) else None
    return f"gh.{match.group('owner')}/{match.group('repo')}".lower() if match else None


def lock_clone_path(repo_url, commit):
    """``work/companions/<owner>__<repo>@<first 12 hex of commit>`` (owner and repo as the URL spells them)."""
    match = _GITHUB_URL_RE.match(repo_url) if isinstance(repo_url, str) else None
    if match is None or not isinstance(commit, str) or not COMMIT_RE.match(commit):
        return None
    return f"work/companions/{match.group('owner')}__{match.group('repo')}@{commit[:12]}"


def read_companion_lock(workspace, companions_root=None):
    """``({alias: entry}, None)`` from ``LOCK.json``, ``(None, problem)`` otherwise
    (``(None, None)`` when the file does not exist: no lock companion can then resolve).

    The file is ``<workspace>/work/companions/LOCK.json``. ``companions_root`` (the gate's
    ``--companions-root`` / ``MHS_DRIVER_GATE_COMPANIONS``) is a directory that holds ``LOCK.json``
    in that file's place. Clone paths recorded in the file stay relative to ``workspace``.
    """
    if companions_root:
        path = os.path.join(companions_root, COMPANION_LOCK_FILE)
        shown = os.path.join(str(companions_root), COMPANION_LOCK_FILE)
    else:
        path = os.path.join(workspace, COMPANIONS_DIR, COMPANION_LOCK_FILE)
        shown = f"{COMPANIONS_DIR}/{COMPANION_LOCK_FILE}"
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            document = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, f"{shown} cannot be read ({type(exc).__name__}: {exc})"
    clones = document.get("clones") if isinstance(document, dict) else None
    if not isinstance(clones, list) or not all(isinstance(item, dict) and isinstance(item.get("alias"), str)
                                               for item in clones):
        return None, f"{shown}: clones must be a list of objects with an alias"
    out = {}
    for item in clones:
        if item["alias"] in out:
            return None, f"{shown}: alias {item['alias']!r} is listed twice"
        out[item["alias"]] = item
    return out, None


def lock_licence(text):
    """``(license_spdx, licence_note)`` of a LOCK.json licence: the text itself when it is an SPDX expression of known
    ids (``Apache-2.0``, ``Apache-2.0 AND BSD-3-Clause``), else ``NOASSERTION`` with the text as the note."""
    import licenses as LIC  # noqa: E402  (same-directory module, stdlib only)
    if not isinstance(text, str) or not text.strip():
        return "NOASSERTION", None
    tokens = text.split(" ")
    ids, operators = tokens[0::2], tokens[1::2]
    if (len(tokens) % 2 == 1 and all(op in ("AND", "OR") for op in operators)
            and all(LIC.canonical_id(token) == token for token in ids)):
        return text, None
    return "NOASSERTION", text[:300]


def lock_problems(pid, entry, companion_lock, workspace=None):
    """What keeps a reviewed override's lock companion (``entry`` with ``lock``) from its ``LOCK.json`` entry.

    The LOCK.json entry must exist; its repo_url must name the entry's package_id, its commit and profile be the
    entry's, its path ``work/companions/<owner>__<repo>@<commit12>``, and ``pid`` must be in its needed_by (the
    authorised scope of the fetch). With ``workspace`` the clone exists and the HEAD its ``.git`` names is the
    commit. ``companion_lock`` is :func:`read_companion_lock`'s mapping (None: LOCK.json missing or unreadable)."""
    alias, lock = entry.get("alias"), entry.get(COMPANION_LOCK_KEY)
    if companion_lock is None:
        return [f"{pid}: companion {alias!r} names lock {lock!r}, but {COMPANIONS_DIR}/{COMPANION_LOCK_FILE} is "
                "missing or unreadable"]
    line = companion_lock.get(lock)
    if line is None:
        return [f"{pid}: companion {alias!r}: {COMPANIONS_DIR}/{COMPANION_LOCK_FILE} has no entry {lock!r}"]
    problems = []
    if lock_package_id(line.get("repo_url")) != entry.get("package_id"):
        problems.append(f"{pid}: companion {alias!r}: the LOCK.json repo_url {line.get('repo_url')!r} does not name "
                        f"{entry.get('package_id')!r}")
    if line.get("commit") != entry.get("commit"):
        problems.append(f"{pid}: companion {alias!r} pins {str(entry.get('commit'))[:12]}, but LOCK.json {lock} pins "
                        f"{str(line.get('commit'))[:12]} (no silent re-pin)")
    if line.get("profile") != entry.get("profile"):
        problems.append(f"{pid}: companion {alias!r}: profile {entry.get('profile')!r} is not the LOCK.json profile "
                        f"{line.get('profile')!r}")
    if line.get("path") != lock_clone_path(line.get("repo_url"), line.get("commit")):
        problems.append(f"{pid}: companion {alias!r}: the LOCK.json path {line.get('path')!r} is not "
                        "work/companions/<owner>__<repo>@<first 12 hex of the commit>")
    needed = line.get("needed_by")
    if not isinstance(needed, list) or pid not in needed:
        problems.append(f"{pid}: companion {alias!r}: {pid} is not in the LOCK.json needed_by of {lock} (the clone "
                        "was fetched for other packages; widening needed_by is a reviewed LOCK.json edit)")
    if workspace is not None and not problems:
        clone = os.path.join(workspace, *str(line.get("path")).split("/"))
        if not os.path.isdir(clone):
            problems.append(f"{pid}: companion {alias!r}: the clone {line.get('path')} is missing")
        elif clone_head(clone) != entry.get("commit"):
            problems.append(f"{pid}: companion {alias!r}: the clone {line.get('path')} is not at "
                            f"{str(entry.get('commit'))[:12]}")
    return problems


def companion_problems(pid, entries, by_pid, lock_by_pid, workspace=None, companion_lock=None):
    """What is wrong with a reviewed override's companions against the corpus (user decision 2026-11-05).

    A companion is a corpus record whose commit is its corpus-lock commit (no silent re-pin), never the repository
    itself. With ``workspace`` (the corpus present) its clone exists, the HEAD its ``.git`` names is that commit, and
    every version-evidence range exists and shows its token. An entry with ``lock`` is a clone fetched under
    work/companions instead (:func:`lock_problems` against ``companion_lock``, the parsed LOCK.json); it need not be a
    corpus record. validate.py repeats these rules."""
    problems = []
    clones = {}
    record = by_pid.get(pid) or {}
    if workspace is not None and record.get("local_path"):
        clones["package"] = os.path.join(workspace, record["local_path"])
    for entry in entries:
        other = entry.get("package_id")
        if other == pid:
            problems.append(f"{pid}: companion {entry.get('alias')!r} is the repository itself")
            continue
        if COMPANION_LOCK_KEY in entry:
            found = lock_problems(pid, entry, companion_lock, workspace)
            problems.extend(found)
            if workspace is not None and not found:
                line = companion_lock[entry[COMPANION_LOCK_KEY]]
                clones["companion:" + str(entry.get("alias"))] = os.path.join(workspace, *str(line["path"]).split("/"))
            continue
        line = lock_by_pid.get(other)
        if other not in by_pid or line is None:
            problems.append(f"{pid}: companion {entry.get('alias')!r} names {other!r}, which is not a corpus record")
            continue
        if line.get("commit") != entry.get("commit"):
            problems.append(f"{pid}: companion {entry.get('alias')!r} pins {str(entry.get('commit'))[:12]}, but the "
                            f"corpus lock pins {other} at {str(line.get('commit'))[:12]} (no silent re-pin)")
            continue
        if workspace is not None:
            clone = os.path.join(workspace, line["local_path"])
            clones["companion:" + str(entry.get("alias"))] = clone
            if not os.path.isdir(clone):
                problems.append(f"{pid}: companion {entry.get('alias')!r}: the clone {line['local_path']} is missing")
            elif clone_head(clone) != entry.get("commit"):
                problems.append(f"{pid}: companion {entry.get('alias')!r}: the clone {line['local_path']} is not at "
                                f"{str(entry.get('commit'))[:12]}")
    if workspace is not None and not problems:
        for entry in entries:
            for proof in entry.get("version_evidence") or []:
                side = proof.get("side")
                key = "companion:" + str(entry.get("alias")) if side == "companion" else side
                clone = clones.get(key)
                if clone is None or not evidence_shown(clone, proof.get("ref"), proof.get("token")):
                    problems.append(f"{pid}: companion {entry.get('alias')!r}: version evidence {side} "
                                    f"{proof.get('ref')} does not show {proof.get('token')!r}")
    return problems


def unknown_overrides(overrides: Mapping[str, Mapping[str, Any]], package_ids: Iterable[str]) -> list[str]:
    """Overrides whose package_id is not a corpus repo (stale or mistyped)."""
    known = set(package_ids)
    return sorted(pid for pid in overrides if pid not in known)


def apply_override(f: RepoFacts, item: Mapping[str, Any], ruled: Decision) -> Decision:
    if ruled.quarantine and item["strategy"] in DISPATCHABLE:
        raise OverrideError(f"{item.get('_file', 'override')}: {f.package_id} is quarantined "
                            f"({ruled.evidence[-1]}); an override cannot dispatch it")
    reason = item.get("reason_code") or f"override:{item['strategy']}"
    family = item.get("family") if item.get("family") is not None else (
        ruled.family if item["strategy"] in DISPATCHABLE + ("bridge-runtime",) else None)
    decision = Decision(
        package_id=f.package_id, strategy=item["strategy"], role=item["role"], reason_code=reason,
        rule="override", quarantine=bool(item.get("quarantine", False)) or ruled.quarantine,
        variant_of=item.get("variant_of"), family=family, justification=item["justification"],
        partner=item.get("partner"), flagship=bool(item.get("flagship", False)), wave=item.get("wave"),
        entry_symbols=[dict(symbol) for symbol in item.get("entry_symbols") or []],
        capability_classes=[str(cap) for cap in item.get("capability_classes") or []],
        omit_sim_contract=item.get("omit_sim_contract") is True,
        publish_review=item.get("publish_review"),
        modes=[str(mode) for mode in item.get("modes") or []],
        companions=[dict(entry) for entry in item.get("companions") or []],
        served_mode=item.get("served_mode"),
        evidence=[f"override ({item.get('_file', 'overrides')}): {item['justification']}",
                  f"rules alone: {ruled.strategy} ({ruled.reason_code}, rule {ruled.rule})"],
    )
    return decision


# ---------------------------------------------------------------------------
# decision
# ---------------------------------------------------------------------------

def _finish(f: RepoFacts, d: Decision) -> Decision:
    """Attach helper, helper status and blocked_on from the family table."""
    if d.strategy in DISPATCHABLE:
        fam = FAMILIES[d.family or "python-object"]
        d.family = fam.name
        d.helper = fam.helper
        d.helper_status = "available" if fam.helper else "blocked"
        if fam.prerequisite and fam.prerequisite not in d.blocked_on:
            d.blocked_on.append(fam.prerequisite)
    else:
        d.helper = None
        d.helper_status = None
    if d.quarantine and "QUARANTINE" not in d.blocked_on:
        d.blocked_on.append("QUARANTINE")
    d.blocked_on.sort()
    return d


def decide(f: RepoFacts, ctx: Context, overrides: Mapping[str, Mapping[str, Any]] | None = None) -> Decision:
    """Run the ordered rules (first match wins), then apply a curated override."""
    ruled: Decision | None = None
    for _number, rule in RULES:
        ruled = rule(f, ctx)
        if ruled is not None:
            break
    assert ruled is not None  # rule 11 always matches
    signals = lure_signals(f)
    if signals:
        ruled.quarantine = True
        if ruled.rule != 3:
            ruled.role = "not-device" if ruled.strategy == "skip" else ruled.role
            ruled.evidence.append("quarantined: " + signals[0])
    audit_head = f.git.get("audit_head")
    if audit_head and f.git.get("commit") and audit_head != f.git.get("commit"):
        ruled.evidence.append(f"HEAD {f.git['commit'][:12]} moved since the clone audit ({audit_head[:12]})")
    override = (overrides or {}).get(f.package_id)
    if override is not None:
        ruled = apply_override(f, override, _finish(f, ruled))
    return _finish(f, ruled)


def triage(facts: list[RepoFacts], overrides: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Decision]:
    """Decisions for a whole corpus, keyed and ordered by package_id."""
    ctx = Context(facts)
    return OrderedDict((f.package_id, decide(f, ctx, overrides)) for f in sorted(facts, key=lambda x: x.package_id))


def summarize(decisions: Mapping[str, Decision]) -> dict[str, Any]:
    ds = list(decisions.values())
    return {
        "total": len(ds),
        "by_strategy": dict(sorted(Counter(d.strategy for d in ds).items())),
        "by_role": dict(sorted(Counter(d.role for d in ds).items())),
        "by_strategy_role": dict(sorted(Counter(f"{d.strategy}/{d.role}" for d in ds).items())),
        "by_rule": dict(sorted(Counter(str(d.rule) for d in ds).items(), key=lambda kv: (len(kv[0]), kv[0]))),
        "by_reason": dict(sorted(Counter(d.reason_code for d in ds).items())),
        "by_family": dict(sorted(Counter(d.family for d in ds if d.strategy in DISPATCHABLE).items())),
        # decision level only: the task cards' dispatchable count (taskcards.dispatchable_now) also applies
        # recon:entry_symbol and the driver package status, and is the authoritative figure
        "dispatchable_decisions": sum(1 for d in ds if d.strategy in DISPATCHABLE
                                      and d.helper_status == "available" and not d.blocked_on and not d.quarantine),
        "quarantine": sum(1 for d in ds if d.quarantine),
        "variants": sum(1 for d in ds if d.variant_of),
        "overrides": sum(1 for d in ds if d.rule == "override"),
    }


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

def _read_jsonl(path: str) -> list[dict[str, Any]]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def load_catalog_notes(path: str = CATALOG_CSV) -> dict[int, dict[str, str]]:
    """Catalogue CSV record number -> the fields triage reads (fork notes)."""
    out: dict[int, dict[str, str]] = {}
    if not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            out[i + 2] = {k: row.get(k) or "" for k in ("relation_to_other_projects", "limitations")}
    return out


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in ("true", "yes", "1")


def facts_from_record(record: Mapping[str, Any], profile: Mapping[str, Any] | None,
                      lock: Mapping[str, Any] | None, scan: Mapping[str, Any] | None,
                      notes: Mapping[int, Mapping[str, str]] | None = None,
                      audit: Mapping[str, Any] | None = None) -> RepoFacts:
    """Assemble :class:`RepoFacts` from a registry record and the optional inputs."""
    profile = profile or {}
    vendor = (record.get("x-vendor") or {}).get("catalog") or {}
    pcat = profile.get("catalog") or {}
    catalog = {
        "adapter_role": str(pcat.get("adapter_role") or vendor.get("adapter_role_zh") or ""),
        "category": str(pcat.get("category") or vendor.get("category_zh") or ""),
        "description_zh": str(pcat.get("description_zh") or vendor.get("description_zh") or ""),
        "relation_to_other_projects": str(pcat.get("relation_to_other_projects") or ""),
        "limitations": str(pcat.get("limitations") or ""),
        "priority": str(pcat.get("priority") or vendor.get("priority") or ""),
    }
    def known(value: Any) -> str:
        text = str(value or "").strip()
        return "" if text.lower() in ("unknown", "none", "n/a") else text

    for key in ("relation_to_other_projects", "limitations"):
        catalog[key] = known(catalog[key])
    for row in [vendor.get("row")] + list(vendor.get("rows_all") or []):
        extra = (notes or {}).get(row) if isinstance(row, int) else None
        for key in ("relation_to_other_projects", "limitations"):
            value = known((extra or {}).get(key))
            if value and value not in catalog[key]:
                catalog[key] = (catalog[key] + " " + value).strip()
    classification = profile.get("classification") or {}
    mhs = profile.get("mhs") or {}
    analyst = {
        "family": classification.get("family"),
        "tier": classification.get("tier"),
        "flags": list((profile.get("quality") or {}).get("flags") or []),
        "mhs_claim": mhs.get("claim_class"),
    }
    lock = lock or {}
    audit = audit or {}
    git = {"repo_url": lock.get("repo_url"), "commit": lock.get("commit")}
    if not lock and audit:  # no corpus lock yet: fall back to the 2026-10-12 clone audit
        origin = str(audit.get("origin") or "").rstrip("/")
        git = {"repo_url": origin[:-4] if origin.endswith(".git") else (origin or None),
               "commit": audit.get("head") if audit.get("valid_head") else None}
    if audit:
        git["audit_head"] = audit.get("head")
        git["audit_issues"] = sorted(str(i) for i in audit.get("issues") or [])
    track, owner, repo = str(record["local_path"]).split("/")[:3]
    # the catalogue classifier's tier and family, as build_registry.py had them before triage
    # (a committed record carries the triaged tier and family; the rules must see the same input)
    cls = (record.get("x-vendor") or {}).get("classification") or {}
    tier = cls.get("catalog_tier") or record.get("tier") or "C"
    families = [cls["catalog_family"]] if cls.get("catalog_family") else list(record.get("families") or [])
    return RepoFacts(
        package_id=record["package_id"], local_path=record["local_path"], track=track, owner=owner, repo=repo,
        tier=tier, families=families,
        stars=int(record.get("stars") or 0), archived=_truthy(vendor.get("archived") or pcat.get("archived")),
        catalog=catalog, analyst=analyst, git=git, scan=dict(scan) if scan is not None else None,
    )


def _scan_one(args: tuple[str, str, str, str, str | None]) -> tuple[str, dict[str, Any] | None]:
    workspace, local_path, owner, repo, commit = args
    root = os.path.join(workspace, local_path)
    if not os.path.isdir(root):
        return local_path, None
    return local_path, SS.scan_repo(root, owner, repo, commit)


def scan_corpus(workspace: str, local_paths: list[str], jobs: int = 1, cache_dir: str | None = None,
                commits: Mapping[str, str | None] | None = None) -> dict[str, dict[str, Any] | None]:
    """Scan clones (optionally in parallel and cached by commit + scanner version)."""
    out: dict[str, dict[str, Any] | None] = {}
    todo = []
    for lp in local_paths:
        cached = _cache_get(cache_dir, lp, (commits or {}).get(lp))
        if cached is not None:
            out[lp] = cached
        else:
            _t, owner, repo = lp.split("/")[:3]
            todo.append((workspace, lp, owner, repo, (commits or {}).get(lp)))
    if jobs > 1 and len(todo) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(_scan_one, todo, chunksize=4))
    else:
        results = [_scan_one(t) for t in todo]
    for lp, facts in results:
        out[lp] = facts
        _cache_put(cache_dir, lp, (commits or {}).get(lp), facts)
    return out


def _cache_file(cache_dir: str, local_path: str, commit: str | None) -> str | None:
    if not cache_dir or not commit:
        return None
    return os.path.join(cache_dir, f"v{SS.SCAN_VERSION}", local_path.replace("/", "__") + f"@{commit}.json")


def _cache_get(cache_dir: str | None, local_path: str, commit: str | None) -> dict[str, Any] | None:
    path = _cache_file(cache_dir or "", local_path, commit)
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cache_put(cache_dir: str | None, local_path: str, commit: str | None, facts: dict[str, Any] | None) -> None:
    path = _cache_file(cache_dir or "", local_path, commit)
    if not path or facts is None:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(facts, fh, sort_keys=True)


def load_corpus_facts(workspace: str = WORKSPACE, jobs: int = 1, cache_dir: str | None = None,
                      records_dir: str = REPOS_DIR, only: Iterable[str] | None = None) -> list[RepoFacts]:
    """Facts for every committed registry record whose clone is in ``workspace``."""
    records = []
    for path in sorted(glob.glob(os.path.join(records_dir, "*", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            records.append(json.load(fh))
    wanted = set(only or [])
    if wanted:
        records = [r for r in records if r["package_id"] in wanted]
    profiles = {}
    for obj in _read_jsonl(os.path.join(workspace, "work", "analysis", "repo_profiles.jsonl")):
        if obj.get("owner") and obj.get("repo"):
            profiles[(str(obj["owner"]).lower(), str(obj["repo"]).lower())] = obj
    locks = {e["local_path"]: e for e in _read_jsonl(LOCK_PATH)}
    audits = {}
    for obj in _read_jsonl(os.path.join(workspace, "clone_audit_2026-10-12", "baseline.jsonl")):
        slug = str(obj.get("directory_slug") or "").lower()
        if slug:
            audits[slug] = obj
    notes = load_catalog_notes(os.path.join(workspace, "openai4s_backend_catalog_all_sources",
                                            "openai4s_backend_catalog.csv"))
    commits = {lp: e.get("commit") for lp, e in locks.items()}
    scans = scan_corpus(workspace, [r["local_path"] for r in records], jobs=jobs, cache_dir=cache_dir,
                        commits=commits)
    out = []
    for record in records:
        _t, owner, repo = record["local_path"].split("/")[:3]
        out.append(facts_from_record(record, profiles.get((owner.lower(), repo.lower())),
                                     locks.get(record["local_path"]), scans.get(record["local_path"]), notes,
                                     audits.get(f"{owner}/{repo}".lower())))
    return out


def format_summary(summary: Mapping[str, Any]) -> str:
    lines = [f"triage {TRIAGE_VERSION}: {summary['total']} repos; dispatchable decisions "
             f"{summary['dispatchable_decisions']} (the cards' count, which also applies recon:entry_symbol, "
             f"is authoritative); "
             f"quarantined {summary['quarantine']}; variants {summary['variants']}; overrides {summary['overrides']}"]
    for key in ("by_strategy", "by_role", "by_rule", "by_family", "by_strategy_role"):
        lines.append(f"{key}:")
        for name, count in summary[key].items():
            lines.append(f"  {name:32} {count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--jobs", type=int, default=1, help="parallel scan workers")
    parser.add_argument("--cache", default=os.environ.get("MHS_TRIAGE_CACHE"),
                        help="directory for cached scan facts (keyed by commit and scanner version)")
    parser.add_argument("--out", help="write one decision per line (JSONL) to this file")
    parser.add_argument("--only", action="append", default=[],
                        help="triage only this package_id (repeatable); duplicate detection (rule 5) then "
                             "compares the selected repos only, so a full run is authoritative")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)
    facts = load_corpus_facts(jobs=args.jobs, cache_dir=args.cache, only=args.only)
    if not facts:
        print("[triage] no registry records found", file=sys.stderr)
        return 2
    overrides = load_overrides()
    stale = unknown_overrides(overrides, (f.package_id for f in facts)) if not args.only else []
    for pid in stale:
        print(f"[triage] ERROR override for {pid}, which is not a registry record", file=sys.stderr)
    decisions = triage(facts, overrides)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            for d in decisions.values():
                fh.write(json.dumps(d.to_json(), ensure_ascii=False) + "\n")
    summary = summarize(decisions)
    print(json.dumps(summary, indent=1) if args.json else format_summary(summary))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
