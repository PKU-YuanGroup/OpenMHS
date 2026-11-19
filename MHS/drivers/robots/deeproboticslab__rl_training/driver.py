"""OpenMHS driver for gh.deeproboticslab/rl_training: the DR02 AMP locomotion Gymnasium task.

``Amp-Flat-Deeprobotics-DR02-v0`` is registered with entry point ``rl_training.envs:AmpLocomotionEnv`` and env config
``DR02AmpFlatEnvCfg`` (``source/.../amp/config/humanoid/dr02/__init__.py:8-15``).  ``AmpLocomotionEnv`` extends Isaac
Lab's ``ManagerBasedRLEnv`` (``amp_locomotion_env.py:63``) and overrides ``step``, ``_reset_idx`` and ``reset``.  This
package is a Gymnasium family driver: the bridge serves ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` through the environment's ``step``/``reset`` interface.

The action is a 21-element joint-position target in ``DR02_DOF_ORDER`` (``flat_env_cfg.py:66`` and
``assets/deeprobotics.py:287-295``); the AMP action config clips each target to -10.0..10.0
(``amp_env_cfg.py:140``).  The Gymnasium ``action_space`` itself is built by Isaac Lab's action manager outside the
clone, so the fake backend uses an unbounded 21-element Box and the input envelope is operator_required. The example
overlay bounds fake inputs only. The fake's internal clipping is a placeholder, not a validation of the external
action manager's scaling, default offsets or clipping order. The observation is a Gymnasium Dict of the configured groups: policy 73,
critic 121, amp_obs_history 305, obs_future 69 and vel 3 dimensions (``amp_env_cfg.py:149-156``); the fake returns all
five groups with these sizes.

Only the package fake backend is provided.  Isaac Sim 5.1.0 / Isaac Lab 2.3.2 with Python 3.11 on Linux
(``README.md:33``) are not importable where the gate runs, and package code never imports the clone.  The upstream
``gym.make`` path is not declared: the registered task expects Isaac Lab's env-config resolution, and that path was not
run.  The fake is an F0 kinematic stand-in, not a physics model, and was not compared with an Isaac Lab run.

This package is simulated R0, model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null).  Evidence
is limited to the fake backend; no hardware, real simulator or GPU run is claimed.
"""

from mhs.driver import Action, Fact, GymnasiumDriver, Limit

from .adapter import AmpContractBridge

ENV_INIT = "source/rl_training/rl_training/tasks/manager_based/locomotion/amp/config/humanoid/dr02/__init__.py"
FLAT_CFG = "source/rl_training/rl_training/tasks/manager_based/locomotion/amp/config/humanoid/dr02/flat_env_cfg.py"
AMP_CFG = "source/rl_training/rl_training/tasks/manager_based/locomotion/amp/amp_env_cfg.py"
AMP_ENV = "source/rl_training/rl_training/envs/amp_locomotion_env.py"
ASSETS = "source/rl_training/rl_training/assets/deeprobotics.py"
SETUP = "source/rl_training/setup.py"


