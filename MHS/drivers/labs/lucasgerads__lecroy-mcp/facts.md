# Facts and limits for gh.lucasgerads/lecroy-mcp

Every citation is a line of the clone at commit `3c866b341605ca689069d729c7b918f1c725d2e6`.  `upstream_code`
citations are the in-tree VISA/SCPI class `oscilloscope:LeCroyScope`; `vendor_doc` citations are the manual text
shipped in the clone as `resources/maui_text.txt` (the PDFs are not cited: the text is the readable source and the
gate cannot read a PDF).  The `Fact` objects in `driver.py` are the authoritative list; this page adds the review
notes.

## Tags

`oscilloscope`, `lecroy`, `maui`, `scpi`, `visa`, `waveform`, `measurement`.

## What the clone is

- `LeCroyScope` is a VISA/SCPI interface for LeCroy oscilloscopes running MAUI firmware (`oscilloscope.py:198-200`).
- `connect()` opens `pyvisa.ResourceManager("@py")`, opens the VISA resource, sets a 10 s timeout and newline
  terminators, then queries `*IDN?` (`oscilloscope.py:221-237`).
- The model is the second comma-separated field of `*IDN?` (`oscilloscope.py:263-273`).
- The profile registry covers WaveSurfer, HDO, MDA, WavePro, WaveRunner and SDA families with 4 or 8 analog
  channels (`oscilloscope.py:53-156`).
- `get_capabilities()` returns the profile values (`oscilloscope.py:275-294`).
- `get_channel_info()` queries `VDIV?`, `OFST?`, `CPL?` (or `COUP?`), `BWL?` and `TRA?`, and, when the profile
  supports them, `INVS?` and `UNIT?` (`oscilloscope.py:440-460`).
- `set_vdiv()` / `set_offset()` write `<channel>:VDIV` / `<channel>:OFST`; `set_coupling()` and
  `set_bwlimit()` validate against the detected profile before writing `<channel>:CPL` / `<channel>:BWL`;
  `set_attenuation()` writes `<channel>:ATTN` (`oscilloscope.py:462-499`).
- `get_timebase_info()` queries `TDIV?`, `TRDL?` and `MSIZ?`; `set_tdiv()` / `set_trigger_delay()` write
  `TDIV` / `TRDL` (`oscilloscope.py:513-527`).
- `get_trigger_info()` queries `TRIG_MODE?`, `TRIG_SELECT?` and `<channel>:TRIG_LEVEL?`; `set_trigger_mode()`
  validates `VALID_TRIG_MODES`; `set_trigger_source()` writes `TRIG_SELECT EDGE,SR,...,SL,...,HT,OFF`;
  `set_trigger_level()` writes `<channel>:TRIG_LEVEL` (`oscilloscope.py:536-565`).
- `force_trigger()` writes `FRTR`, `arm()` writes `ARM`, `stop()` writes `STOP`, and `is_stopped()` queries
  `TRMD?` (`oscilloscope.py:567-583`).
- `measure(channel, param)` queries `<channel>:PAVA? <parameter>` and may write `PACU 1,<parameter>,<channel>`
  when the reply contains `,IV` (`oscilloscope.py:628-640`).
- `calibrate()` queries `*CAL?` and returns the stripped reply (`oscilloscope.py:421-422`).

## Limits and why they are operator-required or closed

- Attenuation is a closed set from the manual: `{1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 10000}`
  (`resources/maui_text.txt:4527`).
- Coupling is a closed set from the manual: `{A1M, D1M, D50, GND}` (`resources/maui_text.txt:4589`).  The
  manual notes that not every model supports every value; the upstream profile validation is narrower
  (`oscilloscope.py:468-477`), so the device may still refuse a value from the closed set.
- Bandwidth limit is a closed set from the manual: `{OFF, 20MHZ, 200MHZ, 500MHZ, 1GHZ, 2GHZ, 3GHZ, 4GHZ,
  6GHZ}` (`resources/maui_text.txt:4544`); the manual says the available filters depend on the model, and the
  upstream profile validation is narrower (`oscilloscope.py:479-488`).  The field is not exposed by this package
  because the configure tool has to stay within the 2048-byte MCP budget.
- Trigger mode is a closed set from the manual: `{AUTO, NORM, SINGLE, STOP}` (`resources/maui_text.txt:4842`).
- The vertical scale (`VDIV`) has no numeric range in the clone or the manual; the manual refers the valid
  ranges to the product datasheet (`resources/maui_text.txt:4985`), so the driver declares
  `Limit.operator_required`.
- The vertical offset (`OFST`) has no numeric range; the manual says the maximum depends on the fixed
  sensitivity and refers to the datasheet (`resources/maui_text.txt:4660`), so the driver declares
  `Limit.operator_required`.
- The timebase (`TDIV`) has no numeric range; the manual refers the timebase specifications to the datasheet
  (`resources/maui_text.txt:4744`), so the driver declares `Limit.operator_required`.
- The trigger delay (`TRDL`) is bounded relative to the current Time/div: `(0 to -10,000) x Time/div` and
  `(0 to +10) x Time/div` (`resources/maui_text.txt:4792`).  The runtime cannot express a bound relative to
  another state field, and the field is not exposed by this package (the configure tool budget), so no `TRDL`
  `Limit` is declared.
- The trigger level (`TRLV`) has no numeric bound; an out-of-range value is adjusted to the closest legal value
  (`resources/maui_text.txt:4818`), and the range depends on the trigger source, so the driver declares
  `Limit.operator_required`.
- The trigger source has no model-independent closed set; the manual says the available sources depend on the
  oscilloscope model (`resources/maui_text.txt:4884`) and lists `C1...Cn, LINE, EX, EX5, EX10, ETM10`
  (`resources/maui_text.txt:4914-4920`).  The driver declares `Limit.operator_required`; the example overlay
  names the sources fitted to one bench.

## Stop path

The `@estop` method calls the native `stop()`, which issues the SCPI write `STOP` (`oscilloscope.py:577-578`).
`STOP` is a write without an acknowledgment in the upstream class. The e-stop now reads
`TRMD?` (oscilloscope.py:580-583), requiring exactly STOP after CHDR OFF before returning. An ignored stop fails with
`SAFE_STATE_UNREACHED` and keeps the latch held; a write returning alone never confirms stopping. The state
concerns acquisition only, not WaveSource output or an external circuit, and another client or the front panel
can resume acquisition.  The upstream `arm_and_wait()` polling loop is not exposed by this driver; if it were,
a `STOP` would not interrupt its `time.sleep(0.05)` loop, which is one reason this package serves `arm()` and
`force_trigger()` as separate actions.  The e-stop does not close the VISA session and does not undo the stop; a
reset only releases the runtime latch, and an operator arms the scope again with the `arm` action.
The VISA session itself has a 10 s timeout set by the upstream `connect()` (`oscilloscope.py:230`).  The e-stop
shares that session with any query in flight: the runtime latches first and does not wait for the running action,
but the `STOP` write can be delayed until an in-flight `*CAL?` or PAVA query returns or times out.  `STOP` is a
software stop of the acquisition, not a safety-rated channel and not a substitute for the scope's front panel or
mains switch.

## Actions and calibration

- `arm` (extension) calls `arm()` and reports that the native write returned; the `stopped` read is the state
  evidence.
- `force_trigger` (extension) calls `force_trigger()` and reports that the native write returned.
- `measure` (extension) calls `measure(1, parameter)`; the raw PAVA reply has the manual's
  `<parameter>,<value>,<state>` form (`resources/maui_text.txt:5617`, example at `5371`), so the action returns
  the reply string rather than inventing a unit or parsing away the state.
- `calibrate` uses the catalogue class `cap.device.calibrate.v1`.  The manual says `*CAL?` returns a diagnostic
  code where 0 means success, and gives `*CAL 0` as the no-failure reply (`resources/maui_text.txt:6376-6381`).
  The action returns `calibrated = true` and `calibration_ref` = the raw reply only for code zero; a nonzero
  diagnostic or a reply with no numeric code raises `DriverFailed` (`MHS.DEVICE.FAULTED`).  The class declares the action `requires_permit`; the
  conformance suite supplies the permit on the simulated endpoint, and the hardware backend is not run here.
  The class's optional `standard_ref`, `targets` and `notes` inputs are accepted with the class's length limits
  and descriptions, but the native `*CAL?` takes no reference and calibrates the scope as a whole, so the
  driver does not send them.  The upstream sets a 10 s VISA timeout at connect (`oscilloscope.py:230`), so the
  blocking `*CAL?` query is bounded by that timeout in normal operation; the driver does not claim to interrupt
  a query already in flight.

## Coverage

- NOT COVERED: the waveform array.  `get_waveform()` / `get_waveforms()` transfer IEEE 488.2 binary blocks as
  time and voltage arrays (`oscilloscope.py:746-810`); no catalogue class in this driver carries a trace array.
- NOT COVERED: the screenshot.  `get_screenshot()` returns PNG bytes (or a raw IEEE 488.2 block)
  (`oscilloscope.py:713-744`); it is not a camera image binding and is not exposed.
- Not exposed: math functions (`set_math`, `get_math_info`, `set_math_zoom`, `get_math_zoom`), cursors
  (`get_cursor_info`, `set_cursor_type`), the bandwidth limit (`set_bwlimit`), the trigger delay
  (`set_trigger_delay`), WaveSource and serial decode.  They are secondary to the channel, timebase, trigger,
  acquisition and scalar-measurement interface served here; the bandwidth limit and trigger delay are left out so
  the single configure tool stays within the 2048-byte MCP budget.
- The fake is an analytic in-memory stand-in, not a recording or a transcript.  The clone has no simulator or
  test suite for this class, and no instrument traffic was captured.  All fake numbers and canned replies are
  placeholders.

## Response formatting

The upstream `query()` returns the instrument reply unchanged (oscilloscope.py:401-405). The manual defaults
to SHORT response headers and shows `C1:VDIV 200E-3 V`; OFF suppresses headers and units
(resources/maui_text.txt:5063-5075). The driver setup sends `CHDR OFF` on both hardware and fake backends before
scalar reads. Another client changing COMM_HEADER can invalidate this session assumption. Manual citations use
the same form-feed-aware line numbering as `show_refs.py` and the gate.

The upstream setting getters catch query exceptions and substitute `N/A` (oscilloscope.py:440-460,
513-521,536-548). Numeric fields already reject that sentinel; coupling and trigger-mode fields now reject it
as `MHS.DEVICE.FAULTED` too, including after a write. A failed readback cannot be returned as an applied setting.
`disconnect` suppresses close exceptions before clearing its stored connections (oscilloscope.py:239-251);
teardown therefore does not prove a physical disconnection.
