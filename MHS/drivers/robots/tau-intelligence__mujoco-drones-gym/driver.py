"""OpenMHS driver for gh.tau-intelligence/mujoco-drones-gym: the HoverAviary MuJoCo environment.

A GymnasiumDriver is configuration only: the bridge derives the ``cap.world.*`` contract from the environment's
spaces.  ``HoverAviary`` is a single-drone hover task (``multi_drone_mujoco/envs/hover_aviary.py:15``).  Its action
space is a 4-element Box of normalized RPM commands in [-1, 1] (``hover_aviary.py:51-53``) and its observation is the
12 values position, roll-pitch-yaw, linear velocity and angular velocity (``hover_aviary.py:68-73``).
``cap.world.step.v1`` therefore takes ``{ticks, action: {values}}`` with four bounded elements, ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no
hardware backend, no stop path to a machine and no operator-required limit.

The ``multi_drone_mujoco.envs`` package re-exports the environment classes
(``multi_drone_mujoco/envs/__init__.py:1-7``) and the upstream README constructs ``HoverAviary`` directly
(``README.md:67``).  Nothing in the clone calls ``register``, so ``env_id`` stays None.  The ``fake`` backend is
this package's pure Python stand-in (fake.py) and does not import the clone.  The ``sim`` backend is
``_build_sim_env``.  It records the checkout's ``assets/cf2`` in ``MJ_DRONES_CF2_ASSETS`` when that variable is
unset, then imports ``HoverAviary`` and calls it with no arguments, the construction in
``multi_drone_mujoco/tests/test_envs.py:63``.  ``base_aviary.py:27-28`` reads that variable once, at import, and
the generated XML names the mesh files under it (``base_aviary.py:111-121``).  ``pyproject.toml:35-36`` discovers
packages matching ``multi_drone_mujoco*`` and the project declares no package data, and ``setup.py:5-28`` is
``find_packages()`` with no ``package_data``, so the ``.obj`` files are not part of the installed distribution.
``gui`` and ``record`` stay the constructor defaults ``False`` (``hover_aviary.py:24-25``), so ``render_mode`` is
None (``base_aviary.py:368``) and no recording directory is created (``base_aviary.py:442-448``).  The factory
was not executed in this workspace.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit ca170dc6760d422e47ef46fb3af46f8cd20410eb.  This
package is model-authored and unreviewed.  This workspace checks the fake backend; the sim factory was not
executed here.
"""

from pathlib import Path

from mhs.driver import Fact, GymnasiumDriver

HOVER = "multi_drone_mujoco/envs/hover_aviary.py"
BASE = "multi_drone_mujoco/envs/base_aviary.py"
_CLONE = Path("robots") / "tau-intelligence" / "mujoco-drones-gym"
_CF2 = Path("multi_drone_mujoco") / "assets" / "cf2"
#: Ends of the two ranges the XML names (base_aviary.py:115-121).
_MESH_MARKERS = ("cf2_0.obj", "cf2_6.obj", "cf2_collision_0.obj", "cf2_collision_31.obj")


def _cf2_mesh_dir() -> Path | None:
    """Absolute ``assets/cf2`` of the pinned checkout, or None when those mesh files are not present.

    ``base_aviary.py:26-28`` uses ``MJ_DRONES_CF2_ASSETS`` when it is set and otherwise the ``assets/cf2``
    directory next to the imported module.  The XML names ``cf2_0.obj`` through ``cf2_6.obj`` and
    ``cf2_collision_0.obj`` through ``cf2_collision_31.obj`` under that directory (``base_aviary.py:115-121``).
    ``/src`` is the tree the install ran from; a checkout beside this package is the same commit when ``/src``
    does not hold the meshes.
    """
    here = Path(__file__).resolve()
    roots = [Path("/src")]
    roots.extend(parent / _CLONE for parent in here.parents)
    seen: set[Path] = set()
    for root in roots:
        directory = root / _CF2
        try:
            key = directory.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        try:
            if all((directory / name).is_file() for name in _MESH_MARKERS):
                return key
        except OSError:
            continue
    return None


