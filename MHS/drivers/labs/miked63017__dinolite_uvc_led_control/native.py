"""Hardware backend: enumerates Dino-Lite microscopes through the upstream worker.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The package is model-authored and
unreviewed, and it is R1; unlike an R2/R3 package, the loader does not refuse its hardware backend for that reason,
so this module must not claim such a refusal.  The acceptance gate runs the fake backend and never imports this
module or the upstream package.

The upstream worker's ``cleanup()`` is a no-op (dinoliteuvccontrol/dinoliteuvccontrol.py:68-69) and its
``display_shutdown_message()`` exits the interpreter; neither is a device stop.  This factory therefore returns a
small adapter whose ``cleanup()`` switches off the main LED and the FLC of the selected microscope, which is the
driver's e-stop and safe state.  ``ourDevices`` exposes the one microscope instance selected by ``index`` (default
0) because one OpenMHS driver instance serves one device.

Options: ``debug`` (false by default) is the worker's ``args.debug`` flag, and ``index`` selects the enumerated
microscope.  The upstream constructor runs ``lsusb`` and, with more than one Dino-Lite, uses ``udevadm`` to map the
video nodes (dinoliteuvccontrol/dinoliteuvccontrol.py:14-59); both commands must exist on the host.
"""


class _Worker:
    """The upstream worker with one selected device and an illumination-off ``cleanup``."""

    def __init__(self, worker, index=0):
        self._worker = worker
        self._index = int(index)
        devices = worker.ourDevices
        if self._index < 0 or self._index >= len(devices):
            raise ValueError(f"the Dino-Lite backend found {len(devices)} device(s); index {self._index} is out "
                             f"of range")
        self._devices = [devices[self._index]]

    @property
    def ourDevices(self):
        return self._devices

    def cleanup(self):
        for device in self._devices:
            device.led_off()
            device.flc_off()

    def __getattr__(self, name):
        return getattr(self._worker, name)


def connect(debug=False, index=0, **options):
    if options:
        raise TypeError(f"unknown Dino-Lite backend options: {sorted(options)}")
    import dinoliteuvccontrol

    class _Args:
        pass

    args = _Args()
    args.debug = bool(debug)
    worker = dinoliteuvccontrol.DinoLiteUVCControl(args)
    return _Worker(worker, index=index)
