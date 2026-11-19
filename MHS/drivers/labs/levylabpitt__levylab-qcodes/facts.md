# Facts and tags for gh.levylabpitt/levylab-qcodes

Every fact cites its source at commit `d001dc1a34e9ec4ea7f7effdfae0da0450e2c5f3`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MCLockin is the LevyLab multichannel lock-in driver and talks to the instrument over ZMQ | upstream_code | levylabinst/MCLockin.py:16-22 |
| The constructor takes the ZMQ server address and a channel configuration mapping each label to a lead number | upstream_code | levylabinst/MCLockin.py:23-36 |
| Each configured label adds measurement parameters X, Y, R, Theta and Mean, named <label>_<measurement> | upstream_code | levylabinst/MCLockin.py:79-85 |
| A measurement is read from the getResults dictionary under the key AI<lead>.Ref<ref>.<measurement> | upstream_code | levylabinst/MCLockin.py:210-215 |
| get_idn reports vendor LevyLab, model MC Lock-in, serial None and firmware v2.15.4.4 | upstream_code | levylabinst/MCLockin.py:177-186 |
| The lock-in state parameter allows start, start sweep and stop | upstream_code | levylabinst/MCLockin.py:87-92 |
| _set_state sends setState and _get_state returns the result of getStatus | upstream_code | levylabinst/MCLockin.py:217-223 |
| The upstream sweep routine treats the getStatus result values idle and sweeping as its state machine | upstream_code | levylabinst/MCLockin.py:258-270 |
| The ZMQInstrument constructor allows 5 s for a response by default | upstream_code | levylabinst/ZMQInstrument.py:42-52 |

Limits: this package serves no writable parameter and no numeric action input, so it declares no `Limit`. The
measurement field names are strings whose syntax is the upstream QCoDeS parameter name `<label>_<measurement>`
(levylabinst/MCLockin.py:79-85); an unknown or unconfigured name is refused before any native call.
All requested names are validated before the first measurement query, including an invalid name after a valid one.
The identity is the static dictionary in `get_idn`, not an identification query to the connected instrument.

Safety: the served interface is read-only. It exposes the native measurement path and the native status read; it
does not serve the upstream AO configuration setters (`_set_amplitude`, `_set_dc`, `_set_freq`, `_set_phase`,
`_set_func`), the state setter (`_set_state`) or the `sweep1d` routine, all of which actuate the lock-in or its sweep
engine. The driver is therefore R0 and declares no native stop; it commands nothing that could be left energised.
The device's own outputs are outside this served interface and must be handled by the experiment supervisor.

Tags: lock-in, multichannel, zmq, measurement, sensor
