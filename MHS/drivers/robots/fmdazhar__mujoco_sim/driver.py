"""OpenMHS driver for gh.fmdazhar/mujoco_sim: the ur5ePegInHoleGymEnv_easy-v0 Gymnasium environment.

The clone is a UR5e arm and Robotiq Hand-e gripper simulator written in MuJoCo (README.md:3-4).  It registers
six Gymnasium environments; this package targets ``ur5ePegInHoleGymEnv_easy-v0`` because that is the first
registered variant and the one the clone's own render test makes (mujoco_sim/test/test_gym_env_render.py:11).

A GymnasiumDriver is configuration only.  The bridge derives the whole contract from the environment's
spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` bounded by the action space
that ``XYZGripperCloseEnv`` installs (the first three elements of the base seven-element Box, i.e. x, y and z
in [-1, 1]; mujoco_sim/envs/wrappers.py:134-138), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

The ``fake`` backend is the package's own pure-Python stand-in (fake.py) and does not import the clone.
The ``sim`` backend is ``_build_sim_env``.  ``setup()`` declares no dependencies and no package data
(setup.py:3-8), so ``pip install .`` installs the Python modules and omits ``mujoco_sim/envs/xmls``.
``ur5ePegInHoleGymEnv`` loads ``xmls/ur5e_demos.xml`` from the directory of its own file
(ur5e_pick_gym_connector.py:17-18).  ``_build_sim_env`` therefore loads that file from the pinned checkout,
so ``__file__`` is the checkout path, then builds the easy variant the way ``register(...)`` does
(mujoco_sim/__init__.py:10-54): the same config and the same four wrappers.  The constructor always calls
``glfw.init`` (ur5e_pick_gym_connector.py:241-242) and the easy wrapper then opens a keyboard window
(wrappers.py:213-215, keyboard.py:21-22), so the sim run needs a display.  That sim path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity): MuJoCo rigid-body
dynamics at a 20 ms control step with a seeded reset, and ``gaps`` naming what this package's fake does not
model.  This package is model-authored and unreviewed: it is checked on the fake backend only, and its
evidence is ``contract_checked``, never an MHS-Device level.
"""

import importlib.util
from pathlib import Path

from mhs.driver import Fact, GymnasiumDriver

#: The gate mounts this worktree (``robots`` is the corpus clone) and mounts ``/src`` only when the install
#: put an unpackaged tree on ``PYTHONPATH``.  Either root is the pinned commit.
_CLONE = Path("robots/fmdazhar/mujoco_sim")
_ENV_REL = Path("mujoco_sim/envs/ur5e_pick_gym_connector.py")
_XML_REL = Path("mujoco_sim/envs/xmls/ur5e_demos.xml")
#: kwargs of the easy registration (mujoco_sim/__init__.py:44-54).
_EASY_CONFIG = {
    "ENV_CONFIG": {"version": 0},
    "UR5E_CONFIG": {"tcp_xyz_randomize": True, "mocap_orient": True},
}
#: keys_to_keep of the easy CustomObsWrapper (mujoco_sim/__init__.py:27-36).
_EASY_KEYS = (
    "connector_pose",
    "controller_pose",
    "ur5e/tcp_pose",
    "ur5e/tcp_vel",
    "ur5e/wrist_force",
    "ur5e/wrist_torque",
)

REGISTRATION = "mujoco_sim/__init__.py"
ENV = "mujoco_sim/envs/ur5e_pick_gym_connector.py"
WRAPPERS = "mujoco_sim/envs/wrappers.py"
CONFIG = "mujoco_sim/config/config.py"
BASE = "mujoco_sim/mujoco_gym_env.py"


def _pinned_checkout() -> Path:
    """The pinned checkout that holds the env module and ``xmls/ur5e_demos.xml`` beside it.

    ``setup.py:6`` is ``find_packages()`` with no ``package_data`` (setup.py:3-8), so the wheel omits
    ``mujoco_sim/envs/xmls``.  ``ur5e_pick_gym_connector.py:17-18`` loads that XML from ``Path(__file__).parent``.
    """
    here = Path(__file__).resolve()
    roots = [Path("/src")]
    roots.extend(parent / _CLONE for parent in here.parents)
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        try:
            if (root / _ENV_REL).is_file() and (root / _XML_REL).is_file():
                return root
        except OSError:
            continue
    raise FileNotFoundError(
        f"{_XML_REL.as_posix()} is not under /src or the pinned clone {_CLONE.as_posix()}")


