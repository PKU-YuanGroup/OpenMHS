"""OpenMHS driver for gh.simple-robotics/simple: the pinned MuJoCo Humanoid model.

The upstream is the Simple physics engine: a C++ core with pybind11 bindings (``simple.Simulator``) and a set of
sandbox scripts.  The card classifies the repository as ``family: ros`` with the ``RosDriver`` helper, but the clone
contains no ROS node, publisher, subscriber, service or action endpoint: its ``cmake/ros.cmake`` and
``cmake/ros2.cmake`` are build helpers, not a runtime interface.  The card's model, ``sandbox/robots/humanoid.xml``
(``models[0]``), is a MuJoCo MJCF, and the upstream itself runs that file in MuJoCo when the humanoid sandbox is
started with ``--mujoco``: ``sandbox/humanoid_mj.py:115-116`` calls ``runMujocoXML(model_path, args)``, and
``sandbox/sim_utils.py:253-279`` loads the same XML with ``mujoco.MjModel.from_xml_path`` and integrates it with
``mujoco.mj_step``.  This package therefore uses the SDK's ``MujocoDriver`` family (DEVIATION FROM THE CARD, recorded
in RESULT.json) and serves that model's control vector and integration state through ``cap.world.step.v1`` and
``cap.world.reset.v1``.

The other upstream runtime, the Simple engine loop at ``sandbox/humanoid_mj.py:84-88``, is not exposed: the engine is
a C++/pybind class, it is not installed here, and no SDK family takes a C++ simulator class.  A direct Driver would
need an invented Python native surface (the clone has no Python ``step``/``reset`` class), so this package does not
pretend to wrap it.

MuJoCo is not installed and cannot be installed where the gate runs (no network, no pip), so ``backends["fake"]`` is
the package's pure-Python stand-in for the ``mujoco`` library (``fake.py``).  It parses the same MJCF for the joint
and actuator shape, the inherited motor ``ctrlrange`` and the option timestep, but its integration is a placeholder
first-order motion, not MuJoCo's physics.  Every difference is listed in the fidelity ``gaps``.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and no MuJoCo, hardware or upstream run is
claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to the upstream clone root.
MODEL = "sandbox/robots/humanoid.xml"
#: The model path relative to this package directory (four levels up to the repository root, then the clone).
MODEL_PATH = "../../../../robots/simple-robotics/simple/" + MODEL
HUMANOID = "sandbox/humanoid_mj.py"
SIM_UTILS = "sandbox/sim_utils.py"


class SimpleHumanoid(MujocoDriver):
    device_id = "simple-humanoid"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Simple Humanoid (MuJoCo MJCF model)"
    vendor, model = "simple-robotics", "Humanoid"
    tags = ["simple", "simulation", "mujoco", "humanoid", "physics", "reinforcement-learning"]
    facts = [
        Fact("Simple is a differentiable physics engine that uses Pinocchio for dynamics computations and Coal for "
             "collision detection", source="vendor_doc", ref="README.md:3"),
        Fact("The upstream README states the code is released under the permissive BSD-3 license",
             source="vendor_doc", ref="README.md:7"),
        Fact("The simple Python package re-exports the compiled simple_pywrap extension",
             source="upstream_code", ref="bindings/python/simple/__init__.py:7"),
        Fact("exposeSimulator exposes the C++ Simulator class through SimulatorPythonVisitor",
             source="upstream_code", ref="bindings/python/core/expose-simulator.cpp:12-14"),
        Fact("The sandbox imports mujoco in a try block and sets mujoco_imported false when the optional dependency "
             "is missing", source="upstream_code", ref=f"{SIM_UTILS}:11-17"),
        Fact("runMujocoXML prints 'Can't run, need to install mujoco' when the optional mujoco import failed",
             source="upstream_code", ref=f"{SIM_UTILS}:253-255"),
        Fact("The humanoid sandbox script sets its model path to ./sandbox/robots/humanoid.xml",
             source="upstream_code", ref=f"{HUMANOID}:27"),
        Fact("Without --mujoco the script builds a Pinocchio model and geometry from the MJCF",
             source="upstream_code", ref=f"{HUMANOID}:29-34"),
        Fact("The Simple-engine loop calls sim.reset() and sim.step(q, v, zero_torque, dt)",
             source="upstream_code", ref=f"{HUMANOID}:84-88"),
        Fact("With --mujoco the script calls runMujocoXML on the same model path",
             source="upstream_code", ref=f"{HUMANOID}:115-116"),
        Fact("SimulationArgs.dt defaults to 1e-3 s", source="upstream_code", ref=f"{SIM_UTILS}:20-22"),
        Fact("runMujocoXML loads an .xml model with mujoco.MjModel.from_xml_path, creates MjData and calls "
             "mujoco.mj_step", source="upstream_code", ref=f"{SIM_UTILS}:253-279"),
        Fact("runMujocoXML sets the loaded model's opt.timestep to args.dt", source="upstream_code",
             ref=f"{SIM_UTILS}:262"),
        Fact("The served model file carries a DeepMind Technologies Limited copyright notice and the Apache License, "
             "Version 2.0", source="upstream_code", ref=f"{MODEL}:1-13"),
        Fact("The served model file is the MuJoCo Humanoid model", source="upstream_code", ref=f"{MODEL}:16"),
        Fact("The model's option element sets a 0.005 s timestep", source="upstream_code", ref=f"{MODEL}:17"),
        Fact("The top-level default motor element sets ctrlrange -1 1 with ctrllimited true",
             source="upstream_code", ref=f"{MODEL}:36"),
        Fact("The torso body starts at 0 0 1.282 and carries a freejoint named root",
             source="upstream_code", ref=f"{MODEL}:110-113"),
        Fact("The model has 21 hinge joints: three abdomen, six per leg (hip x/z/y, knee, ankle y/x) and three per "
             "arm (shoulder1, shoulder2, elbow)", source="upstream_code", ref=f"{MODEL}:122-178"),
        Fact("The worldbody has a floor box with size 10 10 0.1 at position 0 0 -0.1",
             source="upstream_code", ref=f"{MODEL}:107"),
        Fact("The contact section excludes waist_lower against thigh_right and thigh_left",
             source="upstream_code", ref=f"{MODEL}:188-191"),
        Fact("Two fixed tendons named hamstring_right and hamstring_left couple hip_y and knee with coefficients .5 "
             "and -.5 and a range of -0.3 to 2", source="upstream_code", ref=f"{MODEL}:193-202"),
        Fact("The model has 21 motor actuators, one per hinge joint, each with an explicit gear",
             source="upstream_code", ref=f"{MODEL}:204-225"),
        Fact("The model defines four keyframes: squat, stand_on_left_leg, prone and supine",
             source="upstream_code", ref=f"{MODEL}:228-268"),
    ]
    safe_state = ("The bridge stops advancing the model: after an e-stop it refuses step and reset, and the last "
                  "integration state stays readable until an operator clears the latch.")
    #: The real MuJoCo engine contract, used by the implicit ``sim`` backend.  The gate exercises the package's
    #: stand-in module, whose F0 contract is selected by ``fidelity_by_backend`` below.
    fidelity = {
        "engine": "mujoco:Humanoid",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "mj_resetData restores the model's qpos0 and does not use the reset seed; MuJoCo integrates "
                     "fixed dynamics from that state, but the bridge's state capture does not certify callback, "
                     "plugin or RNG completeness, and no seed is offered.",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "MuJoCo itself was not importable where the gate ran (no network, no pip), so no trajectory of this "
            "package was compared with the real engine",
            "the upstream sandbox's MuJoCo mode overwrites the model timestep with --dt (default 1e-3 s) and sets "
            "its own cone and solver options (sandbox/sim_utils.py:22 and 260-266), while this package steps at the "
            "model's 0.005 s and leaves the other options at the engine defaults",
            "mj_resetData restores the model's qpos0 (the torso at its MJCF position 0 0 1.282, every hinge at "
            "zero); the model's four keyframes are not selected",
            "only sandbox/robots/humanoid.xml is served; the other robot files in sandbox/robots (go2, "
            "four_bar_linkage.xml, four_five_bar_linkage.xml and pendulum.xml) and the models that other sandbox "
            "scripts build or load are not",
            "the served MJCF is DeepMind's Apache-2.0 Humanoid model as copied into the sandbox; the Simple engine "
            "itself (simple.Simulator) is not served",
            "no physical device is modelled and the model was not validated against hardware; the package is "
            "model-authored and unreviewed",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {"kind": "none", "seed_control": "none"},
            "timestep_ms": 5.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the model for one free "
                "joint and 21 hinge joints, 21 motor actuators, the inherited ctrlrange and the 0.005 s option step, "
                "then moves each directly actuated joint with a placeholder first-order motor model; it computes no "
                "inertia, torque, contact, friction, tendon, joint-limit or actuator dynamics and produces no MuJoCo "
                "trajectory",
                "the stand-in does not integrate the free base, resolve the floor contact, apply the two hamstring "
                "tendons, the contact exclusions, the joint ranges, damping, stiffness, armature or gear forces; the "
                "humanoid cannot stand or fall on the fake",
                "the fake reset starts the free joint at a placeholder pose (zeros plus an identity quaternion) and "
                "every hinge at zero; the real model's qpos0 and its four keyframes are not reproduced",
                "the fake does not implement mj_getState/mj_setState/mj_stateSize, so a snapshot on the fake uses "
                "the bridge's basic time/qpos/qvel/act/ctrl profile, not MuJoCo's full integration state",
                "MuJoCo itself was not importable where the gate ran (no network, no pip), so the stand-in was not "
                "compared with the real engine",
            ],
        },
    }
