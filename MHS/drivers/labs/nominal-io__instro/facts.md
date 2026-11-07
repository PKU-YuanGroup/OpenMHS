# Facts and tags for gh.nominal-io/instro

Every fact cites its source at commit `311aee4ae227205b773e6cc9c523df9ea7e7ce03` from the clone root as it is.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver,
not from this page.

| fact | source | ref |
|---|---|---|
| `set_voltage` writes `CH{channel}:VOLT` with three decimals and `get_voltage` queries `MEAS:VOLT?` for that channel | upstream_code | instro/psu/drivers/siglent_spd3303.py:20-26 |
| `set_current_limit` writes `CH{channel}:CURR` with three decimals and `get_current` queries `MEAS:CURR?` for that channel | upstream_code | instro/psu/drivers/siglent_spd3303.py:28-34 |
| `get_voltage_setpoint` and `get_current_setpoint` query `CH{channel}:VOLT?` and `CH{channel}:CURR?` | upstream_code | instro/psu/drivers/siglent_spd3303.py:36-42 |
| `output_enable` writes `OUTP CH{channel},ON` or `OUTP CH{channel},OFF` | upstream_code | instro/psu/drivers/siglent_spd3303.py:44-47 |
| `get_output_status` returns the `ch{channel}_enable` entry of the `query_status()` dictionary | upstream_code | instro/psu/drivers/siglent_spd3303.py:49-51 |
| `query_status` decodes the `SYST:STAT?` status word with masks 1 and 2 for the channel CC/CV mode, bits 2-3 for the PSU tracking mode and masks 16 and 32 for the channel enables | upstream_code | instro/psu/drivers/siglent_spd3303.py:151-158 |
| Only channels 1 and 2 are programmable; channel 3 is selectable via the front panel and does not expose a programming interface | upstream_code | instro/psu/drivers/siglent_spd3303.py:189-197 |
| The PSU driver contract documents voltages in volts and currents in amperes | upstream_code | instro/psu/psu.py:36-53 |
| `SiglentSPD3303` composes a `VisaDriver` in `__init__` and `open()`/`close()` open and close that transport | upstream_code | instro/psu/drivers/siglent_spd3303.py:11-18 |
| Every checked write and query reads `SYST:ERR?` afterwards and raises `RuntimeError` on a non-zero error reply | upstream_code | instro/psu/drivers/siglent_spd3303.py:160-174 |

Limits: the two voltage set points and the two current set points are `Limit.operator_required`. The clone
states no numeric output range for the SPD3303 series: the upstream class writes the value with three decimals
and checks the instrument error queue, and the clone names no rating for the installed model.
`site-limits.example.json` is an example overlay, not a statement about any unit; an operator replaces it with
the nameplate range of the installed unit. Until an overlay supplies a bound, each of those writes is refused
`MHS.SAFETY.LIMITS_UNSET`.

Mock path: the card names the upstream PSU simulator (`instro/psu/scpi_sim_server.py`), but that simulator is a
socket SCPI server, not an object with the upstream driver's methods. The fake in `fake.py` is therefore an
in-memory stand-in with the exact public method shapes of `SiglentSPD3303`; its values are placeholders. The
upstream simulator server was not started and no recording was made.

Safety: the output is the hazard this driver controls. The e-stop switches both channel outputs off through
`output_enable(False, channel)`, and the declared safe state is the same native command;
`x-cap.nominal-io.output_off.v1` is the `safe_state=True` action that does it for both channels. The clone
documents no independent hardware emergency stop for this instrument, so `estop_physical_ref` is not set and
the package does not claim one. The device is R1, so the loader does not refuse the hardware backend of this
model-authored, unreviewed package; a human must review it before anyone passes `--allow-hardware`.

Tags: power-supply, dc-source, scpi, visa, two-channel
