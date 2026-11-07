# ROS wave C: the 150 remaining ROS cards, reviewed by Claude (58 contracts, 86 blocks, 6 skips)

After the reviewed ROS helper ([ROS-ACTION-SAFETY.md](ROS-ACTION-SAFETY.md), [ROS-CONTINUATION-B.md](ROS-CONTINUATION-B.md)),
150 ROS `family-config` cards were dispatchable: 148 robot cards of wave 3 and 2 lab cards of wave 6, with card floors
R0 (129) and R1 (21); 55 need the owner's publication decision. On 2026-11-04 the user authorized sending their pinned
sources, the SDK and the specifications to DeepSeek through the existing DeepSeek Harness for authoring only (no
hardware, publication or signatures), and chose the review standard of CODEX-HANDOFF.md section 5.2.

DeepSeek (`deepseek-v4.1-flash:1017`) authored one package per card with `run_wave.py`, the headless overlay and dsh's
default workspace-write mode, the validated interpreter (Python 3.14.7, NumPy 2.5.3, Pillow 13) first on `PATH`: a
two-card trial (batch `ros-wave-c-trial`) and then the other 148 cards ten at a time (batch `ros-wave-c`). The run took
2 h 53 min; a card took 613 s at the median (90th percentile 843 s, longest 1,111 s) and none timed out. The harness
counted 2,046 million tokens for the 148 cards, 99 % of them cache reads. No agent wrote outside its own package
directory (the runner wrote no `outside-writes.txt`).

## Model review

Claude (`claude-opus-5-5`, a model and not a human) reviewed every package in 22 reviewer sessions: a pilot of ten
packages first, then batches assigned as cards finished, balanced by code size. Each reviewer re-ran the gate and
`collect.py --strict`, read every citation against the clone at the pinned commit (with a new printer for ROS binding
references, which `show_refs.py` does not show), traced every stop from its binding through the callback to the
consumer of whatever it stores and every mode branch there, read every Fact, compared the fake with the upstream and
the pinned ROS version's message definitions, checked risk against the hazard table, scanned the code and read the
licence. The review brief grew with every batch: each reviewer's new defect classes were added before the next batch
started. Reviewers edited only their assigned packages, after copying each unchanged; one script then re-ran every
gate and wrote the status, the stable digest and the `MODEL REVIEW` paragraph into each `RESULT.json`.

| Status | Author | After review |
|---|---:|---:|
| pass | 78 | 58 |
| blocked | 66 | 86 |
| skip-proposed | 6 | 6 |

None of the 78 author passes was accepted unchanged: 58 needed fixes and 20 were blocked. All six skip proposals were
accepted (motion-planning, sensor-model and middleware libraries, a MATLAB example, a template and a framework).

## What the review found

- **Stops that do not stop (20 author passes blocked).** A stored selector acknowledged unconditionally that the
  controller ignores in its running mode (quadruped_ctrl), or that a higher-priority branch overrides (Spot's float
  mode); a LAND, disarm, motor-cut or `MAV_CMD_DO_MOTOR_TEST` request (px4-sitl-ros-example, mrs_crazyflies, blueboat;
  the hector LAND re-enables the motors and is sent twice per e-stop); a world reset that keeps the commanded velocity
  (sjtu_drone); deleting a world model (me5413); a MoveIt `stop()` that never reaches the package's own controller
  (erdalpekel/panda_simulation); unacknowledged posture setpoints or an unawaited action goal returned as a completed
  e-stop (cheetah_sim, ltamp); a gripper release (lihuang3); a firmware position write without acknowledgement
  (tetheria aero hand). Each such binding was removed, the e-stop now reports `SAFE_STATE_UNREACHED` with the latch
  held, and the package is blocked. The gate cannot see these: they pass G6 on a fake that acknowledges.
- **`safe_state` misstated** what holds after the stop (a free-running Gazebo does not stop when the latch refuses new
  steps; a zero-current request leaves the noise running; a pause that a GUI or a child coordinator can resume).
- **Facts that say more than their cited lines**, in most packages: an added "so ..." clause, a neighbouring call, a
  wrong file, units from a comment the code contradicts.
- **Fakes that hide upstream behaviour**: ROS 1 versus ROS 2 field names; flattened `nav_msgs/Odometry`; missing
  headers; delta instead of absolute actions; stand-in MuJoCo fakes claiming the real engine's F1 fidelity, resetting
  to zero quaternions or treating torque motors as positions; a cancel answered PREEMPTED that upstream never sends;
  resource reads on topics nobody publishes, which a real graph answers with `NOT_READY` after a 2 s wait.
