# Facts and tags for gh.akperuht/pydaq

This package binds one device of the upstream repository: the Digimess PN300 programmable power supply
(`Control_lib/instrument_control.py:1637`). The other entry symbols are different instruments (`pynskabox`,
`SR810_30_lockin`, `AVS47`, `Anritsu68367C`) and are not covered by this driver.

Every fact cites its source at commit `edb7584d00891aa0f1a0ef483d12d1d59ab4f794`. The facts are also written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The PN300 is a Digimess programmable power supply controlled over GPIB | upstream_code | Control_lib/instrument_control.py:1637-1639 |
| The instrument is identified with *IDN? on connection | upstream_code | Control_lib/instrument_control.py:1664 |
| reset writes *RST | upstream_code | Control_lib/instrument_control.py:1713-1722 |
| Source A or B is selected with SEL_A or SEL_B | upstream_code | Control_lib/instrument_control.py:1724-1744 |
| The active source is read with SEL? and its reply contains SEL_A or SEL_B | upstream_code | Control_lib/instrument_control.py:1746-1763 |
| The output is switched on with OUT_ON and off with OUT_OFF | upstream_code | Control_lib/instrument_control.py:1766-1797 |
| The output state is read with OUT? | upstream_code | Control_lib/instrument_control.py:1766-1797 |
| The operating mode is selected with OPER_IND, OPER_TRAC or OPER_PAR and read with OPER? | upstream_code | Control_lib/instrument_control.py:1799-1846 |
| The source is constant current with CONT_CC or constant voltage with CONT_CV, read with CONT? | upstream_code | Control_lib/instrument_control.py:1849-1890 |
| The voltage setpoint is written as VSET <volts> and read with VSET? | upstream_code | Control_lib/instrument_control.py:1892-1911 |
| The current setpoint is written as ISET <amperes> and read with ISET? | upstream_code | Control_lib/instrument_control.py:1913-1947 |
| The measured output voltage and current are read with VOUT? and IOUT? | upstream_code | Control_lib/instrument_control.py:1968-1996 |
| The protection mode is read with PROT? and the reply names LIMITING or CUT-OUT | upstream_code | Control_lib/instrument_control.py:2020-2035 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| output | OUT_ON / OUT_OFF | allowed {ON, OFF} | Control_lib/instrument_control.py:1766-1797 |
| source | SEL_A / SEL_B | allowed {A, B} | Control_lib/instrument_control.py:1724-1744 |
| operating_mode | OPER_IND / OPER_TRAC / OPER_PAR | allowed {IND, TRAC, PAR} | Control_lib/instrument_control.py:1799-1824 |
| source_type | CONT_CC / CONT_CV | allowed {CC, CV} | Control_lib/instrument_control.py:1849-1871 |
| voltage (V) | VSET | operator_required: the clone states the unit but no voltage range | `driver.py` reason |
| current (A) | ISET | operator_required: the clone gives only mode-dependent ranges with non-numeric glyphs | `driver.py` reason |

`site-limits.example.json` is an illustrative deployment overlay, not a device fact. It supplies the two
`operator_required` bounds so the conformance suite can exercise the setpoint writes; a real site replaces it with
bounds validated for its load. Without that overlay every call that sets voltage or current is refused with
`MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop writes `OUT_OFF`, the upstream class's output-disable command (`Control_lib/instrument_control.py:1792`),
and the `x-cap.akperuht.output_off.v1` action writes the same command as the declared safe state. The driver declares
R2 because a power supply delivers energy into an unknown load; the package is model-authored and unreviewed and its
hardware backend must not be used until a human signs `reviewed_by`. No hardware run was performed.

Tags: power supply, dc source, pn300, scpi, gpib
