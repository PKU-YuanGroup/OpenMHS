"""OpenMHS driver for gh.liuskywalkerjskd/mujoco_iiwa7_r800: the KUKA LBR iiwa 7 R800 MuJoCo model.

A ``MujocoDriver`` is configuration only: ``model_path`` names the MJCF model (the card's ``models[0]``,
``iiwa7_mjcf/iiwa7_tuned.xml``) and the bridge derives the contract from the model it loads.  ``cap.world.step.v1``
takes ``{ticks, action: {ctrl: [7 numbers]}}``, bounded per actuator by the model's ``actuator_ctrlrange``
(the seven arm joints); ``cap.world.reset.v1`` takes ``{seed}`` and restores the model defaults.  The world state is
the integration state of the model (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot install MuJoCo where it runs (no network, no pip), so the ``fake`` backend is this package's
stand-in ``mujoco`` module (fake.py).  It parses the model file for the model shape (seven hinge joints, seven
actuators and their control ranges) and advances a placeholder first-order motion, not MuJoCo's physics; the
fidelity ``gaps`` say so.  A backend name that ``backends`` does not list imports the real ``mujoco`` module and loads
the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of the clone at commit bf300255e9b511b6ad43ab40727347033a2619dd.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to the clone root.
MODEL = "iiwa7_mjcf/iiwa7_tuned.xml"
#: The same file, relative to this package (the clone under robots/ at the pinned commit stays read-only).
MODEL_PATH = "../../../../robots/liuskywalkerjskd/mujoco_iiwa7_r800/" + MODEL
README = "README.md"
TUNING = "TUNING_REPORT.md"
CONTROLLER = "iiwa7_controller/controller.py"


class Iiwa7MuJoCo(MujocoDriver):
    device_id = "iiwa7"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "KUKA LBR iiwa 7 R800 (MuJoCo MJCF)"
    vendor, model = "KUKA / liuskywalkerjskd iiwa7-mujoco", "LBR iiwa 7 R800"
    tags = ["arm", "iiwa7", "kuka", "manipulator", "mujoco", "robot", "simulation"]
    facts = [
        Fact("The package's model is the MJCF file iiwa7_mjcf/iiwa7_tuned.xml, whose root element is "
             "'<mujoco model=\"iiwa7_tuned\">'", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model declares angle=radian with autolimits=true, so its joint and control ranges are radians",
             source="upstream_code", ref=f"{MODEL}:23"),
        Fact("The model uses the implicitfast integrator with a timestep of 0.002 s", source="upstream_code",
             ref=f"{MODEL}:25"),
        Fact("The model header describes its tuning as a general actuator with gaintype=fixed, biastype=affine, "
             "gainprm=2000 and biasprm '0 -2000 -200' (PD kp=2000 kd=200), per-joint forcerange, armature 0.1 and "
             "seven contact excludes", source="upstream_code", ref=f"{MODEL}:14-20"),
        Fact("The iiwa default class gives every arm joint the axis 0 0 1, damping 0.5 and armature 0.1, and the "
             "default general actuators gaintype=fixed, biastype=affine, gainprm=2000 and biasprm '0 -2000 -200'",
             source="upstream_code", ref=f"{MODEL}:28-30"),
        Fact("The joint1 default class sets the joint range -2.96706 to 2.96706 rad and the matching ctrlrange, "
             "with a forcerange of -176 to 176", source="upstream_code", ref=f"{MODEL}:31-34"),
        Fact("The joint2 default class sets the joint range -2.09440 to 2.09440 rad and the matching ctrlrange, "
             "with a forcerange of -176 to 176", source="upstream_code", ref=f"{MODEL}:35-38"),
        Fact("The joint3_mid default class sets the joint range -2.96706 to 2.96706 rad and the matching ctrlrange, "
             "with a forcerange of -110 to 110", source="upstream_code", ref=f"{MODEL}:39-42"),
        Fact("The joint4_mid default class sets the joint range -2.09440 to 2.09440 rad and ref 1.5708, with the "
             "matching ctrlrange and a forcerange of -110 to 110", source="upstream_code", ref=f"{MODEL}:43-46"),
        Fact("The joint5_mid default class sets the joint range -2.96706 to 2.96706 rad and the matching ctrlrange, "
             "with a forcerange of -110 to 110", source="upstream_code", ref=f"{MODEL}:47-50"),
        Fact("The joint6_distal default class sets the joint range -2.09440 to 2.09440 rad and ref -1.5708, with "
             "the matching ctrlrange and a forcerange of -40 to 40", source="upstream_code", ref=f"{MODEL}:51-54"),
        Fact("The joint7_distal default class sets the joint range -3.05433 to 3.05433 rad and the matching "
             "ctrlrange, with a forcerange of -40 to 40", source="upstream_code", ref=f"{MODEL}:55-58"),
        Fact("The model has seven joints, iiwa_joint_1 to iiwa_joint_7, on the link bodies iiwa_link_1 to "
             "iiwa_link_7", source="upstream_code", ref=f"{MODEL}:102-153"),
        Fact("The model has seven general actuators, actuator1 to actuator7, on iiwa_joint_1 to iiwa_joint_7, each "
             "naming the matching joint default class so it takes that class's ctrlrange",
             source="upstream_code", ref=f"{MODEL}:174-182"),
        Fact("The arm's tool point is the site attachment_site at 0 0 0.05 on iiwa_link_7, 5 cm along its local +Z",
             source="upstream_code", ref=f"{MODEL}:147-153"),
        Fact("The model excludes seven non-adjacent body pairs from collision, from iiwa_link_0/iiwa_link_1 to "
             "iiwa_link_5/iiwa_link_7", source="upstream_code", ref=f"{MODEL}:164-172"),
        Fact("The model has one home keyframe whose qpos and ctrl are all zeros", source="upstream_code",
             ref=f"{MODEL}:184-190"),
        Fact("iiwa7_tuned.xml is the MuJoCo (MJCF) model of the KUKA LBR iiwa 7 R800, converted from the ROS "
             "iiwa_stack URDF and tuned to mujoco_menagerie/kuka_iiwa_14 engineering conventions",
             source="vendor_doc", ref=f"{README}:3-5"),
        Fact("The home keyframe matches the real robot's ready pose of J4 = -90 degrees and J6 = +90 degrees, with "
             "the other joints at 0 degrees", source="vendor_doc", ref=f"{README}:319-322"),
        Fact("Because iiwa7.xml sets ref=+1.5708 on J4 and ref=-1.5708 on J6, qpos zero is that home pose; the "
             "physical angle is qpos - ref", source="vendor_doc", ref=f"{README}:330-337"),
        Fact("The pose API takes a 7-vector [x, y, z, qx, qy, qz, qw] in the base frame, in metres and with the "
             "quaternion in xyzw order", source="vendor_doc", ref=f"{README}:131-141"),
        Fact("The controller drives only the seven arm joints: ARM_NV = 7 and ARM_NU = 7, so any gripper channel "
             "beyond them stays independent", source="upstream_code", ref=f"{CONTROLLER}:47-50"),
        Fact("The tuned model's forcerange is -176 to 176 N m for J1/J2, -110 to 110 N m for J3 to J5 and -40 to "
             "40 N m for J6/J7, from the iiwa7 datasheet", source="vendor_doc", ref=f"{TUNING}:21"),
        Fact("The clone also ships iiwa7_with_gripper.xml (the arm plus a Robotiq 2F-85 on the flange) and "
             "robotiq_2f85.xml (the standalone gripper)", source="vendor_doc", ref=f"{README}:188-197"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:iiwa7_tuned",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed input (cap.world.reset.v1 accepts a seed for the class contract and ignores it) and "
                     "restores the model defaults, so a run repeats on the same engine but no seed selects a "
                     "different state",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the model file for the "
            "joint count, the actuator count and the per-actuator control ranges but integrates a placeholder "
            "first-order motion of each actuated joint toward its control target, so trajectories, contacts, "
            "inertias, damping, armature, PD gains and forceranges are not MuJoCo's",
            "no mesh or texture of the meshes directory is loaded and no contact, equality or tendon constraint "
            "is resolved by the stand-in; the seven contact excludes of the model are not applied",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering is offered and no physical iiwa7 robot is modelled; nothing was validated against KUKA "
            "hardware",
            "only the card's first model is served: the composite iiwa7_with_gripper.xml (eight actuators, the "
            "gripper on ctrl[7]) and the standalone robotiq_2f85.xml are not served by this package",
        ],
    }
