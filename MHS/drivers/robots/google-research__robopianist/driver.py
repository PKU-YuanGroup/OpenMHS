"""OpenMHS Gymnasium driver for RoboPianist: two simulated Shadow Hands playing a MIDI piece on a simulated piano.

RoboPianist never defines its environment class.  ``robopianist.suite.load`` builds the ``PianoWithShadowHands``
composer task from a MIDI piece and returns ``mujoco_utils.composer_utils.Environment``, a dm_control composer
environment of a library outside the clone.  This package therefore names the factory as ``native`` and declares
what it returns in ``native_factory``; gate G7 checks the factory and its return statement at the pinned commit and
holds the fake to the dm_env interface (MHS/sdk/src/mhs/driver/factory_check.py).  Both backends declare the
SDK's ``dm_env_v1`` profile, which maps TimeSteps explicitly (a LAST step with discount 0 is terminated, with a
positive discount truncated) and turns the action spec into the step envelope.

The hand action bounds come from the Shadow Hand model of the MuJoCo Menagerie, a git submodule of the clone
(third_party/mujoco_menagerie, gitlink 1afc8be).  The gate reads those citations at the gitlink commit from the
submodule's own object store.  The pinned code reads the hand XML from a copy that scripts/install_deps.sh makes
after checking the submodule out at that same commit.

The fake is an analytic dm_env stand-in (fake.py).  The live ``sim`` backend (sim.py) calls
``robopianist.suite.load`` lazily with the default task arguments; it has not been run: no robopianist, dm_control,
MuJoCo, MIDI synthesizer or soundfont was installed.  Evidence is contract_checked on the fake only.
"""

from mhs.driver import Fact, GymnasiumDriver

_SUITE = "robopianist/suite/__init__.py"
_TASK = "robopianist/suite/tasks/piano_with_shadow_hands.py"
_BASE = "robopianist/suite/tasks/base.py"
_HAND = "robopianist/models/hands/shadow_hand.py"
_PIANO_CONSTANTS = "robopianist/models/piano/piano_constants.py"
_INSTALL = "scripts/install_deps.sh"
_RIGHT_XML = "third_party/mujoco_menagerie/shadow_hand/right_hand.xml"
_LEFT_XML = "third_party/mujoco_menagerie/shadow_hand/left_hand.xml"

#: dm_env TimeSteps mapped explicitly; the citations name the factory, the action spec and the episode end.
_DM_ENV = {"profile": "dm_env_v1",
           "source_refs": [f"{_SUITE}:87-93", f"{_TASK}:226-237", f"{_TASK}:209-220"]}


