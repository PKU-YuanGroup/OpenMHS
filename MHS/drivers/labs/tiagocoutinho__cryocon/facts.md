# Facts and tags for gh.tiagocoutinho/cryocon

The clone is a small library around a CryoCon temperature controller (tested with the M32 and M24C models, README.md:9)
plus an optional sinstruments simulator and a tango server. This package is a direct Driver over
`cryocon.cryocon:CryoCon` (the card's `decision` is direct-driver); every request is built by a member descriptor
around a text command (`cryocon/cryocon.py:105-128`, `cryocon/cryocon.py:187-206`).

Every fact cites its source at commit `a60636963d001e407c534494443b772742f6f545`: `upstream_code` is a code,
docstring or comment line of the clone; `vendor_doc` is a text file of the clone. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README says the library has been tested with the M32 and M24C models and should work with other CryoCon models | vendor_doc | README.md:9 |
| A CryoCon simulator is provided and is installed with the simulator extra | vendor_doc | README.md:98-104 |
| The hardware accepts a query only every 100 ms, and queries can be grouped in a single request | vendor_doc | README.md:72-78 |
| CryoCon binds the system properties to *IDN, SYSTEM:NAME, SYSTEM:HWR, SYSTEM:FWR, SYSTEM:LOCKOUT, SYSTEM:REMLED, SYSTEM:DISTC, SYSTEM:DATE and SYSTEM:TIME | upstream_code | cryocon/cryocon.py:340-348 |
| to_date and to_time parse the SYSTEM:DATE and SYSTEM:TIME replies into datetime.date and datetime.time | upstream_code | cryocon/cryocon.py:66-89 |
| channel_member builds the ':INPUT <id>:<name>' command, and Channel binds NAM, TEMP, UNIT, MIN, MAX, VARI, SLOP, OFFS and ALAR to it | upstream_code | cryocon/cryocon.py:105-141 |
| A channel's unit is one of K, C, F or S | upstream_code | cryocon/cryocon.py:18 |
| to_float returns None for the fault '-------', out-of-range '.......' and 'N/A' replies | upstream_code | cryocon/cryocon.py:9-39 |
| control() reads :CONTROL? and sets :CONTROL or :STOP | upstream_code | cryocon/cryocon.py:350-355 |
| to_float_unit drops the last character of a set point reply (its unit character) | upstream_code | cryocon/cryocon.py:42-43 |
| Loop.output_power reads OUTP and is a percentage | upstream_code | cryocon/cryocon.py:164 |

## Limits

None. This package binds no `@write` parameter and no numeric invoke input: the only capability is the catalogue's
read-verb `cap.measure.temperature.v1`, whose optional `probe` and `location` inputs are strings, so there is no
field whose bound the runtime would enforce and no `Limit` to declare. `site-limits.example.json` is therefore not
needed and is not part of the package.

## Scope and safety

The state reads are the system properties (`idn`, `name`, `hw_revision`, `fw_revision`, `lockout`, `led`,
`display_filter_time`, `date`, `time`, `control`) and the readable members of the first configured input channel and
first configured control loop (`channel`, `channel_name`, `temperature`, `temperature_unit`, `minimum`, `maximum`,
`alarm`, `loop`, `loop_setpoint`, `loop_source`, `loop_type`, `loop_output_power`, `loop_range`). The `channel`
and `loop` backend options select another configured entry; otherwise the first one of the upstream dictionaries is
used (`cryocon/cryocon.py:252-253`). The driver exposes one channel and one loop only: channels B to D and the other
loops are read through the same descriptors but are not separate state fields.

`cap.measure.temperature.v1` measures the selected channel and returns it in degrees Celsius. The channel reports
its own unit (`K`, `C`, `F` or `S`, `cryocon/cryocon.py:18`); the action converts `K`, `C` and `F` with the standard
definitions and refuses `S` (sensor units, not a temperature) with `MHS.DEVICE.PRECONDITION_UNMET`. A faulted
channel (`None`, `cryocon/cryocon.py:36-39`) is refused with `MHS.DEVICE.FAULTED`. These are conversions and
preconditions, not device bounds.

The upstream also offers writes. `Channel.name` has a setter, but `Channel.unit`, `minimum`, `maximum` and `alarm`
are readable only (`cryocon/cryocon.py:133-141`); `Loop` writes set point, type, range, gains and manual output
power (`cryocon/cryocon.py:151-185`); and `control(True/False)` or `STOP` switches the controller output
(`cryocon/cryocon.py:350-355`). The loop set point, output power and control writes are heating actuations (R2 or
above under `MHS/spec/04-safety.md`), and the clone's `STOP` request is the only output stop. This package binds
none of them, so it never changes the controller's output and its risk is the class floor of its only capability,
R0.

The upstream simulator (`cryocon/simulator.py`) is a sinstruments TCP device server, not the `CryoCon` object API the
driver uses, and its optional dependencies are not installed. The package fake mirrors the upstream class and
`Channel`/`Loop` descriptors with fixed placeholder values marked `# placeholder` in `fake.py`; those values are test
data, not facts, limits or a recording.

The hardware path was never run: `native.py` opens the upstream class through connio, the gate never imports it, and
`driver.lock.json` `reviewed_by` is null. No claim of hardware testing or human review is made. This package is R0,
so the loader's refusal of an unreviewed model-written hardware backend (R2/R3 only) does not apply and is not
claimed.

Tags: cryocon, temperature, thermometer, controller, read-only
