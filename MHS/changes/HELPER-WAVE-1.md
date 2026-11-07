# Helper wave 1: the 33 cards the helper integration opened, reviewed by Claude (21 contracts, 11 blocks, 1 skip)

The [helper integration](HELPER-INTEGRATION.md) made 33 cards dispatchable: 10 Ophyd, 8 QCoDeS, 5 PyLabRobot, 3
MCP-client and 3 tag-bridge cards, two cards re-routed to python-object, and the re-dispatch of the code-less blocked
packages neuracoreai/bigym (now Gymnasium) and misterblue/ros2_raspicam_node (now an R0 camera card through a reviewed
capability-class override). The user had authorized these author runs on 2026-11-04 together with the ROS wave. DeepSeek
(`deepseek-v4.1-flash:1017`) authored them in batch `helper-wave-1` exactly as in [ROS wave C](ROS-WAVE-C.md): ten at a
time, the headless overlay in dsh's default workspace-write mode, the validated interpreter first on `PATH`. A card took
495 s at the median (90th percentile 627 s, longest 865 s); none timed out; the harness counted 408 million tokens, 99 %
of them cache reads; no agent wrote outside its package directory.

## Review

The authors passed 30 of the 33 cards, although the agents that built and assessed these helpers had predicted that
most of them would be blocked. Claude (`claude-opus-5-5`, a model and not a human) reviewed every package as in ROS
wave C, with an addendum that gave each reviewer the family's helper documentation, its Sonnet-reviewed exemplar and
the readiness evidence for each card, and asked for every author pass to be checked against that evidence.

| Status | Author | After review |
|---|---:|---:|
| pass | 30 | 21 |
| blocked | 2 | 11 |
| skip-proposed | 1 | 1 |

The high author pass rate came mostly from one move: authors left the card's helper and wrote a direct `Driver`
(a `DECISION_DEVIATION`), which the helpers' source proofs do not cover. Each such package was judged on its own stop
and fake. Nine author passes were blocked, each with source evidence: a stop that raises in the package's own
deployment and is a no-op afterwards (dodal), a "configurable stop" the class cannot have and that is really a new
setpoint (BEC positioner), a Python-side list cleared as an e-stop (qickodes), a stop that a shared ZeroMQ REQ socket
can prevent from being sent (bcs-ophyd-zmq), an unacknowledged FIFO command whose consumer is in an absent submodule
(qcodes-drivers), a Halt that cannot be sent while another synchronous call runs (pylabrobot-protobuf), an
option-injected "power-cut relay" no source line shows (hamilton-control), a fridge heater served instead of the
repository's microscope (scanning-squid) and fake replies shaped to pass TCAP-003 that the firmware in the clone does
not send (qcdrivers). Twenty-one packages pass after review, all but one with fixes: a stop-then-command race that let
a syringe pump move after a completed e-stop (uni-lab-os), unconfirmed EPICS `put`s and `stop(deep=False)` calls made
to confirm, HTTP stop responses checked by a fresh status read (odyssey), invented stops removed in favour of honest R0
read-only subsets (caproto_cryostat, pamila, ari_sxn_common, ophyd-ads), a laser instrument raised to R2 (lumipy), and
upstream thread-safety and lifecycle hazards disclosed.

## Registry

`MHS/registry/overrides/helper-wave-1-routing.json` holds 20 reviewed entries (direct-driver routes for the packages
that honestly left their helper, skip and reference routes, a capability-class correction that makes pamila an R0 card,
and `publish_review: required` for licence conflicts). The bigym and zhinst entries replaced their earlier entries in
`robots.json` and `labs.json`, and sls-detector's entry gained a publication review (no licence file). Four
`RESULT.json` files kept `catalogue_requests` for capabilities their reviewed drivers no longer declare; the
orchestrator removed those entries and added requests for the two new read capabilities (caproto_cryostat,
ari_sxn_common). The registry was rebuilt and every `task.json` synchronized.

## Found, not fixed

- Direct-`Driver` deviations for helper-family cards bypass the helpers' source proofs; G7 checks only first-level
  attribute names, never resolves a transport-family native, and does not see calls on members (`.put`, `.set`).
- Direct-`Driver` reads run alongside long actions without the driver lock, which corrupts natives that are not
  thread-safe; G8.NO_UNIT forces a unit on every numeric input, so "1" stands for an unknown unit.
- A stop that destroys the native object without a reopen route, and a command whose device acknowledgement is the
  same for every input, cannot be modelled faithfully under G8 TSAFE-001/SAFE-014 and TCAP-003.
- G4 does not evaluate expressions such as `2**16`.

## Result

The review was applied by one script that re-ran every gate (33 decisions, none refused; pamila after its
capability-class override reached the card). The registry was rebuilt twice (the second build changed nothing) and every
`task.json` synchronized. On the final state of the tree:

| State | Cards |
|---|---:|
| dispatchable | 0 |
| done | 823 (681 pass, 131 blocked, 11 skip-proposed) |
| recon | 3 |
| waiting for a helper | 22 (pymmcore-plus 9, http 5, sila2 5, mavlink 2, lerobot 1) |
| skip, reference, bridge-runtime | 1,526, 319, 270 |
| quarantined | 4 |

- `collect.py --strict` over all 681 passing packages: every package passes the gate with the digest its `RESULT.json`
  records; the only warning is the historical `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`.
- `build_registry.py --check`: 0 generated files differ. `validate.py --no-corpus` passes; the pilot check counts 20 of
  20; `build_changelog.py --check` passes.
- The SDK suite (3,212 tests, 5 skipped), the registry suite (310) and the OpenAI4S integration tests (129) pass.

- After this record was written, the full `tools/oss_export_check.py` passed on the final tree in a fresh export of
  15,628 tracked files (temporary root outside the workspace): the generators' checks, the spec doctests, the SDK and
  registry suites, registry validation, the release site build and its freshness check, the thermostat gate, the gates
  of all ten exemplars (the five new ones included) and the OpenAI4S integration tests.

Not run: any native transport, upstream code, device server or hardware; every result is `contract_checked` on a fake.