class DeepRoboticsDR02Amp(GymnasiumDriver):
    device_id = "deeprobotics-dr02-amp"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "Amp-Flat-Deeprobotics-DR02-v0"
    native = "rl_training.envs.amp_locomotion_env:AmpLocomotionEnv"
    backends = {"fake": ".fake:FakeAmpLocomotionEnv"}
    display_name = "Deep Robotics DR02 AMP locomotion (Isaac Lab training task)"
    vendor, model = "Deep Robotics", "DR02"
    tags = ["deep-robotics", "dr02", "humanoid", "locomotion", "amp", "isaac-lab", "reinforcement-learning",
            "simulation", "gymnasium"]
    actions = {
        "cap.world.step.v1": Action(limits={
            "action.values": Limit.operator_required(
                "the clone configures an internal JointPositionActionCfg clip but does not define the "
                "Gymnasium input Box; the operator supplies the input envelope, including for this R0 fake"
            ),
        }),
    }

    def make_bridge(self, native):
        return AmpContractBridge(env=native, env_id=self.env_id, device_id=self.device_id,
                                 seed=self.seed, autoreset=self.autoreset, max_ticks=self.max_ticks,
                                 env_origin="the fake backend .fake:FakeAmpLocomotionEnv")

    facts = [
        Fact("The DR02 AMP task is registered as Amp-Flat-Deeprobotics-DR02-v0 with entry point "
             "rl_training.envs:AmpLocomotionEnv and env config DR02AmpFlatEnvCfg", source="upstream_code",
             ref=f"{ENV_INIT}:8-15"),
        Fact("AmpLocomotionEnv extends Isaac Lab's ManagerBasedRLEnv", source="upstream_code", ref=f"{AMP_ENV}:63"),
        Fact("AmpLocomotionEnv.step applies the action through the action manager, then steps the simulation "
             "cfg.decimation times", source="upstream_code", ref=f"{AMP_ENV}:106-122"),
        Fact("AmpLocomotionEnv.step returns obs_buf, reward_buf, reset_terminated, reset_time_outs and extras",
             source="upstream_code", ref=f"{AMP_ENV}:175"),
        Fact("AmpLocomotionEnv.reset forwards to the base reset, resets the AMP helper and returns obs_buf with "
             "extras", source="upstream_code", ref=f"{AMP_ENV}:206-209"),
        Fact("The AmpLocomotionEnvCfg field only_positive_rewards defaults to True", source="upstream_code",
             ref=f"{AMP_ENV}:59-60"),
        Fact("AmpLocomotionEnv.step clips the total reward to a minimum of 0 when only_positive_rewards is true",
             source="upstream_code", ref=f"{AMP_ENV}:139-141"),
        Fact("The DR02 AMP config sets the joint-position action joint_names from DR02_DOF_ORDER and the "
             "per-joint action scale", source="upstream_code", ref=f"{FLAT_CFG}:66-67"),
        Fact("DR02_DOF_ORDER lists the DR02 joint names in action order: left leg, right leg, waist, left arm and "
             "right arm", source="upstream_code", ref=f"{ASSETS}:287-295"),
        Fact("The AMP action config is a JointPositionActionCfg with use_default_offset, the clip (-10.0, 10.0), "
             "and preserve_order enabled", source="upstream_code", ref=f"{AMP_CFG}:135-141"),
        Fact("The observation groups are policy (73 dims), critic (121 dims), amp_obs_history (305 dims), "
             "obs_future (69 dims) and vel (3 dims)", source="upstream_code", ref=f"{AMP_CFG}:149-156"),
        Fact("The policy observation is [ang_vel(3), proj_grav(3), cmd(3), cmd_flag(1), dof_pos(21), "
             "dof_vel(21), actions(21)]", source="upstream_code", ref=f"{AMP_CFG}:150-151"),
        Fact("The AMP environment config sets decimation 4, episode_length_s 20.0 and sim.dt 0.005 s, with the "
             "comment naming 0.02 / decimation", source="upstream_code", ref=f"{AMP_CFG}:675-680"),
        Fact("The default scene config creates 4096 environments, so the upstream environment is vectorized",
             source="upstream_code", ref=f"{AMP_CFG}:701"),
        Fact("The README says rl_training is an IsaacLab-based RL training library and lists "
             "Amp-Flat-Deeprobotics-DR02-v0 as the DR02 environment", source="vendor_doc", ref="README.md:16-23"),
        Fact("The README requires Isaac Sim 5.1.0, Isaac Lab 2.3.2 and Python 3.11 on Linux", source="vendor_doc",
             ref="README.md:33"),
        Fact("The README tells users to deploy policies in MuJoCo or on real robots through a separate Deep "
             "Robotics deploy repository", source="vendor_doc", ref="README.md:26-27"),
        Fact("The package install requirements list no serial, USB, VISA or ROS client library", source="upstream_code",
             ref=f"{SETUP}:20-33"),
    ]
    safe_state = ("the analytic fake stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is an F0 kinematic
    #: stand-in; the upstream Isaac Lab physics path was not run, so no higher level is claimed.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its placeholder "
                     "kinematic update is deterministic; the upstream task's seed controls Isaac Lab's generators and "
                     "physics, and GPU physics determinism was not established because the stack was not run",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no Isaac Sim/PhysX rigid-body dynamics, contacts, friction, actuator, sensor, "
            "noise or rendering model; the fake's joint positions, velocities, reward and terminal flags are "
            "placeholders and do not reproduce the upstream MDP",
            "the upstream environment is vectorized over 4096 environments in the default scene; the fake drives one "
            "environment, because the MHS Gymnasium bridge drives one",
            "the upstream Gymnasium action space is built by Isaac Lab's action manager outside the clone; the fake "
            "uses an unbounded 21-element Box, so action.values is operator_required at the endpoint; the example "
            "site overlay is fake-scale test data, not a source-backed Gymnasium action space",
            "the fake clips raw input to -10.0..10.0 as a placeholder; it does not reproduce the per-joint "
            "action scales, default joint offsets, or the external action manager's processing order",
            "the fake returns all five configured observation groups with their upstream sizes (73, 121, 305, 69, "
            "3), but every value is placeholder state, not an Isaac Lab observation",
            "the fake truncates at 20 s / 20 ms = 1000 control ticks (from episode_length_s 20.0 and the 0.02 s "
            "control step) and never terminates; the upstream termination terms and timeout manager are not modelled",
            "the upstream path is gym.make with Isaac Lab's env-config resolution, not the bare registered env_id; "
            "that path needs Isaac Sim 5.1.0 and Isaac Lab 2.3.2 and was not run, so no sim backend is declared",
            "live construction also needs the Isaac application lifecycle, the configured assets and the "
            "deep_robotics_model submodule; the package does not serve the Lite3 rough-task entry on the card "
            "or any of the separate real-robot deployment paths",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state and the bridge has no "
            "declared checkpoint profile",
            "no wall-clock pacing: realtime_factor 0 and the clock is lockstep",
        ],
    }
