"""OpenMHS driver for gh.ritalaezza/gym-agx: the BendWire-v0 environment (a Gymnasium family driver).

``BendWire-v0`` is a legacy OpenAI Gym environment of the ReForm sandbox for deformable linear objects.  It is a
simulated device (R0): the AGX Dynamics engine runs in-process behind ``gym_agx.envs:BendWireEnv``, and the bridge
serves ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  The action is a ``Box(-1, 1)`` of
``n_actions`` values; for the default right gripper that is three velocity commands (x, y, z).  There is no hardware
backend, no e-stop path to a machine and no operator-required limit.

AGX Dynamics and its licence are not installed where the gate runs (the package imports ``agx*`` at module import,
``gym_agx/envs/agx_env.py:9-20``), and package code never imports the clone, so the ``fake`` backend is the package's
own pure Python surrogate.  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make(env_id)`` through the bridge (``GymnasiumDriver.open_native``); that path needs gym, numpy, matplotlib and
scipy (``setup.cfg:21-25``) plus AGX Dynamics and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant and
rule in ``facts`` cites a line of the clone at the pinned commit 1773c4aa3ecc2e509623ff3d14163f9d5721f227.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "gym_agx/__init__.py"
BW_ENV = "gym_agx/envs/explicit/bend_wire_env.py"
GOAL_ENV = "gym_agx/envs/agx_goal_env.py"
DLO_ENV = "gym_agx/envs/dlo_env.py"
BW_SIM = "gym_agx/sims/bend_wire.py"
END_EFFECTOR = "gym_agx/rl/end_effector.py"
UTILS = "gym_agx/utils/utils.py"


class BendWire(GymnasiumDriver):
    device_id = "bendwire"
    env_id = "BendWire-v0"
    native = "gym_agx.envs:BendWireEnv"
    backends = {"fake": ".fake:FakeBendWireEnv"}
    display_name = "Gym AGX BendWire-v0 (deformable linear object)"
    vendor, model = "Rita Laezza", "BendWire-v0"
    tags = ["gym-agx", "bend-wire", "deformable-linear-object", "reinforcement-learning", "simulation",
            "agx-dynamics"]
    facts = [
        Fact("BendWire-v0 is registered with entry point gym_agx.envs:BendWireEnv, n_substeps=2 and "
             "max_episode_steps=1000", source="upstream_code", ref=f"{INIT}:30-35"),
        Fact("The action space is Box(-1, 1) with one element per velocity-controlled end-effector constraint",
             source="upstream_code", ref=f"{GOAL_ENV}:142"),
        Fact("The default right gripper has three velocity-controlled translation constraints (x, y and z) and a "
             "hinge constraint that is not velocity-controlled, so its action vector has three elements",
             source="upstream_code", ref=f"{BW_ENV}:74-102"),
        Fact("The action time step is the AGX simulation time step times n_substeps", source="upstream_code",
             ref=f"{GOAL_ENV}:149-151"),
        Fact("The BendWire scene builder sets TIMESTEP to 1/100 s (100 Hz) and N_SUBSTEPS to 2", source="upstream_code",
             ref=f"{BW_SIM}:34-35"),
        Fact("The reward is dense with range -1.5 to 1.5, success when the curvature distance is below 0.05, and "
             "success does not end the episode", source="upstream_code", ref=f"{BW_ENV}:110-114"),
        Fact("The dense reward is the negative curvature distance clipped to the configured reward range, or the "
             "upper reward bound minus 100 times the end-effector speed clipped to zero and the upper bound when the "
             "goal is reached", source="upstream_code", ref=f"{BW_ENV}:24-37"),
        Fact("Rewards are rounded with np.round(..., decimals=4)", source="upstream_code", ref=f"{BW_ENV}:39-40"),
        Fact("Success means the curvature distance is below the configured threshold", source="upstream_code",
             ref=f"{BW_ENV}:42-44"),
        Fact("step() returns the legacy Gym tuple observation, reward, done, info", source="upstream_code",
             ref=f"{GOAL_ENV}:166-178"),
        Fact("reset() restores the start scene and returns a fresh observation", source="upstream_code",
             ref=f"{GOAL_ENV}:180-188"),
        Fact("The default observation configuration adds DLO curvature and end-effector position observations, with "
             "DLO curvature and end-effector velocity as goals", source="upstream_code", ref=f"{BW_ENV}:104-108"),
        Fact("The observation is a dict with observation, achieved_goal and desired_goal", source="upstream_code",
             ref=f"{DLO_ENV}:107-116"),
        Fact("construct_space gives every numpy observation leaf a Box with infinite bounds", source="upstream_code",
             ref=f"{UTILS}:17-20"),
        Fact("The right gripper's max_velocity is 10/1000 m/s and its max_acceleration is 10/1000 m/s^2",
             source="upstream_code", ref=f"{BW_ENV}:79-80"),
        Fact("rescale_velocity limits the speed change per call to max_acceleration*dt and clamps the speed to "
             "max_velocity", source="upstream_code", ref=f"{END_EFFECTOR}:183-186"),
        Fact("The goal assembly is added from the goal scene file and a randomized goal is sampled only when "
             "randomized_goal is set", source="upstream_code", ref=f"{DLO_ENV}:134-147"),
        Fact("The BendWire cable is declared with LENGTH 0.1 m, RADIUS as LENGTH/100, LENGTH increased by "
             "2*RADIUS, and RESOLUTION 1000 segments per metre", source="upstream_code", ref=f"{BW_SIM}:36-39"),
        Fact("get_cable_curvature allocates cable_segment_edges.shape[1] - 2 values, one per adjacent pair of "
             "cable segments", source="upstream_code", ref=f"{UTILS}:243-248"),
        Fact("AgxGoalEnv.__init__ calls self.seed(); the class defines no seed method of its own, so the method "
             "comes from its external Gym base", source="upstream_code", ref=f"{GOAL_ENV}:133-134"),
        Fact("The README describes the package as the OpenAI Gym interface for the AGX Dynamics simulation software",
             source="vendor_doc", ref="README.md:3"),
        Fact("The environments import AGX Dynamics and raise DependencyNotInstalled without it", source="upstream_code",
             ref="gym_agx/envs/agx_env.py:9-20"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F1"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "agx-dynamics:BendWire-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the start scene and the default fixed goal are static, so a fresh environment repeats a run; "
                     "the package fake seeds its Python RNG from reset(seed).  BendWireEnv.reset() takes no seed "
                     "argument and the class defines no seed method of its own, so on the upstream sim backend "
                     "cap.world.seed.v1 cannot be shown to reach AGX Dynamics; that path was not run",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the package fake is a pure Python analytic stand-in, not AGX Dynamics: the cable, contacts, plasticity "
            "and the AGX solver are not modelled, and its curvature length, start state and goal arrays are "
            "placeholders",
            "the real cable segment count and the saved scene state live in the binary "
            "gym_agx/envs/assets/bend_wire.agx file, which the package does not parse; the fake returns 8 curvature "
            "values while the device returns one per adjacent segment pair (about 100 for the 0.1 m cable at 1000 "
            "segments per metre), and AGX sets the exact count when it initializes the cable",
            "the AGX time step is set by the scene builder to 1/100 s and BendWire-v0 runs n_substeps=2, so one "
            "action is 20 ms; the fake integrates one 20 ms step instead of two 10 ms AGX steps",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the fake stores observations as Python lists; upstream returns numpy arrays built by construct_space",
        ],
    }
