# Facts and tags for gh.josuablejeru/labmastro

Every fact cites the pinned clone at commit `86db05e8dd4e37d66667e18e4d8e2fadbb864b18`. `upstream_code` refs name
`path/in/clone:LINE` or a bounded range. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

Tags: `power-supply`, `modbus`, `modbus-rtu`, `tag-bridge`, `hanmatek`.

## Facts

| fact | source | ref |
|---|---|---|
| HanmatekHmInstrument opens the port in Modbus RTU mode with slave address 1 by default, at 9600 baud, 8 data bits, no parity, 1 stop bit and a 1 s timeout. | upstream_code | labmastro/power_supply/hanmatek/hm/instrument.py:7-28 |
| get_voltage reads holding register 0x0010 with two decimals (function code 3); get_current reads 0x0011 with three decimals and divides that result by 1000 again before returning it. | upstream_code | labmastro/power_supply/hanmatek/hm/control.py:12-20 |
| set_voltage writes int(voltage * 100) to register 0x0030 and set_current writes int(current * 1000) to 0x0031, both with function code 6. | upstream_code | labmastro/power_supply/hanmatek/hm/control.py:30-42 |
| set_over_voltage_protection writes int(volts * 100) to 0x0020 and set_over_current_protection writes int(amps * 1000) to 0x0021 with function code 6. | upstream_code | labmastro/power_supply/hanmatek/hm/control.py:44-54 |
| power_on and power_off write 1 and 0 to register 0x0001 and then return get_power_status, which reads 0x0001 and reports False only for 0. | upstream_code | labmastro/power_supply/hanmatek/hm/control.py:66-82 |
| get_power combines registers 0x0012 and 0x0013 as (high_power < 16) + low_power, a comparison rather than a shift. | upstream_code | labmastro/power_supply/hanmatek/hm/control.py:22-28 |
| set_over_power_protection splits int(watts * 1000) into a high word for 0x0022 and a low word for 0x0023 and writes them with two separate function code 6 requests. | upstream_code | labmastro/power_supply/hanmatek/hm/control.py:56-64 |

## Register points (tag_config)

| point | register | codec | access | ref |
|---|---|---|---|---|
| output | 0x0001 | 0/1 as a boolean (strict) | read-write | control.py:66-82 |
| voltage_display | 0x0010 | uint16, 2 decimals | read | control.py:14 |
| current_display | 0x0011 | uint16, 3 decimals | read | control.py:19 |
| voltage_set | 0x0030 | uint16, 2 decimals | write | control.py:32-33 |
| current_set | 0x0031 | uint16, 3 decimals | write | control.py:38-41 |
| over_voltage_set | 0x0020 | uint16, 2 decimals | write | control.py:46-47 |
| over_current_set | 0x0021 | uint16, 3 decimals | write | control.py:52-53 |

Decimals are those the upstream passes to `read_register` or multiplies by before `write_register`. The package
reads 0x0011 with its three decimals only and does not reproduce the extra division of `get_current`; the
displayed current in amperes therefore differs from the upstream method's return value by a factor of 1000.

## Scope and what is not covered

- The setpoint and protection registers are only written upstream; no line shows that they are readable, so the
  state reports the last value this endpoint wrote and the supply acknowledged (the Modbus function 6 echo), not a
  read-back. A value that is not a multiple of the register resolution is refused, never rounded.
- NOT COVERED: power display (0x0012/0x0013), because the pinned code combines the two words with a comparison and
  the intended encoding is not established; over-power protection (0x0022/0x0023), because the upstream splits one
  value over two separate non-atomic writes. Voltage times current gives the power from the covered reads.
- The output range of the HM model is not in the clone (the class is meant for every HM model, `instrument.py:1`), so
  every setpoint and protection limit is `Limit.operator_required`.
- The stop is the output-off write of register 0x0001 confirmed by reading 0x0001 back. It does not change setpoints
  and it proves what the supply reports, not that a connected load is de-energized.
- Residual hazard: `output_on` energises the load at the setpoints the supply holds at that moment (front panel, an
  earlier session or this endpoint). They cannot be read (write-only registers upstream) and the operator limits bound
  only the values this endpoint writes, so the operator sets and verifies the setpoints on the supply before enabling
  the output. A setpoint write whose outcome is unknown keeps commands, including `output_on`, refused until the
  setpoint is written again and acknowledged.
- An `output_on` or `output_off` whose read-back does not confirm the write is an unknown outcome: further writes and
  commands wait for a confirmed stop.
- Licence: `pyproject.toml` line 6 says MIT while the repository's `LICENSE` file is the GPL version 3; the card and
  lock record GPL-3.0. The owner decides before publication.
