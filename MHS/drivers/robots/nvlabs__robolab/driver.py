"""OpenMHS driver for gh.nvlabs/robolab: the RoboLab Gymnasium environment (a Gymnasium family driver).

RoboLab is a task-based evaluation benchmark for robot manipulation policies built on NVIDIA Isaac
Lab and run in simulation (README.md:5).  The card's entry class is the runtime environment
``robolab.core.environments.env:RobolabEnv`` (robolab/core/environments/env.py:24); the generated task
environments register it with Gymnasium (robolab/core/environments/config.py:318-325).  A
GymnasiumDriver is configuration only: ``env_id`` names one registered task environment and the bridge
derives the whole contract from the environment's spaces.  ``cap.world.step.v1`` takes
``{ticks, action}``, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine
and no operator-required limit.

This package serves the documented example environment ``BananaInBowlTask`` (docs/environment_run.md:9-17).
The built-in DROID registration registers each task class under its own name (env_prefix and
env_postfix are empty, robolab/registrations/droid/auto_env_registrations_jointpos.py:113-121), so a
deployment must run that registration before ``gymnasium.make("BananaInBowlTask")``; the sim backend
was not run here because Isaac Sim, Isaac Lab and an NVIDIA GPU are not available where the gate runs.

The gate cannot import the upstream stack, so the ``fake`` backend is this package's pure-Python
kinematic stand-in (fake.py), not Isaac Sim.  A backend name that ``backends`` does not list
(``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the
upstream package and the registration above and was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity
FID-002): the Isaac Lab rigid-body simulation, its 66.67 ms environment step, a seeded reset and the
gaps that name what this package's fake does not model.  Every constant and rule cites a line of the
clone at the pinned commit (ad45d4f974725d020f82c2b0d77d78533aeba2b3).  This package is model-authored
and unreviewed: it is checked on the fake backend only, and its evidence is ``contract_checked``,
never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "robolab/core/environments/env.py"
CONFIG = "robolab/core/environments/config.py"
BASE = "robolab/core/environments/base.py"
FACTORY = "robolab/core/environments/factory.py"
REGISTRATION = "robolab/registrations/droid/auto_env_registrations_jointpos.py"
DROID = "robolab/robots/droid.py"
ROBOTS_README = "robolab/robots/README.md"
CAMERA = "robolab/variations/camera.py"
DOCS_REGISTRATION = "docs/environment_registration.md"
DOCS_RUN = "docs/environment_run.md"


class Robolab(GymnasiumDriver):
    device_id = "robolab"
    env_id = "BananaInBowlTask"
    native = "robolab.core.environments.env:RobolabEnv"
    backends = {"fake": ".fake:FakeRobolabEnv"}
    display_name = "RoboLab BananaInBowlTask (Isaac Lab)"
    vendor, model = "NVIDIA", "RoboLab BananaInBowlTask"
    tags = ["robolab", "robot-manipulation", "isaac-lab", "isaac-sim", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("RoboLab is a task-based evaluation benchmark for robot manipulation policies built on NVIDIA "
             "Isaac Lab and run in simulation", source="vendor_doc", ref="README.md:5"),
        Fact("The requirements are Isaac Sim 5.0 or 5.1, Isaac Lab 2.2.0 or 2.3.2.post1, Python 3.11, Linux "
             "Ubuntu 22.04+ and an NVIDIA RTX GPU", source="vendor_doc", ref="README.md:162-174"),
        Fact("RobolabEnv extends ManagerBasedRLEnv and is the runtime environment class",
             source="upstream_code", ref=f"{ENV}:24"),
        Fact("RobolabEnv.step zeroes the action of every frozen (terminated) environment and then calls "
             "ManagerBasedRLEnv.step with the whole batched action", source="upstream_code",
             ref=f"{ENV}:65-73"),
        Fact("When an environment terminates during stepping, RobolabEnv freezes it instead of resetting it: it "
             "records success/failure and the termination step and the environment holds its final state",
             source="upstream_code", ref=f"{ENV}:76-104"),
        Fact("register_generated_env registers the generated task environment with gymnasium under the generated "
             "name, entry point robolab.core.environments.env:RobolabEnv and the generated env_cfg_entry_point",
             source="upstream_code", ref=f"{CONFIG}:318-325"),
        Fact("The built-in DROID registration passes env_prefix and env_postfix as empty strings, so the "
             "registered environment name is the task class name", source="upstream_code",
             ref=f"{REGISTRATION}:113-121"),
        Fact("The documented registered environment name for the BananaInBowlTask example is "
             "BananaInBowlTask", source="vendor_doc", ref=f"{DOCS_RUN}:9-17"),
        Fact("The environment name is the concatenation env_prefix + TaskClassName + env_postfix",
             source="vendor_doc", ref=f"{DOCS_REGISTRATION}:205-209"),
        Fact("DroidJointPositionActionCfg takes 7 arm joint targets plus a binary gripper, 8 action values",
             source="vendor_doc", ref=f"{ROBOTS_README}:26-28"),
        Fact("The binary gripper action closes when the action value is greater than 0.5 and opens otherwise",
             source="upstream_code", ref=f"{DROID}:306-320"),
        Fact("The built-in DROID observation config has the image_obs, proprio_obs and viewport_cam groups",
             source="upstream_code", ref=f"{REGISTRATION}:83-86"),
        Fact("The proprioception terms are arm_joint_pos, gripper_pos (noise std 0.05 and clipped to 0-1), "
             "ee_pos, ee_quat, eef_pos and eef_quat", source="upstream_code", ref=f"{DROID}:433-442"),
        Fact("The DROID wrist camera is 720 pixels high, 1280 pixels wide and RGB",
             source="upstream_code", ref=f"{DROID}:42-50"),
        Fact("The egocentric mirrored viewport camera is 480 pixels high, 864 pixels wide and RGB",
             source="upstream_code", ref=f"{CAMERA}:179-186"),
        Fact("The DROID registration passes dt = 1/(60*2) s and decimation = 8, so one environment step advances "
             "8 physics steps of 1/120 s = 66.67 ms", source="upstream_code",
             ref=f"{REGISTRATION}:129-131"),
        Fact("The generated configuration assigns self.decimation and self.sim.dt from those registration "
             "arguments", source="upstream_code", ref=f"{CONFIG}:196-200"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; the values are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:BananaInBowlTask",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream reset seeds the Isaac Lab environment; the fake draws its start offsets from "
                     "Python's random.Random(seed), so one implementation repeats a trajectory for the same seed "
                     "and actions, but a seed gives different state than the Isaac Lab/PhysX run",
        },
        "timestep_ms": 66.66666666666667,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed environment is an NVIDIA Isaac Sim/Isaac Lab rigid-body simulation with PhysX contacts, "
            "actuators and GPU physics; the fake backend is a pure-Python kinematic stand-in with no contacts, "
            "actuator dynamics, sensors, noise or PhysX solver, and its numeric constants are placeholders",
            "the fake does not model the 100+ benchmark tasks, their success/failure predicates, the frozen "
            "terminated-env behaviour or an episode length; it never reports terminated or truncated",
            "the fake returns a 4x6x3 RGB placeholder for the wrist camera and a 2x3x3 RGB placeholder for the "
            "viewport camera; the deployed cameras are 720x1280 and 480x864 RGB",
            "the fake's 8-value joint-position action is a kinematic tracking stand-in: it does not reproduce the "
            "Franka arm's joint limits, actuators or the binary gripper's physical command mapping",
            "the fake samples start offsets with Python's random.Random while Isaac Lab uses its own event and "
            "physics random streams, so one seed gives different trajectories on the two",
            "no snapshot and restore are offered: RobolabEnv exposes no get_state/set_state pair that the bridge "
            "uses",
        ],
    }
