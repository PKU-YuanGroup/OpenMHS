# P5 backlog packages, BL-12

Unit BL-12 repairs two passing lab packages. Both used to send `*RST` from the safety reset. The clones do not state the effect on the output, so SAFE-042 (`MHS/spec/04-safety.md`, the paragraph that begins "SAFE-042") forbids that call as a reset step. Each package now offers the upstream reset method as an ordinary command. The safety reset sends nothing. `authored_by` is unchanged. `reviewed_by` stays null. Evidence is `contract_checked` on the fake backend. No hardware run and no human review are claimed.

Nothing was taken from the stopped attempts. The package trees under `development/p5-backlog-packages/project` and `development/ext-p5-backlog-packages.fast-stopped/project` matched this tree's base manifest for both directories. This record is the first write of the repair.

`MHS/changes/RE-ENABLE-AND-TERMINAL-STOP.md` still lists both packages under "Found, not fixed" (lines 247-249 and 306-307: `*RST` in the reset, output state unstated, waiting on a human check of the manuals). That file records the finding as it stood. This unit did not edit it.

No SDK file, registry file, task card, lock file or companion lock was edited. `prepare.py --sync` was not run.

## eta-systems/labor-gpib

Package `MHS/drivers/labs/eta-systems__labor-gpib`, id `gh.eta-systems/labor-gpib`. Class `Ngmo2` sets `risk = "R2"` (`driver.py` line 79) because the supply sources voltage and current. Risk stays R2. Status stays pass. Upstream pin `d5fe1b230344452bc32b756fc14567acde683c74`. `license_spdx` is `NOASSERTION` (`driver.lock.json`). Publication still needs the owner's decision. This unit does not publish the package. `authored_by` remains `deepseek-v4.1-flash:1017`, run `wP-032`, date 2026-10-30.

Clone `labs/eta-systems/labor-gpib/src/devices/rohde_schwarz_ngmo2.py`:

- Line 80 is the comment "Returns the power supply to the *RST default conditions".
- `rst` (lines 81-83) writes `*RST` and then calls `cls`. `cls` (lines 30-31) writes `*CLS`.
- `reset` (lines 85-86) calls `rst`.
- Channel `off` (lines 394-395) writes `:OUT:` plus the channel letter plus ` OFF`.

The comment states no output, voltage, current or averaging. The call is therefore an ordinary command. It is not a reset step. It is not a declared re-enable: `reenable=True` would claim that the command re-arms the supply, and the clone does not say that. It is not a safe-state action: `safe_state=True` would make the e-stop send `*RST`.

`x-cap.eta-systems.scpi_rst.v1` is `driver.py` `scpi_rst` (lines 383-393). It sets `_voltage_setpoint`, `_current_limit` and `_averaging_samples` to `None` (lines 389-391) and then calls `native.reset()` (line 392), which sends `*RST` and then `*CLS`. The exception from `reset()` still propagates. A later read of those three fields raises `DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", ...)` from `_known_applied` (lines 150-164) until the operator writes that field again, including when `*RST` was sent and the following `*CLS` write failed. The upstream class has no query for them, so the driver must not keep reporting the last applied number and must not invent zero. Queried fields, including `output_enabled`, still return the instrument reply. The fake's post-`*RST` numbers, including an output that is off, are placeholder test data (`fake.py` `_reset_state`, lines 99-104).

The e-stop (`driver.py` `stop`, lines 396-399) still sends only `:OUT:A OFF`. The existing safe-state action `x-cap.eta-systems.output_off.v1` (lines 364-370) is unchanged and still sends `:OUT:A OFF`.

`RESULT.json` `catalogue_requests` keeps `x-cap.eta-systems.output_off.v1` and adds `x-cap.eta-systems.scpi_rst.v1`. The author coverage sentence that said the reset sends `*RST` was corrected. A MODEL REVIEW paragraph was appended. Its head is `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null): `. Earlier review paragraphs were left as written. `driver.lock.json` was not edited.

Gate digest before and after: `sha256:2d12269fed28b897e3362edbd7a4e276845c14d7fe02bacad51efdcf3b4a051c`. `gate.failed` is empty. The digest identifies the gate report without its clock, so an empty finding list keeps the same digest. `collect.py --strict` reported no `RESULT_DIGEST_STALE`.

## smithsonian/rxlab-instruments

Package `MHS/drivers/labs/smithsonian__rxlab-instruments`, id `gh.smithsonian/rxlab-instruments`. Class `E8257D` sets `risk = "R1"` (`driver.py` line 38). Risk stays R1. Status stays pass. Upstream pin `2fbf8e6913e9eb2143088ed3a0b49d01a22fb93c`. `authored_by` remains `deepseek-v4.1-flash:1017`, run `wB2-025`, date 2026-10-29.

Clone `labs/smithsonian/rxlab-instruments/labinstruments/generic.py` lines 65-68: `reset` has the docstring "Reset instrument." and sends `*RST`. The docstring states no RF output, frequency or power.

Clone `labinstruments/agilent.py` lines 142-146: `power_off` writes `:OUTP OFF`. The e-stop still calls `power_off` (`driver.py` `stop`, lines 139-142).

`x-cap.smithsonian.scpi_rst.v1` is `driver.py` `scpi_rst` (lines 123-137). It calls `native.reset()` and returns `command_sent: true`. A later read returns the instrument reply. The receipt does not state what `*RST` set. The fake sets frequency `1.0e9` Hz, power `-20.0` dBm and output false inside `reset` (`fake.py` lines 67-77). Those numbers are placeholders. No Fact, Limit or receipt cites them.

