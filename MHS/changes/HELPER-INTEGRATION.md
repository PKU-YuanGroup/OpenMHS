# Helper integration: five helper families, the AS7265x repair and reviewed card corrections

This change composes the work of five agents into one source change against the registry state of 2026-11-04: the
`mcp-client`, `pylabrobot`, `qcodes`, `ophyd` and `tag-bridge` families become available, each with one exemplar
package; gate G4 reads a literal `range()`; the AS7265x package is repaired; registry overrides gain reviewed
capability classes and an added publication review; and reviewed overrides re-route the cards the helper work found
misrouted. Every exemplar is model-authored (`reviewed_by` null) and passes on its fake backend only
(`contract_checked`); nothing ran on hardware.

## Families enabled

| Family | Helper | Exemplar | Record |
|---|---|---|---|
| `mcp-client` | `McpClientDriver` | `MHS/drivers/labs/mattjax16__rigol-dho-mcp` (Rigol DHO oscilloscope server, R0) | this record |
| `pylabrobot` | `PyLabRobotDriver` (new) | `MHS/drivers/labs/oelemento__star-sim` (STARlet twin) | [PYLABROBOT-FINITE-HELPER.md](PYLABROBOT-FINITE-HELPER.md) |
| `qcodes` | `QcodesDriver` | `MHS/drivers/labs/qcodes__qcodes_contrib_drivers` (Thorlabs PM100D, R1) | [OPHYD-QCODES-EXEMPLARS.md](OPHYD-QCODES-EXEMPLARS.md) |
| `ophyd` | `OphydDriver` (new read-only profile) | `MHS/drivers/labs/bcda-aps__apstools` (R0 monitor) | [OPHYD-QCODES-EXEMPLARS.md](OPHYD-QCODES-EXEMPLARS.md) |
| `tag-bridge` | `TagDriver` (new) | `MHS/drivers/labs/josuablejeru__labmastro` (Hanmatek HM supply, R2) | [TAG-BRIDGE-HELPER.md](TAG-BRIDGE-HELPER.md) |

`http`, `sila2`, `pymmcore-plus`, `mavlink` and `lerobot` stay blocked: their helpers either serve one pinned
profile only, or their upstreams show no stop that the user's rule of 2026-11-04 accepts (an actuator without a
source-backed stop stays blocked).

## Kit and SDK changes made while composing

- The task-card schema's `helper` enum, the shipped-registry test of dispatchable helpers and `collect.py`'s
  `FAMILY_HELPERS` list all eleven enabled helpers; without the enum entry gate G1 refuses every rebuilt card of a
  family as `CARD_INVALID`.
- `mhs.driver new` maps `PyLabRobotDriver` cards to the python-object templates and `McpClientDriver` and `TagDriver`
  cards to the direct ones (with `--like`, gate G2 names the lock `backends` to set); a new test checks that every
  mapped helper has a template kind.
- `MHS/drivers/EXEMPLARS.txt` lists the five exemplars. The star-sim exemplar's native class `RobotEnv` is the generic
  robot-environment class name of gym-style libraries, and three accepted packages that mention `MujocoRobotEnv` or
  robel's `RobotEnv` would have failed `collect.py --strict` with `EXEMPLAR_RESIDUE`; `robotenv` is now family
  vocabulary, while `star_sim` stays residue.
- The dead planned recipes of the flipped families are removed; the PyLabRobot family page opens with the
  independence statement like the other helper pages.
- Gate G4's new `range()` reader skips a literal that no float holds (a cited line with a `range()` argument of more
  than 308 digits crashed the gate); `MHS/handoff/REVIEW.md` item 2 lists what the reader shows.

## Registry override fields

An override may now carry `capability_classes`: 1 to 8 stable catalogue classes a reviewer confirmed in the
source. They replace the scan's name-derived candidate classes on the card and in the record, so the card's risk floor
(CAP-017) follows them; a robot card with reviewed classes is not marked `needs_recon: motion`, and a class that is not
a stable catalogue class stops the build. An override may also say `publish_review: "required"`, which adds a
publication review whatever the licence class; it can never waive one. The schema, `triage.py`, `taskcards.py`, the
overrides README and five registry tests cover both fields.

## Overrides

All justifications start `Model review of the helper integration, 2026-11-05:`.

- `gh.neuracoreai/bigym` (robots): family-config `gymnasium`, not `mujoco`: `BiGymEnv` subclasses `gymnasium.Env`
  (`bigym/bigym_env.py:34`) and the examples build env classes directly. The blocked record without code was moved
  aside so that the card can be dispatched again.
- `gh.misterblue/ros2_raspicam_node` (partners): `capability_classes` `cap.sensing.image.v1`: the node only publishes
  JPEG frames and reads its parameters once at start, so the card's R1 floor from a name-scanned
  `cap.device.configure.v1` becomes R0. Its blocked record without code was moved aside as well.
- `gh.alba-synchrotron/sls-detector` and `gh.cyberorigin2077/open_cyber_glove`: direct-driver `python-object` (a TCP
  client with a stop port and an upstream simulator; a binary serial glove), each read in its clone.
- `gh.dayr3n33/instruments`, `gh.jdmax/epics-device-lib` and `gh.jhu-lcsr/good_robot`: untriaged (recon cards).
- `gh.bcda-aps/apstools` and `gh.josuablejeru/labmastro`: `publish_review: required`. apstools declares
  `LicenseRef-ANL-Open-Source-License` (`pyproject.toml:24`) where the registry read BSD-3-Clause; labmastro's
  `LICENSE` is GPL-3.0 while `pyproject.toml:6` says MIT. The owner decides before either is published.

