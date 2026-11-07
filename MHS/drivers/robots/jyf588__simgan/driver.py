"""OpenMHS driver for gh.jyf588/simgan: the SimGAN HopperURDFEnv-v3 environment (a Gymnasium family driver).

The card names four entry symbols of the clone; this package serves one of them, ``HopperURDFEnvV3``
(``my_pybullet_envs/hopper_env_v3.py:32``), through ``GymnasiumDriver``.  The environment is an old-style ``gym.Env``:
``reset()`` takes no seed, ``step(a)`` returns a four-tuple and ``seed(seed)`` is a separate method.  The Gymnasium
bridge handles exactly that legacy API (it calls ``seed()`` and retries ``reset()`` when ``reset(seed=...)`` is
refused), so the card's family-config decision stands; there is no deviation from the card.

The contract is derived from the environment's spaces: the action is a ``Box`` of three elements bounded by -1 and
+1 (``hopper_env_v3.py:100-103``) and the observation is an eleven-element ``Box`` with infinite bounds
(``hopper_env_v3.py:104-106``).  ``cap.world.step.v1`` takes ``{ticks, action: {values: [3 numbers]}}``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated
(R0): there is no hardware backend and no operator-required limit.

The ``fake`` backend is the package's own kinematic stand-in (``fake.py``); pybullet and ``gym==0.14.0`` are not
installed where the gate runs (``README.md:21-29``) and package code never imports the clone.  A backend name that
``backends`` does not list (``sim``) would be served by ``gym.make(env_id)`` (``GymnasiumDriver.open_native``); that
path needs the upstream packages and was not run here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002): the fake is a kinematic
reimplementation, so it claims F0, not the F1 rigid-body simulation of the upstream.  Every fact cites a line of the
clone at the pinned commit (23283d7b5629f1653567b2437bb28aac1cc17169).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "my_pybullet_envs/hopper_env_v3.py"
ROBOT = "my_pybullet_envs/hopper.py"


class Hopper(GymnasiumDriver):
    device_id = "simgan-hopper"
    env_id = "HopperURDFEnv-v3"
    env_kwargs = {"render": False}
    native = "my_pybullet_envs:HopperURDFEnvV3"
    backends = {"fake": ".fake:FakeHopperURDFEnvV3"}
    display_name = "SimGAN HopperURDFEnv-v3 (PyBullet hopper)"
    vendor, model = "jyf588", "HopperURDFEnv-v3"
    tags = ["simgan", "hopper", "pybullet", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("HopperURDFEnvV3 subclasses gym.Env", source="upstream_code", ref=f"{ENV}:32"),
        Fact("HopperURDFEnv-v3 is registered with entry point my_pybullet_envs:HopperURDFEnvV3 and "
             "max_episode_steps=500", source="upstream_code", ref="my_pybullet_envs/__init__.py:34-38"),
        Fact("The physics timestep is 1/500 s per Bullet substep", source="upstream_code", ref=f"{ENV}:60"),
        Fact("An environment step advances the simulation for range(control_skip) physics substeps and increments "
             "the timer at each substep", source="upstream_code", ref=f"{ENV}:243-250"),
        Fact("control_skip has constructor default 10", source="upstream_code", ref=f"{ENV}:40"),
        Fact("The action space is Box(low=-1, high=+1) with one element per controlled joint",
             source="upstream_code", ref=f"{ENV}:100-103"),
        Fact("The robot has three controlled joints, ctrl_dofs [3, 4, 5]", source="upstream_code",
             ref=f"{ROBOT}:53"),
        Fact("The action is compressed with tanh before it is used as the joint command",
             source="upstream_code", ref=f"{ENV}:221"),
        Fact("apply_action scales the action by max_forces and writes it as the torque of the controlled joints",
             source="upstream_code", ref=f"{ROBOT}:124-132"),
        Fact("max_forces starts as nominal_max_forces, [200.0] * 3", source="upstream_code",
             ref=f"{ROBOT}:48-49"),
        Fact("The observation is the five joint positions a_q[1:] followed by the six joint velocities a_dq",
             source="upstream_code", ref=f"{ROBOT}:167-175"),
        Fact("obs_scaling is [1.0] * 5 + [1.0] * 2 + [0.1] * 4: the last four velocities are scaled by 0.1",
             source="upstream_code", ref=f"{ROBOT}:51"),
        Fact("The observation space is Box(-inf, +inf) with one bound per observation value",
             source="upstream_code", ref=f"{ENV}:104-106"),
        Fact("The episode is not done only while every controlled joint speed is below 50 and the height is "
             "between 0.6 and 1.8", source="upstream_code", ref=f"{ENV}:281"),
        Fact("step returns (observation, reward, not not_done, {'sas_window': ...})", source="upstream_code",
             ref=f"{ENV}:283"),
        Fact("The reward is a 3.0 alive bonus, plus the average forward speed, minus 0.5 times the squared action "
             "sum, minus 3.0 per joint at its limit and minus an acceleration penalty capped at 5.0",
             source="upstream_code", ref=f"{ENV}:255-272"),
        Fact("The acceleration penalty weight acc_pen_weight defaults to 0.05", source="upstream_code",
             ref=f"{ENV}:53"),
        Fact("reset restarts the simulation, applies the timestep _ts and sets gravity (0, 0, -10)",
             source="upstream_code", ref=f"{ENV}:108-121"),
        Fact("The robot starts at base_init_pos [0, 0, 1.3] with zero orientation", source="upstream_code",
             ref=f"{ROBOT}:45-46"),
        Fact("With init_noise the reset perturbs the initial joint positions by 0.02 and velocities by 0.1",
             source="upstream_code", ref=f"{ROBOT}:91-96"),
        Fact("reset() takes no seed argument", source="upstream_code", ref=f"{ENV}:108"),
        Fact("seed(seed) replaces np_random with gym.utils.seeding.np_random(seed)", source="upstream_code",
             ref=f"{ENV}:312-315"),
        Fact("render defaults to True and opens a PyBullet GUI connection; render=False uses a headless client",
             source="upstream_code", ref=f"{ENV}:77-80"),
        Fact("The constructor selects the soft-floor, deformable-floor, low-power, EMF-power, heavy-head and "
             "randomization variants with boolean options", source="upstream_code", ref=f"{ENV}:44-51"),
        Fact("The model loads assets/hopper_my.urdf, or assets/hopper_my_heavyhead.urdf when heavy_head is set",
             source="upstream_code", ref=f"{ROBOT}:79-83"),
        Fact("The README creates a Python 3.6 conda environment and installs requirements.txt",
             source="vendor_doc", ref="README.md:21-29"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the fake state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The deployed backend is the
    #: package's kinematic fake, so the level is F0; the derived members are written out with the gaps.
    fidelity = {
        "engine": "custom:simgan-hopper-kinematic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.seed.v1 or a reset seed fixes the reset perturbation of the fake and the update is "
                     "deterministic, so one fake repeats a trajectory for the same seed and actions; the upstream "
                     "uses numpy's generator and adds observation and action noise by default, so the two do not "
                     "share trajectories",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in: no rigid-body, contact, actuator, sensor or noise model and "
            "no PyBullet, so it is F0 and cannot reproduce the upstream contact dynamics",
            "the upstream advances physics at 1/500 s and applies the action for a constructor-default "
            "control_skip=10 substeps (a 20 ms control period by default); the fake advances one 20 ms transition "
            "from a made-up kinematic update",
            "the fake draws the reset perturbation from Python's random.Random while upstream uses numpy's "
            "generator, and the upstream adds observation and action noise by default, so a seed gives different "
            "trajectories on the two",
            "the upstream termination and reward terms are computed here against the fake's kinematic state; the "
            "fake does not reproduce the upstream joint torques, forward speed or joint-limit penalties",
            "no rendering and no wall-clock pacing: realtime_factor 0, ticks advance simulated time by "
            "timestep_ms only; the upstream constructor opens a PyBullet GUI unless render=False",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "the upstream environment class never truncates; the registration max_episode_steps=500 is applied by "
            "gym.make, not by this fake and not by the bridge, so the fake has no truncation flag",
        ],
    }
