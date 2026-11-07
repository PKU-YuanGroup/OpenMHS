"""OpenMHS driver for gh.osudrl/humanoid_hanoi: the Digit box-tower-of-Hanoi MuJoCo scene (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the card's first model (``models[0]``,
``sim/digit_sim/digit-v3-box-tower-of-hanoi.xml``) and the bridge derives the whole contract from the MJCF it loads.
The step action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (20 motors, one per named
leg and arm joint), and the state is the integration state of the model (``time_ms``, ``qpos``, ``qvel``, ``ctrl``)
plus the tick count; ``cap.world.reset.v1`` resets the data to the model defaults.  The device is simulated (R0): there
is no hardware backend, no e-stop path to a machine and no operator-required limit.

The card's ``models`` also lists the g1 and h1 MJCF scenes; this package serves the first one (Digit, the default
``--robot`` of the upstream evaluation entry point) because one MujocoDriver serves one model file.

The gate cannot install MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the model shape (actuator count, control ranges, joint dimensions, time
step) but its integration is a placeholder, not MuJoCo's physics; the driver's fidelity ``gaps`` say so.  A backend
name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path
was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of it at commit 64bc880efe38c7a357f57ac2d2bb888334ec0284.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "sim/digit_sim/digit-v3-box-tower-of-hanoi.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/osudrl/humanoid_hanoi/" + MODEL


class DigitHanoi(MujocoDriver):
    device_id = "digit-hanoi"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Digit v3 box tower of Hanoi (MuJoCo model)"
    vendor, model = "OSU Dynamic Robotics Laboratory", "Digit v3 (box tower of Hanoi)"
    tags = ["digit", "humanoid", "hanoi", "manipulation", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The card's first model is the MJCF scene digit-v3-box-tower-of-hanoi.xml, whose root element is "
             "<mujoco model='digit'>", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model integrates with timestep 0.0005 s, Newton solver, 50 iterations, impratio 20, elliptic cone "
             "and gravity 0 0 -9.80665", source="upstream_code", ref=f"{MODEL}:3"),
        Fact("The floating base of the torso is three slide joints (x, y and z, the z joint with ref 1.01) and a "
             "ball joint", source="upstream_code", ref=f"{MODEL}:89-92"),
        Fact("The scene adds three box bodies (box0, box1 and box2), each with three slide joints and a ball joint",
             source="upstream_code", ref=f"{MODEL}:360-391"),
        Fact("The actuator section has 20 motor actuators, one per named leg and arm joint, with per-motor ctrlrange: "
             "hip-roll, shoulder-roll, shoulder-pitch and elbow -1.4125 to 1.4125; hip-yaw and shoulder-yaw "
             "-1.5835307242068533 to 1.5835307242068533; hip-pitch -13.557993638726353 to 13.557993638726353; "
             "knee -14.457309387714753 to 14.457309387714753; toe-a and toe-b -0.8395188473154137 to "
             "0.8395188473154137", source="upstream_code", ref=f"{MODEL}:404-423"),
        Fact("The joint tree gives 82 qpos and 72 qvel coordinates: the base 3 slides and 1 ball, the three boxes 9 "
             "slides and 3 balls, and 30 hinges plus 6 balls in the legs and arms", source="upstream_code",
             ref=f"{MODEL}:89-387"),
        Fact("The equality section has six connect constraints coupling the left and right achilles rods, toe-a rods "
             "and toe-b rods", source="upstream_code", ref=f"{MODEL}:394-401"),
        Fact("The model has a gyro, an accelerometer and a magnetometer on the torso IMU site, with cutoff 34.9, 157 "
             "and 2.5 and noise 0.00173, 0.0396 and 0.001", source="upstream_code", ref=f"{MODEL}:425-428"),
        Fact("The upstream evaluation entry point defaults --robot to \"digit\", with \"h1\" and \"g1\" as the other "
             "choices", source="upstream_code", ref="eval.py:12"),
        Fact("The README names the Digit humanoid robot as the default robot", source="vendor_doc",
             ref="README.md:47"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:digit",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "input and a reset restores the model defaults, so a run repeats exactly on the same engine but "
                     "no seed selects a different one",
        },
        "timestep_ms": 0.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator control ranges and the joint dimensions but integrates a placeholder first-order motion of "
            "each actuated joint toward its control target, so trajectories, contacts and actuator dynamics are not "
            "MuJoCo's",
            "no mesh or texture of the stl asset directory is loaded and no contact, equality or tendon constraint "
            "is resolved by the stand-in; the six connect constraints of the model and the three box bodies are not "
            "simulated",
            "the gyro, accelerometer and magnetometer of the model are not simulated, so no sensor or noise model "
            "contributes to the state",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "snapshot and restore use the bridge's fallback copy of time, qpos, qvel and ctrl, not MuJoCo's full "
            "integration state, because the stand-in has no mj_getState or mj_setState",
            "no physical Digit robot is modelled and nothing was validated against the hardware",
            "the package serves the card's first model only; the g1 and h1 MJCF scenes are separate models",
        ],
    }
