"""OpenMHS driver for gh.medevilunknown/water-pouring-robot-simulation: the SO-101 pouring environment.

The card's entry symbol is ``so101_mujoco.mujoco.pour_env:So101PourEnv``
(``workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py:7``), a Gymnasium environment that wraps a
MuJoCo model.  The card says ``family: mujoco`` and ``helper: MujocoDriver``, but the upstream class is not a bare
``mujoco`` model/data pair: it owns the model and data, exposes a six-value continuous action space and an
eighteen-value observation, and implements reset, step, water flow, reward and termination itself.  A
``MujocoDriver`` would expose raw ``data.ctrl`` bounded by ``actuator_ctrlrange`` and an observation of
``time``/``qpos``/``qvel`` instead of ``So101PourEnv.action_space`` and ``step()``.  This package therefore uses
``GymnasiumDriver``, which serves exactly the upstream ``reset(seed, options)`` and ``step(action)`` and derives the
input schema from the environment's spaces (DEVIATION FROM THE CARD: helper GymnasiumDriver).  The decision
``family-config`` is unchanged.

``cap.world.step.v1`` takes ``{ticks, action: {values: [six numbers in -1..1]}}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware
backend and no e-stop path to a machine.  The e-stop is the runtime's software latch; the environment state stays
readable and no step or reset is accepted until ``mhs.safety.reset`` clears it.

The gate cannot import mujoco, gymnasium or numpy, so the ``fake`` backend is the package's own pure Python stand-in
(``fake.py``).  It has the public methods the upstream class has (``reset``, ``step``) and duck-types the two spaces,
but its dynamics are a kinematic placeholder, not MuJoCo; it was never compared with the upstream environment.

``So101PourEnv`` is not registered with Gymnasium.  The module's own script and the root README construct the class
directly (``pour_env.py:97``, ``README.md:125-126``), and the constructor loads ``xml_path``, whose default is the
relative name ``scene.xml`` (``pour_env.py:13-15``).  The clone has no setup.py.  With the pinned clone root on
``PYTHONPATH``, the class file is
``workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py`` (``pour_env.py:7``), so that root exposes it
as ``workshop.dev.docker.workspace.src.so101_mujoco.mujoco.pour_env``.  The ``sim`` backend is ``_build_sim_env``:
it imports that module and constructs ``So101PourEnv`` with the absolute path of the ``scene.xml`` beside it.
MuJoCo resolves the include and ``meshdir="../meshes"`` (``so101_new_calib.xml:6``) from that file.  The import
stays inside the factory, so the fake backend does not import MuJoCo.  The returned object is the upstream
instance.  The real upstream was not installed, imported or run in this workspace.  Every Fact cites a line of the
clone at commit ``ff33ae12ae58ef9569ff40d75c88635a14c61d27``.  This package is model-authored and unreviewed.
"""

from pathlib import Path

from mhs.driver import Fact, GymnasiumDriver

POUR_ENV = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py"
SCENE = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/scene.xml"
SO101 = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/so101_new_calib.xml"
README = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/README.md"
ROOT_README = "README.md"


def _build_sim_env(**_options):
    """Build the real ``So101PourEnv`` (``pour_env.py:7``) for the ``sim`` backend.

    Nothing in the clone calls ``gymnasium.register``.  ``pour_env.py:97`` and ``README.md:125-126`` construct
    ``So101PourEnv()`` after the process can import ``pour_env`` (the README first changes into the mujoco
    directory, ``README.md:112``).  The clone has no setup.py, so the sim run puts the archive root on
    ``PYTHONPATH``.  The class file is ``workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py``
    (``pour_env.py:7``), which that root exposes as
    ``workshop.dev.docker.workspace.src.so101_mujoco.mujoco.pour_env``.  The constructor's default ``xml_path``
    is the relative name ``scene.xml`` (``pour_env.py:13-15``), so the call passes the absolute path of the
    ``scene.xml`` beside the imported module.  MuJoCo resolves the include and ``meshdir="../meshes"``
    (``so101_new_calib.xml:6``) from that file.  The fake backend never calls this function.
    """
    import workshop.dev.docker.workspace.src.so101_mujoco.mujoco.pour_env as pour_env

    scene = Path(pour_env.__file__).resolve().parent / "scene.xml"
    return pour_env.So101PourEnv(xml_path=str(scene))


