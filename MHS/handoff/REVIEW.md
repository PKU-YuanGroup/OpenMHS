OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Human review of a model-written driver

A passing gate proves a package's *contract* on a fake: limits are enforced before the native layer, the e-stop reaches
it, outputs match their schemas, names exist upstream. It does **not** prove that a number is right, that the upstream API
does what the fake pretends, or that the device is safe. A package is `contract_checked`, never more, until a human has
read it and (for hardware) run it with the device under supervision.

Who: someone who knows the device class and has the vendor manual at hand. A model never reviews its own work. Section 5 says
what changes when a project has another model review instead.

## 1. When review is mandatory

- **Always before a package is merged**: the checklist in section 2 (about 15 minutes for a small driver).
- **Before the hardware backend may start** (a hardware device at `R2` or above): a human sets `reviewed_by` in
  `driver.lock.json`. `mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, state_dir=...)` raises
  `LoadError` with `reason == "review_required"` until then. Even for `R1` hardware, run first with a person next to the
  device and a physical stop in reach.
- **ROS hardware at every risk level**: `RosDriver` additionally requires a human signature of scope `hardware`, even
  at R0/R1 and for human-authored packages, before any backend factory or connection. A model leaves `reviewed_by` null.
  Review endpoint/type references, namespace resolution and service application-success predicates as described in
  [ros-driver.md](../sdk/docs/ros-driver.md); a topic publication is not acknowledged completion or stopping.
- **5 % audit**: in every wave, pick 5 % of the passing packages at random and repeat the whole checklist, including a
  second reading of every limit. Record the miss rate; a rate above 10 % means the prompt or the cards need work before
  the next wave.

## 2. Checklist

1. **Re-run the gate yourself**, not the model's `RESULT.json`: `python3 MHS/handoff/tools/collect.py <dir>` must show no
   `RESULT_UNTRUSTED`, no `RESULT_DIGEST_STALE` and no `EXEMPLAR_RESIDUE`. Its `UNSOURCED_LIMIT_GATE_WARNING` and
   `UNVERIFIABLE_CITATION` lines are your reading list for steps 2 and 3: open every cited line (`show_refs.py`) and every
   cited PDF page. Read the `note:` lines too: `DECISION_DEVIATION` means the card's shape was wrong, and the notes of
   `RESULT.json` must say why. When you have signed `reviewed_by` (section 3) those two kinds print as `accepted by <you>`
   and `collect.py <dir> --strict`, which CI runs, passes.