class RoboPianistPianoWithShadowHands(GymnasiumDriver):
    """The environment ``robopianist.suite.load`` builds, behind the dm_env adapter; analytic fake for the gate."""

    device_id = "robopianist-piano-with-shadow-hands"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "robopianist.suite:load"
    native_factory = {"returns": "mujoco_utils.composer_utils.Environment", "ref": f"{_SUITE}:87-93"}
    backends = {"fake": ".fake:FakePianoEnvironment", "sim": ".sim:make_env"}
    dm_env_by_backend = {"fake": dict(_DM_ENV), "sim": dict(_DM_ENV)}
    tags = ["gymnasium", "dm-env", "dm-control", "mujoco", "simulation", "piano", "shadow-hand", "bimanual",
            "robopianist"]
    display_name = "RoboPianist: two Shadow Hands at a simulated piano"
    vendor = "Google Research (RoboPianist)"
    model = "PianoWithShadowHands, built by robopianist.suite.load"
    safe_state = (
        "Software latch over a synchronous simulator: the dm_control composer world integrates physics only inside a "
        "native step or reset, so after an e-stop no step or reset is dispatched until mhs.safety.reset clears the "
        "latch, and a native step already running completes (the e-stop waits for it within its budget) before the "
        "e-stop confirms. There is nothing physical: two simulated Shadow Hands and a simulated piano."
    )
    fidelity = {
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": ("A dm_env reset takes no seed: the live environment is seeded once, when it is built "
                      "(random_state=seed, robopianist/suite/__init__.py:87-93); no seeded determinism is claimed "
                      "for MuJoCo or for the fake."),
        },
        "reset": "full",
        "snapshot_restore": False,
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic: dm_env stand-in for robopianist.suite.load (no MuJoCo, dm_control, MIDI or sound)",
            "fidelity_level": "F0",
            "gaps": [
                "the fake is an analytic stand-in with no physics, piano, hands, MIDI or sound; it keeps only the "
                "dm_env calls the SDK's adapter makes (reset, step, action_spec, observation_spec, "
                "control_timestep, close)",
                "its action spec copies the shape and per-element bounds of the default task (45 values: 22 per "
                "hand, then the sustain pedal), each cited in the facts; the order and dtype of a hand's elements "
                "in the live spec are those of mujoco_utils.spec_utils.create_action_spec, a library outside the "
                "clone (robopianist/models/hands/shadow_hand.py:372-378)",
                "its observation is only the goal vector (178 values, all placeholders); the live observation also "
                "has the hands' joint positions, the piano's key and sustain state and, when the MIDI has "
                "fingering, the fingering (robopianist/suite/tasks/piano_with_shadow_hands.py:414-449)",
                "its episode lasts 8 control steps and every reward is 0.0 (placeholders); the live episode lasts "
                "as many control steps as the MIDI piece has frames",
            ],
        },
        "sim": {
            "engine": "dm_control composer: robopianist.suite.load (PianoWithShadowHands on MuJoCo)",
            "fidelity_level": "F1",
            "gaps": [
                "not run: no robopianist, dm_control, MuJoCo, fluidsynth or soundfont was installed; the live "
                "route is a source-reviewed contract, not validated execution",
                "importing robopianist needs the TimGM6mb.sf2 soundfont that scripts/install_deps.sh downloads "
                "(robopianist/__init__.py:48-58) and the Shadow Hand XML it copies from the menagerie submodule "
                "(scripts/install_deps.sh:78-88)",
                "only environment_name and seed are accepted; midi_file and task_kwargs would change the episode "
                "or the action space the package declares, and the PIG repertoire files are not in the clone",
                "with the default task arguments the discount stays 1.0 (piano_with_shadow_hands.py:146-149, "
                "209-220), so the end of a piece is a LAST step that the dm_env adapter reports as truncated; when "
                "the external Environment reads get_discount relative to should_terminate_episode decides whether a "
                "wrong-press termination (off by default) carries discount 0.0, and that code is outside the clone",
                "constructing the task can print to standard output; sim.py sends Python's sys.stdout to "
                "standard error while it builds the environment, but native libraries writing to file descriptor 1 "
                "are not redirected",
            ],
        },
    }
    facts = [
        Fact("load(environment_name, midi_file=None, seed=None, stretch=1.0, shift=0, recompile_physics=False, "
             "legacy_step=True, task_kwargs=None) is the suite's environment factory.",
             source="upstream_code", ref=f"{_SUITE}:50-59"),
        Fact("load reads a midi_file when one is given and otherwise refuses a name outside ALL with a ValueError.",
             source="upstream_code", ref=f"{_SUITE}:75-83"),
        Fact("load returns composer_utils.Environment with a PianoWithShadowHands task, random_state=seed, "
             "strip_singleton_obs_buffer_dim=True, recompile_physics and legacy_step.",
             source="upstream_code", ref=f"{_SUITE}:87-93"),
        Fact("The suite imports composer from dm_control and composer_utils from mujoco_utils.",
             source="upstream_code", ref=f"{_SUITE}:20-21"),
        Fact("The core requirements include dm_control, dm_env_wrappers, mujoco and mujoco_utils.",
             source="upstream_code", ref="setup.py:36-40"),
        Fact("The debug environments are named RoboPianist-debug-<name>-v0 after the pieces of music.DEBUG_MIDIS.",
             source="upstream_code", ref=f"{_SUITE}:36-39"),
        Fact("The debug MIDI library maps eight piece names, TwinkleTwinkleLittleStar among them, to functions "
             "that build the pieces.", source="upstream_code", ref="robopianist/music/library.py:544-553"),
        Fact("The PIG repertoire pieces are read from robopianist/music/data/pig_single_finger/*.proto.",
             source="upstream_code", ref="robopianist/music/__init__.py:34-36"),
        Fact("The suite quickstart loads RoboPianist-debug-TwinkleTwinkleLittleStar-v0, reads action_spec(), and "
             "calls env.reset() and env.step(action) until timestep.last().",
             source="vendor_doc", ref="robopianist/suite/README.md:17-28"),
        Fact("Importing robopianist raises FileNotFoundError when neither SalamanderGrandPiano.sf2 nor the default "
             "TimGM6mb.sf2 soundfont exists.", source="upstream_code", ref="robopianist/__init__.py:48-58"),
        Fact("The import first reads ~/.robopianistrc, when it exists, for a DEFAULT_SOUNDFONT.",
             source="upstream_code", ref="robopianist/__init__.py:29-44"),
        Fact("install_deps.sh downloads TimGM6mb.sf2 from SourceForge and copies the soundfonts into "
             "robopianist/soundfonts.", source="upstream_code", ref=f"{_INSTALL}:60-76"),
        Fact("install_deps.sh checks the menagerie submodule out at 1afc8be64233dcfe943b2fe0c505ec1e87a0a13e and "
             "copies its shadow_hand directory to robopianist/models/hands/third_party/shadow_hand.",
             source="upstream_code", ref=f"{_INSTALL}:78-88"),
        Fact("The repository declares third_party/mujoco_menagerie as a git submodule.",
             source="upstream_code", ref=".gitmodules:1-4"),
        Fact("The README says the MuJoCo Menagerie has its own licence and the rest of the code is Apache-2.0.",
             source="vendor_doc", ref="README.md:154"),
        Fact("The Shadow Hand XML files are read from robopianist/models/hands/third_party/shadow_hand.",
             source="upstream_code", ref="robopianist/models/hands/shadow_hand_constants.py:18-19"),
        Fact("The physics timestep is 0.005 s and the control timestep 0.05 s (20 Hz).",
             source="upstream_code", ref=f"{_BASE}:27-31"),
        Fact("The right hand starts at (0.4, 0.15, 0.13) and the left hand at (0.4, -0.15, 0.13).",
             source="upstream_code", ref=f"{_BASE}:33-37"),
        Fact("The task's action spec is the right hand's spec, then the left hand's, then a sustain spec from 0.0 "
             "to 1.0.", source="upstream_code", ref=f"{_TASK}:226-237"),
        Fact("before_step gives the first and second halves of all but the last action element to the right and "
             "left hands and the last element to the sustain pedal.",
             source="upstream_code", ref=f"{_TASK}:176-186"),
        Fact("A hand's action spec is created from its actuators by mujoco_utils' spec_utils.create_action_spec.",
             source="upstream_code", ref=f"{_HAND}:372-378"),
        Fact("forearm_tx has a dummy range that the task sets at initialization, and forearm_ty ranges from 0.0 to "
             "0.06.", source="upstream_code", ref=f"{_HAND}:41-52"),
        Fact("The default forearm degrees of freedom are forearm_tx and forearm_ty.",
             source="upstream_code", ref=f"{_HAND}:85"),
        Fact("The ShadowHand constructor adds the forearm degrees of freedom before it collects the joints and "
             "actuators.", source="upstream_code", ref=f"{_HAND}:138-141"),
        Fact("Each forearm degree of freedom adds a position actuator whose ctrlrange is its joint range.",
             source="upstream_code", ref=f"{_HAND}:303-309"),
        Fact("The forearm_tx range is the piano's half width either side, offset by the hand's y position.",
             source="upstream_code", ref=f"{_BASE}:160-164"),
        Fact("The task overrides the forearm_tx joint range and actuator ctrlrange with that range.",
             source="upstream_code", ref=f"{_BASE}:188-194"),
        Fact("The piano's size is the size of its base body's geom.",
             source="upstream_code", ref="robopianist/models/piano/piano.py:93-94"),
        Fact("The piano base is a box geom of size BASE_SIZE.",
             source="upstream_code", ref="robopianist/models/piano/piano_mjcf.py:103-104"),
        Fact("BASE_SIZE is half of the base's length, width and height, and the base width is PIANO_LENGTH.",
             source="upstream_code", ref=f"{_PIANO_CONSTANTS}:45-48"),
        Fact("PIANO_LENGTH is 52 white keys of 0.0225 m plus 51 spaces of 0.001 m.",
             source="upstream_code", ref=f"{_PIANO_CONSTANTS}:22-36"),
        Fact("The right Shadow Hand's position actuator classes set ctrlrange: wrist_y -0.523599 to 0.174533, "
             "wrist_x -0.698132 to 0.488692, thbase -1.0472 to 1.0472, thproximal 0 to 1.22173, thhub -0.20944 to "
             "0.20944, thmiddle -0.698132 to 0.698132, thdistal -0.261799 to 1.5708, metacarpal 0 to 0.785398, "
             "knuckle -0.349066 to 0.349066, proximal -0.261799 to 1.5708 and middle_distal 0 to 3.1415.",
             source="upstream_code", ref=f"{_RIGHT_XML}:12-62"),
        Fact("The right hand has 20 position actuators: wrist (2), thumb (5), first, middle and ring finger (3 each, "
             "the last on a tendon) and little finger (4).", source="upstream_code", ref=f"{_RIGHT_XML}:323-344"),
        Fact("The left Shadow Hand's position actuator classes set the same ctrlranges.",
             source="upstream_code", ref=f"{_LEFT_XML}:12-62"),
        Fact("The left hand's 20 position actuators follow the same order and classes.",
             source="upstream_code", ref=f"{_LEFT_XML}:322-343"),
        Fact("The goal observation holds the keys and sustain of the current frame and the next n_steps_lookahead "
             "frames.", source="upstream_code", ref=f"{_TASK}:380-389"),
        Fact("The default n_steps_lookahead is 1 and wrong_press_termination is False.",
             source="upstream_code", ref=f"{_TASK}:53-56"),
        Fact("The enabled observables are the hands' joint positions, the piano's key and sustain state, the goal "
             "and, when the piece has fingering, the fingering.", source="upstream_code", ref=f"{_TASK}:414-449"),
        Fact("after_step marks the episode to end at the last note frame.",
             source="upstream_code", ref=f"{_TASK}:192-193"),
        Fact("Each episode starts with discount 1.0.", source="upstream_code", ref=f"{_TASK}:146-149"),
        Fact("get_discount returns the task's discount, and should_terminate_episode ends the episode at the last "
             "frame, or on a wrong key press when wrong_press_termination is set, with discount 0.0.",
             source="upstream_code", ref=f"{_TASK}:209-220"),
        Fact("The reward adds key press, sustain and energy terms, a fingering term (an optimal-transport "
             "fingering term when the piece has none) and a forearm term.",
             source="upstream_code", ref=f"{_TASK}:130-144"),
        Fact("Without fingering, the task constructor prints a line to standard output.",
             source="upstream_code", ref=f"{_TASK}:136-141"),
        Fact("The package version is 1.0.10.", source="upstream_code", ref="robopianist/__init__.py:17"),
    ]
