"""OpenMHS driver for gh.limxdynamics/humanoid-mujoco-sim: the LimX HU_D03 humanoid MJCF as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model (``models[0]``,
``humanoid-description/HU_D03_description/xml/HU_D03_03.xml``) and the bridge derives the whole contract from the
model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked
against the model's ``actuator_ctrlrange`` (one element per motor actuator) before it is written to ``data.ctrl``,
then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` +
``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``).  The device is simulated (R0): there is no hardware backend and no
operator-required limit; the model's control ranges are derived from the MJCF file itself.

The upstream repository is a MuJoCo viewer around the LimX low-level SDK: ``simulator.py`` loads an MJCF by robot
type, steps it, receives ``RobotCmd`` from the SDK and publishes ``RobotState``/``ImuData`` back (README.md:5,
simulator.py:25-26, :69, :84, :132).  This package serves the MuJoCo model, not the SDK topic layer.

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and never
imported).  The card's model files live in the ``humanoid-description`` submodule, which the pinned superproject
commit records as a gitlink (``git ls-tree`` shows ``160000 commit``), so no Fact cites a line inside it: gate G4
reads the superproject tree and would report REF_MISSING.  The driver still loads the model from the checkout path.
Every Fact below cites a line of the superproject at commit
``4a1f297725660172e590a239020cc08fb3798aa3``.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the actuator count, the control ranges and the joint dimensions, but its
integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same model file; that path was
not run here.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "humanoid-description/HU_D03_description/xml/HU_D03_03.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/limxdynamics/humanoid-mujoco-sim/" + MODEL


class LimxHumanoid(MujocoDriver):
    device_id = "limx-hu-d03"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "LimX HU_D03 humanoid (MuJoCo simulation)"
    vendor, model = "LimX Dynamics", "HU_D03_03"
    tags = ["limx", "hu-d03", "humanoid", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository is a MuJoCo simulation environment for LimX humanoid robots (HU_D03, HU_D04) used to "
             "visualize models, test motion controllers and validate RL policies before deploying to hardware",
             source="vendor_doc", ref="README.md:5"),
        Fact("The prerequisites are Linux x86_64; the bundled prebuild/kinematic_projection helper is x86_64-only "
             "and simulation functionality is limited on aarch64", source="vendor_doc", ref="README.md:12-14"),
        Fact("The README installs the LimX motion control SDK wheel from limxsdk-lowlevel/python3/amd64",
             source="vendor_doc", ref="README.md:27"),
        Fact("The available models are HU_D03_03 and HU_D04_01", source="vendor_doc", ref="README.md:32"),
        Fact("The upstream loads the model with mujoco.MjModel.from_xml_path(asset_path) and creates MjData from it",
             source="upstream_code", ref="simulator.py:25-26"),
        Fact("The upstream takes the actuator count from model.nu and the joint count from model.njnt",
             source="upstream_code", ref="simulator.py:29-32"),
        Fact("The upstream takes the integration step from model.opt.timestep", source="upstream_code",
             ref="simulator.py:45"),
        Fact("The upstream subscribes its simulation-side callback with robot.subscribeRobotCmdForSim",
             source="upstream_code", ref="simulator.py:69"),
        Fact("The simulation loop calls mujoco.mj_step(model, data) on every iteration", source="upstream_code",
             ref="simulator.py:84"),
        Fact("For the non-floating-base branch the upstream computes data.ctrl from the received RobotCmd as "
             "Kp * (q_cmd - q) + Kd * (dq_cmd - dq) + tau", source="upstream_code", ref="simulator.py:105-115"),
        Fact("The upstream publishes the robot state to the LimX SDK with publishRobotStateForSim",
             source="upstream_code", ref="simulator.py:132"),
        Fact("The upstream initializes the LimX SDK robot with robot.init(robot_ip) before starting the simulation",
             source="upstream_code", ref="simulator.py:218"),
        Fact("The upstream selects the model from the ROBOT_TYPE environment variable and passes it to "
             "SimulatorMujoco", source="upstream_code", ref="simulator.py:229-236"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:HU_D03_03",
        "fidelity_level": "F1",
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator control ranges and the qpos/qvel dimensions but integrates a placeholder velocity proportional "
            "to each control value, so trajectories, contacts, friction and actuator dynamics are not MuJoCo's",
            "no mesh or texture of the model's asset directory is loaded by the stand-in and no contact, equality, "
            "tendon or actuator constraint of the model is resolved; the free base is not integrated",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "the upstream simulator exchanges RobotCmd, RobotState and ImuData with the LimX SDK (simulator.py:69, "
            ":132); this package exposes only the MuJoCo ctrl vector and integration state, not that topic layer",
            "the upstream viewer, the kinematic_projection helper and the virtual joystick are not part of this "
            "driver; it has no rendering",
            "no physical robot is modelled and nothing was validated against the HU_D03 hardware",
        ],
    }
