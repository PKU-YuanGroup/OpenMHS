# Companion sources: a simulator package's stop may cite the simulator's own repository

A task card may now declare reviewed companion sources (`companions`): corpus repositories cloned locally at their corpus-lock commit, such as the simulator whose world control is a simulator package's only stop. Only the e-stop binding, its read-back (`safety_bindings.safe_state`, which must read the stopped state back), the command of the one action declared `reenable=True` and facts may cite them, as `companion:<alias>/<path>:<LINE>`; the gate checks each clone, its HEAD at the pin, its tracked files, the version evidence and the scope, and fails closed. Five Gazebo simulator packages (ROS 1 Noetic, Gazebo 11) now pass with the gazebo_ros world pause as their stop.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 as the phase-3 agent p3-companion, in a
private project copy (`work/handoff-runs/claude-20261104/development/p3-companion/`) of `snapshot-3`, from the
preflight design in `development/p3-companion-preflight/` (`DESIGN.json`, `DESIGN.txt`, `PREFLIGHT.json`). Not
integrated; a Claude Sonnet review follows (the user's decision). No hardware, Gazebo, ROS graph or human review is
involved anywhere below: every result is `contract_checked` on fakes.

## Why

The user's decision of 2026-11-05 (`work/handoff-runs/claude-20261104/user-decisions-20261105.json`, decision 1):
a stop may cite a locally cloned companion repository at a pinned commit, limited to local pinned commits; each
package checks that the companion version matches the one it uses and confirms the pause by a state read-back. 22
blocked simulator packages had no stop in their own clone (GZ-PAUSE 16, CTRL-SWITCH 3, WEBOTS-PAUSE 2, GZ-TRANSPORT 1;
`development/blocked-triage-2/TRIAGE-2.json`). The preflight found five ready, all ROS 1 Noetic with Gazebo classic 11,
whose stop is gazebo_ros's `/gazebo/pause_physics`.

## Design

Declaration. A reviewed override field `companions` (new file `MHS/registry/overrides/companion-sources.json`; schema
`overrides.schema.json`): 1 to 3 entries of `alias`, the companion's corpus `package_id`, its `commit` (it must be the
corpus-lock commit), a `profile` (`ros1-noetic-gazebo11`), a one-line `reason` and `version_evidence`, items
`{side, ref, token}` whose `path:LINE` range in the tree its side names (`package`, `companion` or
`companion:<alias>`) shows the token. Each entry restates the card's current decision and adds only `companions`.
`triage.py` checks the shape (`check_companions`); `build_registry.py` (`attach_companions`) checks the corpus rules
(`triage.companion_problems`: a corpus record, its lock commit, never the repository itself; with the corpus, the
clone's HEAD read from its `.git` files and every evidence range) and copies the entries onto the card with the
clone's `local_path`, `repo_url` and licence (`taskcard.schema.json` `companions`). `validate.py` repeats the rules,
refuses a card whose companions no override declares, and compares the lock's `companions` with the card's.
`driver.lock.json` repeats `[{package_id, commit}]` (`driver-lock.schema.json`, mirrored by `sync_data.py`);
`mhs.driver new` copies it from the card. The gate reads the companions from `task.json`, a file of the package, so
they count only as the registry card confirms them: G1 refuses a `task.json` that differs from the registry card
`MHS/registry/tasks/<track>/<dir>.json` (`CARD_EDITED`, older than this change), and for a card that declares
companions it also refuses a missing or unreadable registry card and a `track` that is not one plain path segment
(`COMPANION_CARD`), so the gate fails closed outside the project tree. `validate.py` `check_overlays` refuses a
`task.json` whose companions differ from the card's, absence included, and `check_companions` a card whose companions
differ from the override resolved against the corpus lock.

Grammar. `companion:<alias>/<path>:<LINE>[-<END>]` (`mhs.driver.upstream.parse_source_ref`: the alias has the card's
form and the path must already be clean and relative). `parse_ref` is unchanged and refuses the prefix (it holds a
colon), so every check that was not taught it fails closed (`REF_FORMAT`, `ROS_REF_FORMAT`).

Scope and read-back (gate G7, `ros_check.py`). Companion citations are allowed in `safety_bindings.estop`,
`safety_bindings.safe_state` and the `commands` entry of the action declared `reenable=True`; anywhere else
`ROS_COMPANION_SCOPE`, and an alias the card does not declare `ROS_COMPANION_UNDECLARED`. A stop or read-back that
cites a companion needs (`ROS_COMPANION_READBACK`): the stop as `safety_bindings.estop`; a read-back that is a
service call whose name cannot resolve to the stop's (two global names, or two of one kind, compare segment by
segment; a relative or private name resolves against a namespace the gate cannot see, so it counts as the stop when
its segments end the other's: `gazebo/pause_physics`, `pause_physics` and `~pause_physics` are all refused against
`/gazebo/pause_physics`); a `success` predicate on one state field (`path` not `$`) with a scalar value;
`state_ref` on both bindings; and the read-back's `state_ref` line shows that field as a word. Endpoint, `source_name`
and type literals are checked in the companion's text exactly as in the clone's. The bridge accepts `state_ref` as
metadata (`bridge/ros.py` `_META`); the runtime is otherwise unchanged: the e-stop already runs the stop and then the
read-back, and any failure is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry.

