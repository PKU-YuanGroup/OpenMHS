"""OpenMHS driver for gh.carlosferrazza/humanoid-bench: the ``h1-stand-v0`` Gymnasium environment.

HumanoidBench registers one Gymnasium environment per robot and task (``humanoid_bench/__init__.py:5-21``).
This package targets ``h1-stand-v0``: the H1 humanoid without hands standing still.  ``humanoid_bench.env:
HumanoidEnv`` is the card's AST-confirmed entry class; it wraps a MuJoCo model in a Gymnasium environment and
``HumanoidEnv.step`` delegates to ``self.task.step`` (``humanoid_bench/env.py:226-227``).

A GymnasiumDriver is configuration only.  The bridge derives the whole contract from the environment's
spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` bounded by the ``Box(-1, 1)``
that ``HumanoidEnv`` installs (``humanoid_bench/env.py:162-166``), ``cap.world.reset.v1`` takes ``{seed,
options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package (it needs MuJoCo, dm_control, numpy and the pinned ``install``
dependencies, and package code never imports the clone), so the ``fake`` backend is the package's own pure
Python stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("h1-stand-v0")`` after ``import humanoid_bench`` (``GymnasiumDriver.open_native`` and
``humanoid_bench/__init__.py:1-21``); that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity): the MuJoCo H1 stand
model, its 20 ms control step and a seeded reset, with ``gaps`` naming what this package's fake does not
model.  This package is model-authored and unreviewed: it is checked on the fake backend only, and its
evidence is ``contract_checked``, never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "humanoid_bench/__init__.py"
ENV = "humanoid_bench/env.py"
TASKS = "humanoid_bench/tasks.py"
ROBOTS = "humanoid_bench/robots.py"
LOCOMOTION = "humanoid_bench/envs/basic_locomotion_envs.py"
STAND_XML = "humanoid_bench/assets/envs/h1_pos_stand.xml"


class H1Stand(GymnasiumDriver):
    device_id = "humanoid-bench-h1-stand"
    env_id = "h1-stand-v0"
    native = "humanoid_bench.env:HumanoidEnv"
    backends = {"fake": ".fake:FakeHumanoidStand"}
    display_name = "HumanoidBench H1 stand (h1-stand-v0)"
    vendor, model = "carlosferrazza/humanoid-bench", "h1-stand-v0"
    tags = ["humanoid", "humanoid-bench", "mujoco", "stand", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("h1-stand-v0 is registered by the loop that registers one <robot>-<task>-v0 environment for every "
             "robot and task, with entry point humanoid_bench.env:HumanoidEnv and the task's max_episode_steps",
             source="upstream_code", ref=f"{INIT}:5-21"),
        Fact("The environment id h1-stand-v0 is documented in the benchmark's environment list",
             source="vendor_doc", ref="README.md:131"),
        Fact("The H1 robot has dof 26", source="upstream_code", ref=f"{ROBOTS}:1-2"),
        Fact("The Stand observation space is a Box from -inf to +inf with shape (robot.dof * 2 - 1,)",
             source="upstream_code", ref=f"{LOCOMOTION}:40-44"),
        Fact("The observation concatenates qpos and qvel into one flat vector", source="upstream_code",
             ref=f"{TASKS}:32-36"),
        Fact("HumanoidEnv replaces the controller space with a Box from -1 to 1 of the model's actuator shape",
             source="upstream_code", ref=f"{ENV}:162-166"),
        Fact("The model path is built as envs/{robot}_{control}_{task}.xml under the assets directory, so "
             "h1-stand-v0 loads envs/h1_pos_stand.xml", source="upstream_code", ref=f"{ENV}:123-130"),
        Fact("The registration loop uses control pos for every robot except g1 and digit", source="upstream_code",
             ref=f"{INIT}:5-9"),
        Fact("The h1_pos model has 19 position actuators in its actuator block", source="upstream_code",
             ref="humanoid_bench/assets/robots/h1_pos.xml:231-251"),
        Fact("The stand model's MuJoCo timestep is 0.002 s", source="upstream_code", ref=f"{STAND_XML}:2"),
        Fact("Task.frame_skip is 10, so one environment step advances 10 physics frames", source="upstream_code",
             ref=f"{TASKS}:10"),
        Fact("Task.step calls do_simulation with frame_skip", source="upstream_code", ref=f"{TASKS}:60-62"),
        Fact("The default episode limit is 1000 steps", source="upstream_code", ref=f"{TASKS}:12"),
        Fact("The Stand task sets _move_speed = 0 and success_bar = 800", source="upstream_code",
             ref=f"{LOCOMOTION}:100-102"),
        Fact("The stand reward is small_control * stand_reward * dont_move", source="upstream_code",
             ref=f"{LOCOMOTION}:67-76"),
        Fact("The episode terminates when the root height qpos[2] is below 0.2", source="upstream_code",
             ref=f"{LOCOMOTION}:96-97"),
        Fact("Task.step always returns truncated=False; truncation is not performed by the task",
             source="upstream_code", ref=f"{TASKS}:69"),
        Fact("HumanoidEnv.step delegates to self.task.step(action)", source="upstream_code", ref=f"{ENV}:226-227"),
        Fact("A reset restores the keyframe, adds uniform noise of +-randomness to qpos and returns the task's "
             "reset observation", source="upstream_code", ref=f"{ENV}:229-242"),
        Fact("The default reset randomness is 0.01", source="upstream_code", ref=f"{ENV}:64"),
        Fact("seed(seed) calls numpy.random.seed(seed)", source="upstream_code", ref=f"{ENV}:244-245"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:h1-stand-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream reset draws from numpy's seeded generator, so one seed and one action "
                     "sequence repeat a trajectory; this package's fake draws its start noise from Python's "
                     "random.Random, so the same seed gives a different trajectory on the fake and upstream",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed model is MuJoCo rigid-body dynamics with contacts (F1), but the fake backend is a "
            "pure-Python analytic stand-in: it models no contacts, actuator forces, sensors or contact noise, "
            "and its numeric constants are placeholders, not the model's",
            "the fake does not reproduce the keyframe start state or the upstream numpy random stream: reset "
            "draws Python random.Random noise for a repeatable stand-in, so a seed gives different states than "
            "upstream",
            "the fake does not model the stand reward, the 0.2 m termination height or the 1000-step episode "
            "limit; it returns terminated=False and truncated=False",
            "no physical device is modelled and the benchmark was never validated against one",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