def _easy_env_class():
    """Load ``ur5ePegInHoleGymEnv`` from the checkout file so ``__file__`` resolves the XML.

    The file is loaded by its path and is not inserted into the import table.  Its ``mujoco_sim.*`` imports
    still come from the installed package (the same Python modules ``pip install .`` ships).  ``_XML_PATH``
    is computed in this module (ur5e_pick_gym_connector.py:17-18), so the class defined here opens the
    checkout's ``xmls/ur5e_demos.xml`` and the meshes that file includes (ur5e1.xml:68-93).
    """
    path = (_pinned_checkout() / _ENV_REL).resolve()
    spec = importlib.util.spec_from_file_location("ur5e_pick_gym_connector", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the pinned {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loaded = getattr(module, "__file__", None)
    if loaded is None or Path(loaded).resolve() != path:
        raise ImportError(f"loaded {loaded}, not the pinned {path}")
    return module.ur5ePegInHoleGymEnv


def _build_sim_env(**_options):
    """Build the real easy variant the way ``register`` does (mujoco_sim/__init__.py:10-54).

    The constructor is called with the registration's ``config`` (mujoco_sim/__init__.py:44-54) and the
    default ``render_mode`` ``"rgb_array"`` (ur5e_pick_gym_connector.py:38).  The four wrappers are applied
    in the registration's order (mujoco_sim/__init__.py:13-42).  The returned object is that wrapped
    upstream environment.
    """
    env = _easy_env_class()(config=_EASY_CONFIG)
    from gymnasium.wrappers import FlattenObservation
    from mujoco_sim.envs.wrappers import CustomObsWrapper, SpacemouseIntervention, XYZGripperCloseEnv

    env = XYZGripperCloseEnv(env)
    env = SpacemouseIntervention(env)
    env = CustomObsWrapper(env, keys_to_keep=list(_EASY_KEYS))
    return FlattenObservation(env)


class UR5ePegInHole(GymnasiumDriver):
    device_id = "ur5e-peg-in-hole"
    env_id = "ur5ePegInHoleGymEnv_easy-v0"
    env_module = "mujoco_sim"  # importing it runs register(...) at mujoco_sim/__init__.py:10-12
    native = "mujoco_sim.envs:ur5ePegInHoleGymEnv"
    #: ``fake`` is this package's stand-in.  ``sim`` is a callable, so the lock's string backends stay the
    #: fake entry only (check.py compares string entries when every entry is a string).
    backends = {"fake": ".fake:FakeUR5ePegInHoleEnv", "sim": _build_sim_env}
    display_name = "mujoco_sim UR5e peg-in-hole (ur5ePegInHoleGymEnv_easy-v0)"
    vendor, model = "fmdazhar", "mujoco_sim"
    tags = ["ur5e", "peg-in-hole", "mujoco", "manipulation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The clone is a UR5e arm and Robotiq Hand-e gripper simulator with a state-based peg-in-hole "
             "Gymnasium environment and custom Gymnasium wrappers",
             source="vendor_doc", ref="README.md:3-4"),
        Fact("Importing mujoco_sim registers ur5ePegInHoleGymEnv_easy-v0 with entry point "
             "mujoco_sim.envs:ur5ePegInHoleGymEnv",
             source="upstream_code", ref=f"{REGISTRATION}:10-12"),
        Fact("setup() names the package and find_packages() and declares no install_requires and no package_data",
             source="upstream_code", ref="setup.py:3-8"),
        Fact("The environment loads the MuJoCo model from xmls/ur5e_demos.xml beside the env module",
             source="upstream_code", ref=f"{ENV}:17-18"),
        Fact("The constructor calls glfw.init and reads the primary monitor size for every render mode",
             source="upstream_code", ref=f"{ENV}:240-242"),
        Fact("The env module imports SliderController and ForceFeedback while the class module loads",
             source="upstream_code", ref=f"{ENV}:11-12"),
        Fact("ForceFeedback's module imports tkinter and matplotlib at import time",
             source="upstream_code", ref="mujoco_sim/utils/force_feedback.py:1-5"),
        Fact("SliderController's module imports tkinter at import time",
             source="upstream_code", ref="mujoco_sim/utils/slider_controller.py:1"),
        Fact("The renderer module imports imageio at module scope",
             source="upstream_code", ref="mujoco_sim/mujoco_rendering.py:6"),
        Fact("The wrapper module imports Keyboard and SpaceMouse at load time",
             source="upstream_code", ref=f"{WRAPPERS}:6-8"),
        Fact("SpacemouseIntervention tries SpaceMouse and on OSError constructs Keyboard",
             source="upstream_code", ref=f"{WRAPPERS}:209-215"),
        Fact("Keyboard opens a pygame display window in its constructor",
             source="upstream_code", ref="mujoco_sim/devices/keyboard.py:21-22"),
        Fact("SpaceMouse opens the HID device with hid.device().open",
             source="upstream_code", ref="mujoco_sim/devices/spacemouse.py:183-184"),
        Fact("The env module imports scipy.spatial.transform.Rotation, glfw and OpenGL at load time",
             source="upstream_code", ref=f"{ENV}:13-15"),
        Fact("The easy variant applies XYZGripperCloseEnv, SpacemouseIntervention, CustomObsWrapper and "
             "FlattenObservation", source="upstream_code", ref=f"{REGISTRATION}:13-42"),
        Fact("The easy registration passes config ENV_CONFIG version 0 and UR5E_CONFIG tcp_xyz_randomize True "
             "and mocap_orient True", source="upstream_code", ref=f"{REGISTRATION}:44-54"),
        Fact("The easy variant ends with gymnasium's FlattenObservation wrapper",
             source="upstream_code", ref=f"{REGISTRATION}:38-41"),
        Fact("The base action space is a seven-element Box from -1.0 to 1.0",
             source="upstream_code", ref=f"{ENV}:234-236"),
        Fact("XYZGripperCloseEnv narrows the action space to the first three elements (x, y, z) of the base Box",
             source="upstream_code", ref=f"{WRAPPERS}:134-138"),
        Fact("The observation space is a Dict of nine Box members, each bounded by +-1e6",
             source="upstream_code", ref=f"{ENV}:172-206"),
        Fact("The easy variant keeps connector_pose, controller_pose, ur5e/tcp_pose, ur5e/tcp_vel, "
             "ur5e/wrist_force and ur5e/wrist_torque", source="upstream_code", ref=f"{REGISTRATION}:27-36"),
        Fact("CustomObsWrapper rebuilds the state Dict with only the kept keys",
             source="upstream_code", ref=f"{WRAPPERS}:54-62"),
        Fact("controller_pose is a six-element array: the controller position and its orientation",
             source="upstream_code", ref=f"{ENV}:540-542"),
        Fact("control_dt is 0.02 s and physics_dt is 0.002 s",
             source="upstream_code", ref=f"{CONFIG}:13-14"),
        Fact("n_substeps is int(control_dt // physics_dt), so one control step runs ten physics steps",
             source="upstream_code", ref=f"{BASE}:34-36"),
        Fact("_max_episode_steps is 1000.0", source="upstream_code", ref=f"{CONFIG}:15"),
        Fact("step sets truncated once _elapsed_steps reaches _max_episode_steps",
             source="upstream_code", ref=f"{ENV}:471-475"),
        Fact("step returns observation, reward, terminated, truncated and info",
             source="upstream_code", ref=f"{ENV}:476"),
        Fact("reset returns the observation and an empty info dict",
             source="upstream_code", ref=f"{ENV}:391-393"),
        Fact("reset accepts an optional seed argument", source="upstream_code", ref=f"{ENV}:257"),
        Fact("Port randomization draws with np.random.uniform from numpy's global generator, so the reset seed "
             "argument does not seed it", source="upstream_code", ref=f"{ENV}:276-279"),
        Fact("reward_shaping is False and sparse_reward_weights is 0 by default",
             source="upstream_code", ref=f"{CONFIG}:88-92"),
        Fact("The step returns the sparse reward while reward_shaping is False",
             source="upstream_code", ref=f"{ENV}:721-723"),
        Fact("task_complete_tolerance is 0.0025", source="upstream_code", ref=f"{CONFIG}:93"),
        Fact("The task is complete when the connector-to-port distance is below the tolerance",
             source="upstream_code", ref=f"{ENV}:710"),
        Fact("The UR5e home joint position is [-1.907, -1.565, 2.350, -2.355, -1.571, 1.234]",
             source="upstream_code", ref=f"{CONFIG}:40"),
        Fact("The default Cartesian workspace bounds are [0.2, -0.3, 0.0] to [0.6, 0.3, 0.05]",
             source="upstream_code", ref=f"{CONFIG}:41"),
        Fact("The environment declares the render modes human and rgb_array",
             source="upstream_code", ref=f"{ENV}:30-35"),
        Fact("The clone pins mujoco 3.2.5 and gymnasium 1.0.0",
             source="upstream_code", ref="requirements.txt:2-3"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:ur5ePegInHoleGymEnv_easy-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) and is deterministic afterwards, "
                     "so one seed repeats a trajectory of this package; the upstream reset accepts a seed but "
                     "draws the port and controller randomization from numpy's global generator "
                     "(ur5e_pick_gym_connector.py:276-279), so a seed does not fix those draws upstream and the "
                     "two backends do not start from the same state",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed model is MuJoCo rigid-body dynamics with contacts (F1), but the fake backend is a "
            "pure-Python kinematic stand-in: it models no rigid-body dynamics, contacts, friction, actuator "
            "forces, sensors or noise, and its start positions and step scale are placeholders",
            "the fake does not model the peg-in-hole task, the reward or task-success termination: it returns "
            "the sparse -1 reward, never terminates for success and only truncates at 1000 steps",
            "the fake uses Python's random.Random for its start noise while the upstream reset accepts a seed "
            "but draws from numpy's global generator, so one seed gives different starting states on the two",
            "the easy variant's SpacemouseIntervention wrapper opens a SpaceMouse or a keyboard at construction "
            "and ur5ePegInHoleGymEnv.__init__ calls glfw and creates a MuJoCo renderer, so the sim backend needs "
            "a display and input devices and was not run here",
            "the observation is the flattened 27-value array of the six kept members; its values are placeholder "
            "test data and were not compared with a MuJoCo run",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes get_state but no set_state, and the "
            "bridge requires both",
        ],
    }
