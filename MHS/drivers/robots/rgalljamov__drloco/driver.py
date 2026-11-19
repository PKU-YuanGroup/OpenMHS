"""OpenMHS driver for gh.rgalljamov/drloco: the walker3d_flat_feet MJCF (a MuJoCo family driver).

The card's entry symbols are the two Gym environment classes ``MimicWalker3dEnv`` and
``MimicWalker165cm65kgEnv`` (``drloco/mujoco/mimic_walker3d.py:27`` and
``drloco/mujoco/mimic_walker_165cm_65kg.py:20``).  They call the legacy ``MimicEnv`` constructor
(``drloco/mujoco/mimic_env.py:18``), which loads one bundled MJCF through gym's ``MujocoEnv`` and runs
``step(action)`` on it.  This package serves the card's ``models[0]``, the MJCF that the main entry
``MimicWalker3dEnv`` selects (``drloco/mujoco/mimic_walker3d.py:38``), through ``MujocoDriver``.

A ``MujocoDriver`` is configuration only: the bridge loads the model, derives ``action.ctrl`` from the
model's ``actuator_ctrlrange`` and serves ``cap.world.step.v1`` (``{ticks, action: {ctrl: [...]}}``) and
``cap.world.reset.v1``.  The world state is the bridge's integration state.  The upstream environment
layer is not served: its observations, normalized policy action, reward and reference-trajectory reset
are listed in the fidelity ``gaps`` below.  The model file is read in place from the read-only clone at
the pinned commit and is never copied into this package.

The device is simulated (R0): there is no hardware backend, no physical stop and no operator-required
limit.  MuJoCo and mujoco-py are not installed where the acceptance gate runs, so ``backends["fake"]``
is this package's pure Python stand-in ``mujoco`` module (fake.py).  It parses the same MJCF for the
joint dimensions, the actuator targets and the default motor control range, but its integration is a
placeholder motion, not MuJoCo's physics.  A backend name that ``backends`` does not list (``sim``)
imports the real ``mujoco`` module and loads the same file; that path was not run here.

Every Fact cites a line or line range of the clone at commit
3a1e4999b726be67dccc5d332b52edb76a7bde09.  This package is model-authored and unreviewed: it is checked
on the fake backend only, and no MuJoCo engine, simulator or hardware run is claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/.
MODEL = "drloco/mujoco/xml/walker3d_flat_feet.xml"
MODEL_PATH = "../../../../robots/rgalljamov/drloco/" + MODEL
ENV = "drloco/mujoco/mimic_env.py"
WALKER3D = "drloco/mujoco/mimic_walker3d.py"
WALKER165 = "drloco/mujoco/mimic_walker_165cm_65kg.py"
README = "README.md"
DOCS = "docs/scripts/mimic_env.rst"
CONFIG = "drloco/config/config.py"
HYPER = "drloco/config/hypers.py"
SIM_CONFIG = "drloco/mujoco/config.py"


class DrlocoWalker3d(MujocoDriver):
    device_id = "drloco-walker3d"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    model_path = MODEL_PATH
    # The fake is a stand-in ``mujoco`` module object, not a package class G7 can record: name the imported class,
    # as the other MuJoCo packages do, so the gate selects the simulator-family warning instead of a recorder proxy.
    backends = {"fake": FakeMujoco}
    display_name = "DRLoco walker3d walking simulation (walker3d_flat_feet MJCF)"
    vendor, model = "rgalljamov", "walker3d_flat_feet"
    tags = ["drloco", "deepmimic", "biped", "legged", "mujoco", "mjcf", "walker", "simulation"]
    facts = [
        Fact("The README titles the project Deep Reinforcement Learning by Imitation with MuJoCo and Stable "
             "Baselines 3", source="vendor_doc", ref=f"{README}:2"),
        Fact("The README says the repository implements DeepMimic and learns controllers for walking robots "
             "simulated with the MuJoCo physics engine", source="vendor_doc", ref=f"{README}:6-9"),
        Fact("The documentation says the environment's step runs the simulation for the configured number of "
             "frames and that the MuJoCo simulation runs at 1 kHz, with the policy control frequency equal to "
             "the simulation frequency divided by the frame skip", source="vendor_doc", ref=f"{DOCS}:21-29"),
        Fact("MimicEnv subclasses gym's MujocoEnv and gym.utils.EzPickle", source="upstream_code",
             ref=f"{ENV}:18"),
        Fact("MimicEnv reads the control frequency from the configuration, computes the frame skip from it and "
             "initializes MujocoEnv with the MJCF path and that frame skip", source="upstream_code",
             ref=f"{ENV}:47-52"),
        Fact("MimicEnv.step(action) rescales the action before applying it to the simulation", source="upstream_code",
             ref=f"{ENV}:60-83"),
        Fact("The upstream step applies the same action for the configured frame skip with do_simulation and, "
             "on a MuJoCo exception, resets the environment and ends the episode", source="upstream_code",
             ref=f"{ENV}:81-91"),
        Fact("The upstream step ends the episode when the COM z position is below 0.5 or the episode reaches "
             "the configured maximum length, and returns the old gym four-tuple (observation, reward, done, "
             "info)", source="upstream_code", ref=f"{ENV}:116-126"),
        Fact("The alive bonus is 0.2 and the maximum episode duration is 3000 control steps", source="upstream_code",
             ref=f"{HYPER}:51-58"),
        Fact("The default environment id is StraightMimicWalker with a control frequency of 200 Hz",
             source="upstream_code", ref=f"{CONFIG}:18-21"),
        Fact("The configured simulation frequency of StraightMimicWalker is 1000 Hz", source="upstream_code",
             ref=f"{SIM_CONFIG}:5-14"),
        Fact("_rescale_actions clips the policy action to [-1, 1] and scales each element by the action space's "
             "high or low value; the comment calls those the joint torque ranges "
             "specified in the MJCF file", source="upstream_code", ref=f"{ENV}:170-192"),
        Fact("The observation concatenates the phase variable, the desired walking speed, the joint positions "
             "without COM x and the joint velocities", source="upstream_code", ref=f"{ENV}:403-431"),
        Fact("The upstream reset_model takes the initial qpos and qvel from the reference trajectories and applies "
             "them to the simulation", source="upstream_code", ref=f"{ENV}:526-539"),
        Fact("The upstream reset lowers the COM z position by the lowest foot corner so that the walker starts in "
             "ground contact", source="upstream_code", ref=f"{ENV}:541-559"),
        Fact("MimicWalker3dEnv is the main 3D bipedal walker environment and loads "
             "drloco/mujoco/xml/walker3d_flat_feet.xml", source="upstream_code", ref=f"{WALKER3D}:27-40"),
        Fact("MimicWalker165cm65kgEnv loads drloco/mujoco/xml/walker_165cm_65kg.xml", source="upstream_code",
             ref=f"{WALKER165}:20-28"),
        Fact("The MJCF root element is <mujoco model=\"walker3d\"> and its compiler element declares angle radian, "
             "coordinate local and inertiafromgeom false", source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The default class gives every motor ctrllimited true, ctrlrange -300 300, gear 1, forcelimited true "
             "and forcerange -300 300", source="upstream_code", ref=f"{MODEL}:6-10"),
        Fact("The option element selects the RK4 integrator with timestep 0.001 s", source="upstream_code",
             ref=f"{MODEL}:11"),
        Fact("The torso body is at 0 0 1.08 and its inertial element gives mass 53.5", source="upstream_code",
             ref=f"{MODEL}:15-16"),
        Fact("The torso carries three slide joints (com_x, com_y, com_z) and three hinge joints (trunk_rot_x, "
             "trunk_rot_y, trunk_rot_z); com_z has joint position 0 0 -1.08 and ref 1.08", source="upstream_code",
             ref=f"{MODEL}:18-23"),
        Fact("The right leg has a sagittal hip joint with range -0.8727 0.8727 rad, a frontal hip joint with range "
             "-0.7854 0.0873 rad, a knee joint with range 0 2.6180 rad and an ankle joint with range -0.3491 0.6981 "
             "rad", source="upstream_code", ref=f"{MODEL}:28-37"),
        Fact("The left leg has a sagittal hip joint with range -0.8727 0.8727 rad, a frontal hip joint with range "
             "-0.0873 0.7854 rad, a knee joint with range 0 2.6180 rad and an ankle joint with range -0.3491 0.6981 "
             "rad", source="upstream_code", ref=f"{MODEL}:50-59"),
        Fact("The actuator section declares one motor actuator for each of the eight actuated leg joints",
             source="upstream_code", ref=f"{MODEL}:71-80"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state and stored ctrl are kept and stay readable. Safety reset advances no ticks and does not clear ctrl; a later explicit step without an action reuses it")
    #: The fidelity contract of the real engine path (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the timestep and the lockstep clock; the values are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:walker3d_flat_feet",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge reports determinism none: cap.world.reset.v1 restores the model defaults with "
                     "mj_resetData and takes no seed, and a native checkpoint does not establish hidden-state, "
                     "contact, plugin or RNG completeness.  The same state and controls repeat on one engine, but "
                     "no seed selects a different state.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the upstream environment layer is NOT COVERED: its step takes a policy action clipped to [-1, 1] and "
            "rescales it to the model's torque range (drloco/mujoco/mimic_env.py:170-192), its observation is the "
            "phase variable, desired speed, qpos and qvel vector (drloco/mujoco/mimic_env.py:403-431), its reward "
            "and termination are the DeepMimic imitation reward and the COM z and episode-length conditions "
            "(drloco/mujoco/mimic_env.py:116-126), and its reset starts from reference-trajectory qpos and qvel "
            "with a ground-contact shift (drloco/mujoco/mimic_env.py:526-559); the MuJoCo bridge instead exposes "
            "the model step and mj_resetData defaults, and takes the model's raw control vector",
            "the upstream uses the legacy mujoco_py binding (drloco/mujoco/mimic_env.py:7); this package loads the "
            "MJCF through the SDK's mujoco module, whose compiled model may differ",
            "only the card's models[0] is served: the also-shipped walker3d_hip3d.xml and walker_165cm_65kg.xml "
            "models are not loaded by this package",
            "the MuJoCo engine and mujoco-py were not importable where the gate ran, so no trajectory of this "
            "package was compared with the real engine",
            "the bridge exposes qpos, qvel, ctrl and time, not camera, inertial, contact-force or sensor arrays; "
            "no rendering is served",
            "no physical walker is modelled or driven; this simulated package has no hardware backend and nothing "
            "was validated against hardware",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in is deterministic from its reset state, but it takes no seed and its "
                         "placeholder motion is not MuJoCo's physics.",
            },
            "timestep_ms": 1.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the pinned MJCF for "
                "the joint dimensions, the actuator targets and the default motor ctrlrange, but integrates a "
                "placeholder motion of each actuated joint",
                "the stand-in loads no geom, contact, constraint, inertia, damping, actuator force or sensor; it "
                "ignores the model's mass and joint-range data, so it is not the model's dynamics",
                "the fake has no mj_getState/mj_setState/mj_stateSize, so the bridge uses its basic checkpoint "
                "profile: time, qpos, qvel, act and ctrl are restored, not MuJoCo's full integration state",
                "the fake reports the model's own 0.001 s option timestep (drloco/mujoco/xml/"
                "walker3d_flat_feet.xml:11) but its per-step motion is placeholder data, not a physical integration",
                "MuJoCo itself was not importable where the gate ran, so the stand-in was not compared with the "
                "real engine and the sim backend that imports mujoco was not run",
            ],
        },
    }
