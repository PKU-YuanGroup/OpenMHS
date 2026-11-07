# Facts and tags for gh.qcoherence/qcodes-drivers

Every fact cites the pinned clone at commit `619bdd35bda80f767f42a1681d6dd26819ad09a9`: `upstream_code` (a code or
docstring line of the clone) or `vendor_doc` (a text file of the clone).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package drives one ADwin Gold II through the QCoDeS Instrument `ADwin_Gold2:ADwin_Gold2`
(`ADwin_Gold2.py:549`).  The card asked for the `QcodesDriver` helper, but that family proves one explicit
`self.<name> = Parameter(...)` assignment per served field
(`MHS/sdk/docs/qcodes-driver.md`).  This clone constructs every Parameter with `add_parameter`
(`ADwin_Gold2.py:569-709`), which the QcodesDriver source proof does not cover, so the package is a direct `Driver`
over the class methods.  `RESULT.json` records the deviation from the card.

The served interface is the device's primary analog input/output path: the five scalar settings (`adwin_mode`,
`ramp_size`, `subsampling`, `output_mask`, `input_mask`), an action that sends eight output voltages through the
native FIFO, an action that reads the measurement FIFO and converts the ADC codes, and the native `go_to_zero` command.

BLOCKED (model review, 2026-11-05): no stop is proven from the clone, so the e-stop sends `go_to_zero` and then
reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held, and `zero_outputs` is not a safe-state action (see
Safety). The gate fails G6 `ESTOP_FAILED` and G8 `SAFE-028`, the expected blocked state.

| fact | source | ref |
|---|---|---|
| ADwin_Gold2 is the QCoDeS Instrument class for the ADwin Gold II | upstream_code | ADwin_Gold2.py:549-552 |
| The constructor takes the instrument name, a boot file, a process file and an ADwin number that defaults to 1 | upstream_code | ADwin_Gold2.py:557 |
| The constructor opens ADwin.ADwin(adwin_no), boots it, loads and starts the process and clears both FIFOs | upstream_code | ADwin_Gold2.py:711-714 |
| process_load stops the process, loads the process file, sets a 3000-step process delay (10 us on the T11 clock) and starts the process | upstream_code | ADwin_Gold2.py:727-736 |
| set_outputs builds the FIFO from the mode, input mask, output mask, ramp size and subsampling, then appends the targets; it does not reset the outputs to 0 V | upstream_code | ADwin_Gold2.py:754-779 |
| set_outputs_one_cycle sends the FIFO with a one-point ramp, waits two process durations and restores the ramp size | upstream_code | ADwin_Gold2.py:783-790 |
| launch_measurement sends the FIFO and sleeps for ramp_size times the process duration | upstream_code | ADwin_Gold2.py:792-794 |
| go_to_zero sets the output mask to all eight outputs, commands 0 V on all eight, sends one cycle, restores the mask and clears both FIFOs | upstream_code | ADwin_Gold2.py:796-804 |
| read_inputs reads all values in the measurement FIFO at once | upstream_code | ADwin_Gold2.py:806-812 |
| clear_fifos clears FIFO 1 and FIFO 2 | upstream_code | ADwin_Gold2.py:814-817 |
| volt_to_binary returns int(V / 10 * 2**15 + 2**15) as the DAC binary representation | upstream_code | ADwin_Gold2.py:742-744 |
| binary_to_volt converts the ADC binary back to a voltage between -10 V and +10 V | upstream_code | ADwin_Gold2.py:750-752 |
| set_mode accepts an integer mode or the strings normal, lockin, lockin2 and lockin2_inv | upstream_code | ADwin_Gold2.py:848-864 |
| set_output_mask accepts a mask integer or a list of output indices and sums 2**(i-1) for each list index | upstream_code | ADwin_Gold2.py:884-898 |
| set_input_mask accepts a mask integer or a list of input indices and sums 2**(i-1) for each list index | upstream_code | ADwin_Gold2.py:904-918 |
| set_ramp_size and get_ramp_size read and write the internal ramp size rs | upstream_code | ADwin_Gold2.py:876-882 |
| set_subsampling and get_subsampling read and write the subsampling factor | upstream_code | ADwin_Gold2.py:924-930 |
| The adwin_mode validator accepts 0x0 through 0x80010 or the four mode names | upstream_code | ADwin_Gold2.py:569-578 |
| FIFO_SZ is 1000000 | upstream_code | ADwin_Gold2.py:12 |
| The ramp_size validator is Numbers(0, FIFO_SZ) | upstream_code | ADwin_Gold2.py:580-587 |
| The subsampling validator is Numbers(0, 2**16) | upstream_code | ADwin_Gold2.py:597-603 |
| The output_mask validator accepts 0b1 through 0b11111111 or a list of indices 1 to 8 | upstream_code | ADwin_Gold2.py:605-614 |
| The input_mask validator accepts 0b0 through 0b11111111111111 or a list of indices 1 to 14 | upstream_code | ADwin_Gold2.py:616-625 |
| The outputs Parameter has unit V and the validator Arrays(-10, 10) | upstream_code | ADwin_Gold2.py:627-636 |
| The inputs Parameter has unit V and converts each FIFO value with binary_to_volt | upstream_code | ADwin_Gold2.py:638-646 |
| The lock-in frequency, amplitude, bandwidth and port Parameters call self.device.Set_FPar, Get_FPar, Set_Par and Get_Par directly | upstream_code | ADwin_Gold2.py:648-709 |
| The README says the repository holds custom drivers for instruments used with QCoDeS | vendor_doc | README.md:5 |
| The README says the ADwin relies on the nanoqt submodule and the external ADwin package must be installed | vendor_doc | README.md:15-29 |
| .gitmodules declares the submodule adwin/nanoqt | upstream_code | .gitmodules:1-3 |
| adwin_zero.py boots the ADwin from ./nanoqt/ressources and loads the process ./nanoqt/ressources/acquisition-gold2.TB1 | upstream_code | adwin/adwin_zero.py:10-16 |
| acqui_adwin.py writes one command into FIFO 1, then queues n_ramp pairs of ramp commands in a loop and a final command, all with SetFifo_Long | upstream_code | adwin/acqui_adwin.py:30-36 |
| get_input_size divides ramp_size by subsampling | upstream_code | ADwin_Gold2.py:819-826 |

