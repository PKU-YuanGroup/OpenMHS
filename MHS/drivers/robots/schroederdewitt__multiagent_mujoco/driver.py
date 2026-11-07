"""OpenMHS driver for gh.schroederdewitt/multiagent_mujoco: the coupled half-cheetah MJCF world (MuJoCo family driver).

MAMuJoCo is a benchmark for continuous multi-agent robotic control built on OpenAI's MuJoCo Gym environments
(README.md:7).  Its ``MujocoMulti`` environment (the card's entry symbol,
``multiagent_mujoco/mujoco_multi.py:29``) reads ``scenario`` and ``agent_conf`` from ``env_args``, builds one MuJoCo
scene per scenario and maps per-agent action blocks onto that scene's actuator vector
(``mujoco_multi.py:33-34`` and ``:108-121``).  The card is ``family-config`` with the ``MujocoDriver`` helper, and its
``models`` are the MJCF files of those scenarios, so this package serves the card's first model,
``multiagent_mujoco/assets/coupled_half_cheetah.xml``, as a simulated ``world.sim``.

A ``MujocoDriver`` is configuration only.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [nu numbers]}}``;
the bridge checks each ``ctrl`` element against the model's per-actuator ``actuator_ctrlrange`` before writing
``data.ctrl`` and then runs ``mj_step`` ``ticks`` times.  The served model gives all twelve motors the default
``ctrlrange`` -1 to 1 (``coupled_half_cheetah.xml:36`` and ``:126-138``) and sets ``timestep`` 0.01 s (``:39``).
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit; the control envelope is the model's own.  MuJoCo and mujoco-py are not installed and cannot be installed
where the gate runs (no network, no pip), so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same MJCF file for the joint layout, the actuator count, the control ranges and the option
timestep but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file;
that path was not run here.

The multi-agent layer of ``MujocoMulti`` (scenario partitions, per-agent observations, reward, episode limit and the
``TimeLimit`` wrapper) is not served: the MuJoCo bridge carries the model's integration state and control vector
only.  The model file is read from the read-only clone at the pinned commit and is never copied into this package or
imported.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "multiagent_mujoco/assets/coupled_half_cheetah.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/schroederdewitt/multiagent_mujoco/" + MODEL
MUJOCO_MULTI = "multiagent_mujoco/mujoco_multi.py"
CHEETAH_ENV = "multiagent_mujoco/coupled_half_cheetah.py"
SETUP = "setup.py"


class MultiAgentMujocoCheetah(MujocoDriver):
    device_id = "mamujoco-cheetah"
    model_path = MODEL_PATH
    native = "multiagent_mujoco.mujoco_multi:MujocoMulti"
    backends = {"fake": FakeMujoco}
    display_name = "MAMuJoCo coupled half-cheetah world (MuJoCo)"
    vendor, model = "Christian Schroeder de Witt et al.", "MAMuJoCo coupled_half_cheetah"
    tags = ["cheetah", "coupled", "mujoco", "multi-agent", "reinforcement-learning", "simulation", "world"]
    facts = [
        Fact("The repository is a benchmark for continuous multi-agent robotic control based on OpenAI's MuJoCo Gym "
             "environments", source="vendor_doc", ref="README.md:7"),
        Fact("The documented requirement is OpenAI Gym 0.10.8 and MuJoCo 2.1", source="vendor_doc",
             ref="README.md:15"),
        Fact("The install_requires list is numpy, gym, mujoco-py, scipy, Jinja2, glfw and Cython: there is no "
             "serial, VISA, USB or vendor-SDK transport package", source="upstream_code", ref=f"{SETUP}:41-48"),
        Fact("MujocoMulti is a MultiAgentEnv subclass", source="upstream_code",
             ref=f"{MUJOCO_MULTI}:29"),
        Fact("MujocoMulti reads scenario and agent_conf from env_args", source="upstream_code",
             ref=f"{MUJOCO_MULTI}:33-34"),
        Fact("For the coupled_half_cheetah scenario MujocoMulti builds the local CoupledHalfCheetah environment "
             "under a TimeLimit and wraps it in NormalizedActions", source="upstream_code",
             ref=f"{MUJOCO_MULTI}:86-90"),
        Fact("step maps the per-agent action blocks into one MuJoCo action vector and steps the wrapped "
             "environment", source="upstream_code", ref=f"{MUJOCO_MULTI}:108-121"),
        Fact("reset resets the wrapped environment and returns the per-agent observations", source="upstream_code",
             ref=f"{MUJOCO_MULTI}:188-192"),
        Fact("CoupledHalfCheetah builds gym's MuJoCoEnv from assets/coupled_half_cheetah.xml with frame_skip 5",
             source="upstream_code", ref=f"{CHEETAH_ENV}:7-9"),
        Fact("The scenario observation concatenates qpos[1:] and qvel", source="upstream_code",
             ref=f"{CHEETAH_ENV}:28-32"),
        Fact("The served model is the MJCF root '<mujoco model=\"cheetah\">'", source="upstream_code",
             ref=f"{MODEL}:31"),
        Fact("The default motor class sets ctrllimited true and ctrlrange -1 1", source="upstream_code",
             ref=f"{MODEL}:36"),
        Fact("The model sets gravity 0 0 -9.81 and the integration timestep 0.01 s", source="upstream_code",
             ref=f"{MODEL}:39"),
        Fact("The first cheetah torso has three root joints: rootx and rootz slides and rooty a hinge",
             source="upstream_code", ref=f"{MODEL}:53-55"),
        Fact("The second cheetah torso torso2 has three root joints: rootx2 and rootz2 slides and rooty2 a hinge",
             source="upstream_code", ref=f"{MODEL}:88-90"),
        Fact("A spatial tendon named tendon1 couples the sites t1 and t2 and is limited to range 1.5 to 3.5",
             source="upstream_code", ref=f"{MODEL}:120-124"),
        Fact("The actuator block declares twelve motors, bthigh to ffoot on the first cheetah and bthigh2 to ffoot2 "
             "on the second", source="upstream_code", ref=f"{MODEL}:126-138"),
        Fact("The twelve motors declare no ctrlrange of their own, so they inherit the default motor ctrlrange -1 1 "
             "of line 36", source="upstream_code", ref=f"{MODEL}:127-138"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the values and the gaps below are this
    #: package's.
    fidelity = {
        "engine": "mujoco:coupled_half_cheetah",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "input and cap.world.reset.v1 restores the model defaults (mj_resetData), so a run repeats on "
                     "one engine but no seed selects a different state; the stand-in integrates its own placeholder "
                     "motion",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the multi-agent layer of MujocoMulti is not served: scenario and agent_conf partitions, per-agent "
            "observations, reward, episode limit and the TimeLimit wrapper are absent, and cap.world.step.v1 carries "
            "no reward, terminated or truncated; only the selected MJCF model is stepped",
            "the upstream scenario CoupledHalfCheetah wraps this model in mujoco-py with frame_skip 5 and resets "
            "with N(0,0.1) noise on qpos and qvel; the bridge advances one physics tick per tick and resets to the "
            "mj_resetData model defaults",
            "only the card's first model, coupled_half_cheetah.xml, is served; the manyagent_ant and "
            "manyagent_swimmer models, and the manyagent assets generated at construction, are other models and are "
            "not part of this driver",
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF for the joint "
            "layout, the actuator count, the per-actuator control ranges and the option timestep, but integrates a "
            "placeholder first-order motion of each actuated joint toward its control value; contacts, friction, "
            "damping, gear, tendon and actuator dynamics are not MuJoCo's",
            "the served model's spatial tendon coupling sites t1 and t2 is ignored by the stand-in",
            "MuJoCo was not importable where the gate ran, so no trajectory of this package was compared with the "
            "real engine or with the upstream mujoco-py scenario",
            "no viewer, rendering, camera stream, reward or multi-agent observation is exposed: the package serves "
            "only the cap.world.* integration state and control vector",
            "no physical robot is modelled and nothing was validated against hardware",
        ],
    }
