"""OpenMHS driver for gh.vikashplus/robohive: the FrankaReachFixed-v0 environment (a Gymnasium family driver).

The environment is ``robohive.envs.arms.reach_base_v0:ReachBaseV0`` registered by robohive as
``FrankaReachFixed-v0`` (robohive/envs/arms/__init__.py:21-24).  A GymnasiumDriver is configuration only: the bridge
derives the contract from the environment's spaces and serves ``cap.world.step.v1`` with ``{ticks, action}``, where
the action is a ``Box`` over the normalized joint commands (``{"values": [...]}``), ``cap.world.reset.v1`` with
``{seed, options}`` and ``cap.world.seed.v1`` with ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate does not install robohive or MuJoCo and package code never imports the clone, so the ``fake`` backend is the
package's own pure Python kinematic stand-in for the registered environment (see fake.py).  ``backends`` names only
that fake; the upstream simulator path (a backend name the class does not list) would need robohive, mujoco and the
scene assets on the machine and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
engine, level, determinism, timestep, clock, reset and the gaps.  Every rule and number cites a line of the clone at
the pinned commit (6c14798e48b9904dd8c9151837a1d2468b87bcf3).  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REACH = "robohive/envs/arms/reach_base_v0.py"
ENV_BASE = "robohive/envs/env_base.py"
ARMS_INIT = "robohive/envs/arms/__init__.py"


class FrankaReachFixed(GymnasiumDriver):
    device_id = "robohive-franka-reach"
    env_id = "FrankaReachFixed-v0"
    native = "robohive.envs.arms.reach_base_v0:ReachBaseV0"
    backends = {"fake": ".fake:FakeReachBaseV0"}
    display_name = "RoboHive FrankaReachFixed-v0 (MuJoCo manipulation environment)"
    vendor, model = "Vikash Kumar (vikashplus)", "FrankaReachFixed-v0"
    tags = ["robohive", "franka", "reach", "manipulation", "reinforcement-learning", "mujoco", "simulation",
            "gymnasium"]
    facts = [
        Fact("FrankaReachFixed-v0 is registered with entry point robohive.envs.arms.reach_base_v0:ReachBaseV0 and "
             "max_episode_steps=50", source="upstream_code", ref=f"{ARMS_INIT}:21-24"),
        Fact("ReachBaseV0 declares the observation keys qp_robot, qv_robot and reach_err", source="upstream_code",
             ref=f"{REACH}:17-19"),
        Fact("The observation is the full qpos and qvel as qp_robot and qv_robot plus reach_err, the target site "
             "position minus the robot site position", source="upstream_code", ref=f"{REACH}:74-81"),
        Fact("The dense reward weights are reach -1.0, bonus 4.0 and penalty -50", source="upstream_code",
             ref=f"{REACH}:22-26"),
        Fact("The reach task uses far_th 1.0 and counts a bonus below 0.1 and 0.05: solved is reach_dist < 0.050 and "
             "done is reach_dist > 1.0", source="upstream_code", ref=f"{REACH}:85-96"),
        Fact("The environment normalizes actions by default (normalize_act=True) and builds the action space as "
             "gym.spaces.Box(-1, 1) of sim.model.nu elements", source="upstream_code", ref=f"{ENV_BASE}:97-99"),
        Fact("The observation space is a gym.spaces.Box of -10 to 10 for every element of the observation vector",
             source="upstream_code", ref=f"{ENV_BASE}:139"),
        Fact("MujocoEnv.step clips the action to the action space before it is sent to the robot",
             source="upstream_code", ref=f"{ENV_BASE}:254-260"),
        Fact("Under gymnasium, reset returns (observation, {})", source="upstream_code", ref=f"{ENV_BASE}:512-513"),
        Fact("Under gymnasium, the step result is the five-tuple (obs, reward, terminal, False, info)",
             source="upstream_code", ref=f"{ENV_BASE}:279-282"),
        Fact("The registration comment gives 50 steps of 40 skips at 2 ms, i.e. a 0.08 s environment step and a 4 s "
             "episode", source="upstream_code", ref=f"{ARMS_INIT}:24"),
        Fact("ReachBaseV0 defaults frame_skip to 40", source="upstream_code", ref=f"{REACH}:53"),
        Fact("dt is the model timestep multiplied by frame_skip", source="upstream_code", ref=f"{ENV_BASE}:521-522"),
        Fact("The observation vector is built by concatenating the declared observation keys, so its width is the "
             "sum of the key lengths", source="upstream_code", ref=f"{ENV_BASE}:334"),
        Fact("A reset samples the target site position uniformly from target_xyz_range with the environment random "
             "generator", source="upstream_code", ref=f"{REACH}:100-103"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "robohive:FrankaReachFixed-v0 (MuJoCo)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the random generator of the next reset; the physics "
                     "of the upstream MuJoCo model is deterministic for one seed and action sequence. The package's "
                     "fake uses Python's random.Random and a kinematic joint update, while upstream draws from "
                     "numpy's generator and steps MuJoCo, so one seed does not give the same trajectory on both",
        },
        "timestep_ms": 80.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream model is a MuJoCo rigid-body scene of a Franka Panda arm, a table and a target site; the "
            "fake backend is a kinematic stand-in (F0-style) that moves joint positions by a fixed gain per action "
            "and does not integrate rigid-body dynamics, contacts or actuator forces",
            "the upstream environment, MuJoCo and the scene assets were never run here (the gate installs neither "
            "robohive nor mujoco, and package code never imports the clone), so no trajectory of this package was "
            "compared with upstream and no physical device was attached",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair",
            "the 50-step episode limit belongs to the TimeLimit wrapper that gymnasium.make adds around the "
            "registered environment; the fake applies the same limit directly",
            "the observation is a state vector of joint positions, joint velocities and the reach error; images, "
            "contacts and sensor noise are not part of this contract",
        ],
    }
