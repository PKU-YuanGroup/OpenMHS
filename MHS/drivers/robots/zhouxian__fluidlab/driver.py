"""OpenMHS driver for gh.zhouxian/fluidlab: the FluidLab Circulation-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives
``cap.world.step.v1``/``cap.world.reset.v1``/``cap.world.seed.v1`` from the environment's spaces.  The bridge sees a
legacy gym environment through the same interface (``reset()`` returns an observation and ``step(action)`` returns
``observation, reward, done, info``); the fake backend models the ``FluidEnv`` API of the clone.  ``cap.world.step.v1``
takes ``{ticks, action}`` with the action ``{values}`` bounded by the environment's action space, and
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The environment is a simulation (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.  The gate cannot import the upstream package (Taichi, torch, yacs and a GPU stack; see
``environment.yml``), and package code never imports the clone, so the ``fake`` backend is the package's own small
stand-in for ``fluidlab.envs.circulation_env:CirculationEnv``.

The ``fidelity`` attribute is the model as deployed (spec 05-fidelity FID-002).  It says F1: the upstream is a
multi-material differentiable physics engine, but the fake published here does not model its particles or smoke field.
Every constant and rule of this package cites a line of the clone at the pinned commit
7295eb6ed7ee92b2be471fd30b432238577f28ce.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV_INIT = "fluidlab/envs/__init__.py"
CIRCULATION = "fluidlab/envs/circulation_env.py"
FLUID_ENV = "fluidlab/envs/fluid_env.py"
AGENT_CFG = "fluidlab/envs/configs/agent_circulation.yaml"
AIRCON = "fluidlab/fluidengine/effectors/aircon.py"
MPM = "fluidlab/fluidengine/simulators/mpm_simulator.py"
LOSS = "fluidlab/fluidengine/losses/circulation_loss.py"


class FluidLabCirculation(GymnasiumDriver):
    device_id = "fluidlab-circulation"
    env_id = "Circulation-v0"
    native = "fluidlab.envs.circulation_env:CirculationEnv"
    backends = {"fake": ".fake:FakeCirculationEnv"}
    action_space_ref = f"{CIRCULATION}:27"
    display_name = "FluidLab Circulation-v0 (indoor air circulation)"
    vendor, model = "Zhou Xian et al.", "FluidLab Circulation-v0"
    tags = ["fluidlab", "fluid-simulation", "differentiable-physics", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("FluidLab is a set of standardized complex robotic fluid manipulation tasks powered by FluidEngine, a "
             "multi-material fully differentiable physics engine supporting liquids, solids and gases",
             source="vendor_doc", ref="README.md:21-23"),
        Fact("Every environment is registered as <env_name>-v<id> with entry point "
             "fluidlab.envs.<env_name.lower()>_env:<EnvName>Env, kwargs version and loss_type='default', and "
             "max_episode_steps=10000", source="upstream_code", ref=f"{ENV_INIT}:4-10"),
        Fact("CirculationEnv requires the version argument and takes loss=True, loss_type='diff' and seed=None",
             source="upstream_code", ref=f"{CIRCULATION}:16"),
        Fact("CirculationEnv has horizon 1000 and horizon_action 1000", source="upstream_code",
             ref=f"{CIRCULATION}:21-22"),
        Fact("With loss_type='default' gym_misc replaces the horizon with horizon_action", source="upstream_code",
             ref=f"{FLUID_ENV}:86-87"),
        Fact("The action range of the circulation environment is [-0.1, 0.1]", source="upstream_code",
             ref=f"{CIRCULATION}:27"),
        Fact("The circulation agent has 8 action dimensions", source="upstream_code", ref=f"{AGENT_CFG}:6"),
        Fact("The action velocity scales are 1 for the first six dimensions, 100000 for dimension seven and 50 for "
             "dimension eight", source="upstream_code", ref=f"{AGENT_CFG}:8"),
        Fact("The environment is a 3-D Taichi MPM simulation with particle density 1e6, 100 local substeps, gravity "
             "(0, -20, 0), horizon 1000 and CPU checkpoints", source="upstream_code", ref=f"{CIRCULATION}:30-37"),
        Fact("The scene adds a room static mesh at position (0.5, 0.5, 0.5), euler (0, 0, 0), scale (1.4, 3.0, 1.4), "
             "SDF resolution 128, material PILLAR and dynamics enabled", source="upstream_code",
             ref=f"{CIRCULATION}:48-57"),
        Fact("The scene adds one 'nowhere' body of 10 water particles", source="upstream_code",
             ref=f"{CIRCULATION}:60-64"),
        Fact("The smoke field is resolved at 128, with dt 0.03, 50 solver iterations, decay 0.99 and q_dim 1",
             source="upstream_code", ref=f"{CIRCULATION}:67-72"),
        Fact("The observation samples at most 200 particles per body", source="upstream_code",
             ref=f"{CIRCULATION}:24"),
        Fact("gym_misc builds observation_space as Box(-inf, inf, obs.shape) and action_space as "
             "Box(action_range[0], action_range[1], (agent.action_dim,))", source="upstream_code",
             ref=f"{FLUID_ENV}:85-93"),
        Fact("reset restores the stored initial state and returns the observation", source="upstream_code",
             ref=f"{FLUID_ENV}:95-97"),
        Fact("_get_obs concatenates each body's sampled positions, velocities and used flags, the agent state, and the "
             "smoke field's v and q slices taken as [::10, 60:68, ::10]", source="upstream_code",
             ref=f"{FLUID_ENV}:99-125"),
        Fact("step clips the action to action_range before advancing the simulator", source="upstream_code",
             ref=f"{FLUID_ENV}:131-134"),
        Fact("The episode ends when t equals horizon; a NaN reward is replaced with -1000 and also ends the episode",
             source="upstream_code", ref=f"{FLUID_ENV}:139-147"),
        Fact("seed calls the base environment's seed and then sets the process random seeds", source="upstream_code",
             ref=f"{FLUID_ENV}:31-33"),
        Fact("The step reward of the circulation loss is 11 minus the current step loss", source="upstream_code",
             ref=f"{LOSS}:134-136"),
        Fact("The air-conditioner effector's get_state output is a 9-element vector: position (3), quaternion (4), "
             "strength s and radius r", source="upstream_code", ref=f"{AIRCON}:175-195"),
        Fact("The MPM physics timestep is 2e-4 s and one environment step covers int(2e-3 / self.dt) substeps",
             source="upstream_code", ref=f"{MPM}:24-30"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "fluidlab:FluidLab (MPM + smoke field)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 records the seed, and reset restores the stored initial state "
                     "of the environment, so the same seed and the same actions repeat a trajectory; this package's "
                     "fake is deterministic and does not draw a random state at reset, and upstream draws scene "
                     "particles with numpy at construction time",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream model is a multi-material differentiable MPM fluid and smoke simulation; the fake "
            "integrates a small agent-only state and models no particles, smoke, contacts or fluid forces",
            "the fake observation is a 9-value agent-state slice (position, quaternion, strength s and radius r); "
            "for this scene the upstream observation concatenates 5487 float32 values: 70 body state (10 particles "
            "of x, v and used), 9 agent state, 4056 smoke v samples and 1352 smoke q samples",
            "one cap.world.step.v1 tick is one environment step; the MPM simulator runs int(2e-3 / 2e-4) internal "
            "substeps of 2e-4 s per step, so the control period is 2e-3 s (timestep_ms 2.0) and the substeps are "
            "not individually addressable through the bridge",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time only by the declared step",
            "no actuator, sensor or noise model: the AirCon scales are applied to the simplified agent state, and "
            "the reward is a stand-in, not the 11 minus temperature-loss formula of the upstream loss",
            "the fake uses Python floats and lists; upstream returns float32 numpy arrays from a Taichi simulation "
            "and its scene is built with numpy's random generator",
            "snapshot and restore are not offered: FluidEnv exposes no get_state/set_state through the environment "
            "object the bridge inspects",
            "no physical device is modelled and neither the model nor the fake was compared with the upstream "
            "environment or validated against any device",
        ],
    }
