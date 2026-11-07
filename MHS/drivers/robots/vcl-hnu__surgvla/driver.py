"""OpenMHS driver for gh.vcl-hnu/surgvla: the SurRoL ECMReach-v0 environment (a Gymnasium family driver).

The upstream repository is SurgVLA-Bench, built on the SurRoL laparoscopic surgical simulator.  This package serves
one of its registered Gym environments, ``ECMReach-v0`` (surrol/gym/__init__.py:43-47), whose entry class is
``surrol.tasks.ecm_reach:ECMReach``.  It is a simulated R0 device: the environment is a PyBullet scene, no hardware
backend is declared, and its action space (a 3-D velocity box from -1 to 1) is the only bound.

The card's family-config decision is right for this environment: all three served capabilities come from the
Gymnasium bridge (``cap.world.step.v1``, ``cap.world.reset.v1``, ``cap.world.seed.v1``).  The bridge derives the
action contract from the environment's ``gym.spaces.Box``, so the driver declares no limit of its own and the
``fidelity`` gap says what the fake does not model.

The gate never imports the clone (PyBullet, numpy and the URDF assets are not installed there), so ``backends`` names
the package's pure-Python fake (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make("ECMReach-v0")`` through the family driver; that path was not run here.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and its evidence is contract_checked, never an MHS-Device level.

Every fact cites a line of the clone at the pinned commit 9446d6544757830c8ad184a5faadcde5cd2e4905.
"""

from mhs.driver import Fact, GymnasiumDriver

SURROL_ENV = "surrol/gym/surrol_env.py"
ECM_ENV = "surrol/tasks/ecm_env.py"
ECM_REACH = "surrol/tasks/ecm_reach.py"
ECM_ROBOT = "surrol/robots/ecm.py"
GYM_INIT = "surrol/gym/__init__.py"


