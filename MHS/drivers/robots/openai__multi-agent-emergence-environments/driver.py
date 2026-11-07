"""OpenMHS driver for gh.openai/multi-agent-emergence-environments: the Base MuJoCo multi-agent environment (a
Gymnasium family driver).

The package is a simulated environment family: ``Base`` builds a MuJoCo world through ``mujoco-worldgen``, adds
environment modules and returns observations from them (mae_envs/envs/base.py:13, :31-35, :53-93).  The card's
``make_env`` entry symbol is the full hide-and-seek factory that stacks wrappers on ``Base``
(mae_envs/envs/hide_and_seek.py:219-251, :350-362).  A GymnasiumDriver is configuration only: the bridge derives the
``cap.world.*`` contract from the environment's spaces, so ``cap.world.step.v1`` takes ``{ticks, action}``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator bound.

The pinned clone cannot be imported or run where the gate runs: it needs ``mujoco-worldgen``, ``mujoco-py`` and
MuJoCo 2.1 binaries (README.md:7-11) and was tested only on Python 3.6 (README.md:14).  The ``fake`` backend is
therefore the package's own reduced pure Python stand-in (fake.py); it models ``reset``/``step``, a Box action space
with the ``action_lims`` bounds and a placeholder observation, not MuJoCo or the module stack.  The fake's dimensions
and constants are test data, not facts.  A backend name ``backends`` does not list is served by
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); this repository has no registered Gym id, and that path was
not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit (bafaf1e11e6398624116761f91ae7c93b136f395).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "mae_envs/envs/base.py"
HIDE_AND_SEEK = "mae_envs/envs/hide_and_seek.py"


class MaeBase(GymnasiumDriver):
    device_id = "mae-envs-base"
    env_id = None
    native = "mae_envs.envs.base:Base"
    backends = {"fake": ".fake:FakeBase"}
    display_name = "OpenAI Multi-Agent Emergence Environments Base (MuJoCo)"
    vendor, model = "OpenAI", "mae_envs Base"
    tags = ["multi-agent", "mujoco", "hide-and-seek", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Base is the multi-agent environment base class; users start from it, add environment modules and "
             "stack wrappers on top", source="vendor_doc", ref="README.md:18"),
        Fact("The repository depends on the separate mujoco-worldgen package, must install it and its requirements "
             "before this package, and was tested only on Mac OS X and Ubuntu 16.04 with Python 3.6",
             source="vendor_doc", ref="README.md:7-14"),
        Fact("The Base constructor defaults are horizon 250, n_substeps 5, n_agents 2, floor_size 6.0, grid_size 30 "
             "and action_lims (-1.0, 1.0), with deterministic_mode False", source="upstream_code",
             ref=f"{BASE}:27-29"),
        Fact("n_substeps is the number of internal MuJoCo steps per outer environment step, described as action "
             "repeat", source="upstream_code", ref=f"{BASE}:18-19"),
        Fact("Base passes tuple(action_lims) as the action_space, horizon and deterministic_mode to the "
             "mujoco-worldgen Env constructor", source="upstream_code", ref=f"{BASE}:31-35"),
        Fact("The world parameters use size (floor_size, floor_size, 2.5) and num_substeps n_substeps",
             source="upstream_code", ref=f"{BASE}:70-71"),
        Fact("The episode draws floor_size uniformly from floor_size_dist, builds each attempt with "
             "WorldBuilder(world_params, seed) and returns builder.get_sim()", source="upstream_code",
             ref=f"{BASE}:68-88"),
        Fact("The hide-and-seek factory defaults are n_substeps 15, horizon 80, floor_size 6.0, grid_size 30 and "
             "action_lims (-0.9, 0.9)", source="upstream_code", ref=f"{HIDE_AND_SEEK}:219-231"),
        Fact("The hide-and-seek factory constructs Base with n_hiders + n_seekers agents", source="upstream_code",
             ref=f"{HIDE_AND_SEEK}:248-251"),
        Fact("The hide-and-seek factory stacks SplitMultiAgentActions, AgentAgentObsMask2D, an observation wrapper, "
             "a reward wrapper, PreparationPhase and DiscretizeActionWrapper on Base", source="upstream_code",
             ref=f"{HIDE_AND_SEEK}:350-362"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco-worldgen:mae_envs",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "Base passes a seed to WorldBuilder in _get_sim (mae_envs/envs/base.py:77) and accepts "
                     "deterministic_mode (mae_envs/envs/base.py:29); the package's fake draws its start state from "
                     "Python's random.Random(seed), so the trajectory repeats for one seed on the fake only",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a reduced pure Python stand-in for Base and hide_and_seek:make_env: it does not model "
            "MuJoCo contacts, the module stack, the reward wrappers or the observation dictionaries, and its "
            "dimensions and integration constants are placeholders",
            "the pinned clone does not state the MuJoCo physics timestep: n_substeps is the number of internal "
            "steps per outer step (mae_envs/envs/base.py:18-19) and the timestep lives in mujoco-worldgen, so "
            "timestep_ms is 0 and no simulated duration is claimed",
            "the pinned clone does not state the raw action dimension: Base passes the two-tuple action_lims to "
            "mujoco-worldgen, which builds the Box from the simulation's actuators "
            "(mae_envs/envs/base.py:31-35); the fake uses two action values per agent as a placeholder",
            "no wall-clock pacing: realtime_factor 0, ticks advance the fake only",
            "the environment is the system of record; no physical device is modelled and the model was never "
            "validated against one",
            "snapshot and restore are not offered: the pinned clone exposes no get_state/set_state",
            "no rendering: the upstream viewer needs mujoco_py and is not modelled",
        ],
    }
