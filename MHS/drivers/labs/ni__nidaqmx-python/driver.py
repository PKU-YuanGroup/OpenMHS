"""OpenMHS driver for gh.ni/nidaqmx-python: one NI-DAQmx analog input voltage task.

A direct Driver (decorated methods) over the upstream class nidaqmx.task._task:Task
(generated/nidaqmx/task/_task.py:64).  The upstream package is the NI-DAQmx API for Python: a ``Task`` is the object
a measurement runs in, a voltage measurement task is a ``Task`` with one AI voltage channel that is created from the
channel collection (examples/analog_in/voltage_sample.py:8-12), and ``read()`` returns the sampled voltages in the
units of the measurement, volts (generated/nidaqmx/task/_task.py:585-593).

* reads: whether the task is done and the name of the virtual channel it acquires from;
* capabilities: ``cap.measure.voltage.v1`` (one DC voltage sample; the class verb is read; the class's optional
  ``channel`` and ``range_v`` inputs are not taken because the channel and its range are fixed when the task is
  created and ``read()`` reads that channel, and an RMS measurement (``dc: false``) needs digitized data and is
  refused ``MHS.DEVICE.PRECONDITION_UNMET``), one extension action that acquires a block of samples (its sample count
  is ``Limit.operator_required``: no line of the clone bounds how many samples one read may request, so
  ``site-limits.example.json`` supplies the site's bound), and the two extension actions that start and stop the
  task;
* the native stop (``Task.stop``) is the e-stop and, as ``stop_task``, the safe-state action.

The card's decision is direct-driver, which this package follows.  The card's candidate classes cap.sensing.read.v1
and cap.actuation.gpio.v1 bind sensor and io resource kinds (``catalog show``); a task that measures a voltage binds
``cap.measure.voltage.v1``, whose resource kinds include ``instrument.dmm``, and that is the catalogue class here.
A ``Task`` exposes no writable scalar of its own (every channel and timing setting is made on a child object when
the task is created), so ``native.py`` configures the task and this driver has no ``cap.device.configure`` parameter.

Every Fact cites a line of the clone at the pinned commit (04211cd36322a1fa2269c7d6edd63b6051daf034).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and the hardware backend was never opened.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The upstream module of the native class, relative to the clone root.
MODULE = "generated/nidaqmx/task/_task.py"
#: The upstream example of a software-timed analog input voltage measurement.
EXAMPLE = "examples/analog_in/voltage_sample.py"
#: The AI channel collection where the voltage channel (and its min/max range) is created.
COLLECTION = "generated/nidaqmx/task/collections/_ai_channel_collection.py"


class NidaqmxVoltageTask(Driver):
    device_id = "nidaqmx-ai"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = "nidaqmx.task._task:Task"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTask"}
    vendor, model = "NI", "NI-DAQmx analog input voltage task"
    display_name = "NI-DAQmx analog input task (voltage measurement)"
    tags = ["daq", "nidaqmx", "ni-daqmx", "analog input", "voltage measurement"]
    facts = [
        Fact("Task is the DAQmx task object a measurement or generation runs in", source="upstream_code",
             ref=f"{MODULE}:64-65"),
        Fact("A voltage measurement task is a Task with one AI voltage channel: add_ai_voltage_chan('Dev1/ai0') "
             "followed by read()", source="upstream_code", ref=f"{EXAMPLE}:8-12"),
        Fact("channel_names lists the virtual channels of the task", source="upstream_code",
             ref=f"{MODULE}:177-181"),
        Fact("is_task_done() indicates whether the measurement or generation completed", source="upstream_code",
             ref=f"{MODULE}:379-392"),
        Fact("read() without a sample count returns one sample: a scalar for one channel, a list for N channels",
             source="upstream_code", ref=f"{MODULE}:543-545"),
        Fact("read() with a sample count returns a list for one channel and a list of lists for N channels",
             source="upstream_code", ref=f"{MODULE}:547-550"),
        Fact("read() scales the samples to the units of the measurement; the channel-creation method sets the units",
             source="upstream_code", ref=f"{MODULE}:585-593"),
        Fact("The voltage range is a channel-creation option with the library defaults min_val=-5.0 and max_val=5.0, "
             "not a range the clone states for a device", source="upstream_code", ref=f"{COLLECTION}:2266-2269"),
        Fact("start() transitions the task to the running state to begin the measurement", source="upstream_code",
             ref=f"{MODULE}:1207-1225"),
        Fact("stop() stops the task and returns it to the state it was in before start()",
             source="upstream_code", ref=f"{MODULE}:1227-1240"),
        Fact("clear() aborts the task if necessary and releases its resources", source="upstream_code",
             ref=f"{MODULE}:325-336"),
        Fact("close is an alias of clear()", source="upstream_code", ref=f"{MODULE}:364-368"),
    ]
    safe_state = "measurement stopped (Task.stop): the task returns to its pre-start state and no longer acquires"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("task_done", type="boolean", description="True while no measurement is in progress in the task")
    def task_done(self):
        return bool(self.native.is_task_done())

    @read("channel_name", type="string", description="Name of the virtual channel the task acquires from")
    def channel_name(self):
        return str(self.native.channel_names[0])

    # -- measurement capabilities ---------------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Read one DC voltage sample from the task's analog input channel",
            input={"dc": Field("boolean",
                               description="True to read the DC (instantaneous) voltage; False (RMS) is not "
                                           "supported by a DAQmx voltage read")})
    def measure_voltage(self, dc: bool = True):
        if not dc:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "this task reads the instantaneous (DC) voltage of its channel; an RMS measurement needs digitized "
                "data and is not supported")
        return {"voltage": float(self.native.read())}

    @action(name="x-cap.ni.sample_voltages.v1",
            description="Acquire a block of voltage samples from the analog input task",
            input={"count": Field(
                "integer", unit="1", description="Number of samples to acquire in one read",
                limit=Limit.operator_required(
                    "no line of the clone bounds the samples one read may request: it depends on the input buffer "
                    "of the device, a task setting, so the site sets the bound of its device"))},
            output={"voltages": Field("array", items="number", unit="V",
                                      description="The acquired voltages in volts, in acquisition order"),
                    "count": Field("integer", unit="1", description="Number of samples returned")})
    def sample_voltages(self, count):
        values = [float(item) for item in self.native.read(int(count))]
        return {"voltages": values, "count": len(values)}

    # -- task control ---------------------------------------------------------------------------------------------
    @action(name="x-cap.ni.start_task.v1",
            description="Start the task (the native start) so it begins the measurement",
            output={"task_done": Field("boolean",
                                       description="True when the task reports that the measurement is complete")})
    def start_task(self):
        self.native.start()
        return {"task_done": bool(self.native.is_task_done())}

    @action(name="x-cap.ni.stop_task.v1", safe_state=True,
            description="Stop the task (the native stop, the safe state); it takes no input",
            output={"task_done": Field("boolean", description="True once the task is stopped")})
    def stop_task(self):
        self.native.stop()
        return {"task_done": bool(self.native.is_task_done())}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop(self):
        """The native stop: the runtime latches first, then Task.stop() ends the measurement."""
        self.native.stop()

    def teardown(self):
        self.native.close()