def _build_sim_env(**_options):
    """Build the real ``HoverAviary`` for the ``sim`` backend.

    Nothing in the clone calls ``register``.  ``test_envs.py:63`` calls ``HoverAviary()``.  The constructor
    defaults are ``gui=False`` and ``record=False`` (``hover_aviary.py:24-25``), so ``render_mode`` stays None
    (``base_aviary.py:368``) and ``launch_passive`` is not called (``base_aviary.py:1064-1066``).  ``setdefault``
    records the checkout mesh directory before the import when ``MJ_DRONES_CF2_ASSETS`` is unset.  It does not
    assign an attribute of the imported package.  ``base_aviary.py:27-28`` reads the variable once, while that
    module loads, and ``base_aviary.py:25`` is the upstream hook for a different mesh checkout.  The returned
    object is that upstream instance; nothing on it is wrapped or replaced.
    """
    import os

    mesh_dir = _cf2_mesh_dir()
    if mesh_dir is not None:
        os.environ.setdefault("MJ_DRONES_CF2_ASSETS", str(mesh_dir))
    from multi_drone_mujoco.envs.hover_aviary import HoverAviary

    return HoverAviary()


class HoverAviary(GymnasiumDriver):
    device_id = "hover-aviary"
    env_id = None
    native = "multi_drone_mujoco.envs.hover_aviary:HoverAviary"
    #: ``fake`` is this package's stand-in.  ``sim`` calls HoverAviary (hover_aviary.py:15) through
    #: ``_build_sim_env``.  The sim entry is a callable, so the lock's string entry (``fake`` only) still
    #: matches: the lock comparison runs only when every declared backend is a string.
    backends = {"fake": ".fake:FakeHoverAviary", "sim": _build_sim_env}
    action_space_ref = f"{HOVER}:51-53"
    display_name = "MuJoCo multi-drone gym HoverAviary (single-drone hover)"
    vendor, model = "tau-intelligence", "HoverAviary"
    tags = ["mujoco", "quadcopter", "hover", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("HoverAviary is the single-drone hover task: hover at height 1.0 and remain stable",
             source="upstream_code", ref=f"{HOVER}:3"),
        Fact("The action is a 4-element normalized RPM command in [-1, 1]", source="upstream_code",
             ref=f"{HOVER}:5"),
        Fact("The action space is a Box with low -1 and high 1 for each of the 4 motors", source="upstream_code",
             ref=f"{HOVER}:51-53"),
        Fact("The observation is 12 values: position (3), roll-pitch-yaw (3), linear velocity (3) and angular "
             "velocity (3)", source="upstream_code", ref=f"{HOVER}:68-73"),
        Fact("The default simulation frequency is 240 Hz and the default control frequency is 48 Hz",
             source="upstream_code", ref=f"{HOVER}:22-23"),
        Fact("The control period is 1/ctrl_freq and the physics step is 1/sim_freq; the environment runs "
             "sim_freq/ctrl_freq physics sub-steps per control step", source="upstream_code",
             ref=f"{BASE}:350-354"),
        Fact("The default initial position is [0.0, 0.0, 0.1]", source="upstream_code",
             ref=f"{HOVER}:33-34"),
        Fact("EPISODE_LEN_SEC is 10 s", source="upstream_code", ref=f"{HOVER}:32"),
        Fact("The episode truncates when step_counter / SIM_FREQ reaches the episode length",
             source="upstream_code", ref=f"{HOVER}:113-115"),
        Fact("The episode terminates when the altitude is below 0 or above 3 m, or when the absolute roll or pitch "
             "exceeds pi/2", source="upstream_code", ref=f"{HOVER}:105-110"),
        Fact("The reward is -(height error) - 0.1*(xy error) - 0.05*|velocity| - 0.05*(|roll| + |pitch|), plus 1 "
             "when both errors are below 0.05 and -100 when terminated", source="upstream_code",
             ref=f"{HOVER}:83-95"),
        Fact("The info dict reports the position and the absolute height error", source="upstream_code",
             ref=f"{HOVER}:117-121"),
        Fact("reset(seed, options) delegates the seed to the Gymnasium base class, restores the initial position and "
             "orientation, zeroes step_counter and last_clipped_action, and returns the observation and info",
             source="upstream_code", ref=f"{BASE}:490-524"),
        Fact("step preprocesses the action, runs the physics sub-steps, increments step_counter by "
             "SIM_STEPS_PER_CTRL and returns observation, reward, terminated, truncated and info",
             source="upstream_code", ref=f"{BASE}:528-598"),
        Fact("With the MuJoCo physics mode each simulation sub-step advances the model with mujoco.mj_step",
             source="upstream_code", ref=f"{BASE}:577-579"),
        Fact("The package's runtime dependencies are gymnasium>=0.29.0, mujoco>=3.0.0 and numpy>=1.21.0; no "
             "hardware transport is declared", source="upstream_code", ref="setup.py:13-15"),
        Fact("The tests construct HoverAviary with no arguments", source="upstream_code",
             ref="multi_drone_mujoco/tests/test_envs.py:63"),
        Fact("The README constructs HoverAviary with ctrl_freq 48", source="upstream_code", ref="README.md:67"),
        Fact("HoverAviary defaults gui and record to false and target_height to 1.0, and leaves initial_xyzs None "
             "so the start pose is [[0.0, 0.0, 0.1]]", source="upstream_code", ref=f"{HOVER}:18-34"),
        Fact("CF2 meshes are read from MJ_DRONES_CF2_ASSETS, or from assets/cf2 beside the imported module when "
             "that variable is unset", source="upstream_code", ref=f"{BASE}:22-28"),
        Fact("The generated XML names cf2_0.obj through cf2_6.obj and cf2_collision_0.obj through "
             "cf2_collision_31.obj under that mesh directory", source="upstream_code", ref=f"{BASE}:111-121"),
        Fact("The constructor compiles that XML with mujoco.MjModel.from_xml_string", source="upstream_code",
             ref=f"{BASE}:419-429"),
        Fact("render_mode is human when gui is true and otherwise stays the passed value, which defaults to None",
             source="upstream_code", ref=f"{BASE}:368"),
        Fact("base_aviary imports mujoco.viewer at module scope", source="upstream_code", ref=f"{BASE}:15"),
        Fact("mujoco.viewer.launch_passive runs only when render_mode is human", source="upstream_code",
             ref=f"{BASE}:1064-1066"),
        Fact("A recording directory is created only when record is true", source="upstream_code",
             ref=f"{BASE}:442-448"),
        Fact("Package discovery includes names matching multi_drone_mujoco*", source="upstream_code",
             ref="pyproject.toml:35-36"),
        Fact("setup() installs find_packages() and does not set package_data", source="upstream_code",
             ref="setup.py:5-28"),
        Fact("Importing the package loads BaseAviary, which loads the mesh path at import time",
             source="upstream_code", ref="multi_drone_mujoco/__init__.py:11"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The upstream environment is a MuJoCo rigid-body world with
    #: contacts and an RPM-to-thrust/torque actuator; the fake backend is a pure Python stand-in (see the gaps).
    fidelity = {
        "engine": "mujoco:HoverAviary",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) records the seed and the hover start pose is fixed, so one action sequence repeats "
                     "from a reset; the fake is deterministic as well and makes no random draw",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python kinematic stand-in, not MuJoCo: it integrates placeholder "
            "accelerations and angular-rate gains, has no contacts, thrust/torque actuator, ground effect, drag, "
            "downwash, wind, obstacles or sensors, and was not compared with the upstream environment",
            "the sim backend constructs the upstream HoverAviary, a MuJoCo rigid-body model with contacts and an "
            "RPM-to-thrust/torque actuator; the fake was not compared with that environment",
            "no wall-clock pacing: realtime_factor 0, ticks advance the lockstep environment only",
            "timestep_ms is the physics step (1/240 s); one cap.world.step.v1 tick is one control step of 5 physics "
            "sub-steps (1/48 s, base_aviary.py:350-354, 585)",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }
