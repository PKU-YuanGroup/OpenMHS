"""Hardware backend: builds the upstream PyMoDAQ DAQ_NIDAQmx_Actuator plugin for an analog output task.

The gate never imports this module and no hardware run was made.  The upstream plugin owns a Qt/PyMoDAQ settings
tree; the factory selects the Analog_Output task type, adds the requested AO channel and builds the task for it.
Options: ``device`` is the NI-DAQmx device name (for example a name of the form DevN) and ``channel`` is the
physical AO channel name reported by the card; ``options`` are passed to the upstream constructor.
"""


def connect(device=None, channel=None, **options):
    from pymodaq_plugins_daqmx.hardware.national_instruments.daq_NIDAQmx import DAQ_NIDAQmx_Actuator

    native = DAQ_NIDAQmx_Actuator(**options)
    if device is not None:
        native.device = device
    if channel is not None:
        group = native.settings.child("ao_channels")
        group.addNew(channel)
        group.child(channel).child("ao_type").setValue("Voltage")
    native.settings.child("NIDAQ_type").setValue("Analog_Output")
    native.update_task()
    return native
