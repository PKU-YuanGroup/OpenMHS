# Facts and tags for gh.little-did-i-know/scpi-instrument-control

Every fact cites its source at commit `e252a04dd33d57a543f5a65280cadfbaa634a4a5`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package controls generic SCPI-99 power supplies and Siglent SPD series models | upstream_code | scpi_control/power_supply.py:3-4 |
| PowerSupply is the power-supply entry class and creates its outputs after connect | upstream_code | scpi_control/power_supply.py:35 |
| The SPD3303X and SPD3303X-E outputs 1 and 2 are rated 30 V and 3 A | upstream_code | scpi_control/psu_models.py:77-78 |
| A voltage setpoint is accepted only when 0 <= volts <= max_voltage | upstream_code | scpi_control/power_supply_output.py:76 |
| A current setpoint is accepted only when 0 <= amps <= max_current | upstream_code | scpi_control/power_supply_output.py:116 |
| The Siglent setpoint commands are CH{ch}:VOLT and CH{ch}:CURR | upstream_code | scpi_control/psu_scpi_commands.py:96-99 |
| A voltage setting is sent as 'CH1:VOLT 5.0' | upstream_code | scpi_control/psu_scpi_commands.py:183 |
| The Siglent measurement commands are MEASure:VOLTage? CH{ch} and MEASure:CURRent? CH{ch} | upstream_code | scpi_control/psu_scpi_commands.py:103-105 |
| The Siglent output command is OUTPut CH{ch},{ON|OFF} | upstream_code | scpi_control/psu_scpi_commands.py:107 |
| Tracking is sent as OUTP:TRACK {mode} with the numeric wire values 0 independent, 1 series, 2 parallel | upstream_code | scpi_control/psu_scpi_commands.py:140-151 |
| The identity example is 'Siglent Technologies,SPD3303X,SPD3XXXXXXXXXXX,V1.01' and *IDN? returns it | upstream_code | scpi_control/power_supply.py:196-205 |
| SYST:ERR? reads the error queue | upstream_code | scpi_control/power_supply.py:219-225 |
| reset() writes *RST and turns off all outputs | upstream_code | scpi_control/power_supply.py:207-213 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| voltage (V) | CH1:VOLT | 0 to 30.0 | scpi_control/psu_models.py:77 |
| current (A) | CH1:CURR | 0 to 3.0 | scpi_control/psu_models.py:77 |
| tracking | OUTP:TRACK | one of 0, 1, 2 | scpi_control/psu_scpi_commands.py:151 |

The voltage and current bounds are those of the SPD3303X/SPD3303X-E output 1. The upstream code also enforces the
lower bound 0 at `scpi_control/power_supply_output.py:76` (voltage) and `:116` (current); neither bound comes from the
generic fallback profile, which the upstream comments call typical rather than measured
(`scpi_control/psu_models.py:267-275`).

Safety: the e-stop writes `OUTPut CH1,OFF` and `OUTPut CH2,OFF`. It does not switch output 3, whose setpoints and
measurement path are not available over SCPI (output 3 is an output command only, but this driver does not configure
it). The SPD3303X command form is `scpi_control/psu_scpi_commands.py:107`; `power_supply.py:227-243` shows the
upstream's own all-outputs-off safety method, which this driver mirrors with the wire commands. R1 needs no
independent hardware stop.

What is not covered: the waveform, timer and remote-sense subsystems; output-state read-back (the SPD3303X status
word is bit-encoded and this text command map cannot decode it); channels 2 and 3; the other instrument classes in
the repository (`Oscilloscope`, `FunctionGenerator`).

Tags: power supply, psu, siglent, spd3303x, scpi
