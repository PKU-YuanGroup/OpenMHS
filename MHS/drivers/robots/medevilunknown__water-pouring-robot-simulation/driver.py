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
but its dynamics are a kinematic placeholder, not MuJoCo; it was never compared with the upstream environment.  Every
Fact cites a line of the clone at commit ``ff33ae12ae58ef9569ff40d75c88635a14c61d27``.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

POUR_ENV = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/pour_env.py"
SCENE = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/scene.xml"
SO101 = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/so101_new_calib.xml"
README = "workshop/dev/docker/workspace/src/so101_mujoco/mujoco/README.md"


class So101Pour(GymnasiumDriver):
    device_id = "so101-pour"
    native = "so101_mujoco.mujoco.pour_env:So101PourEnv"
    backends = {"fake": ".fake:FakeSo101PourEnv"}
    action_space_ref = f"{POUR_ENV}:19"
    display_name = "SO-101 pouring simulation (So101PourEnv)"
    vendor, model = "medevilunknown", "So101PourEnv"
    tags = ["so101", "robot-arm", "pouring", "manipulation", "mujoco", "gymnasium", "reinforcement-learning",
            "simulation"]
    facts = [
        Fact("The entry class So101PourEnv is a subclass of gym.Env", source="upstream_code", ref=f"{POUR_ENV}:7"),
        Fact("So101PourEnv loads a MuJoCo model from the xml_path argument, whose default is scene.xml, and creates "
             "MjData from that model", source="upstream_code", ref=f"{POUR_ENV}:13-16"),
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
