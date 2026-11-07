"""OpenMHS driver for gh.uwrobotlearning/wheeledlab: the Isaac-MushrDriftRL-v0 task (a Gymnasium family driver).

The upstream repository is an Isaac Lab task pack: ``wheeledlab_tasks`` registers gym environments whose entry point is
``isaaclab.envs:ManagerBasedRLEnv`` and whose configuration is one of the ``*EnvCfg`` classes in the clone.  The card's
entry symbol for this package is the drift configuration ``MushrDriftRLEnvCfg`` (``source/wheeledlab_tasks/
wheeledlab_tasks/drifting/mushr_drift_env_cfg.py:369``).  A ``GymnasiumDriver`` is configuration only: the bridge derives
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the environment.  On the fake backend the
environment is the package's own ``fake.py`` stand-in, which has the Gymnasium members ``reset``, ``step`` and ``close``.

The upstream environment itself needs Isaac Sim 4.5.0 and Isaac Lab 2.0.2 on Linux (``README.md:7-10``), plus a GPU; the
gate never imports or installs it.  A backend name that ``backends`` does not list (``sim``) would be served by
``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path was not run here.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.
The ``fidelity`` attribute is the contract of the model as deployed by this package (spec 05-fidelity FID-002); its gaps
say exactly what the fake does not model.  Every Fact cites a line of the clone at the pinned commit
(a5017ce0696032805190448b2addb8077e458387).  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "source/wheeledlab_tasks/wheeledlab_tasks/__init__.py"
CFG = "source/wheeledlab_tasks/wheeledlab_tasks/drifting/mushr_drift_env_cfg.py"
ACTIONS = "source/wheeledlab_tasks/wheeledlab_tasks/common/actions.py"
OBSERVATIONS = "source/wheeledlab_tasks/wheeledlab_tasks/common/observations.py"
ACKERMANN = "source/wheeledlab/wheeledlab/envs/mdp/actions/ackermann_actions.py"
TEST = "source/wheeledlab_tasks/test/create_and_step_env.py"


class MushrDrift(GymnasiumDriver):
    device_id = "wheeledlab-mushr-drift"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    env_id = "Isaac-MushrDriftRL-v0"
    native = "wheeledlab_tasks.drifting.mushr_drift_env_cfg:MushrDriftRLEnvCfg"
    backends = {"fake": ".fake:FakeMushrDriftEnv"}
    display_name = "WheeledLab MuSHR drift (Isaac Lab task)"
    vendor, model = "UWRobotLearning", "Isaac-MushrDriftRL-v0"
    tags = ["wheeledlab", "isaac-lab", "isaac-sim", "mushr", "drifting", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The drift task is registered as Isaac-MushrDriftRL-v0 with entry point isaaclab.envs:ManagerBasedRLEnv "
             "and env_cfg_entry_point MushrDriftRLEnvCfg", source="upstream_code", ref=f"{INIT}:14-21"),
        Fact("MushrDriftRLEnvCfg extends ManagerBasedRLEnvCfg and sets seed 42, num_envs 1024 and env_spacing 0",
             source="upstream_code", ref=f"{CFG}:369-373"),
        Fact("The drift configuration sets sim.dt = 0.005 s (200 Hz) and decimation = 4 (50 Hz), so one environment "
             "step applies one action over four physics steps of 20 ms", source="upstream_code",
             ref=f"{CFG}:393-394"),
        Fact("The drift episode length is 5 simulated seconds", source="upstream_code", ref=f"{CFG}:396"),
        Fact("The MuSHR action group is an RCCarRWDActionCfg with scale (3.0, 0.488), base length 0.325, base width "
             "0.2, wheel radius 0.05, no_reverse True and bounding strategy clip", source="upstream_code",
             ref=f"{ACTIONS}:8-23"),
        Fact("The Ackermann action term reports action_dim 2: target velocity and target steering angle",
             source="upstream_code", ref=f"{ACKERMANN}:103-105"),
        Fact("apply_actions passes component 0 of the processed action as the target velocity and component 1 as the "
             "target steering angle", source="upstream_code", ref=f"{ACKERMANN}:136-140"),
        Fact("process_actions clips every action component to [-1.0, 1.0] before scaling, and with no_reverse set it "
             "clamps the velocity component to at least 0", source="upstream_code", ref=f"{ACKERMANN}:119-133"),
        Fact("The policy observation group concatenates root_pos_w, root_euler_xyz, base_lin_vel, base_ang_vel and "
             "last_action; last_action is clipped to (-1, 1) and the first four terms carry Gaussian noise",
             source="upstream_code", ref=f"{OBSERVATIONS}:23-54"),
        Fact("The project targets Isaac Lab 2.0.2 and Isaac Sim 4.5.0 on Linux 64-bit", source="upstream_code",
             ref="README.md:7-10"),
        Fact("Real-robot deployments are maintained in the separate RealLab repository, not in this clone",
             source="upstream_code", ref="README.md:173-175"),
        Fact("The upstream test starts Isaac Sim through AppLauncher and instantiates the task with "
             "gym.make(task_name, cfg=env_cfg)", source="upstream_code", ref=f"{TEST}:13-28"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is a kinematic
    #: single-environment stand-in, so the level is F0 and the gaps carry the limitations of both the fake and the
    #: unrun upstream engine.
    fidelity = {
        "engine": "isaaclab:ManagerBasedRLEnv (Isaac-MushrDriftRL-v0)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake fixes its initial yaw from reset(seed) and its kinematics are deterministic, so one "
                     "implementation repeats a trajectory for the same seed and actions; the upstream Isaac Sim task "
                     "was not run and is not claimed to be repeatable",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic single-environment stand-in: no rigid-body dynamics, contacts, tire "
            "slip, actuator, sensor or noise model; the upstream Isaac Sim 4.5.0 / Isaac Lab 2.0.2 task was not run",
            "the upstream task is vectorized (num_envs 1024 in the configuration and its test samples "
            "env.unwrapped.single_action_space); the fake models one environment with a 2-element action and a "
            "14-element observation, so it is not the batched Isaac Lab interface",
            "each environment step applies one action over decimation 4 physics steps of sim.dt 0.005 s, a 20 ms "
            "control period; timestep_ms names the 5 ms physics step, not the control period",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time only",
            "the fake pays a constant 0.0 reward, never terminates and truncates at 250 control steps (5 s episode "
            "length); the upstream reward, termination and off-track conditions are not modelled",
            "no physical device is modelled; real-robot deployments live in the separate RealLab repository",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