class So101Pour(GymnasiumDriver):
    device_id = "so101-pour"
    native = "so101_mujoco.mujoco.pour_env:So101PourEnv"
    #: ``fake`` is this package's stand-in.  ``sim`` constructs ``So101PourEnv`` (``pour_env.py:7``) through
    #: ``_build_sim_env``.  The sim entry is a callable, so the lock's string entry (``fake`` only) still describes
    #: the package's declared string backend.
    backends = {"fake": ".fake:FakeSo101PourEnv", "sim": _build_sim_env}
    action_space_ref = f"{POUR_ENV}:19"
    display_name = "SO-101 pouring simulation (So101PourEnv)"
    vendor, model = "medevilunknown", "So101PourEnv"
    tags = ["so101", "robot-arm", "pouring", "manipulation", "mujoco", "gymnasium", "reinforcement-learning",
            "simulation"]
    facts = [
        Fact("The entry class So101PourEnv is a subclass of gym.Env", source="upstream_code", ref=f"{POUR_ENV}:7"),
        Fact("So101PourEnv loads a MuJoCo model from the xml_path argument, whose default is scene.xml, and creates "
             "MjData from that model", source="upstream_code", ref=f"{POUR_ENV}:13-16"),
        Fact("The module's own script constructs So101PourEnv() with that default path", source="upstream_code",
             ref=f"{POUR_ENV}:97"),
        Fact("The root README changes into the mujoco directory before running the scripts that import pour_env",
             source="vendor_doc", ref=f"{ROOT_README}:112"),
        Fact("The root README imports So101PourEnv from pour_env and constructs it with no arguments",
             source="vendor_doc", ref=f"{ROOT_README}:125-126"),
        Fact("The root README's install line is pip install mujoco ultralytics groq opencv-python gymnasium numpy",
             source="vendor_doc", ref=f"{ROOT_README}:102"),
        Fact("The root README requires MuJoCo >= 3.3 and says this simulation was tested with 3.3.7",
             source="vendor_doc", ref=f"{ROOT_README}:105"),
        Fact("The action space is a continuous Box of six values from -1 to 1: five arm joint targets and one "
             "absolute gripper command", source="upstream_code", ref=f"{POUR_ENV}:18-19"),
        Fact("The observation space is a Box of eighteen unbounded values: five arm joint positions, five arm joint "
             "velocities, one gripper width, three bottle coordinates, three beaker coordinates and one beaker "
             "volume", source="upstream_code", ref=f"{POUR_ENV}:21-23"),
        Fact("The constructor initializes beaker_ml to 0.0, target_ml to 100.0, max_steps to 500 and current_step to "
             "0", source="upstream_code", ref=f"{POUR_ENV}:29-32"),
        Fact("reset(seed, options) calls gym.Env.reset(seed), restores the MuJoCo data with mj_resetData, zeroes "
             "beaker_ml and current_step and returns _get_obs() with an empty info dict", source="upstream_code",
             ref=f"{POUR_ENV}:34-39"),
        Fact("step increments current_step, adds action[:5]*0.05 to ctrl[:5], sets ctrl[5] to action[5] and advances "
             "MuJoCo with mj_step", source="upstream_code", ref=f"{POUR_ENV}:41-50"),
        Fact("Water flow starts only when the bottle tilt is above 30 degrees and is 25.0 * min(1, (tilt-30)/60) "
             "times the model timestep, added to beaker_ml", source="upstream_code", ref=f"{POUR_ENV}:52-56"),
        Fact("The episode terminates when beaker_ml reaches 150 or current_step reaches max_steps; truncated is "
             "always False", source="upstream_code", ref=f"{POUR_ENV}:60-61"),
        Fact("The observation concatenates qpos[:5], qvel[:5], the gripper joint position, the bottle site position, "
             "the beaker site position and beaker_ml into a float32 array", source="upstream_code",
             ref=f"{POUR_ENV}:65-71"),
        Fact("The reward is minus the distance between the gripperframe and bottle_grasp sites, plus "
             "10*(1-|beaker_ml-target_ml|/target_ml) while beaker_ml is positive, minus 50 while beaker_ml exceeds "
             "110", source="upstream_code", ref=f"{POUR_ENV}:73-86"),
        Fact("The bottle tilt is the angle between the water_bottle body's z axis and the world z axis, in degrees, "
             "computed from the body quaternion", source="upstream_code", ref=f"{POUR_ENV}:88-94"),
        Fact("The scene model includes so101_new_calib.xml", source="upstream_code", ref=f"{SCENE}:2"),
        Fact("The included robot model sets meshdir to ../meshes", source="upstream_code", ref=f"{SO101}:6"),
        Fact("The scene model sets the MuJoCo timestep to 0.002 s with the implicitfast integrator",
             source="upstream_code", ref=f"{SCENE}:5"),
        Fact("The imported model defines six position actuators (shoulder_pan, shoulder_lift, elbow_flex, "
             "wrist_flex, wrist_roll and gripper) with per-actuator ctrlrange bounds", source="upstream_code",
             ref=f"{SO101}:179-186"),
        Fact("The README calls So101PourEnv a standard Gymnasium environment for training low-level control "
             "policies", source="vendor_doc", ref=f"{README}:10"),
        Fact("The README says the control layer implements a standard Gymnasium API", source="vendor_doc",
             ref=f"{README}:24-25"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the deployed fake (spec 05-fidelity section 2).  The upstream is a MuJoCo
    #: rigid-body model (F1); the package's deployed fake is kinematic (F0) and says so in the gaps.
    fidelity = {
        "engine": "custom:So101PourEnv kinematic fake (upstream mujoco scene.xml not integrated)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "So101PourEnv.reset() restores the MuJoCo model defaults with mj_resetData and draws no "
                     "random initial state (pour_env.py:34-39), so a reset always starts from the same state; the "
                     "package's fake is deterministic and ignores the seed.  The same recorded seed and command "
                     "sequence therefore repeat a state-hash sequence in the fake, but no MuJoCo trajectory was run "
                     "or compared.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic fake only: joint positions move directly to the accumulated control target and water "
            "accumulates from a wrist-angle proxy; the fake integrates no MuJoCo rigid bodies, contacts, friction, "
            "gravity, position actuators or free bottle/beaker bodies",
            "the upstream So101PourEnv is a MuJoCo rigid-body simulation at a 0.002 s timestep (scene.xml:5); this "
            "package's fake is an F0 stand-in and no trajectory was compared with MuJoCo",
            "the fake's bottle and beaker site positions, initial joints and tilt mapping are placeholder test data "
            "(fake.py marks each with '# placeholder'); the upstream derives them from MuJoCo forward kinematics and "
            "the loaded scene.xml",
            "the fake does not parse scene.xml, so101_new_calib.xml or the mesh assets; it uses the cited 0.002 s "
            "timestep for the water-flow calculation but no model geometry",
            "the fake returns a Python list of 18 floats, while upstream returns a numpy float32 array",
            "no rendering: the bridge does not serve cap.world.render.v1 and the fake has no renderer",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: So101PourEnv defines neither get_state nor set_state",
            "no physical device is modelled and nothing was validated against hardware",
        ],
    }
    #: The sim backend is the upstream MuJoCo environment, not the kinematic fake.  The class contract above stays
    #: the fake's; this override replaces the members that would otherwise describe the fake.
    fidelity_by_backend = {
        "sim": {
            "engine": f"mujoco:{SCENE}",
            "fidelity_level": "F1",
            "determinism": {
                "kind": "seeded",
                "seed_control": "none",
                "notes": "So101PourEnv.reset(seed, options) calls gym.Env.reset(seed), then mj_resetData, and zeroes "
                         "beaker_ml and current_step (pour_env.py:34-39). The reset draws no random initial state, "
                         "so the same action sequence repeats from a fresh environment. The seed does not select "
                         "the start pose. So101PourEnv defines neither get_state nor set_state.",
            },
            "gaps": [
                "the sim backend is the upstream So101PourEnv loaded from scene.xml (pour_env.py:13-16); the "
                "default fake backend is the F0 kinematic stand-in and was not compared with this environment",
                "the constructor is called with the absolute path of the pinned scene.xml because the default "
                "xml_path is the relative name scene.xml (pour_env.py:13-15); the included model resolves meshes "
                "from meshdir ../meshes (so101_new_calib.xml:6)",
                "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the 0.002 s model "
                "timestep only (scene.xml:5)",
                "snapshot and restore are not offered: So101PourEnv defines neither get_state nor set_state",
                "no rendering: reset and step do not render (pour_env.py:34-63)",
                "no physical device is modelled and nothing was validated against hardware",
            ],
        },
    }
