"""OpenMHS driver for gh.isaac-sim/isaacgymenvs: the Ant environment of the Isaac Gym suite (a Gymnasium family driver).

The repository is a suite of reinforcement-learning environments for the external NVIDIA Isaac Gym simulator; the
simulator itself is downloaded separately (README.md:13-14), and this package never imports or runs the clone.  The
card selects ``family-config``/``sim-env`` with the Gymnasium helper, so the driver is configuration only and
``native`` names ``isaacgymenvs.tasks.ant:Ant``, the task class behind ``task="Ant"`` (README.md:39-45).

The upstream task uses the legacy Gym API pinned by ``gym==0.23.1`` (setup.py:17): ``VecTask.step`` returns the
four-tuple ``(obs_dict, reward, reset, info)`` and ``VecTask.reset`` returns an observation dictionary.  The bridge
accepts that four-tuple (MHS/sdk/docs/bridges.md, "Gymnasium and MuJoCo"), and the fake below implements the
Gymnasium-shaped five-tuple with the same 60-element observation and 8-element action contract, so the fake is a
kinematic recording stand-in rather than the Isaac Gym physics.

The device is simulated (R0): there is no hardware backend, no actuator and no operator-required limit.  The
``fake`` backend is the only backend in ``driver.lock.json``; the real ``isaacgymenvs.make(task="Ant", ...)`` path
needs the separately installed Isaac Gym Preview 4 and a CUDA device and was not run here.

The ``fidelity`` attribute describes the model as deployed (MHS-005 FID-002): the fake is F0 (kinematic, no rigid-body
dynamics or contacts), with a fixed 16.6 ms step taken from the Ant configuration.  Every fact cites a line of the
clone at the pinned commit aeed298638a1f7b5421b38f5f3cc2d1079b6d9c3.  This package is model-authored and unreviewed:
it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ANT = "isaacgymenvs/tasks/ant.py"
VECTASK = "isaacgymenvs/tasks/base/vec_task.py"
ANT_CFG = "isaacgymenvs/cfg/task/Ant.yaml"


class IsaacAnt(GymnasiumDriver):
    device_id = "isaac-ant"
    env_id = "Ant"
    native = "isaacgymenvs.tasks.ant:Ant"
    backends = {"fake": ".fake:FakeAnt"}
    action_space_ref = f"{VECTASK}:113"
    display_name = "Isaac Gym Ant (simulated)"
    vendor, model = "NVIDIA", "Isaac Gym Ant"
    tags = ["isaac-gym", "ant", "quadruped", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository contains example reinforcement-learning environments for the NVIDIA Isaac Gym",
             source="vendor_doc", ref="README.md:8"),
        Fact("Isaac Gym itself is a separate Preview 4 download installed before this repository, so the simulator "
             "is external to the clone", source="vendor_doc", ref="README.md:13-14"),
        Fact("The public factory is isaacgymenvs.make(seed, task, num_envs, sim_device, ...)", source="upstream_code",
             ref="isaacgymenvs/__init__.py:14-20"),
        Fact("The documented Ant example calls isaacgymenvs.make(seed=0, task=\"Ant\", num_envs=..., "
             "sim_device=\"cuda:0\", rl_device=\"cuda:0\")", source="vendor_doc", ref="README.md:39-45"),
        Fact("Ant is the task class behind task=\"Ant\": class Ant(VecTask)", source="upstream_code", ref=f"{ANT}:41"),
        Fact("Ant sets numObservations to 60 and numActions to 8", source="upstream_code", ref=f"{ANT}:67-68"),
        Fact("The observation concatenates 1 torso height, 3 local velocities, 3 local angular velocities, yaw, "
             "roll, target angle, up projection, heading projection, 8 scaled joint positions, 8 scaled joint "
             "velocities, 24 contact-force values and 8 actions (60 values)", source="upstream_code",
             ref=f"{ANT}:401-406"),
        Fact("The observation space is a Box from -inf to +inf over num_observations values", source="upstream_code",
             ref=f"{VECTASK}:107"),
        Fact("The action space is a Box from -1 to 1 over num_actions values", source="upstream_code",
             ref=f"{VECTASK}:113"),
        Fact("The Ant configuration sets clipActions to 1.0", source="upstream_code", ref=f"{ANT_CFG}:13"),
        Fact("VecTask.step clamps every action to -clip_actions .. clip_actions before applying it",
             source="upstream_code", ref=f"{VECTASK}:374"),
        Fact("The Ant episode length is 1000 control steps", source="upstream_code", ref=f"{ANT_CFG}:10"),
        Fact("An agent is reset when its progress reaches max_episode_length - 1, or when its torso height falls "
             "below termination_height", source="upstream_code", ref=f"{ANT}:368-369"),
        Fact("The Ant termination height is 0.31 and a fallen agent receives the death cost", source="upstream_code",
             ref=f"{ANT_CFG}:28-29"),
        Fact("A fallen agent (torso height below termination_height) is reset", source="upstream_code",
             ref=f"{ANT}:368"),
        Fact("The Ant timestep is dt=0.0166 s (1/60 s)", source="upstream_code", ref=f"{ANT_CFG}:43"),
        Fact("Ant takes its dt from the simulation configuration", source="upstream_code", ref=f"{ANT}:112"),
        Fact("A reset draws joint positions uniformly from -0.2 to 0.2 and joint velocities uniformly from -0.1 to "
             "0.1", source="upstream_code", ref=f"{ANT}:257-258"),
        Fact("The install requires gym==0.23.1, the legacy Gym API", source="upstream_code", ref="setup.py:17"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, while the last observation stays readable; there is no "
                  "actuator to stop")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2); the fake is F0.
    fidelity = {
        "engine": "isaacgymenvs:Ant (kinematic stand-in for the Isaac Gym Ant task)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the test data of the fake; its kinematic transitions "
                     "are deterministic, so one seed repeats a trajectory.  The upstream Ant reset uses torch's "
                     "random generator and the Isaac Gym physics engine, so this fake does not reproduce upstream "
                     "trajectories.",
        },
        "timestep_ms": 16.6,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake has no rigid-body dynamics, no contacts, no actuators and no Isaac Gym physics: joint "
            "positions and the torso height follow a simple kinematic rule, so forces and contact behaviour are "
            "not modelled",
            "the fake returns a 60-element observation in the upstream layout but fills the contact-force block "
            "with zeros and derives the root and joint values from test data, not from simulation",
            "the upstream VecTask.step returns (obs_dict, reward, reset, info) from the legacy Gym API while the "
            "fake returns the Gymnasium five-tuple; the bridge accepts both, and the real isaacgymenvs.make path "
            "was never run because Isaac Gym Preview 4 is external and needs a CUDA device",
            "the fake models one environment, while isaacgymenvs.make returns a vectorised environment of "
            "num_envs copies (4096 by default in the Ant configuration)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
