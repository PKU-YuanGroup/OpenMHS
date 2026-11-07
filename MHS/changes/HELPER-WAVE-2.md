OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Helper wave 2: the 15 waiting cards the phase-2 routing opened, reviewed by Claude and verified by a second model (9 contracts, 6 blocks)

The model review of the waiting cards (phase 2, 2026-11-05) routed 15 of the 62 cards that waited for a helper family
at takeover to reviewed direct-driver overrides (`MHS/registry/overrides/waiting-routing.json`): lab robots and liquid
handlers (Opentrons OT-2 and Flex, the ad-sdl OT-2, PAL, BMG and UR modules, a Tecan Fluent connector, an OT-2
controller over SSH), stages and microscopes (openuc2 ImSwitch, the TALOS transfer stage, a pycromanager control app,
a Prior ProScan stage), a fish sorter, a pump bench and an EPICS driver pack. All are `python-object` cards with the
Julabo exemplar; twelve have an R2 floor. The user had authorized these author runs on 2026-11-04 (up to 62 cards
that a helper integration makes dispatchable; with helper wave 1 this uses 48). DeepSeek (`deepseek-v4.1-flash:1017`)
authored them in batch `helper-wave-2` as in [helper wave 1](HELPER-WAVE-1.md), six at a time. Two runs ended with a
DeepSeek server error (`PI_AI_ERROR: Internal Server Error`) before writing the package and were re-run with `--redo`
(the old output moved aside); one of those re-runs ended its turn before writing `driver.py` and was run a third time.
Over the 18 runs an agent took 446 s at the median (longest 679 s); the harness counted 225 million tokens, 92 % cache
reads; no author wrote outside its package directory.

## Review

Claude (`claude-opus-5-5`, a model and not a human) reviewed every package as in the earlier waves, one reviewer per
package that owned its directory, with an addendum (the card's routing evidence and what to watch for, and the phase-2
mechanisms: declared re-enable with no `@reset` beside it, terminal e-stop, the reset policy of SAFE-042). Each decision
was then verified by Claude Sonnet (`claude-sonnet-5-5`), which re-ran the gate and the strict collector and tried to
refute the decision; it agreed on all 15, with no blocker or major finding, so no dispute round ran. Each package's
`RESULT.json` carries both paragraphs.

| Status | Author | After review |
|---|---:|---:|
| pass | 14 | 9 |
| blocked | 1 | 6 |

Every author pass was changed. The recurring defect was a stop that the SDK counted as achieved although nothing
confirmed it, now refused with `MHS.SAFETY.SAFE_STATE_UNREACHED` and the latch held unless a fresh read confirms it:
an HTTP run cancel whose answer and run state were never read, with an unanswered run list read as "no runs" (ad-sdl
OT-2); a safe-state action that reported "stopped: false" as a completed result (TALOS); a Tecan `StopMethod` returned
without reading the run state (Fluent); Modbus write replies ignored although pymodbus returns exceptions as messages
(fish sorter); an all-axis stop that returns nothing reported as stopped (ImSwitch); a Smoothie halt that waits for the
lock a running move holds, which the lock-free fake hid (Opentrons OT-2; after a halt the driver now sends nothing but
the re-enable, M999 and a home); and a heater served behind a stop that stops neither the plate carrier nor the assay
(BMG, reduced to its one source-backed stop). Six packages are blocked with evidence: an e-stop that only disconnects a
.NET remote service (PAL), an e-stop that only closes the SSH client of a protocol started as root (OT-2 controller), a
deprecated console RESET that cannot interrupt a move (pycromanager app), no stop command anywhere (ProScan), a pump
stop written by a queue worker that dies silently on one unparsable reply (pump bench), and the UR module (below).

## Registry

The UR module's override gained `publish_review: required` (the MIT clone ships Universal Robots' manual and Robotiq
files); the EPICS driver pack's override now names the Lake Shore 336 client the reviewed package serves. The registry
was rebuilt and every `task.json` synchronized.

## Found, not fixed

- `gh.ad-sdl/ur_module` is blocked as `SDK_BUG`: its re-enable (a brake release, only with safety status NORMAL,
  confirmed RUNNING) is rightly permit-gated, but the SAFE-031 conformance test needs a second distinct valid input for
  the only gated capability while CORE-086 makes a re-enable input-free. A phase-3 change addresses the test.
- Opening several of these backends already acts on the device (lights, initialisation, homing); the reviews disclose
  it for the human reviewer.

## Result

Both reviews were applied by one script that re-ran every gate (15 Claude Opus and 15 Claude Sonnet decisions, none
refused). On the final state of the tree: dispatchable 0; done 842 (697 pass, 134 blocked, 11 skip-proposed). The
strict collector passes all 9 new contracts with the digests their `RESULT.json` records; `validate.py --no-corpus`
passes.
