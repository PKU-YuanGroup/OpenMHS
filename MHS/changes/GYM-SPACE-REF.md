# GYM-SPACE-REF — Gymnasium packages whose fake copies the upstream action space cite it

GYM-LIMITS stopped the Gymnasium bridge labelling the bounds it derives from a package's fake `upstream_code` and added
`GymnasiumDriver.action_space_ref` for a fake that copies the upstream space (`MHS/changes/GYM-LIMITS.md`). This change
read the fake's action space of each of the 207 packages against the upstream line it cites: 71 now set
`action_space_ref`, so their step bounds are `upstream_code` again with a ref that G4 checks. G4 learnt to read
`Discrete(n)`.

## The reading

The candidates are the 207 packages whose `reference.json` step limits have a `ref` that starts `action_space of`. For
each, the fake's `action_space` statement, the module constants it uses and the comments next to them were read with the
upstream lines they cite (`show_refs.py` prints the same lines for a package), and where the line alone did not settle it,
the code around it: the branch the package's configuration takes (`task == "pick_and_place"`, `control_type == "ee"`,
`normalise_a`), where the width comes from (`len(ACTIONS)`, `n_actions`, a configuration default), and whether a subclass or
wrapper replaces the space. A package got a ref only when all of these hold:

- neither the space nor a constant it uses is marked `# placeholder`;
- the fake's space has the upstream's bounds and width for the configuration the package serves;
- one span of the cited file (a line, or one statement of a few lines) writes the numbers, and G4 finds them there.

| Outcome | Packages |
|---|---|
| `action_space_ref` set: a `Box`, or a `Dict` of `Box`es | 59 |
| `action_space_ref` set: a `Discrete(n)`, or a `Dict` of three | 12 |
| no ref: the space, or a constant it uses, is marked `# placeholder` (2 of them now pass `env_origin`) | 58 |
| no ref: the upstream builds the bounds from names or computes them (`Discrete(len(self.actions))`, `Box(-action_high, action_high)`, `np.ones(n) * self.max_torque`), so no line shows the numbers | 48 |
| no ref: the fake cites no line that defines its space | 14 |
| no ref: the fake's space is not the upstream's (width, structure, or a clamp where the upstream space is unbounded) | 8 |
| no ref: the bounds come from two places (two controllers, two or three files) | 5 |
| no ref: the cited line is documentation (a README, an `.rst` page), not the code that builds the space | 2 |
| no ref: no single line defines the space (`nebula`, a 125-line block of controller configs) | 1 |

The decision and its reason for each of the 207 are in `work/handoff-runs/gym-space-ref/decisions.json`, and the survey
that printed each fake's space next to the lines it cites in `survey/` beside it (not exported).

## G4 reads `Discrete(n)`

The CartPole exemplar's fake copies `Discrete(2)` (`gymnasium/envs/classic_control/cartpole.py:151`), from which the bridge
derives `action.index` 0 .. 1. G4 found 2 on that line but not 1, so the ref warned `G4.REF_VALUE ... does not show [1.0]`,
and so would every `Discrete(n)` space: twelve fakes copy one. `_numbers_in` (`mhs.driver.check`) now reads `Discrete(n)`,
`Discrete(n=5)` and `Discrete(3, start=-1)` as showing the largest action `start + n - 1`; the smallest is the literal
`start` or 0, which G4 never asks for. `MultiDiscrete` and `MultiBinary` are not read: no cited line needed them.

A number more that a line shows can only remove a `REF_VALUE` warning, and no passing package had one, so no finding of any
other package changed.

## The refs

- Most refs cite the statement that builds the space: the `Box(...)`, the `Discrete(...)`, or a `Dict` of them
  (`furniture/env/furniture.py:298-310`).
- Where the `Box` takes its bounds straight from names, the ref cites the line that writes the numbers:
  `self.min_action, self.max_action = -0.25, 0.25` (tactile_gym), the module constants `action_low`/`action_high` (ur5e
  CoppeliaSim), `self.action_range` (fluidlab), `JOINT_LIMITS` (gym-soarm), the defaults of the two parameters that
  highway-v0's parameter file does not set (bark-ml), and the qpos controller's joint limits (simple).
- Data files: gym_multirotor and robosumo cite the motor `ctrlrange` lines of the MJCF their MuJoCo environment builds its
  space from, and nsmr the default robot JSON the space reads.
