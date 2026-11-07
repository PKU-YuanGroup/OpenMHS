"""OpenMHS driver for gh.stanfordvl/behavior-1k: the OmniGibson environment of the BEHAVIOR-1K benchmark.

A GymnasiumDriver is configuration only.  ``native`` is the card's entry symbol,
``omnigibson.envs.env_base:Environment`` (``env_base.py:38``), and the bridge derives the capability contract from
the environment's spaces: ``cap.world.step.v1`` takes ``{ticks, action}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The environment's action space is a Dict of robot
name to robot action space (``env_base.py:429``); the fake deployed by this package reduces it to one robot with two
position-controlled joints, so the step action is ``{"robot": {"values": [q0, q1]}}`` with the fake's placeholder
bounds.  ``env_id`` stays unset because OmniGibson registers no environment with ``gymnasium.make``; the documented
construction is ``og.Environment(cfg)`` (``docs/getting_started/quickstart.md:134``).

The gate cannot import the upstream stack (it needs Isaac Sim 5.1.0 on an NVIDIA RTX GPU,
``docs/getting_started/installation.md:9-10``, ``setup.sh:339``), and package code never imports the clone.  So the
``fake`` backend is the package's own reduced stand-in (``fake.py``); the upstream environment was never run.  This
package is model-authored and unreviewed: it is checked on the fake backend only.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  It is F0
because the stand-in models state transitions directly: no scene, contact, physics, sensor or noise model.  The seed
is not a determinism claim: upstream ``reset`` declares no seed parameter (``env_base.py:838``), so the
``cap.world.seed.v1`` value the bridge stores is not read by the environment.  Every constant and rule below cites a
line of the clone at the pinned commit cd484e0477e79bf1f17d373af232c53431ccc660.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "OmniGibson/omnigibson/envs/env_base.py"
TASK = "OmniGibson/omnigibson/tasks/task_base.py"
DUMMY = "OmniGibson/omnigibson/tasks/dummy_task.py"
DOCS = "docs/omnigibson/environments.md"


class Behavior1K(GymnasiumDriver):
    device_id = "behavior-1k"
    native = "omnigibson.envs.env_base:Environment"
    backends = {"fake": ".fake:FakeEnvironment"}
    display_name = "BEHAVIOR-1K OmniGibson environment (simulated)"
    vendor, model = "Stanford Vision and Learning Lab", "BEHAVIOR-1K (OmniGibson)"
    tags = ["behavior-1k", "omnigibson", "household", "embodied-ai", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The environment module imports gymnasium as gym", source="upstream_code", ref=f"{ENV}:6"),
        Fact("Environment is a gym.Env subclass and its docstring says it follows the OpenAI Gym interface",
             source="upstream_code", ref=f"{ENV}:38-40"),
        Fact("Environment(configs) takes a config file path or raw config dictionaries, merged sequentially",
             source="upstream_code", ref=f"{ENV}:43-49"),
        Fact("The default env config uses gm.DEFAULT_SIM_STEP_FREQ for action_frequency, gm.DEFAULT_PHYSICS_FREQ "
             "for physics_frequency, gm.DEFAULT_RENDERING_FREQ for rendering_frequency, automatic_reset False, "
             "flatten_action_space False, flatten_obs_space False and num_envs 1",
             source="upstream_code", ref=f"{ENV}:1023-1031"),
        Fact("gm.DEFAULT_SIM_STEP_FREQ is 30", source="upstream_code",
             ref="OmniGibson/omnigibson/macros.py:219"),
        Fact("A simulator step interval is sim_step_dt = 1.0 / action_frequency, so the 30 Hz default is 1/30 s",
             source="upstream_code", ref=f"{ENV}:83"),
        Fact("The action space is a Dict of each robot's name to robot.action_space; flatten_action_space replaces "
             "it with one Box", source="upstream_code", ref=f"{ENV}:425-451"),
        Fact("The observation space is assembled from every robot's, the task's and the external sensors' spaces "
             "and stored as a Dict; flatten_obs_space keeps a flattened Dict", source="upstream_code",
             ref=f"{ENV}:386-423"),
        Fact("step takes an action and n_render_iterations and calls og.sim.step() once", source="upstream_code",
             ref=f"{ENV}:718-762"),
        Fact("step returns the five-tuple (obs_list, rewards, terminateds, truncateds, infos)",
             source="upstream_code", ref=f"{ENV}:807"),
        Fact("A termination condition named timeout sets truncated; every other done condition sets terminated",
             source="upstream_code", ref=f"{ENV}:782-790"),
        Fact("automatic_reset resets only the environments whose done flag is set", source="upstream_code",
             ref=f"{ENV}:794-803"),
        Fact("reset takes env_indices, get_obs and **kwargs (it declares no seed parameter) and resets the task and "
             "the step and episode counters", source="upstream_code", ref=f"{ENV}:838-854"),
        Fact("reset returns (obs_list, {'obs_info': info_list})", source="upstream_code", ref=f"{ENV}:903"),
        Fact("close is a no-op to satisfy RL frameworks", source="upstream_code", ref=f"{ENV}:523-525"),
        Fact("render returns None when the environment has no external sensors", source="upstream_code",
             ref=f"{ENV}:809-813"),
        Fact("The default config has no robots and its task type is DummyTask", source="upstream_code",
             ref=f"{ENV}:1052-1057"),
        Fact("DummyTask creates no termination conditions and no reward functions", source="upstream_code",
             ref=f"{DUMMY}:15-21"),
        Fact("BaseTask._step_reward starts from zeros and adds every reward function's output", source="upstream_code",
             ref=f"{TASK}:299-312"),
        Fact("The docs call Environment an OpenAI gym-compatible interface and the main entry point for interacting "
             "with the simulation", source="vendor_doc", ref=f"{DOCS}:5"),
        Fact("The docs step the environment with obs, reward, terminated, truncated, info = env.step(action)",
             source="vendor_doc", ref=f"{DOCS}:41"),
        Fact("The docs list step, reset, render, observation_space and action_space as the Gym-like interface",
             source="vendor_doc", ref=f"{DOCS}:46"),
        Fact("The documented construction is env = og.Environment(cfg)", source="vendor_doc",
             ref="docs/getting_started/quickstart.md:134"),
        Fact("Installation requires an NVIDIA RTX 2070+ GPU with 8GB+ of VRAM", source="vendor_doc",
             ref="docs/getting_started/installation.md:9-10"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and counters stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge would derive the
    #: engine, determinism kind and an empty timestep from the fake; they are written out so the whole contract reads
    #: in one place.
    fidelity = {
        "engine": "analytic:OmniGibson-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "no determinism claim: the upstream Environment.reset declares no seed parameter "
                     "(env_base.py:838) and passes the bridge's seed keyword into **kwargs without reading it, so "
                     "cap.world.seed.v1 cannot make a run reproducible; the fake restarts from a fixed pose, which "
                     "was not compared with any upstream run",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a reduced kinematic stand-in for OmniGibson, not the simulator: one robot with two "
            "position-controlled joints and proprioception only, no scene, objects, contacts, dynamics, actuators, "
            "sensors or noise; the joint positions jump to the commanded values",
            "the action and observation spaces are reduced: upstream action_space is a Dict of robot name to "
            "robot action space (env_base.py:429) and observation_space a Dict of robot, task and sensor spaces "
            "(env_base.py:386-423); the fake's two-joint spaces and their bounds are placeholders, not the real "
            "robot's control limits",
            "the fake returns one environment's observation and scalar reward and flags; upstream step returns "
            "per-environment lists and tensors (env_base.py:730-735, 807) and reset returns an obs list "
            "(env_base.py:903)",
            "no seed or determinism: upstream reset has no seed parameter (env_base.py:838), and physics and asset "
            "randomisation are not modelled",
            "the default DummyTask has no termination condition and no reward function (dummy_task.py:15-21), so "
            "the fake never terminates and pays 0.0; a BEHAVIOR-1K activity task would terminate on its own "
            "conditions",
            "timestep_ms is the upstream default action interval (30 Hz, macros.py:219 and env_base.py:83); the "
            "fake advances no simulated time and is not wall-clock paced",
            "no rendering (render returns None without external sensors, env_base.py:809-813), no snapshot or "
            "restore (the environment exposes no get_state/set_state), and no physical device is modelled",
            "the upstream Environment was never imported or run here (Isaac Sim 5.1.0, RTX GPU, setup.sh:339) and "
            "the fake was never compared with it",
        ],
    }