Gates G1, G2, G4 (`check.py`). G1: the registry card confirms the companions of `task.json` (`COMPANION_CARD`,
`CARD_EDITED`, above); each companion clone exists (`NO_COMPANION_CLONE`), is the top of a git checkout
(`COMPANION_NOT_GIT`), its HEAD is the pinned commit (`COMPANION_HEAD`, an error, stricter than the package clone's
`HEAD_DIFFERS` warning), no tracked file is modified before (`COMPANION_MODIFIED`) or changes during the run
(`COMPANION_WRITTEN`), every version-evidence range shows its token and the profile's distro is shown on the package
side and on a companion side (`COMPANION_VERSION`); a malformed card entry or a synthetic tutorial with companions is
`COMPANION_CARD`. G2: the lock's companions equal the card's (`COMPANION_MISMATCH`, also when only one side has
them) and each pin is in its clone (`COMPANION_COMMIT_ABSENT`). G4: a companion fact resolves at the companion's pin,
never the working tree (`REF_MISSING`, `REF_LINE`, `COMPANION_REF_BINARY` is an error), an undeclared alias is
`COMPANION_UNDECLARED`, and a companion citation on a bound, `estop_physical_ref` or `action_space_ref` is
`COMPANION_REF_SCOPE`. Every companion defect is a gate error: no new warning exists for a signature to accept, so
`collect.py --strict` passes unsigned only when the gate passes. A card without companions sees no new finding and no
digest moves.