2. **Read every `Limit` (and a `GymnasiumDriver`'s `action_space_ref`) against the line it cites.** Gate G4 checks only that the line exists; when the line does not show
   the number it merely warns, so an invented bound cited to a real line passes. `python3 MHS/handoff/tools/show_refs.py <dir>`
   prints every citation of `driver.py` next to the cited lines of the clone at the pinned commit. Confirm the number, the
   unit and what it bounds (the maximum of the device, or only a default?). G4 reads `2 * math.pi`, `-math.pi / 2` and
   `np.radians(90)` as numbers, `5,000`, `750_000` and `0b1111_1111` as the numbers they write, `±5` and `abs(x) > 1000` as
   symmetric bounds, `0.08 m` as 80 for a limit in `mm`, the angles of a line that states degrees (`deg`, `°`, or the
   CJK degree sign right after a number) also in radians, a Gymnasium `Discrete(n)` as its largest action `n - 1`, a
   literal integer `range(start, stop[, step])` as its first and last elements (`range(0, 255)` shows 0 and 254, and the
   stop literal 255 stays shown, whatever role the range plays on the line: a membership test or a loop), and
   `np.ones(4)` and `-np.ones([4])` as 1 and -1. A bounded source-only AST reader also follows straight-line
   ones-based bounds into a `Box` when their complete definitions, including any literal scale, are in the cited
   span (for example `self.max_torque = 1000; high = np.ones(n) * self.max_torque; Box(-high, high)`). It rejects
   control flow, dynamic calls, mutation, reassignment and aliases; it proves numeric bounds, not shape or
   out-of-span values. An isolated scaled ones expression does not infer an unstated negative bound;
   a warning for any other expression is a prompt to read the line, not noise.
3. **A bound that is not stated anywhere must be `Limit.operator_required(...)`.** A catalogue class's default bounds
   (for example -50..300 Cel for a thermal setpoint) are not a source for a particular device: a device whose manual says
   5..80 Cel must declare its own `Limit`, or be `operator_required`. Reject a package that leaves a hardware input to the
   class default without saying so. A default of the upstream's constructor (`num_ports=9`, `syringe_ul=1000`) is no
   better a source: the `UNSOURCED_LIMIT_GATE_WARNING` of such a bound is the sign; ask for `operator_required`.
4. **Every `Fact`** is something the cited line says, not an interpretation. No fact of another repository, except a
   companion source the card declares (`companion:<alias>/<path>:<LINE>`, item 13).
5. **The stop path.** The `@estop` method calls the real native stop (not a flag in the fake), returns promptly and does not
   wait for a running action. `safe_state` says what the device is left in. `R2+` hardware cites an independent physical
   stop (`estop_physical_ref`) or has a `safe_state=True` action. That action runs during an e-stop as well: it must not
   call an upstream method that waits for the device with a long default (a 60-minute `wait_for`), or that joins
   a worker without a timeout: the Duke Humanoid's `shutdown()` joins a sensor process that never sees its stop
   flag (wave D). Check every `@reset` hook and reset binding for re-arming: a reset only re-establishes
   communication that changes nothing on the device (SAFE-042). Anything that enables, powers or starts the device
   is the declared re-enable (`reenable=True`, no `@reset` beside it, CORE-086); a stop that only a new native
   session undoes is declared `estop_terminal` (CORE-087). Check that both declarations are true of the upstream.
   A **sensed-confirmation stop** (`safety_bindings["sensed_stop"]`, SAFE-049, simulated devices only): trace every
   request step into the upstream (what it changes; repeating it after the safe state must undo nothing), every source
   to its producer and every `fill_refs` line (a field the producer leaves at its default is never a sensed state),
   look for competing publishers on request and source topics in the shipped launch files and for nodes that undo
   the stop (an offboard node that re-arms), check that `safe_state` names only the sensed state and the confirmation
   window, that every threshold cites a line showing the number or is `operator_required`, and that a stack that can
   also drive a real vehicle (MAVROS, cflib) says so. Check each ROS 2 source's `history`: a new subscription replays
   what a transient-local publisher keeps, and an understated history lets that replay count. The cited line must
   create that source's publisher with that QoS (the gate checks only that it shows a publisher and the durability
   and depth outside comments, and that a volatile publisher's QoS is not a variable defined on other lines; that the
   line publishes this source's topic is yours to read), and an `operator_required` history must say why the clone
   does not show it (the operator states it
   for a live run). A ROS 1 producer stamp is not a freshness proof: the bridge has no proven offset between that clock and its wall clock, so every ROS 1 stamp sample is discarded, including a stamp one second ahead, a ROS simulation clock, a delayed latch, a frame already in a client buffer, and a sample from a transport that cannot report its buffer. An empty queue, a socket poll, a continuation flag, and a fixed lead are not that proof. When the declaration names an exclusion, silence, a subscription error, and a sample the exclusion ring drops are not proof the competing publisher stopped. A dropped sample was not inspected, so the tail that remains cannot confirm. Require a passive sample on that subscription, still fresh at the commit. A nonzero watched field refuses the confirmation. An arrival source (`freshness: arrival`) is ROS 2 only, cites a volatile publisher, has no `stamp_path`, and sets `min_interval_ms`: the first sample is discarded and a closer sample restarts the count. Do not accept arrival on a transient-local publisher or on ROS 1.
   An **isolated simulator host** (`process_by_backend`, `isolated_process_v1`, [sim-host.md](../sdk/docs/sim-host.md)):
   trace the declared stop into the upstream (a single call that cannot exit or retry for long is better than a
   helper that loops and calls `sys.exit`) and the read-back to the state the simulator's step loop reads (never an
   acknowledgement of the request), check what a step or reset in flight does to the stopped state (the SDK stops
   again after it, but a call that never ends keeps the e-stop unreached), what the stopped simulator keeps (a stored
   command that acts again when a step resumes it), who else can resume it, and what construction launches, installs
   or fetches; the bounds are package choices and must say so.