- **Undisclosed hazards**: real-robot paths inside simulator repositories (a `real_robot` flag, a MAVROS HIL plugin,
  launch files that drive physical bases on the same topic); launch files that start competing publishers; upstream
  `close()` calling `killall -9` or `pkill -f` host-wide; constructors that parse the host's command line, arm a
  vehicle or wait without a timeout.
- **Limits**: unsourced bounds the author had accepted (plugin clamps cited as symmetric limits, one-sided limits,
  URDF velocities in rad/s read as degrees) became `Limit.operator_required` with example overlays.
- **Licences**: conflicts between files of one clone (GPL-3.0 repositories with proprietary or Apache-2.0 headers,
  MIT or GPL LICENSE files with other package.xml licences).

## Decisions

- Simulators (the user's decision of 2026-11-04): a package that declares no live backend is accepted as a fake-only
  contract with its live-construction hazards disclosed; a declared live route that is known to be incompatible stays
  blocked. Actuators whose upstream offers no source-backed stop stay blocked.
- A stop counts when its effect is proven from source: a physics-level joint lock, a pause or lapse-lock that the
  simulator honours, a multiplexer source whose every branch publishes zero, a gripper hold applied in every branch,
  or a reset that clears the cached commands under the simulator lock. Each such package says what still runs and
  who can undo it (a GUI, another client).
- Primary function: a package must drive the repository's own device class, not a test fixture that happens to have
  a stop (agilex ugv_gazebo_sim and the UR10e repository's FZI test robot are blocked).
- When a review paragraph did not fit the 8,000-character notes, the author's text was truncated with " [...]", as in
  wave D (17 packages); every author's complete `RESULT.json` is kept with the reviewer originals of the batch.
- Every orchestrator decision on a reviewer's question is listed in the batch's ORCHESTRATOR-DECISIONS.md.

## Registry

`MHS/registry/overrides/ros-wave-c-routing.json` holds 44 reviewed entries: 39 routing corrections (Gymnasium,
MuJoCo, direct-driver and skip routes for cards the scan misread) and 5 `publish_review: required` corrections for
licence conflicts. Five recon entries in `robots.json` were replaced by their reviewed Gymnasium routes, and
humanoid-description's routing entry gained `publish_review`. The registry was rebuilt and every package's
`task.json` synchronized.

## Found, not fixed

- The runtime sends a stop binding more than once per e-stop (the SAFE-040 retry, ordinary action cancels, and a stop
  bound both as `safety_bindings.estop` and as a `safe_state=True` action): upstream stops must be idempotent.
- The MuJoCo bridge publishes actuators without a control range with ±1.797e308 bounds: models that mix bounded and
  unbounded actuators cannot pass (multipanda_ros2, SDK_BUG), and fully unbounded models pass with only
  `G8.SAFE014_NOT_APPLICABLE`; 44-element limit arrays exceed G8.TOOL_SIZE.
- Code in git submodules is absent at the pinned parent commit, so the gate cannot read it (crazyflie-sim).
- When a stop silences the only observed topic, a faithful fake fails G8 TSAFE-001/SAFE-014, and moving the topic to
  an explicit observation fails TCAP-003.
- G7 checks ROS message type names, not fields or array sizes, and accepts any namespace-qualified suffix of a name.
- A stdio MHS server would be corrupted by upstream code that prints to stdout.
- The registry record's mode comes from a README scan and no override field carries it (mrw-code, mgreiff).

## For the owner

Hardware signatures (every ROS hardware backend needs a human `reviewed_by`), the 55 publication decisions and the
licence conflicts named above, and the clone file of adyansh04/grove-g1 the gate reports modified
(`workspace/vendor/unitree_mujoco/unitree_robots/go2w/assets/terrain.STL`, as for rule 11).

## Result

The review was applied by one script that re-ran every gate (150 decisions, none refused). The orchestrator then
applied the [helper integration](HELPER-INTEGRATION.md), wrote the overrides above and rebuilt the registry (5,331
generated files changed, none removed or added; a second rebuild changed nothing) and synchronized 711 `task.json`
copies. On that state:

- `collect.py --strict` over all 660 passing packages: every package passes the gate with the digest its `RESULT.json`
  records; the only warning is the historical `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`.
- The SDK suite (3,212 tests, 5 skipped) and the OpenAI4S integration tests (129) pass; `validate.py --no-corpus`
  passes; the pilot check counts 20 of 20; `build_changelog.py --check` passes.
- No `__pycache__` written during the run remains in the tree; the runner reported no outside writes.

The later checks of the combined state are in [helper wave 1](HELPER-WAVE-1.md). Not run: any ROS graph, simulator,
native transport or hardware; every result is `contract_checked` on a fake.
