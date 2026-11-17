"""OpenMHS driver for gh.nico-bohlinger/one_policy_to_run_them_all: the ANYmal B MJCF (a MuJoCo family driver).

The card's entry point is the concrete ``AnymalB(gym.Env)`` (``one_policy_to_run_them_all/environments/anymal_b/
environment.py:27``): a Gymnasium environment that loads a bundled MuJoCo model (``:114``), overwrites its physics step
from the environment configuration (``:115``), converts a twelve-element joint-position action into torques with the
Rudin2022 PD controller (``:248``) and integrates the model (``:252``).  The upstream environment path needs RL-X (the
registration in ``multi_robot/__init__.py``), gymnasium, dm_control and pygame and cannot be constructed where the
acceptance gate runs; a direct GymnasiumDriver would need that whole stack plus the observation, reward, termination
and vectorization pipeline.

This package therefore serves the card's model (``models[0]``, ``one_policy_to_run_them_all/environments/anymal_b/data/
anymal_b.xml``) through ``MujocoDriver``, the card's helper: the bridge loads the MJCF, derives the ``cap.world.step.v1``
control bounds from the model's twelve motor actuators (ctrlrange -40 to 40, ``anymal_b.xml:56``) and serves the model's
own torque control and reset.  It does **not** run ``create_env``, ``AnymalB``, the PD controller or RL-X; the fidelity
``gaps`` list that difference, including the position-offset action of the upstream environment.

The device is simulated (R0, ``world.sim``): no hardware backend, no physical stop and no operator-required bound.
MuJoCo is not installed where the gate runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module
(fake.py).  The model file is read from the read-only upstream clone at the pinned commit and is never copied or
imported.  Every Fact cites a line of the clone at commit 7c1819444028c529b0a964fe3f32878333b1310a.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml"
ENV = "one_policy_to_run_them_all/environments/anymal_b/environment.py"
CONFIG = "one_policy_to_run_them_all/environments/anymal_b/default_config.py"
CONTROL = "one_policy_to_run_them_all/environments/anymal_b/control_functions/rudin2022.py"
INITIAL = "one_policy_to_run_them_all/environments/anymal_b/initial_state_functions/default.py"
FACTORY = "one_policy_to_run_them_all/environments/multi_robot/create_env.py"
REGISTRY = "one_policy_to_run_them_all/environments/multi_robot/robot_helper.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/nico-bohlinger/one_policy_to_run_them_all/" + MODEL


class AnymalB(MujocoDriver):
    device_id = "anymal_b"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "ANYmal B quadruped (MuJoCo model)"
    vendor, model = "Nico Bohlinger", "ANYmal B"
    tags = ["anymal", "quadruped", "legged", "locomotion", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository is the implementation of the paper One Policy to Run Them All: an End-to-end Learning "
             "Approach to Multi-Embodiment Locomotion", source="vendor_doc", ref="README.md:1-3"),
        Fact("The requirements pin mujoco 3.1.3", source="upstream_code", ref="requirements.txt:64"),
        Fact("The multi-robot module defines create_env(config), the environment factory",
             source="upstream_code", ref=f"{FACTORY}:15"),
        Fact("AnymalB is registered in the ROBOTS list", source="upstream_code", ref=f"{REGISTRY}:41"),
        Fact("AnymalB is a gymnasium.Env subclass", source="upstream_code", ref=f"{ENV}:27"),
        Fact("AnymalB stores twelve nominal joint positions, twelve max_joint_velocities values of 15.0 and an "
             "initial_drop_height of 0.5", source="upstream_code", ref=f"{ENV}:59-66"),
        Fact("AnymalB loads the MJCF with mujoco.MjModel.from_xml_path and then overwrites model.opt.timestep with the "
             "timestep of its configuration", source="upstream_code", ref=f"{ENV}:112-115"),
        Fact("The action-space size starts at model.nu and is replaced by multi_robot_max_action_size when that "
             "value is not -1; its Box has infinite lower and upper bounds", source="upstream_code",
             ref=f"{ENV}:132-140"),
        Fact("AnymalB.reset replaces the model state with the qpos and qvel of its initial-state function",
             source="upstream_code", ref=f"{ENV}:199-214"),
        Fact("AnymalB.step runs the action through the control function's process_action, writes the resulting "
             "torques to data.ctrl and calls mujoco.mj_step for nr_substeps", source="upstream_code",
             ref=f"{ENV}:246-252"),
        Fact("The shipped anymal_b configuration sets timestep 0.005 s and an episode length of 20 s",
             source="upstream_code", ref=f"{CONFIG}:31-32"),
        Fact("Rudin2022Control defaults to a control frequency of 50 Hz, p_gain 80, d_gain 2.0 and a scaling factor "
             "of 0.5", source="upstream_code", ref=f"{CONTROL}:2"),
        Fact("process_action scales the action by the scaling factor, adds the nominal joint positions and computes "
             "a PD torque from qpos[7:] and qvel[6:]", source="upstream_code", ref=f"{CONTROL}:24-29"),
        Fact("The default initial state puts the base at the initial drop height plus the terrain centre height and "
             "the twelve joints at their nominal positions", source="upstream_code", ref=f"{INITIAL}:8-13"),
        Fact("The MJCF root element names the model anymal_b", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model uses radians, resolves its meshes from assets/ and enables autolimits",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model's option element selects the pyramidal cone and impratio 100", source="upstream_code",
             ref=f"{MODEL}:4"),
        Fact("The default joint is a hinge with damping 1, frictionloss 0.1 and range -3.14 to 3.14",
             source="upstream_code", ref=f"{MODEL}:10"),
        Fact("The default motor is ctrllimited with ctrlrange -40.0 to 40.0", source="upstream_code",
             ref=f"{MODEL}:56"),
        Fact("The world contains a plane floor and a trunk body at 0 0 0 that carries the free joint",
             source="upstream_code", ref=f"{MODEL}:124-132"),
        Fact("The actuator section has twelve motor actuators, one per leg joint from LF_HAA to RH_KFE",
             source="upstream_code", ref=f"{MODEL}:340-351"),
        Fact("The home keyframe holds 19 qpos values with the base at height 0.5 and the listed joint positions",
             source="upstream_code", ref=f"{MODEL}:355"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the served model state, including the last controls, is kept "
                  "and stays readable. A later explicit step without action reuses those controls")
    #: The fidelity contract of the model as deployed (spec 05-fidelity).  The bridge derives the engine, time step and
    #: snapshot support; the members below state what this package actually serves and what it does not.
    fidelity = {
        "engine": "mujoco:anymal_b",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "MuJoCo integrates a fixed model deterministically on one engine version, but cap.world.reset.v1 "
                     "restores the model defaults and does not use a seed; the bridge publishes no seeded control and "
                     "this package makes no determinism claim.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "this package serves the bare MJCF through the MuJoCo bridge; it does not run create_env, AnymalB, RL-X "
            "or the environment's observation, reward, termination, command-sampling, domain-randomization and "
            "vectorization pipeline",
            "the served action is the model's torque control vector (one value per motor, ctrlrange -40 to 40); "
            "AnymalB.step instead takes twelve joint-position offsets, scales them by 0.5 and converts them to "
            "torques with the Rudin2022 PD controller before writing data.ctrl",
            "a reset runs mj_resetData and restores the compiled model defaults (base at 0 0 0, all joints at "
            "zero); AnymalB.reset places the trunk at initial_drop_height plus the terrain centre height (0.5 m) "
            "and the joints at the nominal pose",
            "the MJCF states no <option timestep>, so the served step is MuJoCo's 0.002 s default; AnymalB "
            "overwrites the model timestep with the 0.005 s configuration value and integrates four substeps per "
            "50 Hz control step",
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the free "
            "base, the twelve hinge joints, the twelve motors and their default ctrlrange, then gives each actuated "
            "hinge a placeholder velocity proportional to its control value and holds the free base where the model "
            "puts it; it computes no inertia, torque, gravity, contact, friction, constraint, damping or actuator "
            "dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no OBJ mesh or texture and resolves no collision or contact; the model's floor, "
            "geometry and contact excludes are not applied",
            "the fake exposes no mj_getState/mj_setState, so its snapshots use the bridge's basic profile; the real "
            "engine has the full integration-state codec, which this package did not run",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine, and the real sim path (a backend name backends does not list) was not run",
            "no physical ANYmal B is modelled and nothing was validated against hardware",
        ],
    }
    #: The deployed fake has no physics; it must not inherit the real engine's F1 description.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
        },
    }