class SurgVLAECMReach(GymnasiumDriver):
    device_id = "surgvla-ecm-reach"
    env_id = "ECMReach-v0"
    native = "surrol.tasks.ecm_reach:ECMReach"
    backends = {"fake": ".fake:FakeECMReachEnv"}
    action_space_ref = f"{SURROL_ENV}:77"
    display_name = "SurRoL ECMReach-v0 (laparoscopic ECM reach)"
    vendor, model = "vcl-hnu", "SurgVLA-Bench / ECMReach-v0"
    tags = ["surgical-robotics", "laparoscopy", "ecm", "reach", "reinforcement-learning", "simulation", "gymnasium",
            "pybullet", "surrol", "surgvla"]
    facts = [
        Fact("ECMReach-v0 is registered with entry point surrol.tasks.ecm_reach:ECMReach and "
             "max_episode_steps=50", source="upstream_code", ref=f"{GYM_INIT}:43-47"),
        Fact("The ECM action size is 3", source="upstream_code", ref=f"{ECM_ENV}:25"),
        Fact("The action space is a Box from -1.0 to 1.0 with one bound per action element",
             source="upstream_code", ref=f"{SURROL_ENV}:77"),
        Fact("ECMReach selects the dmove action mode", source="upstream_code", ref=f"{ECM_REACH}:11"),
        Fact("In dmove mode the action is scaled by 0.01 and added to the RCM position, then sent through the ECM "
             "inverse kinematics", source="upstream_code", ref=f"{ECM_ENV}:138-145"),
        Fact("The ECMReach workspace limits are ((0.45, 0.55), (-0.05, 0.05), (0.60, 0.70))",
             source="upstream_code", ref=f"{ECM_REACH}:12"),
        Fact("A reset draws the goal uniformly from the workspace limits", source="upstream_code",
             ref=f"{ECM_REACH}:29-34"),
        Fact("The ECM starts at (0.45, 0.05, 0.70): the workspace lower x, upper y and upper z",
             source="upstream_code", ref=f"{ECM_REACH}:12-22"),
        Fact("The success threshold is 0.005 m: DISTANCE_THRESHOLD is 0.005 and SCALING is 1.0",
             source="upstream_code", ref=f"{ECM_ENV}:27-31"),
        Fact("The sparse reward is 0 on success and -1 otherwise: compute_reward is _is_success - 1",
             source="upstream_code", ref=f"{ECM_ENV}:73-77"),
        Fact("The observation is a Dict with the keys observation, achieved_goal and desired_goal",
             source="upstream_code", ref=f"{ECM_ENV}:118-122"),
        Fact("ECMReach sets has_object to False, so object_pos is empty and the observation vector is the 6-value "
             "robot state", source="upstream_code", ref=f"{ECM_ENV}:42-116"),
        Fact("The step returns (observation, reward, done, info) and done is always False",
             source="upstream_code", ref=f"{SURROL_ENV}:109-119"),
        Fact("A reset rebuilds the scene, resamples the goal and returns the observation",
             source="upstream_code", ref=f"{SURROL_ENV}:121-141"),
        Fact("EcmEnv sets the step duration to 0.1 s", source="upstream_code", ref=f"{ECM_ENV}:48"),
        Fact("SurRoLEnv.step advances the simulation by step(self._duration)", source="upstream_code",
             ref=f"{SURROL_ENV}:102"),
        Fact("The simulation loop calls p.stepSimulation() int(duration * 240) times, i.e. 240 physics steps per "
             "simulated second", source="upstream_code", ref="surrol/utils/pybullet_utils.py:18-20"),
        Fact("The environment's seed() stores numpy's generator and returns [seed]", source="upstream_code",
             ref=f"{SURROL_ENV}:160-162"),
        Fact("The goal draw uses numpy's global random generator (np.random.rand)",
             source="upstream_code", ref=f"{ECM_REACH}:32"),
        Fact("The ECM has 4 degrees of freedom and its end-effector link index is 4", source="upstream_code",
             ref=f"{ECM_ROBOT}:60-62"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the last observation and tick stay readable")
    #: Fidelity contract of the model as deployed (spec 05-fidelity section 2).  The upstream environment is a
    #: PyBullet rigid-body scene (F1); the package's checked backend is the kinematic fake of fake.py, and the gaps
    #: say exactly where it differs and that the sim backend was not run.
    fidelity = {
        "engine": "pybullet",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the fake's random.Random and the kinematic step is deterministic, so one "
                     "seed and one action sequence repeat a trajectory; upstream's seed() stores a numpy Generator "
                     "that _sample_goal does not use (it draws from the global numpy RNG), so the fake's seeded goal "
                     "stream is a stand-in, not upstream's",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream model is PyBullet rigid-body dynamics with contacts and ECM inverse kinematics "
            "(surrol/gym/surrol_env.py:93-119, surrol/tasks/ecm_env.py:125-145); this package's fake moves the "
            "end effector kinematically by action * 0.01 m and holds the orientation at zero, so its trajectories are "
            "not the upstream ones",
            "no actuator, sensor or noise model is declared by the clone; the F1 claim stops at rigid-body dynamics "
            "with contacts and the model was never validated against a physical ECM",
            "the sim backend (gym.make('ECMReach-v0') on the PyBullet environment) was not run where the gate ran; "
            "only the fake backend is checked",
            "the seed path is a stand-in: upstream seed() stores numpy's generator but _sample_goal uses the global "
            "numpy RNG (surrol/tasks/ecm_reach.py:32), so the fake seeds its own random.Random instead",
            "no wall-clock pacing: realtime_factor 0 and lockstep; the physics timestep is 1000/240 ms "
            "(surrol/utils/pybullet_utils.py:18-20) and the control period is 100 ms: one env.step advances "
            "self._duration = 0.1 s, i.e. 24 physics steps (surrol/tasks/ecm_env.py:48, surrol/gym/surrol_env.py:102); "
            "one bridge tick is one env.step, and the fake advances that 100 ms transition without modelling the "
            "substeps",
            "snapshot and restore are not offered: the upstream environment exposes no get_state/set_state",
            "the fake loads no URDF assets and offers no rendering",
        ],
    }
