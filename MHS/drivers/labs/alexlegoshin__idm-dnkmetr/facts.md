# Facts and limits for gh.alexlegoshin/idm-dnkmetr

Upstream pin: `8f69873e51d2dce10c292feda3a44f745f1af5c1`. Every reference below is a line of that clone.
`upstream_code` covers the Python source and the JSON instrument profiles.

Tags: `power supply`, `dc source`, `gpp-4323`, `gw instek`, `scpi`, `voltage setpoint`, `current limit`, `output enable`.

## Facts

| fact | source | ref |
|---|---|---|
| The GPP-4323 profile maps `set_voltage` to `VSET1:{value:.4f}` and `set_current_limit` to `ISET1:{value:.4f}`. | upstream_code | `instruments/gwinstek_psu_generic.json:21-22` |
| The profile switches the output with `ALLOUTON` (on) and `ALLOUTOFF` (off). | upstream_code | `instruments/gwinstek_psu_generic.json:27-28` |
| The profile measures output voltage with `VOUT1?` and output current with `IOUT1?`. | upstream_code | `instruments/gwinstek_psu_generic.json:24-25` |
| In tracking-series mode the terminals supply 0 to 64 V and only channel 1 is controlled. | upstream_code | `instruments/gwinstek_psu_generic.json:7` |
| The profile declares `max_voltage_v` 64.0. | upstream_code | `instruments/gwinstek_psu_generic.json:30` |
| The profile declares `max_current_limit_a` 3.0. | upstream_code | `instruments/gwinstek_psu_generic.json:31` |
| The profile notes confirm that `VSET1?` and `ISET1?` read back the value that was set. | upstream_code | `instruments/gwinstek_psu_generic.json:7` |
| `VOUT1?` and `IOUT1?` append a unit suffix, and `query_number` extracts the first number. | upstream_code | `drivers.py:29-39` |
| `PowerSupply.set_voltage` writes `set_voltage`; `PowerSupply.set_current_limit` writes `set_current_limit`. | upstream_code | `drivers.py:117-122` |
| `PowerSupply.enable_output` writes `output_on_value` or `output_off_value` according to its state. | upstream_code | `drivers.py:124-127` |
| `PowerSupply.measure_voltage` and `measure_current` query the profile's measure commands. | upstream_code | `drivers.py:129-135` |
| A serial profile with `baud_rate` `auto` detects the speed from the `*IDN?` reply. | upstream_code | `drivers.py:61-72` |
| The profile records the identity `GW INSTEK,GPP-74323,SN:GEZ823770,V1.22`. | upstream_code | `instruments/gwinstek_psu_generic.json:7` |

## Limits

| field | bound | source | ref |
|---|---|---|---|
| `voltage_setpoint` | 0 to 64.0 V | upstream_code | `instruments/gwinstek_psu_generic.json:7` |
| `current_limit` | at most 3.0 A; no lower bound is stated in the clone | upstream_code | `instruments/gwinstek_psu_generic.json:31` |

The current limit has only the sourced maximum.  The clone states no lower bound for `ISET1`; the driver therefore
does not invent one.  The site overlay can narrow both ranges and can add a lower current bound without widening.

## Shape of the package

The card proposed a `ScpiDriver`, but the GPP-4323 writes are prefix commands without a separator
(`VSET1:12.0000`, `ISET1:0.5000`).  The SCPI command table sends one formatted line per command, and the upstream
writes must not gain a space or lose the colon.  The package is therefore a direct `Driver` over
`drivers:PowerSupply`; `driver.lock.json` records the deviation in the RESULT notes.  The hardware factory in
`native.py` opens the upstream class and adds the two readback command names that the profile notes confirm.

## Not covered

The repository also has a `Multimeter` class and a `SwitchController` class.  This package models only the
GPP-4323 power supply; the multimeter profiles (`rigol_dm3068.json`, `akip_2101.json`, `akip_b778.json`) and the
STM32 switch board are not bound here.  The card lists them as entry symbols, and they were verified in the clone,
but one driver package serves one device.  The switch controller has no profile in the clone and its own docstring
says it is not used yet (`drivers.py:147`).