Tags: `qcodes`, `adwin`, `real-time`, `analog input`, `analog output`, `daq`.

## Limits

Every numeric write and the output action carry a bound stated in the clone, except `subsampling`:

| input | bound | source | ref |
|---|---|---|---|
| `adwin_mode` | 0 to 0x80010 | upstream_code | ADwin_Gold2.py:573 |
| `ramp_size` | 0 to 1000000 (`FIFO_SZ`) | upstream_code | ADwin_Gold2.py:12 |
| `subsampling` | `Limit.operator_required` (the validator `Numbers(0, 2**16)` allows 0, which divides by zero in `get_input_size`) | operator | ADwin_Gold2.py:600, 819-826 |
| `output_mask` | 1 to 255 (`0b11111111`) | upstream_code | ADwin_Gold2.py:609 |
| `input_mask` | 0 to 16383 (`0b11111111111111`) | upstream_code | ADwin_Gold2.py:620 |
| `targets[*]` | -10 to 10 V | upstream_code | ADwin_Gold2.py:630 |

`subsampling` is `Limit.operator_required` (model review): the upstream validator's lower bound 0 divides by zero
in `get_input_size`, and the clone does not show what the real-time process accepts; `site-limits.example.json` shows
an example overlay. The output voltage bound is the upstream validator `Arrays(-10, 10)`; `volt_to_binary` maps
+10 V to 65536 (2**16), and the clone's own script also sends 2**16 (`adwin/acqui_adwin.py:28`); how the process
treats that code is not in the clone.

## Safety

The ADwin Gold II is a low-voltage real-time analog I/O controller: eight DAC outputs in the -10 V to +10 V domain
and a FIFO of ADC inputs, wired to whatever the experiment connects (gate or bias lines of a sample, for example).
The package stays R1, the card's floor. The outputs are actuators, and no stop is proven from the clone:

- `go_to_zero` (`ADwin_Gold2.py:796-804`) builds a 0 V command for all eight outputs, writes it into FIFO 1 with
  `SetFifo_Long`, sleeps two process durations, restores the output mask and clears both FIFOs. Nothing
  acknowledges the command or reads an output back.
- The real-time process that consumes FIFO 1 (`acquisition-gold2.TB1`, `adwin/adwin_zero.py:15`) is in the
  `adwin/nanoqt` git submodule (`.gitmodules:1-3`, `README.md:15-29`), which is not part of the pinned commit, so
  what a FIFO command does is not in the clone.
- FIFO 1 is a command queue: the clone's script queues ten (`n_ramp`, line 12) pairs of ramps one after
  another (`adwin/acqui_adwin.py:30-36`). Behind a running ramp, `go_to_zero`'s own `clear_fifos` two process durations
  later can delete its zero command unexecuted.
- The command keeps the current `adwin_mode` as its mode word (`ADwin_Gold2.py:754-779`), so in a lock-in mode the
  zero command is a lock-in command.
- `go_to_zero` rebuilds the instance's `fifo_list` and output mask, which a running `set_output_voltages` also uses;
  the e-stop does not take the driver lock, so an overlapping e-stop can send that action's targets instead of 0 V.

The e-stop therefore still calls `go_to_zero` (best effort) and then raises `MHS.SAFETY.SAFE_STATE_UNREACHED`: the
latch stays held and refuses every later write and invoke; reads remain available. The loaded real-time process is
never stopped (`process_load`, `ADwin_Gold2.py:727-736`, has no stopping wrapper). Unblocking needs the process
source (the submodule) and a stop whose effect is confirmed, or a human-cited physical stop of the outputs.

## Fake fidelity

`fake.py` keeps the five settings in attributes and repeats the FIFO header construction, the one-cycle send, the
eight-output zeroing and the ADC/DAC formulas of the upstream methods.  It does not model the ADwin device driver,
the FIFO capacity or the real-time process that consumes the FIFO; it omits the upstream `time.sleep` calls.  The
starting settings and the canned ADC codes are placeholders, not facts.  The driver calls the class methods
directly, so the QCoDeS validators and the `outputs`/`inputs` parsers are bypassed on both backends; the fake does
not add a validation layer the real class does not have.

## Hardware backend

`native.py` imports `ADwin_Gold2.ADwin_Gold2` only when an operator loads the hardware backend.  Deployment must put
the pinned clone root on `PYTHONPATH`, install QCoDeS, numpy, tqdm and the vendor `ADwin` package, and supply the
boot file and process file; none of these is guessed.  The upstream constructor boots the ADwin, loads and starts the
process before it returns, so the operator must be prepared for that on load.  Nothing was run: the package has
never opened an ADwin. At R1 the loader does not refuse the hardware backend of an unreviewed model-written driver
(it does so at R2 and R3), so the package's blocked status is what keeps it from deployment.