6. **Native return codes** become `DriverFailed` or `OutcomeUnknown`; nothing is swallowed. The gate injects exceptions, not
   return codes: **it cannot see a driver that ignores the integer a return-code SDK gives back**. For such an SDK
   (most robot arms) the package must carry its own case in `test_driver.py` that makes the fake return a non-zero code and
   expects a `failed` receipt, as the xArm exemplar does. Check that the case exists and exercises the real code path.
   Units are converted in the driver only where the upstream unit differs (`native_unit`).
7. **The fake is faithful.** It uses the upstream signatures and the upstream's behaviour for the cases the tests touch.
   SCPI and serial fakes answer the real command syntax: a command whose spelling was altered to get through gate G7
   (a space inserted into `V5R`) is a defect, the package should be a direct driver. A fake that returns whatever the test
   expects proves nothing. Numbers in a fake are marked `# placeholder` and appear in no `Fact` or `Limit`; a fake array
   smaller than the device's (an image) is named in the notes and the fidelity `gaps`. The one place fake numbers reach the
   reference is the step bounds a Gymnasium driver derives from its fake's action space: they carry no source, and
   `REFERENCE.md` prints them with `no source: action_space of the fake backend ...`. When they are placeholders, the notes
   and the fidelity `gaps` say so. An `action_space_ref` makes them `upstream_code`: it claims the fake copies the
   upstream's space, so read the cited line, and reject it for a placeholder space.
8. **Scope.** One device class per package. Other devices of the repository are named in `facts.md` or the notes. Large data
   is not exposed (`NEEDS_ARTIFACTS`).
9. **Provenance.** `driver.lock.json` has `authored_by.kind: "model"` with a real `model_id`, `reviewed_by: null` until you
   sign, and the pinned commit and licence of the card. Nothing claims a hardware run.
10. **Obfuscated code.** The gate's static scan rejects exits, `sys.argv`, patching `mhs`, reaching into frames or
    `sys.modules`, and naming a private member of the served-mode binding or the safe-state commit
    (`_bind_served_mode`, `_grant_served_mode`, `_served_mode`, `_commit_safe_state_locked`, ...: a package that grants
    itself a sensed confirmation). It does not follow aliased reflection: look for `getattr` with built strings, `importlib` of `mhs.*`,
    `_g = getattr`, `eval`/`exec`, dynamic imports, and anything in `test_driver.py` that is not a plain extra test case.
    Read `native.py` (the hardware factory, which the gate never imports) line by line: it is the only code that will run
    against a real device.
11. **Licence.** `publish_review: required` on the card means the owner decides before publication. Do not merge such a
    package into a published tree without that decision. A `SUBMODULE_SOURCE` note of `collect.py` names a git
    submodule the package cites: another repository, read at the parent's gitlink commit, whose licence the card does
    not state; check it before publication.
12. **Risk.** The card's floor comes from the catalogue classes, and an extension id or `cap.device.configure.v1` has a
    low one, so a model can drive a laser or a high-voltage supply at R1 without breaking a rule of the gate. Compare
    `risk` with the hazard table of `MHS/spec/04-safety.md` (a laser above class 1, an arm, a pump that dispenses: R2;
    a class 3B+ laser, high voltage: R3) and raise it; wave A had six such packages. A simulator package's command on a
    topic that a physical robot's driver also consumes (`cmd_vel`, a joint command) follows that robot's hazard (a
    mobile base or a limb: R2) however simulated the deployment, because a real robot behind the same bridge would act
    on it; a world service that only the simulator serves (`/gazebo/set_model_state`, `/gazebo/delete_model`, the
    pause and unpause) stays R0.