Tools. `show_refs.py` reads the companions from the registry card (`!!` and a bad citation when `task.json` differs
from that card or declares companions without one) and prints a header per companion (pin, profile, licence, the
HEAD read from `.git/HEAD`, the ref file or `packed-refs`, no git command), the version evidence with its lines, and
every companion citation of driver.py, bindings included; `!! HEAD differs`, `!! undeclared companion alias` and
`!! token not shown` count as bad citations. It now also resolves `ref=` values that are module string constants or
their sums, and refs built by a module helper: a call of a one-`return` helper with literal arguments
(`ref=_source("263")`) and a parameter of the enclosing helper, listed once per value its callers pass (hector's
`_action(..., limit_ref)` over the `_JOINTS` rows, printed at each row's line). Over the 693 passing packages
`<not a constant>` falls from 16 to 0 and only two results change, both to 0 bad citations
(`czbiohub-sf__reglo-icc-pump-control` 15, `drcl-usc__hector_simulation` 1). `collect.py` adds a never-failing `COMPANION_SOURCE` note per companion and reads
companion refs for its residue scan. Patched copies of the batch tools `review/notes/r00-ros_refs.py` and
`review-tools/fact_overlap.py` are in the private copy's `batch-tools/` (they live outside the project tree).

Version match (REVIEW.md item 13). Same ROS generation (catkin), same distro (the package's README, CI or install
lines name Noetic; gazebo_ros 2.9.3 is the Noetic release, `CHANGELOG.rst:5-7`), same simulator major (gazebo_dev's
`gazebo11`; Gazebo classic `CMakeLists.txt:20`, `Changelog.md:3`: 11.15.1). Gazebo classic and gz-sim never substitute
for each other, and a ROS 1 gazebo_ros never covers a ROS 2 package.

## The five packages

All five keep their `authored_by` (deepseek-v4.1-flash:1017) and get a MODEL REVIEW paragraph; each declares
`companions` gazebo_ros_pkgs at `cd9cc952` and gazebo-classic at `b22c6e15`, the stop `/gazebo/pause_physics`, the
read-back `/gazebo/get_physics_properties` with `pause == true`, and the declared re-enable `x-cap.<owner>.resume.v1`
(`/gazebo/unpause_physics`, CORE-086; no reset binding, so `mhs.safety.reset` only releases the latch). Each fake
keeps a paused flag the three services act on, with negative switches (no answer to the pause, a read-back that fails
as with a non-ODE engine, a read-back with `pause` false as after another client's unpause, a failed unpause), and
silences the topics a paused world does not publish. Each package's tests cover the confirmed e-stop, the three
failure paths (failed receipt `SAFE_STATE_UNREACHED`, latch held), the latch refusing commands and the resume, the
reset leaving the world paused, and the resume after the reset.

| package | was | stored motion command on resume (orchestrator condition, SAFE-042) | other changes | stable digest |
|---|---|---|---|---|
| robots/6-robot__wpr_simulation | blocked HELPER_MISSING (G6, G8) | cleared first: the resume publishes a zero Twist on `/cmd_vel` (WPRPlugin stores it, `wpr_plugin.cpp:237-243`, and its queue runs while paused, `245-251`), then unpauses; the zero is unacknowledged and disclosed | `/odom` left the device resource; the cmd_vel receipt reports the values it sent | `sha256:18641583b76980bc880b28b3b21af6ae4fecd06000f5f12119223839d08cd5c6` |
| robots/drcl-usc__hector_simulation | blocked HELPER_MISSING (G6, G8) | disclosed, not cleared: the controller's only other mode, BRAKE (`joint_controller.cpp:158-164`: zero position stiffness, zero velocity, damping 20, zero torque), removes the position stiffness and applies damping only; no hold command was found that the package could send (a PMSM command sets the position target it names, `142-145`, and the package reads no joint position), and `hector_ctrl` republishes all ten commands at 1 kHz | `/gazebo/model_states` left the device resource; MotorCmd receipts report the values sent | `sha256:48e810fcd1a3dee0931ccfe795901d417a374c70770aaad861b9435b1ffc737a` |
| robots/ipa320__cob_simulation | blocked HELPER_MISSING (G6) | none stored by this package (world edits only); the robot's controllers (outside the clone) resume theirs, disclosed | the fake's delete of an absent model is disclosed against gazebo_ros's `success false` | `sha256:0ebe226fd300fb5c791c204a6de64139bdaa4f321683db2f70f18b6317d75c64` |
| robots/mortezaaliyari__multi-robot-gazebo-navistack | blocked HELPER_MISSING (G6) | cleared first: zero Twists on both `/tb3_*/cmd_vel` (gazebo_ros_diff_drive stores them, companion `gazebo_ros_diff_drive.cpp:335-340`), then the unpause; unacknowledged, and move_base can publish new commands, disclosed | the four odom/scan resource reads became explicit read capabilities; cmd_vel receipts report the values sent; risk R2 instead of the author's R0 (review round 1) | `sha256:be48f7ce57c964f491849a4148ebb588d6772432c37ca6273c6203ab1b7e143e` |
| robots/nus-advanced-robotics-centre__me5413_final_project | blocked HELPER_MISSING (G6) | disclosed: planar_box resumes the velocity gazebo_ros_planar_move stored, driven by the world plugin the package does not command; the Jackal's controller is outside the clone | none to the resource (it had no reads) | `sha256:6a44e194883ae4db214c3263be078efe135e130e696dddd76945702e5423121f` |

A zero publication before the unpause is the clearing the plugins allow; it is a topic publication, handled on the
plugin's own queue thread, so it is not confirmed before the world runs and a stored command can act for a few world
steps. The packages implement it in a bridge wrapper (`make_bridge`), as `anhtuduong__ur5legovision` decorates its
receipts; a package that overrides `make_bridge` gets no stop-once report list (`_sdk_ros_route`), so a stop may be
sent twice, which is safe.

Why the resource changed. A paused Gazebo publishes no world-update topic (odometry, model states, laser scans,
`/clock`). With such a topic in the device resource, a reset device cannot be read (TSAFE-001 reads it twice after the
reset, before the re-enable, and failed `no fresh ROS topic observation before deadline`), and every command waits
for the topic's timeout before it runs. Those topics are now explicit read capabilities that fail `NOT_READY` while
the world is paused (the fakes model that); the receipts report what each publication sent so the conformance
suite's TCAP-003 still sees an effect. The orchestrator asked for the silence to be disclosed; it is, in each
package's `safe_state` or gaps and facts.md.

Disclosed in every package (`safe_state`, facts, fidelity gaps, facts.md): the pause is the paused flag
(`World::Step` updates only while not paused, `World.cc:835-854`), not a measured standstill; a GUI step or a
WorldControl `multi_step` advances a paused world (`World.cc:1630-1640`); pending spawn and delete messages are
processed on every step (`World.cc:835-863`); the Gazebo GUI that `empty_world.launch` opens by default and any other
client can unpause it, and MHS does not watch the flag after the e-stop; the read-back needs the ODE engine
(`gazebo_ros_api_plugin.cpp:1496-1528`); the deployment's gazebo_ros and Gazebo must be the pinned releases (rosbridge
cannot read their versions).

Risk (review round 1). A simulator package's command on a topic that a physical robot's driver also consumes follows
that robot's hazard however simulated the deployment (`MHS/spec/04-safety.md` section 2.1: mobile-base transit is
R2, and a simulated or hybrid label never lowers the risk of a binding that can affect physical equipment); a world
service that only the simulator serves stays R0. So wpr (`/cmd_vel`), hector (the ten joint `MotorCmd` topics) and
now multi-robot (`/tb3_0/cmd_vel` and `/tb3_1/cmd_vel`, raised from the author's R0; its resume takes the device's
R2, as wpr's does) are R2, and cob (`/gazebo/set_model_state`, `/gazebo/delete_model`) and me5413
(`/gazebo/delete_model` and the me5413_world plugin's `/rviz_panel/respawn_objects` and `/cmd_unblock`) stay R0.
REVIEW.md item 12 now states the rule. Six other passing packages mention `cmd_vel` in driver.py at device risk R0
(anurye/gym-turtlebot, blackcoffeerobotics/bcr_bot, fazildgr8/ros_autonomous_slam, goanywherenus/sim_igibson_ros,
jackvice/roboterrain, rlxai/rbot); they are outside this change and are listed for a risk review, not changed. A
risk or wording change adds no gate finding, so no recorded digest moved.

## The other 17 rows stay blocked

| class | packages |
|---|---|
| version-mismatch (12): no local companion clone at the package's version; a clone at another version needs the network and the user's go-ahead | andrejorsula/panda_gz_moveit2 (CTRL-SWITCH, Galactic), atharva-05/unitree_ros2_sim (ROS 2 Humble), blackcoffeerobotics/bcr_arm (CTRL-SWITCH, Humble or Jazzy), erdalpekel/panda_simulation (CTRL-SWITCH, Melodic, Gazebo 9), ethz-asl/rotors_simulator (Kinetic, Gazebo 7), evronix/quadruped_sim2sim (ROS 2 Humble), gsilano/crazys (Kinetic), lihuang3/ur5_ros-gazebo (Kinetic, Gazebo 7), linorobot/linorobot2 (gz-sim 8 Harmonic), novog93/sjtu_drone (ROS 2), osrf/vrx (GZ-TRANSPORT, gz-sim 8), rigbetellabs/tortoisebot (Ignition Fortress) |
| needs-more (5) | buenos-dan/cheetah_sim (no line names a distro; Python 2 rules out Noetic), jackymao1999/webots_demo (Webots R2021a; its ROS 1 supervisor controller is not at the local Webots pin), maskor/webots_ros2_spot (no ROS pause endpoint; needs a Webots supervisor helper), ros-simulation/gazebo_ros_demos (no citable distro; G8 TCAP-003), wh200720041/warehouse_simulation_toolkit (Noetic and Gazebo 11 match, but G8 TCAP-003 fails besides SAFE-028; needs companion-cited observations, outside decision 1) |

Deferred design items (`DESIGN.json` `deferred`): a list-element read-back predicate (controller switch), topic
read-backs (gz-sim, Webots), run-time composed endpoint names, companion-cited observations, a Webots supervisor
helper, and companion clones at other versions. warehouse_simulation_toolkit may not need companion observations:
the receipt pattern used for the five (a command's receipt reports what it sent, so TCAP-003 sees an effect without
a world-update topic in the resource) could serve it; not attempted, because this change keeps the 17 rows blocked.

## Validation

- New tests: `MHS/sdk/tests/driver/test_companion_sources.py` (32: grammar, `companion_sources`, G7 scope, aliases,
  read-back rules, among them the distinct-call rule however the two names are spelled and a table of the name rule,
  literals, the pin; G1, G2 and G4 on a real package with temporary git clones, among them a `task.json` that its
  registry card does not confirm; a scratch ROS package whose stop, read-back, re-enable and a fact cite a companion
  passing G1 to G8; the scaffold's lock); `MHS/registry/tests/test_companion_overrides.py` (16: override shape,
  schema, decision pass-through, corpus rules, validator, `task.json` companions against the card, the shipped file);
  `MHS/sdk/tests/handoff/test_tools.py` `ShowRefsTests` (two more: refs built by helpers, `task.json` read against
  the registry card).
- Mutation check (`development/p3-companion/scripts/mutants.py`, `logs/mutants-r1.log`): 21 of 21 mutants killed
  (the HEAD check, the scope, the read-back rule, `success.path '$'`, unclean paths, companion bounds, the lock, the
  pinned read, the evidence tokens, the after-run write check, the state_ref word check, a missing registry card as a
  warning, an unreadable registry card, any `track`, no distinct-call rule, names compared as spelled; the registry's
  self reference, re-pin, card without an override, `task.json` companions ignored, their presence ignored).
- The five packages pass all nine gates with their recorded digests (`logs/digests-r1-b.log`; review round 1 added no
  gate finding, so no digest moved) and the two changed packages' own suites pass (hector 11, multi-robot 15).
  `collect.py --strict` over all 693 passing packages of the private copy (`logs/collect-r1/`): 693 pass the gate with
  their recorded digests (no `RESULT_DIGEST_STALE`); the only warning is the known MCM3000 PDF citation
  (`UNVERIFIABLE_CITATION`, user-owned). SDK suite 3,460 OK (5 skipped; `logs/sdk-suite-r1c.log`). Two earlier runs
  under load each failed one runtime timing test, a different one each time: a PyLabRobot deadline expiring mid-step
  (`test_pylabrobot`, while the six collect processes ran; the step it expected to be fenced ran) and a ROS
  action-retirement history test (`test_ros_action_safety_retirement`, at a load average near 10; `safe_state` not yet
  achieved). Both modules load `check.py` or `bridge/ros.py`, but their failing assertions concern when a step or a stop
  completed; each module passes in five repeated runs (`logs/sdk-pylabrobot-rerun-r1.log`,
  `logs/sdk-ros-retirement-rerun-r1.log`) and both pass in the third full run. Registry suite 345 OK; `validate.py`
  (with and without the corpus) PASS; `build_registry.py --check` 0 files differ; `sync_data.py`,
  `build_applicability.py`, `gen_appendices.py`, `gen_errors.py` and `build_changelog.py` checks pass; INTERFACE.md
  unchanged; `dispatch.py --stats` unchanged (done 827, dispatch 15) and `--check-pilot` 20 of 20. `show_refs.py` over
  the 693 passing packages: no crash, and only the two results named under Tools change.
- The registry rebuild re-ranks 316 other cards (`rank` only, a global effect of five more passing packages) and
  `prepare.py --sync` refreshes their `task.json`; those files are generated, never edited.

## Residual risk

The read-back confirms the paused flag the step loop reads, not a sensed standstill. Any client, the GUI or a
WorldControl step can advance or unpause the world after the e-stop; MHS does not watch. The deployment's gazebo_ros
and Gazebo must be the pinned 2.9.3 and 11 releases. Commands stored while paused act on resume where the resume does
not clear them (hector, cob's robot, me5413), and a zero publication is not confirmed where it does (WPR,
multi-robot). The companion clones are shallow, so the cited blocks cannot be compared with older releases. The
gazebo_ros_pkgs record's licence is `NOASSERTION` in the registry, and the companion header prints it: the clone has no
LICENSE file at the pin, and its package.xml files declare different licences (gazebo_ros `Apache 2.0`,
`gazebo_ros/package.xml:13`; gazebo_dev `Apache 2.0`, `gazebo_dev/package.xml:11`; gazebo_plugins `BSD, Apache 2.0`,
`gazebo_plugins/package.xml:12`; gazebo_msgs `BSD`, `gazebo_msgs/package.xml:12`; the metapackage `BSD,LGPL,Apache
2.0`, `gazebo_ros_pkgs/package.xml:10`), so no single SPDX identifier is the repository's and the corpus value stays
(a corpus licence override is outside this change). gazebo-classic is `Apache-2.0` with a LICENSE file. Companion facts
are short statements with citations, not copies.

## Review round 1

Two Claude Sonnet reviewers (safety and evidence lenses) reviewed this change; each finding and what was done:

- F1 (major): the companions the gate reads come from `task.json`, a file of the package; `validate.py` compared only
  the lock's `[package_id, commit]`, and this record said that G1 compares `task.json` with the registry card without
  saying that it does so only where that card exists (the reviewer's probe, a `task.json` with a rewritten profile and
  evidence and an unchanged lock, passed G1 and G2 in a fixture without a registry card). Fixed: G1 now requires a
  readable registry card for a card that declares companions (`COMPANION_CARD`) and names that card only through a plain
  `track` segment (`_registry_card`; a traversal `track` can no longer point the comparison at a planted copy);
  `validate.py` `check_overlays` compares `task.json` companions with the card's, absence included; `show_refs.py` reads
  the registry card; ros-driver.md, driver-authoring.md, the overrides README, the profile spec's G1 row and REVIEW.md
  item 13 (read the companions from the registry card and the override, never from `task.json` alone) say what enforces
  it. The reviewer's probe now gives `G1.CARD_EDITED` with the registry card and `G1.COMPANION_CARD` without it
  (`development/p3-companion/scripts/probe_f1.py`, `logs/probe-f1-r1.log`). The preflight's `DESIGN.txt` (another
  agent's directory, not edited) repeats the old sentence ("G1 already refuses a task.json that differs from the
  registry card"); it holds only where the registry card exists, which G1 now requires. Not done: adding `task.json` to
  the lock's file digests (it would change every lock and digest of the corpus; G1 and the validator now cover it).
- F2 (minor): the read-back's distinct-call rule compared the names as spelled, and no test isolated it. Fixed:
  `_may_name_the_same_endpoint` (above); the old "same call" case, which failed for a missing field, is replaced by a
  read-back that is right in every other respect, spelled `/gazebo/pause_physics`, `gazebo/pause_physics`,
  `pause_physics`, `~pause_physics` and `~/pause_physics`, each refused with that one message, plus a table test of the
  name rule. The reviewer's mutant (the rule disabled) and the spelling mutant are killed. What the compared value
  means (`pause == true` and not `false`) stays the reviewer's trace; REVIEW.md item 13 now says the gate checks only
  that the `state_ref` line shows the field.
- EP-1 (minor): multi-robot was R0 beside the R2 of wpr and hector. Fixed by the rule above (multi-robot R2).
- EP-2 (minor): hector said BRAKE "would let the humanoid collapse". Reworded in driver.py (docstring and fidelity
  gap), facts.md, RESULT.json and the table above to what the cited lines show.
- EP-3 (minor, optional): show_refs printed `<not a constant>` for hector's position Limits. Fixed in the tool
  (above); hector's ten position Limits now print with their `const.xacro` lines.
- EP-4 (nit, optional): the gazebo_ros_pkgs licence prints `NOASSERTION`. Kept, with the reason above.

## Rule deviation

One read-only `git status --porcelain --untracked-files=no` and one `git ls-files` in
`robots/gazebosim/gazebo-classic` (no optional locks, the batch's empty hooks path), to time the gate's
tracked-file check; the clone is unchanged. Every other HEAD was read from `.git` files.

In review round 1 one command (a listing of three packages' command endpoints) ran without
`PYTHONDONTWRITEBYTECODE` and wrote 48 bytecode files: `__pycache__` in cob, multi-robot and me5413 and under
`MHS/sdk/src/mhs`. G1 warns about bytecode in a package (`BYTECODE`), which moved the digests of cob and me5413 until
the caches were moved aside to `development/p3-companion/moved-aside/pycache-r1/`; all five digests were then the
recorded ones.

## A sixth package (integrator-v4, claude-opus-5-5, 2026-11-05)

`gh.rickstaa/ros-gazebo-gym` (a Gymnasium card, `SIM-HOST.md`) now declares the same corpus companion
`gazebo_ros_pkgs` at `cd9cc952` (profile `ros1-noetic-gazebo11`), for facts only: its stop and read-back are the
isolated host's calls of `/gazebo/pause_physics` and `/gazebo/get_physics_properties`, and eight facts cite what the
companion's API plugin does with them. Its override is its unchanged Gymnasium routing, moved here from
`ros-routing-20261102.json` (a repository is overridden once), plus the companion with ten version-evidence ranges
(package: `README.md:7` Noetic, `.ci/Dockerfile.noetic:1`, `package.xml:47`, `core/gazebo_connection.py:50` and `:63`;
companion: `gazebo_ros/CHANGELOG.rst:5-7`, `package.xml:4` and `:23`, `gazebo_ros_api_plugin.cpp:383` and `:492`).
No gazebo-classic companion: the clone shows no Gazebo 11 token, so what a paused world still runs stays uncited.
Logged as I16 in the integrator's `MERGE-LOG.json`; details in `SIM-HOST.md`.
