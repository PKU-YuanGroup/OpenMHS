"""OpenMHS driver for gh.carolzyy/modesuite: the MoDe-Spot-Bend-v0 Isaac Lab environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values}`` shaped by the environment's action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend and no machine to
which an e-stop path could lead.

The upstream environment is a Gymnasium/Isaac Lab simulation, not a hardware driver: ``task/Bend/__init__.py:11-13``
registers ``MoDe-Spot-Bend-v0`` with entry point ``task.Bend.spot_bend_env:SpotBendRodEnv``, and the environment
needs NVIDIA Isaac Sim 4.2.0, Isaac Lab and a GPU (README.md:19 and :50-53).  The gate neither installs nor imports
the clone, and gymnasium is not importable there, so the ``fake`` backend is the package's own pure Python kinematic
stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id, **env_kwargs)`` (GymnasiumDriver.open_native); that path needs the upstream stack and was
not run here.  The action-space bounds are not written in the clone (the Box comes from Isaac Lab's DirectRLEnv),
so the fake uses marked placeholder bounds; the driver declares no Limit and no Fact about a bound the clone does
not state.

This package is model-authored and unreviewed: it is checked on the fake backend only, and the fidelity contract
below describes the fake that was actually exercised.
"""

from mhs.driver import Fact, GymnasiumDriver

BEND = "task/Bend/spot_bend_env.py"
BEND_INIT = "task/Bend/__init__.py"
README = "README.md"


class MoDeSpotBend(GymnasiumDriver):
    device_id = "modesuite-spot-bend"
    env_id = "MoDe-Spot-Bend-v0"
    native = "task.Bend.spot_bend_env:SpotBendRodEnv"
    backends = {"fake": ".fake:FakeSpotBendEnv"}
    display_name = "MoDeSuite MoDe-Spot-Bend-v0 (simulated Spot mobile manipulator)"
    vendor, model = "carolzyy", "MoDeSuite MoDe-Spot-Bend-v0"
    tags = ["modesuite", "mobile-manipulation", "deformable-objects", "isaac-lab", "simulation", "gymnasium"]
    facts = [
        Fact("MoDeSuite is built on NVIDIA Isaac Sim and the Isaac Lab framework", source="vendor_doc",
             ref=f"{README}:19"),
        Fact("The prerequisites are Ubuntu 22.04, Python 3.10, NVIDIA Isaac Sim 4.2.0 and Isaac Lab",
             source="vendor_doc", ref=f"{README}:50-53"),
        Fact("MoDe-Spot-Bend-v0 is registered with entry point task.Bend.spot_bend_env:SpotBendRodEnv",
             source="upstream_code", ref=f"{BEND_INIT}:11-13"),
        Fact("The action space has 9 components: 3 for the base and 6 for the arm", source="upstream_code",
             ref=f"{BEND}:21"),
        Fact("The observation space has 58 components and the rod is sampled at node_num=4 points",
             source="upstream_code", ref=f"{BEND}:25-26"),
        Fact("The simulation dt is 1/200 s and the decimation is 2", source="upstream_code", ref=f"{BEND}:19-33"),
        Fact("SpotBendRodEnv sets self.dt = cfg.sim.dt * cfg.decimation", source="upstream_code", ref=f"{BEND}:128"),
        Fact("The episode length is episode_length_s = 1000.0/40.0, i.e. 25 s", source="upstream_code",
             ref=f"{BEND}:20"),
        Fact("The target position is [3, 3, 1]", source="upstream_code", ref=f"{BEND}:47"),
        Fact("The first three action components drive the base and the last six the arm; the arm target is "
             "command + dt * command * action_scale", source="upstream_code", ref=f"{BEND}:205-214"),
        Fact("The observation concatenates sampled rod nodal positions, root position, root quaternion, target, "
             "joint positions and joint velocities", source="upstream_code", ref=f"{BEND}:284-293"),
        Fact("The reward is the negative sum of four target distances, +1 when the arm end or the rod end beats "
             "its reference, +10 when the flag is set and -500 when the base is unbalanced", source="upstream_code",
             ref=f"{BEND}:317-325"),
        Fact("reach_flag is true when the rod end is closer than 0.3 to the target", source="upstream_code",
             ref=f"{BEND}:330-335"),
        Fact("The base is unbalanced when the gravity direction deviates by more than 45 degrees",
             source="upstream_code", ref=f"{BEND}:249-253"),
        Fact("An episode ends on timeout or when reach_flag or the balance check fires", source="upstream_code",
             ref=f"{BEND}:342-345"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, determinism kind and lockstep clock; they are written out together with what the fake omits.
    fidelity = {
        "engine": "isaac-lab:MoDe-Spot-Bend-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the package's fake resets from Python's random.Random(seed) and its transitions are "
                     "deterministic, so one seed repeats a trajectory; the upstream Isaac Lab environment seeds "
                     "PhysX and its samplers separately, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic/kinematic stand-in (F0): it has no rigid-body, contact or soft-body dynamics "
            "and no PhysX scene, so forces, contacts, friction, deformable-rod behaviour and the 10 ms physics "
            "decimation of the upstream environment are not modelled",
            "the upstream environment needs NVIDIA Isaac Sim 4.2.0, Isaac Lab, a GPU and USD assets "
            "(README.md:19 and :50-53); the sim backend was not run and the fake was never compared with it",
            "the fake returns the configured 58-element observation as Python floats and a simplified distance "
            "reward; upstream returns torch tensors and the four-term reward of compute_rewards",
            "no actuator, sensor, camera or noise model is implemented and there is no rendering",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state, so determinism "
            "is seeded rather than exact",
        ],
    }