13. **Companion sources.** A card may declare `companions` (a reviewed registry override, user decision of 2026-11-05):
    corpus repositories cloned locally at their corpus-lock commit, such as the simulator whose world control is the
    only stop of a simulator package. Only the e-stop binding, its read-back (`safety_bindings.safe_state`, with
    `state_ref`), the command of the one action declared `reenable=True` and facts may cite them; every bound, read,
    write, interlock, reset and other command cites the package's own clone, and the gate refuses anything else. Read
    the companions from the registry card (`MHS/registry/tasks/<track>/<dir>.json`) and the override
    (`MHS/registry/overrides/companion-sources.json`), never from `task.json` alone: `task.json` is a file of the
    package, and the gate believes it only because G1 refuses one that differs from the registry card. `show_refs.py`
    reads the registry card and prints `!!` when `task.json` differs from it or declares companions without one. Run
    `show_refs.py` and check: every companion header shows HEAD equal to the pin; every version-evidence token is shown;
    the package side (package.xml catkin or ament, the launch line that includes the simulator bridge, README, CI or
    install lines naming the distro) and the companion side (branch, package.xml or CMake version, the newest CHANGELOG
    entry, the distro's simulator dependency) name the same ROS generation, distro and simulator major, and the single
    profile the package serves (note every other distro the clone also supports; a mismatch keeps the package blocked).
    Trace the stop and the read-back callbacks to the state the simulator's step loop reads (the read-back must read
    that state, never only acknowledge the request, and the value its `success` compares must be the stopped value: the
    gate checks that the read-back is in the stop's namespace, that its field is no acknowledgement field (status,
    done, code, sent and completed style fields included) and that the cited `state_ref` line assigns the field from
    something other than a constant or the request (`res.pause = req.pause;` echoes the caller); that the assigned value is the
    state the step loop reads, and which value means stopped, is yours to trace), list what still acts while the world
    is stopped (callbacks that store commands, world edits, manual steps, another client's or the GUI's resume) and
    check that
    `safe_state`, the facts and the fidelity gaps say it. The re-enable must not resume a stored motion command
    silently: it clears it first where the upstream allows (and says that clearing is unacknowledged), otherwise its
    description and the facts disclose the resumption; where the stored command cannot be cleared before an unpause
    (a controller the package does not command, a position target, a learned policy that keeps acting), the package
    offers no unpause at all (neither re-enable nor ordinary command) and `safe_state` says how the operator recovers
    outside MHS. Topics that the stop silences must not feed the device resource, or a reset device cannot be read.
    For a fetched companion (`lock`, a clone under `work/companions`): read its `work/companions/LOCK.json` entry
    (`show_refs.py` prints it; `ref`, `repo_url`, licence and `needed_by` must fit the card, and `!! LOCK mismatch`,
    `!! writable work tree` or `!! clone missing` is a bad citation), and confirm that the LOCK.json profile is the
    one the package serves. One hardware package, and only a package the user decided so for (decision 4 of
    2026-11-05, `gh.rplab/wil_pycro_control_app`): its stop and the fresh read-back that confirms that stop may cite
    a fetched companion whose card entry sets `hardware_stop` true. The profile is not a ROS profile. The card `ref`
    is the full commit, and the text of `lock` after `@` is that commit's first 12 hex digits. The two members are
    not members of the package clone. Every call of them is during the e-stop, the stop before the read-back, and
    the e-stop contains at least one such pair. Everything else stays as it was: a bound, `estop_physical_ref`,
    `action_space_ref` and every other binding cite the package clone, and a ROS companion is unchanged. The
    hardware backend still needs a human `reviewed_by` with scope `hardware` before it may start. The citation does
    not waive that signature, at any risk. A model does not write `reviewed_by`. For a stall read-back (`stall` on `safety_bindings.safe_state`), check that the compared
    value advances only while the world steps (a companion fact on the step loop) and that the declared
    `estop_latency_ms` covers the worst case; for a list-element read-back (`where`/`field`), check that every selected
    element is a stopped controller and the compared state its stopped value (one selector object, or a list of 2 to 4
    selectors that must each match a different element). For a fresh-sample topic read-back
    (`fresh` on a topic `safety_bindings.safe_state`, E2), check that the compared field is the boolean world-state flag
    the step loop reads (copied from it, not an acknowledgement), that the topic belongs to the world the stop pauses,
    that `min_interval_ms` is below the producer's own publication interval (cite the throttle) and above a burst's
    spacing, that the cited producer and bridge publish without a deeper history than one sample by default (a
    transient-local history replays on subscribe; the burst rule and the discarded first sample cover a back-to-back
    burst only, not a replay spaced at least `min_interval_ms` apart, and no arrival-time rule detects that spaced
    replay; the package says what an operator QoS override would change; asking rosbridge for a volatile reader is
    not proof, because an older rosbridge ignores it), and that `safe_state` says the flag holds only for the
    confirmation window. For the bridges the operator must run (`operator_bridges`, E3), check each argument against
    the bridge's own usage text, that the clone's launch does not already bridge the same names (two bridges are a
    second path), and that `REFERENCE.md` and the facts tell the operator that without them the e-stop fails closed.