`gh.festo-se/festo-pgva` has no override: it gets a code-less blocked record
(`MHS/drivers/labs/festo-se__festo-pgva`, `NO_HARDWARE_FREE_PATH`), because no source line stops a running valve
pulse or vents the chambers.

## Packages

- `MHS/drivers/labs/liamsgithub__as7265x-spectrometer` passes after the blocked-package triage repair: the card's
  entry is the module selector `pyfile:spectrometer.py#*`, G4 reads `range(0,255)` as 0..254, the port bounds every
  wait and owns its register transactions, and the e-stop fences late writes and confirms every LED off.
- The model review of the apstools and PM100D exemplars changed their documentation: field descriptions that read a
  meaning into PV names, the connect bound of the apstools factory (up to seven times the timeout) and its unread
  channels, that every PM100D power read re-applies the power configuration, that the ABOR stop is not synchronised
  with a running read, and the fake's untested validators. Both digests are unchanged.

## Model review

Every exemplar and the new helper code were written by Claude Opus (`claude-opus-5-5`). REVIEW.md section 5 asks for a
reviewer model different from the author; on 2026-11-04 the user chose Claude Sonnet (`claude-sonnet-5-5`, a model
and not a human) for that review. The independence is weaker than a reviewer from another provider, and this record
says so. Three Sonnet reviews read the helpers, the five exemplars and the gate change against their sources, re-ran
the gates and the strict collector, and attacked the claims with mutants and probes; the authors (Claude Opus) applied
the findings and Sonnet re-checked them:

- PyLabRobot: an error after an actuating step was reported as a known failure (`MHS.DEVICE.FAULTED`) and did not
  fence the bridge, so new effects were admitted; every step error except PyLabRobot's five bookkeeping errors is now an
  unknown outcome that fences effects until a confirmed stop and reset. G7 now reads cited code with `ast` (one exact
  line per reference, operation spans capped at 40 lines); duplicate or scattered wells are refused; the mapping-error
  wrapping is restored; the exemplar cites each volume bound on its own line.
- Tag bridge: an acknowledged write whose confirmation read did not hold was reported as a known failure with no
  debt; it is now an unknown outcome that marks every written point and fences effects. G7 proved a Modbus register
  from any matching integer literal (a `functioncode=6` "proved" register 6); it now proves the address in its role as
  the address argument of a read/write call or a register constant, with table and direction checks. The codec refuses
  every inexact value (no tolerance), huge integers are invalid input, and only the Alpaca error numbers verified in a
  clone count as "not performed".
- Ophyd, QCoDeS and G4: the read-only profile's proof survived aliasing, re-export, shadowing and mutation; the G4
  `range()` reader no longer crashes on huge literals; documentation fixes for both exemplars; apstools and labmastro
  gained the publication review for their licence conflicts.

All ten review subjects ended accepted. The exemplars' `RESULT.json` notes carry the `MODEL REVIEW` paragraph with the
Sonnet model id; the review files are kept with the continuation's records. Residuals the reviews left open: the
PyLabRobot G7 still accepts a 40-line span covering several functions and does not check a stop's receiver; the tag
bridge's G7 accepts a register equal to an unrelated constant on the cited line with a warning only; the
minimalmodbus exception class used by the labmastro port is unverified (a wrong name fails safe as an unknown outcome).

## Found, not fixed

- `mhs.driver export` names an `OphydDriver` package's family `ophyd`, which `adapter.schema.json` does not list, so
  exporting such a package fails validation; a `TagDriver` package exports as `other`.
- G4's number reader is super-linear in the length of a digit run: a cited line with an 800-digit literal takes about
  a second, one with 5,000 digits ran for more than two minutes.
- `collect.py`'s residue scan matches substrings: an exemplar identity word such as labmastro's model `HM series` can
  match unrelated prose in a later package.
- The apstools card keeps the scanner's BSD-3-Clause identifier; only its publication review changed.

## Result

The change was composed and checked first in a private copy of the 2026-11-04 snapshot (SDK suite 3,212 tests, 6
skipped; registry suite 310; OpenAI4S integration 129, 4 skipped; strict collection of the 602 then-passing packages;
`build_registry.py --check` 0 differ; `tools/oss_export_check.py --skip-suites` with its temporary root outside the
workspace). It was then applied to the tree by one checked script that refuses unless every target still matched its
snapshot hash and backs up every original (157 actions: 116 files added, 39 replaced, 2 code-less package directories
moved aside), after the ROS wave C authors had finished and before their review was merged
([ROS-WAVE-C.md](ROS-WAVE-C.md)). In the tree, with ROS wave C merged:

- The registry was rebuilt (5,331 generated files changed, none removed or added) and `prepare.py --sync` refreshed
  711 `task.json` copies; a second rebuild and sync changed nothing. `MHS/sdk/INTERFACE.md` and `CHANGELOG.md` were
  regenerated.
- The gates of the five exemplars and the AS7265x package passed on the rebuilt cards before their review paragraphs
  were written.
- `collect.py --strict` over all 660 passing packages: every package passes the gate with the digest its `RESULT.json`
  records; the only warning is the `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`, which waits for a human.
- The SDK suite (3,212 tests, 5 skipped) and the OpenAI4S integration tests (129) pass; `validate.py --no-corpus`
  passes; the pilot check counts 20 of 20.
- `dispatch.py --stats` then counted 33 dispatchable cards (this change's), 790 done, 3 recon, 22 waiting for a helper
  (pymmcore-plus 9, http 5, sila2 5, mavlink 2, lerobot 1), 1,526 skip, 319 reference, 270 bridge-runtime and 4
  quarantined. The 33 cards were authored and reviewed next ([HELPER-WAVE-1.md](HELPER-WAVE-1.md)).

Not run: any native transport, upstream code or hardware.
