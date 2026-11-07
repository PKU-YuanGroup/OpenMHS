# Source facts for gh.google-research/robopianist

Pinned commit: `0d9736c64eba5faafdf214ed7d38d648ffbd5c7f`.  The facts that cite `third_party/mujoco_menagerie/...` lie
in the MuJoCo Menagerie, a git submodule of the clone: the gate reads them at the commit the pinned tree's gitlink
records, `1afc8be64233dcfe943b2fe0c505ec1e87a0a13e`, from the submodule's own object store (warning
`G1.SUBMODULE_SOURCE`); its licence is the Menagerie's, not the card's Apache-2.0 (README.md:154).  Source declarations
and controlled fake results are not native execution.

| Fact | Source | Reference |
|---|---|---|
| load(environment_name, midi_file=None, seed=None, stretch=1.0, shift=0, recompile_physics=False, legacy_step=True, task_kwargs=None) is the suite's environment factory. | upstream_code | `robopianist/suite/__init__.py:50-59` |
| load reads a midi_file when one is given and otherwise refuses a name outside ALL with a ValueError. | upstream_code | `robopianist/suite/__init__.py:75-83` |
| load returns composer_utils.Environment with a PianoWithShadowHands task, random_state=seed, strip_singleton_obs_buffer_dim=True, recompile_physics and legacy_step. | upstream_code | `robopianist/suite/__init__.py:87-93` |
| The suite imports composer from dm_control and composer_utils from mujoco_utils. | upstream_code | `robopianist/suite/__init__.py:20-21` |
| The core requirements include dm_control, dm_env_wrappers, mujoco and mujoco_utils. | upstream_code | `setup.py:36-40` |
| The debug environments are named RoboPianist-debug-<name>-v0 after the pieces of music.DEBUG_MIDIS. | upstream_code | `robopianist/suite/__init__.py:36-39` |
| The debug MIDI library maps eight piece names, TwinkleTwinkleLittleStar among them, to functions that build the pieces. | upstream_code | `robopianist/music/library.py:544-553` |
| The PIG repertoire pieces are read from robopianist/music/data/pig_single_finger/*.proto. | upstream_code | `robopianist/music/__init__.py:34-36` |
| The suite quickstart loads RoboPianist-debug-TwinkleTwinkleLittleStar-v0, reads action_spec(), and calls env.reset() and env.step(action) until timestep.last(). | vendor_doc | `robopianist/suite/README.md:17-28` |
| Importing robopianist raises FileNotFoundError when neither SalamanderGrandPiano.sf2 nor the default TimGM6mb.sf2 soundfont exists. | upstream_code | `robopianist/__init__.py:48-58` |
| The import first reads ~/.robopianistrc, when it exists, for a DEFAULT_SOUNDFONT. | upstream_code | `robopianist/__init__.py:29-44` |
| install_deps.sh downloads TimGM6mb.sf2 from SourceForge and copies the soundfonts into robopianist/soundfonts. | upstream_code | `scripts/install_deps.sh:60-76` |
| install_deps.sh checks the menagerie submodule out at 1afc8be64233dcfe943b2fe0c505ec1e87a0a13e and copies its shadow_hand directory to robopianist/models/hands/third_party/shadow_hand. | upstream_code | `scripts/install_deps.sh:78-88` |
| The repository declares third_party/mujoco_menagerie as a git submodule. | upstream_code | `.gitmodules:1-4` |
| The README says the MuJoCo Menagerie has its own licence and the rest of the code is Apache-2.0. | vendor_doc | `README.md:154` |
| The Shadow Hand XML files are read from robopianist/models/hands/third_party/shadow_hand. | upstream_code | `robopianist/models/hands/shadow_hand_constants.py:18-19` |
| The physics timestep is 0.005 s and the control timestep 0.05 s (20 Hz). | upstream_code | `robopianist/suite/tasks/base.py:27-31` |
| The right hand starts at (0.4, 0.15, 0.13) and the left hand at (0.4, -0.15, 0.13). | upstream_code | `robopianist/suite/tasks/base.py:33-37` |
| The task's action spec is the right hand's spec, then the left hand's, then a sustain spec from 0.0 to 1.0. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:226-237` |
| before_step gives the first and second halves of all but the last action element to the right and left hands and the last element to the sustain pedal. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:176-186` |
| A hand's action spec is created from its actuators by mujoco_utils' spec_utils.create_action_spec. | upstream_code | `robopianist/models/hands/shadow_hand.py:372-378` |
| forearm_tx has a dummy range that the task sets at initialization, and forearm_ty ranges from 0.0 to 0.06. | upstream_code | `robopianist/models/hands/shadow_hand.py:41-52` |
| The default forearm degrees of freedom are forearm_tx and forearm_ty. | upstream_code | `robopianist/models/hands/shadow_hand.py:85` |
| The ShadowHand constructor adds the forearm degrees of freedom before it collects the joints and actuators. | upstream_code | `robopianist/models/hands/shadow_hand.py:138-141` |
| Each forearm degree of freedom adds a position actuator whose ctrlrange is its joint range. | upstream_code | `robopianist/models/hands/shadow_hand.py:303-309` |
| The forearm_tx range is the piano's half width either side, offset by the hand's y position. | upstream_code | `robopianist/suite/tasks/base.py:160-164` |
| The task overrides the forearm_tx joint range and actuator ctrlrange with that range. | upstream_code | `robopianist/suite/tasks/base.py:188-194` |
| The piano's size is the size of its base body's geom. | upstream_code | `robopianist/models/piano/piano.py:93-94` |
| The piano base is a box geom of size BASE_SIZE. | upstream_code | `robopianist/models/piano/piano_mjcf.py:103-104` |
| BASE_SIZE is half of the base's length, width and height, and the base width is PIANO_LENGTH. | upstream_code | `robopianist/models/piano/piano_constants.py:45-48` |
| PIANO_LENGTH is 52 white keys of 0.0225 m plus 51 spaces of 0.001 m. | upstream_code | `robopianist/models/piano/piano_constants.py:22-36` |
| The right Shadow Hand's position actuator classes set ctrlrange: wrist_y -0.523599 to 0.174533, wrist_x -0.698132 to 0.488692, thbase -1.0472 to 1.0472, thproximal 0 to 1.22173, thhub -0.20944 to 0.20944, thmiddle -0.698132 to 0.698132, thdistal -0.261799 to 1.5708, metacarpal 0 to 0.785398, knuckle -0.349066 to 0.349066, proximal -0.261799 to 1.5708 and middle_distal 0 to 3.1415. | upstream_code | `third_party/mujoco_menagerie/shadow_hand/right_hand.xml:12-62` |
| The right hand has 20 position actuators: wrist (2), thumb (5), first, middle and ring finger (3 each, the last on a tendon) and little finger (4). | upstream_code | `third_party/mujoco_menagerie/shadow_hand/right_hand.xml:323-344` |
| The left Shadow Hand's position actuator classes set the same ctrlranges. | upstream_code | `third_party/mujoco_menagerie/shadow_hand/left_hand.xml:12-62` |
| The left hand's 20 position actuators follow the same order and classes. | upstream_code | `third_party/mujoco_menagerie/shadow_hand/left_hand.xml:322-343` |
| The goal observation holds the keys and sustain of the current frame and the next n_steps_lookahead frames. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:380-389` |
| The default n_steps_lookahead is 1 and wrong_press_termination is False. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:53-56` |
| The enabled observables are the hands' joint positions, the piano's key and sustain state, the goal and, when the piece has fingering, the fingering. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:414-449` |
| after_step marks the episode to end at the last note frame. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:192-193` |
| Each episode starts with discount 1.0. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:146-149` |
| get_discount returns the task's discount, and should_terminate_episode ends the episode at the last frame, or on a wrong key press when wrong_press_termination is set, with discount 0.0. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:209-220` |
| The reward adds key press, sustain and energy terms, a fingering term (an optimal-transport fingering term when the piece has none) and a forearm term. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:130-144` |
| Without fingering, the task constructor prints a line to standard output. | upstream_code | `robopianist/suite/tasks/piano_with_shadow_hands.py:136-141` |
| The package version is 1.0.10. | upstream_code | `robopianist/__init__.py:17` |

## Route

`robopianist.suite.load` builds the `PianoWithShadowHands` composer task and returns
`mujoco_utils.composer_utils.Environment`, a class outside the clone.  The package names the factory as `native` and
declares `native_factory`; gate G7 checks that every return of `load` builds that class through the module's import
of `mujoco_utils` and holds the fake to the dm_env interface.  Both backends declare the SDK's `dm_env_v1` adapter: a
LAST step with discount 0 is terminated, with a positive discount truncated (with the default task arguments the
discount stays 1.0, so the end of a piece is reported as truncated); the action spec is the step envelope; a dm_env
reset takes no seed, so no seed capability is served.

## Action envelope of the default task (45 values)

Right hand: the 20 position actuators of the Menagerie XML in the order of its `<actuator>` block, then `forearm_tx`
and `forearm_ty`; left hand likewise; then the sustain pedal (0 to 1).  The finger and wrist bounds are the XML's
actuator class ctrlranges.  `forearm_ty` is 0 to 0.06.  `forearm_tx` spans the piano's half width either side offset
by the hand's y position: half width = (52 x 0.0225 + 51 x 0.001) / 2 = 0.6105 m, so -0.7605 to 0.4605 for the right
hand (y = 0.15) and -0.4605 to 0.7605 for the left (y = -0.15).  The fake copies these numbers; the reference prints
them without a source because no single upstream line shows them all (no `action_space_ref`), and each is cited in the
table above.  The live order and dtype of a hand's elements come from `mujoco_utils.spec_utils.create_action_spec`,
outside the clone.

## Stop

A software latch over a synchronous simulator: the composer world integrates physics only inside a native step or
reset, so after an e-stop nothing is dispatched until `mhs.safety.reset`, and the e-stop waits within its budget for
a step already running before it confirms.  Nothing physical exists.

## Live route (declared, not run)

`sim.py` imports `robopianist` only when the `sim` backend opens and calls `suite.load(environment_name, seed)` with
the default task arguments (default environment `RoboPianist-debug-TwinkleTwinkleLittleStar-v0`); `midi_file` and
`task_kwargs` are refused.  Standard output goes to standard error while the task is built (it prints when the piece
has no fingering).  Installing it needs the submodule, `scripts/install_deps.sh` (fluidsynth, portaudio, ffmpeg, the
TimGM6mb.sf2 soundfont from SourceForge, the Shadow Hand XML) and `pip install -e .`; nothing was installed here.

## Tags

`gymnasium`, `dm-env`, `dm-control`, `mujoco`, `simulation`, `piano`, `shadow-hand`, `bimanual`, `robopianist`.