The command is an ordinary action. `reset_attr` is absent, `reenable` is absent, and the binding has `safe_state` false and `reenable` false. While the latch is engaged the server refuses the command with `MHS.SAFETY.ESTOP_ENGAGED`.

`RESULT.json` `catalogue_requests` was `[]` and now records `x-cap.smithsonian.scpi_rst.v1`. The author sentence that called `*RST` the optional `@reset` recovery hook was corrected. The same MODEL REVIEW head was appended. `driver.lock.json` was not edited.

Gate digest before and after: `sha256:5d4d6f4e7a82ea638ccf2e00411747d440860485b2082310ad8c576b75044eed`. Findings stayed empty, so the digest did not move. `collect.py --strict` reported no `RESULT_DIGEST_STALE`.

## Tests

`python3 -m unittest MHS.drivers.labs.eta-systems__labor-gpib.test_driver` and the rxlab module of the same form. Each module's `test_gate` calls `check_driver`, which sets `write_report` false and does not write `check-report.json`. The labor module has 11 tests. The rxlab module has 11 tests. Class `ScpiRst` in each file checks the declaration, the e-stop, the safety reset and the ordinary command. Labor also checks a failed `*CLS` write after `*RST`.

`python3 MHS/handoff/tools/collect.py --strict` was run on the two package directories only. Both passed with 0 warnings.

Mutants, each applied to one file and then restored to the bytes the passing tests used. Only class `ScpiRst` was run, so the gate was not part of the mutant run:

- labor, a `@reset` hook that calls `native.reset()`: killed by `test_the_declaration_is_an_ordinary_command` because `reset_attr` is set.
- labor, `scpi_rst` returns `command_sent` without calling `native.reset()`: killed by `test_the_ordinary_command_sends_rst_and_forgets_the_cached_set_points`.
- labor, `scpi_rst` calls `native.reset()` and leaves the three caches in place: killed by the same test.
- labor, `scpi_rst` writes the caches to `0.0`, `0.0` and `1`: killed by the same test.
- labor, the three caches are cleared only after `native.reset()` returns: killed by `test_a_failed_write_after_rst_refuses_the_cached_set_points`. The injected `OSError` on `*CLS` left `voltage_setpoint` readable until the clear moved to lines 389-391.
- labor, the command is marked `safe_state=True`: killed by the declaration test (`binding.safe_state`).
- labor, the command is marked `reenable=True`: killed by the declaration test (`model.reenable`).
- rxlab, a `@reset` hook that calls `native.reset()`: killed by `test_the_declaration_is_an_ordinary_command`.
- rxlab, `scpi_rst` returns `command_sent` without calling `native.reset()`: killed by `test_the_ordinary_command_sends_rst_and_does_not_report_the_output`.
- rxlab, the command is marked `safe_state=True`: killed by the declaration test.
- rxlab, the command is marked `reenable=True`: killed by the declaration test.

The declaration tests require `reset_attr` to be `None`, so an empty `@reset` hook that sends nothing also fails. That is stricter than the sentence of SAFE-042. It leaves no hidden reset path.

## Residuals

The instrument manuals are not in the clones. If a human later shows that `*RST` enables an output, the ordinary command should become the declared re-enable (`safety.estop.reenable`). Until that evidence exists, the command stays ordinary and the latch refuses it.

A reviewer may prefer to drop the command. The item asked to offer it as an ordinary command if useful. It is offered because the operator must invoke it by name.

The fake's post-`*RST` numbers are placeholders. They are not instrument defaults.

## Round 1 review

Codex reported that a failed write after `*RST` left the three labor caches readable (`driver.py` used to clear them only after `native.reset()` returned). The fix clears the caches first (`driver.py` lines 389-391) and still lets the exception propagate (`test_driver.py` `test_a_failed_write_after_rst_refuses_the_cached_set_points`: receipt `failed` with `MHS.ADAPTER.SHIM_FAILED`, then each cached read raises `MHS.DEVICE.PRECONDITION_UNMET`). The re-run of the 11 labor tests passed, `show_refs.py` reported 0 bad citations among 38, and `collect.py --strict` passed both packages with 0 warnings. The gate digests did not move.

Grok reported that `facts.md` said lines 81-83 write `*RST` and then `*CLS`. Those lines write `*RST` and call `cls`. The `*CLS` write is `cls` at lines 30-31. `facts.md`, the author coverage sentence, and the MODEL REVIEW sentence now cite lines 30-31 for that write. `DEV/originals/` still holds the pre-change package trees and still matches `base-manifest.json`. No new path was added, so those copies were not overwritten.

The historical "found, not fixed" lines in `RE-ENABLE-AND-TERMINAL-STOP.md` are unchanged, for the integrator.

The gate digests did not move. Findings are still empty. That is the recorded result.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/labs/eta-systems__labor-gpib/RESULT.json`
- `MHS/drivers/labs/eta-systems__labor-gpib/driver.py`
- `MHS/drivers/labs/eta-systems__labor-gpib/facts.md`
- `MHS/drivers/labs/eta-systems__labor-gpib/fake.py`
- `MHS/drivers/labs/eta-systems__labor-gpib/test_driver.py`
- `MHS/drivers/labs/smithsonian__rxlab-instruments/RESULT.json`
- `MHS/drivers/labs/smithsonian__rxlab-instruments/driver.py`
- `MHS/drivers/labs/smithsonian__rxlab-instruments/facts.md`
- `MHS/drivers/labs/smithsonian__rxlab-instruments/fake.py`
- `MHS/drivers/labs/smithsonian__rxlab-instruments/test_driver.py`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
