"""OpenMHS driver for gh.denisgriaznov/custommujocoenviromentforrl: the BallBalanceEnv MuJoCo model.

A ``MujocoDriver`` is configuration only: ``model_path`` names the MJCF model (the card's ``models[0]``,
``assets/ball_balance.xml``) and the bridge derives the whole contract from the model it loads.  ``cap.world.step.v1``
takes ``{ticks, action}`` with ``action.ctrl`` bounded per actuator by the model's ``actuator_ctrlrange`` (the two
``general`` actuators ``act_x`` and ``act_y`` each accept -1 to 1; ``assets/ball_balance.xml:25-27``), and
``cap.world.reset.v1`` takes ``{seed}`` and restores the model defaults.  The device is simulated (R0): no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream repository is a Gymnasium/MuJoCo ball-balancing example.  ``BallBalanceEnv`` (ball_balance_env.py:9)
wraps the same model with a 10-value observation, a constant reward and its own episode end; this package serves the
underlying MuJoCo world named by the card's ``family: mujoco`` and ``helper: MujocoDriver``, so the bridge's
observation is the simulator's time/qpos/qvel and the environment's reward, termination and observation slicing are
not applied (fidelity ``gaps``).  The card's entry symbol was confirmed in the clone (ball_balance_env.py:9).

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py): it parses the MJCF for the joint count, actuator count, control ranges and start positions but integrates
a placeholder motion, not MuJoCo's physics.  A backend name that ``backends`` does not list (``sim``) imports the real
``mujoco`` module and loads the same model file; that path was not run here.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "assets/ball_balance.xml"
MODEL_PATH = "../../../../robots/denisgriaznov/custommujocoenviromentforrl/" + MODEL
ENV = "ball_balance_env.py"
VIEWER = "model_viewer.py"
README = "README.md"


class BallBalance(MujocoDriver):
    device_id = "ball-balance"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "BallBalanceEnv MuJoCo model (ball balancing)"
    vendor, model = "denisgriaznov", "CustomMuJoCoEnviromentForRL"
    tags = ["ball-balance", "mujoco", "reinforcement-learning", "simulation", "world-model"]
    facts = [
        Fact("The repository is an example of creating a custom MuJoCo model and training a reinforcement-learning "
             "agent with the Gymnasium shell and StableBaselines", source="vendor_doc", ref=f"{README}:3"),
        Fact("The README describes a ball-balancing environment with a 10-value observation (position and speed for "
             "rotating the platform along two axes and moving the ball along three axes), a reward of 1 per step "
             "and episodes of 500 steps by default", source="vendor_doc", ref=f"{README}:12"),
        Fact("BallBalanceEnv subclasses gymnasium's MujocoEnv and utils.EzPickle", source="upstream_code",
             ref=f"{ENV}:9"),
        Fact("BallBalanceEnv loads the MJCF model at os.path.abspath('assets/ball_balance.xml') and constructs "
             "MujocoEnv with frame_skip 5", source="upstream_code", ref=f"{ENV}:25-28"),
        Fact("The observation space is an unbounded 10-value Box of float64", source="upstream_code",
             ref=f"{ENV}:23"),
        Fact("The default episode length is 500 steps", source="upstream_code", ref=f"{ENV}:20"),
        Fact("The environment returns a constant reward of 1.0 and terminates when the observation is not finite "
             "or its third value obs[2] is below 0", source="upstream_code", ref=f"{ENV}:36-44"),
        Fact("The environment truncates once step_number exceeds episode_len", source="upstream_code",
             ref=f"{ENV}:43"),
        Fact("The environment's observation concatenates the ball's first three qpos values, its first three qvel "
             "values, and the qpos and qvel of rotate_x and rotate_y", source="upstream_code", ref=f"{ENV}:62-68"),
        Fact("The model's box body has two hinge joints rotate_x and rotate_y on the x and y axes, each with range "
             "-.25 to .25 and damping 20", source="upstream_code", ref=f"{MODEL}:13-16"),
        Fact("The model's ball body has a freejoint named ball and a sphere geom of radius .05", source="upstream_code",
             ref=f"{MODEL}:18-20"),
        Fact("The model has two general actuators, act_x on rotate_x and act_y on rotate_y, each with ctrlrange -1 "
             "to 1 and gainprm '1000 0 0'", source="upstream_code", ref=f"{MODEL}:25-27"),
        Fact("model_viewer.py loads the XML with mujoco.MjModel.from_xml_path, creates mujoco.MjData, steps with "
             "mujoco.mj_step and reads model.opt.timestep", source="upstream_code", ref=f"{VIEWER}:21-33"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:ball_balance",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one data state; cap.world.reset.v1 "
                     "restores the model defaults and the bridge takes no seed input, so a run repeats exactly on "
                     "the same engine.  The fake stand-in is deterministic too, but its trajectories are not "
                     "MuJoCo's.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the deployed model is MuJoCo rigid-body dynamics with contacts (F1), but the fake backend is a "
            "pure-Python stand-in for the mujoco library: it parses the MJCF for the joint count, actuator count, "
            "control ranges and start positions and integrates a placeholder first-order hinge motion plus a "
            "placeholder free fall, not MuJoCo's equations, contacts, friction, actuator forces, sensors or noise",
            "MuJoCo was not installed where the gate ran, so no trajectory of this package was compared with the "
            "real engine; the fake's 2 ms timestep is a placeholder for MuJoCo's library default because the model "
            "sets no <option timestep>",
            "the bridge serves the raw MuJoCo world: observation is the simulator's time/qpos/qvel and the state "
            "adds ctrl/tick/timestep/seed; BallBalanceEnv's 10-value observation selection, constant reward 1.0, "
            "obs[2] < 0 termination and 500-step truncation (ball_balance_env.py:20-44, :62-68) are not applied "
            "by this driver",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no rendering, camera or visualisation is offered; the MJCF's camera, texture and light are part of "
            "the model tree but are not rendered by the bridge",
            "snapshot and restore use the bridge's fallback copy of time/qpos/qvel/ctrl (the stand-in has no "
            "mj_getState/mj_setState), so a restore is not the full integration state of the real engine",
        ],
    }
