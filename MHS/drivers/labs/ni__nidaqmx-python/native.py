"""Hardware backend: opens one NI-DAQmx analog input voltage task.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and no human has reviewed it.  The loader refuses the hardware backend of such a package only at R2 and above; this
one is R1, so nothing stops an operator from enabling it: run it first with a person at the device
(MHS/handoff/REVIEW.md, section 1).  The acceptance gate runs the fake backend and never imports this module or the
nidaqmx package, which also needs the proprietary NI-DAQmx driver installed on the host.

``physical_channel`` (required) is the DAQmx physical channel to measure, for example ``"Dev1/ai0"``: the channel
collection creates the virtual channel from it (``generated/nidaqmx/task/collections/_ai_channel_collection.py``
2266-2309).  Every other keyword goes to ``add_ai_voltage_chan``: ``min_val``/``max_val`` (the voltage range the
device is configured for; the library defaults are -5.0 and 5.0 V, ``.../_ai_channel_collection.py``:2266-2269),
``terminal_config`` and ``units``.  A ``Task`` measures the channels it holds, so this driver requires exactly one
voltage channel and refuses a task that ended up with more.
"""


def connect(physical_channel, **options):
    import nidaqmx

    task = nidaqmx.Task()
    try:
        task.ai_channels.add_ai_voltage_chan(physical_channel, **options)
        channels = int(task.number_of_channels)
        if channels != 1:
            raise ValueError(f"this driver measures one voltage at a time, but {physical_channel!r} created "
                             f"{channels} channels")
    except BaseException:
        task.close()
        raise
    return task
