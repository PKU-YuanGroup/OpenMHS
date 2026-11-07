# Facts and tags for gh.ni/nidaqmx-python

Every fact cites its source at commit `04211cd36322a1fa2269c7d6edd63b6051daf034`: `upstream_code` (a code or a
docstring line of the clone) or `vendor_doc` (a text file of the clone such as README.md or docs/*.md).  The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

The package drives one NI-DAQmx analog input voltage task.  The upstream repository is a driver pack for the whole
NI-DAQmx API; recon picked the central object, `nidaqmx.task._task:Task` (the card's first entry symbol), and the
voltage measurement use the upstream example shows.  The card's candidate classes cap.sensing.read.v1 and
cap.actuation.gpio.v1 bind sensor and io resource kinds; a task that measures a voltage binds
`cap.measure.voltage.v1`, whose resource kinds include `instrument.dmm`, so the package is an `instrument.dmm`
resource.

| fact | source | ref |
|---|---|---|
| Task is the DAQmx task object a measurement or generation runs in | upstream_code | generated/nidaqmx/task/_task.py:64-65 |
| A voltage measurement task is a Task with one AI voltage channel: add_ai_voltage_chan('Dev1/ai0') followed by read() | upstream_code | examples/analog_in/voltage_sample.py:8-12 |
| channel_names lists the virtual channels of the task | upstream_code | generated/nidaqmx/task/_task.py:177-181 |
| is_task_done() indicates whether the measurement or generation completed | upstream_code | generated/nidaqmx/task/_task.py:379-392 |
| read() without a sample count returns one sample: a scalar for one channel, a list for N channels | upstream_code | generated/nidaqmx/task/_task.py:543-545 |
| read() with a sample count returns a list for one channel and a list of lists for N channels | upstream_code | generated/nidaqmx/task/_task.py:547-550 |
| read() scales the samples to the units of the measurement; the channel-creation method sets the units | upstream_code | generated/nidaqmx/task/_task.py:585-593 |
| The voltage range is a channel-creation option with the library defaults min_val=-5.0 and max_val=5.0, not a range the clone states for a device | upstream_code | generated/nidaqmx/task/collections/_ai_channel_collection.py:2266-2269 |
| start() transitions the task to the running state to begin the measurement | upstream_code | generated/nidaqmx/task/_task.py:1207-1225 |
| stop() stops the task and returns it to the state it was in before start() | upstream_code | generated/nidaqmx/task/_task.py:1227-1240 |
| clear() aborts the task if necessary and releases its resources | upstream_code | generated/nidaqmx/task/_task.py:325-336 |
| close is an alias of clear() | upstream_code | generated/nidaqmx/task/_task.py:364-368 |

Limits: the sample count of `x-cap.ni.sample_voltages.v1` is `Limit.operator_required`.  No line of the clone bounds
how many samples one read may request: it depends on the input buffer of the device, a task setting, and on how the
task was configured; a library default is not a bound of the device.  The site supplies the bound of its device in
`site-limits.json`; `site-limits.example.json` is an example overlay, not a statement about any device.

Safety: the e-stop and the safe-state action `x-cap.ni.stop_task.v1` both call the native `stop()`
(generated/nidaqmx/task/_task.py:1227-1240), which stops the measurement and returns the task to its pre-start state.
The device of this package only acquires samples and sets no output, so stopping the task is its safe state.  No line
of the clone documents an independent hardware e-stop and the card's risk floor is R1, so `estop_physical_ref` is not
set (SAFE-045's R2+ rule does not apply).

No `cap.device.configure.v1` parameter is declared: a `Task` exposes no writable scalar of its own; every channel and
timing setting is made on a child object when the task is created, which `native.py` does from the operator's options.

Tags: daq, nidaqmx, ni-daqmx, analog input, voltage measurement