## 3. Signing

After the checklist (and, for hardware, a supervised run), edit `driver.lock.json`:

```json
"reviewed_by": {"reviewer": "Your Name", "date": "2026-11-02", "scope": "contract", "notes": "limits read against the lines"}
```

`scope` is `contract` (code and limits on fakes reviewed) or `hardware` (a reviewed run on the real device). Use
`hardware` only when that run happened. Regenerate nothing else by hand: `python3 -m mhs.driver reference <dir>` and the
gate must still pass.

## 4. Residual risk

The gate evaluates package code in its child process. It cross-checks the child's report against what the parent derives
itself (header, progress stream, evidence state), so a forger would have to reproduce both, and CI re-runs the gate and never
trusts `RESULT.json` or a committed report. But code written specifically to defeat the fingerprints or to forge the child's
report is not ruled out mechanically, and a `test_driver.py` that tampers before its own `check_driver` call can affect
only G9's verdict on its own cases (G1 to G8 ran earlier in a process that never imported it). The static scan makes such
code visible; aliased reflection such as `_g = getattr` is not followed. That is why a human reads every driver, and why the
sandbox ([SANDBOX.md](SANDBOX.md)) is the boundary for what package code can do to the host.

## 5. Review by a model

A project without a reviewer for every package may have a different model than the author review them: it works through the
checklist of section 2, decides (accept; fix, by its own edit or by a fix run of the author model; blocked), and records what it did.
What does not change:

- `reviewed_by` stays `null`. It is a human's signature, and the loader keys the hardware backend of a model-written driver at R2
  or R3 on it; a model never writes it.
- A warning that only a signature accepts (`UNSOURCED_LIMIT_GATE_WARNING`, `UNVERIFIABLE_CITATION`) is not accepted by a model. The
  bound becomes `Limit.operator_required`, or cites a line that shows the number, so `collect.py --strict` passes unsigned.
- The evidence stays `contract_checked`, and nothing is said about the device beyond what the fake shows.

The record is the last paragraph of `RESULT.json` `notes`: it starts `MODEL REVIEW (<model id>, a model and not a human, <date>;
reviewed_by stays null):`, gives the decision, and names every file the reviewer changed. After an edit the reviewer re-runs the gate
and writes its digest, as an author does. The eight packages of the pilot's first two sessions were reviewed this way
(`MHS/changes/PILOT-2.md`); a human who reviews one of them later still signs `reviewed_by` in the usual way.