- fly-craft cites `flycraft/planes/f16_plane.py:161-172`, the lower and the upper bounds of its guidance-law mode.
- Two fakes differ from the upstream in structure only, and their notes say so: robosumo's keeps the two agents' `Box`es in a
  `Dict` where the upstream has a `Tuple` (the bridge bounds no `Tuple` element), and co-llm-agents' serves the single-agent
  `Dict` that the upstream step reads, because the upstream builds its `action_space` attribute from the observation space
  by mistake (the fake's comment). The bounds are the upstream's in both.

## The packages

- **Drivers.** Each of the 71 `driver.py` got one line after `backends`: `action_space_ref = f"{CARTPOLE}:151"` over the
  module constant that already names the cited file (69 packages), else a string literal (gym-aloha, gym-fx).
  `gh.maximilianb2/pc-gym` builds its own `GymnasiumBridge` in `make_bridge` and now passes it `action_space_ref` and
  `env_origin`. `gh.emb-ai/robobenchmart` and `gh.sjtu-visys-team/visfly`, the other two with their own bridge, have
  placeholder spaces: they pass `env_origin` only, so their bound's ref reads `action_space of the fake backend .fake:FakeX`
  instead of naming the class of the object.
- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md` of the 73. A
  comparison with the originals shows 76 changed limits and nothing else: 74 bounds became `upstream_code` with the cited
  ref (69 packages with one derived limit, robosumo with 2, co-llm-agents with 3), 2 refs name the backend;
  `provenance.manifest_digest` changed with the manifest.
- **Gate.** `python3 -m mhs.driver check <dir> --backend fake` passes for all 73, G4 has no finding, and every digest is the
  one `RESULT.json` already recorded: the stable digest covers the gate's findings, and no finding changed.
- **Results.** Each `RESULT.json` got the digest of that run and one sentence at the end of its `MODEL REVIEW` paragraph
  that names `driver.py` and the ref (`MHS/handoff/REVIEW.md` section 5). The CartPole exemplar had no such paragraph and got
  one. `driver.lock.json` is untouched: `authored_by.kind` stays `model` and `reviewed_by` stays null.
- **Tool sizes.** The MCP projection writes a limit's path, bounds, unit and reason into the tool description, never its
  `source` or `ref`, so every tool is byte for byte what it was.
- **Exemplar.** The CartPole exemplar's `README.md` names the pattern in its table ("The fake copies the upstream space,
  so `action_space_ref` cites the line that defines it"). `mhs.driver new --like` copies the exemplar's `driver.py`, its
  `action_space_ref` included; in a package of another repository the copied ref names a file that is not there, and G4
  refuses it (`REF_MISSING`) until the author cites the new environment's line or removes it.
- **Originals.** `driver.py`, `reference.json`, `REFERENCE.md`, `RESULT.json` and `check-report.json` of the 73 as they were,
  and the exemplar's `README.md`, are in `work/handoff-runs/gym-space-ref/originals/` (not exported), with the scripts that
  made the change (`apply_refs.py`, `run_gates.py`, `update_results.py`) and their logs.

## Tests and docs

- `tests/driver/test_ref_values.py`: `Discrete(2)`, `gym.spaces.Discrete(17)`, `Discrete(n=5)` and
  `Discrete(3, start=-1)` show their largest action; a bound past it is still reported; `MultiDiscrete([3, 3])` and
  `Discrete(len(self.actions))` show nothing more.
- `MHS/handoff/REVIEW.md` item 2 lists `Discrete(n)` among the forms G4 reads. `MHS/sdk/docs/driver-authoring.md` section 5
  says that a `Discrete(n)` shows `n - 1`, that a `Box` taking its bounds from names is cited at the line that writes the
  numbers, and that a space whose bounds no line shows gets no ref.

## Found, not fixed

- **Placeholder spaces that look like copies.** Several fakes mark `# placeholder` a space whose numbers are the upstream's,
  for example gym-duckietown (`simulator.py:309`), softgym (`pour_water.py:52-53`), maniskill-vitac2025, squint and jsbgym.
  They got no ref, as the rule says; a reviewer who confirms the copy could drop the mark and cite the line.
- **Bounds G4 cannot read.** 48 upstream spaces build their bounds from names or compute them. A reading of
  `np.ones(n)` and `-np.ones(n)` as 1 and -1 would let a few more cite their `Box` (pybullet_multigoal_gym's
  `Box(-np.ones([4]), np.ones([4]))`, gymfc's `Box(-np.ones(4), np.ones(4))`); the others need the line of the constant,
  which several fakes do not cite.
- **Space Robotics Bench.** The fake's action has 6 values, but the default Franka's hand adds a binary gripper action
  (`srb/assets/object/tool/franka_hand.py:37-39`), so the upstream `total_action_dim` is 7; the fake's comment says six.
  The package keeps its unsourced bound; its width deserves a second look.
- **Isaac Lab clamps.** himloco_lab, isaac_drone_racer, wheeledlab and tacex bound the fake's action by the action term's
  clip or clamp, while the Isaac Lab space itself is unbounded; the bounds stay without a source.
- **Wave C stale references.** The four blocked packages GYM-LIMITS names (smartem, liquidhandler, tecan-genesis,
  galago-tools) are still untouched.

## Result

- The SDK suite passes: 2,113 tests (1 new), 4 skipped. A first run, started before `CHANGELOG.md` indexed this record,
  failed only `test_the_shipped_changelog_lists_every_fragment`; the run after `tools/build_changelog.py` passes.
- The registry suite (276 tests) and `validate.py --no-corpus` pass. `build_registry.py --check` finds no generated file
  that differs, so the registry needs no rebuild: its records copy `gate.digest`, which did not change. (A first check,
  run while the exemplar's files were being edited, stopped because `MHS/drivers/**` changed during the build.)
- `collect.py --strict` over the 576 passing packages: all 576 pass the gate, and only `gh.amsikking/thorlabs_mcm3000` warns,
  as before (its PDF citation waits for a human, `MHS/changes/WAVE-B2.md`). It ran in six parallel chunks of 96, because
  collect.py runs one gate at a time; the CartPole exemplar, whose `README.md` and `RESULT.json` changed during that run,
  was collected again on its own afterwards: it passes with no warning.
- `tools/build_changelog.py` indexes this record.
- `tools/oss_export_check.py`, run after the checks above, passes. In a fresh export of the 13,253 tracked files it runs
  the generators' `--check` modes, the SDK, registry and spec suites, the site build and its freshness check, the
  thermostat gate, the gates of the four exemplars (CartPole included) and the OpenAI4S integration tests.
