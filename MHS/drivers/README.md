# Driver packages

One upstream repository of the corpus (`labs/`, `robots/`) becomes one driver package here:

```
MHS/drivers/<track>/<owner>__<repo>/      task.json  driver.py  fake.py | fixtures/  facts.md  test_driver.py
                                          driver.lock.json  reference.json  REFERENCE.md  RESULT.json
```

`native.py` (the hardware factory), `site-limits.example.json` and `fixtures/conformance.json` are added when the driver needs them.
The package is finished when `python3 -m mhs.driver check <dir> --backend fake` exits 0. The rules, the Driver API and
the gate ids are in [`MHS/sdk/docs/driver-authoring.md`](../sdk/docs/driver-authoring.md); the task cards that say what
each package is for are in [`MHS/registry/tasks/`](../registry/tasks/). Upstream clones are read-only; nothing here imports
or runs upstream code (the gate parses Python interfaces with `ast` and checks ROS endpoint/type citations against pinned source text).

## The five exemplars

[`EXEMPLARS.txt`](EXEMPLARS.txt) lists them, one directory per line. Each has a `README.md` with what it shows, the
files, and what it does not prove. A task card's `exemplar` field points at the one to copy.

| Package | Shape | What to copy it for |
|---|---|---|
| [`labs/tiagocoutinho__julabo`](labs/tiagocoutinho__julabo) | async direct `Driver`, R2 hardware, a circulating bath | an `async def` SDK; a bound no source states (`Limit.operator_required`, filled by `site-limits.example.json`); `x-cap.<owner>.<name>.v1` actions; the native stop as `@estop` and as a safe-state action (SAFE-045 without a cited hardware e-stop); facts that cite line ranges |
| [`labs/thinksrs__srsinst.sr860`](labs/thinksrs__srsinst.sr860) | `ScpiDriver` command map, R1 hardware, a lock-in amplifier | a family driver (class attributes only); limits the code states, with a range reference when the two bounds sit on different lines; an allowed set with an `enum_map`; an `idn` check; a transcript-backed fake; an overlay that narrows |
| [`robots/xarm-developer__xarm-python-sdk`](robots/xarm-developer__xarm-python-sdk) | synchronous direct `Driver`, R2 hardware, a 7-axis arm | a joint array with per-joint `min`/`max` and `names`; nested Cartesian limits; several `operator_required` paths in one input; non-zero API return codes raised as `DriverFailed` (or `OutcomeUnknown`); `emergency_stop` as `@estop` with a documented physical stop (`estop_physical_ref`); `@reset`; `watchdog_ms` backed by a Fact; a fake with the upstream signatures |
| [`robots/farama-foundation__gymnasium`](robots/farama-foundation__gymnasium) | `GymnasiumDriver` family-config, simulated R0, CartPole-v1 | a simulator whose limits come from its spaces; the complete fidelity contract; a pure Python fake when the upstream package cannot be imported where the gate runs. The 68 `MujocoDriver` cards point here too: the shape is the same, but no exemplar covers a MuJoCo model file or a stand-in `mujoco` module (`bridges.md` has the grammar) |
| [`robots/avidbots__flatland`](robots/avidbots__flatland) | `RosDriver` family-config, ROS 1, simulated R0, Flatland | source-cited services and topics without a Python native class; `/clock` as an explicit observation; acknowledged `std_srvs/Empty` pause/resume; a ROS-free recording fake with negative service cases; an empty resource snapshot that does not wait for a paused clock. Pause is a simulator stop, not a physical emergency stop |

## Provenance and review status

All five packages are **model-authored, with no human review**. The original four locks record
`authored_by.kind: "model"` and `model_id: "claude-sonnet-5-5"`; the Flatland exemplar records
`model_id: "deepseek-v4.1-flash:1017"`. Every `driver.lock.json` keeps `reviewed_by: null`. Model review is recorded
in `RESULT.json` notes and does not replace a human signature. No hardware was attached to any exemplar.

- Their evidence is `contract_checked`: the gate ran on the fake backend. It is never an MHS-Device level; only an
  operator-run hardware check on a real device can earn one (`mhs.driver check` refuses `--backend hardware`).
- **A hardware backend is refused** for a model-authored driver of a hardware device at R2 or above until a human signs
  `reviewed_by`: `mhs.adapter.load_driver(dir, backend="hardware", allow_hardware=True, state_dir=...)` raises `LoadError`
  with `reason == "review_required"`. That covers the julabo and the xArm packages (R2). The sr860 driver (R1 hardware) is not
  refused by that rule, but nothing ran on an instrument and its wire syntax is unverified. The Gymnasium driver is
  simulated and has no hardware backend. Flatland is also simulated and has no hardware backend. For ROS drivers,
  the rule is stricter: **every hardware backend, at every risk and regardless of author, requires a human hardware
  review** before the backend factory or WebSocket can run. A model keeps `reviewed_by` null.
- Every `Limit` and `Fact` cites `path:LINE` at the pinned commit (gate G4 checks that the line exists; it only warns when a
  cited line lacks the number, so a reviewer reads every limit against its line).
- The registry marks each package `package_status: pass` (`MHS/registry/tasks/**`); a passing package is maintained and not
  dispatched again.

## Run the gates

From the repository root:

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=MHS/sdk/src
python3 -m mhs.driver check MHS/drivers/robots/xarm-developer__xarm-python-sdk --backend fake      # one package
for d in $(cat MHS/drivers/EXEMPLARS.txt); do python3 -m mhs.driver check $d --backend fake || exit 1; done   # all five
python3 -m mhs.driver reference <dir>          # regenerate reference.json and REFERENCE.md after a change to driver.py
python3 MHS/drivers/robots/farama-foundation__gymnasium/test_driver.py                              # a package's own cases
python3 MHS/registry/validate.py               # the cards, locks, results and reports against the corpus
```

A gate run writes `check-report.json` into the package (new timestamps each time); it is generated and not committed.
`RESULT.json` records the digest the check prints (`gate digest (RESULT.json gate.digest)`), which stays the same while the
result of the gate stays the same. `task.json` is a byte copy of the registry card; after a change that moves the card
(a new `package_status`), run `python3 MHS/registry/build_registry.py --jobs 8` and then `python3 MHS/handoff/tools/prepare.py --sync`,
which copies each regenerated card over the `task.json` of its package and touches nothing else.

Warnings the exemplars carry, none of which fails the gate (julabo, sr860 and xArm pass with none):

| Package | Warning | Why |
|---|---|---|
| Gymnasium | `G6.NO_NATIVE_CALL` for `cap.world.seed.v1`; four `G8.NO_UNIT` (`ticks`, `action.index`, `seed` twice) | every Gymnasium family driver gets them: the seed makes no native call, and the bridge derives integer inputs without a unit |
| Flatland | `G8.SAFE014_NOT_APPLICABLE` | the conformance suite awards **CL2**: no actuating capability declares a numeric limit for SAFE-014 to probe. The other CL3 tests pass, but this is not a full CL3 award or live ROS/hardware evidence |

## New packages

```sh
python3 -m mhs.driver new MHS/drivers/<track>/<owner>__<repo> --card MHS/registry/tasks/<track>/<owner>__<repo>.json \
    --like <the card's exemplar> --model-id <your model id> --run-id <your run id>
```

copies the card, the lock skeleton and the exemplar's code files; `driver-authoring.md` section 2 gives the order of work.
