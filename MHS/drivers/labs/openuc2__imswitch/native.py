"""Hardware backend factory: open the upstream ImSwitch ESP32 stage manager.

Used only with ``backend="hardware"`` after a human sets ``reviewed_by`` in ``driver.lock.json``: this package is
model-authored and R2, so the loader refuses the hardware backend until that review.  The gate runs the fake backend
and never imports this module, the ``imswitch`` package or ``uc2rest``.

Options of the backend:

* ``serialport`` (required): the serial device of the UC2 ESP32 controller, passed to the upstream ESP32Manager;
* ``axes`` (required): the axis names the installed stage controls; they must include ``X``, ``Y`` and ``Z``, the
  axes this driver moves and reads (the factory does not guess the axes of a stage);
* ``stage_properties`` (required): a mapping merged into the positioner ``managerProperties``, for the step sizes,
  speeds, homing parameters, soft limits and TMC settings the site has measured (``ESP32StageManager.py:48-215``).
  It must give ``stepsizeX``, ``stepsizeY`` and ``stepsizeZ``, the calibrated µm per step: the upstream defaults them
  to 1 (``ESP32StageManager.py:55-60``), which would make every µm of the MHS envelope one motor step.  It must not
  set ``frameHomeOnStart``: the upstream then starts frame homing in a background thread during construction
  (``ESP32StageManager.py:350-352, 988-992``), whose later steps would start motion again after an MHS stop;
* ``stage_offsets`` (optional): the per-axis stage offsets of the user frame (``ESP32StageManager.py:48-53``);
* ``baudrate``, ``identity``, ``debug``, ``override_firmwarecheck``, ``deviceID`` and ``requireMaster`` (optional):
  passed to the upstream ESP32Manager (``imswitch/imcontrol/model/managers/rs232/ESP32Manager.py:8-52``).

The options are checked before anything is imported or opened.  Constructing the upstream manager is not
side-effect-free: its ``__init__`` switches the motors on (``isEnable``/``enableauto``, both true by default,
``ESP32StageManager.py:211-214``), commands a -1 then +1 relative move on every configured axis and homes on startup
when ``homeOnStart<axis>`` is set (``ESP32StageManager.py:306-319``), and it pushes TMC, hard-limit and joystick
settings to the controller.  The human hardware review must cover those start-up writes and moves; this factory does
not skip the upstream constructor.
"""

_SERVED_AXES = ("X", "Y", "Z")
_STEP_SIZES = ("stepsizeX", "stepsizeY", "stepsizeZ")


class _Signal:
    """The one Qt-style signal the upstream manager uses on its position callback."""

    def emit(self, *_args, **_kwargs):
        return None


class _CommChannel:
    """A null communication channel; the manager stores it and only emits position updates through it."""

    def __init__(self):
        self.sigUpdateMotorPosition = _Signal()


def connect(**options):
    """Build the ESP32 manager and return the upstream stage manager (with a closing lifecycle hook)."""
    serialport = options.pop("serialport")
    axes = list(options.pop("axes"))
    stage_properties = dict(options.pop("stage_properties", {}) or {})
    stage_offsets = dict(options.pop("stage_offsets", {}) or {})
    rs232_properties = {"serialport": serialport}
    for key in ("baudrate", "identity", "debug", "override_firmwarecheck", "deviceID", "requireMaster"):
        if key in options:
            rs232_properties[key] = options.pop(key)
    if options:
        raise TypeError(f"unknown hardware backend options: {sorted(options)}")
    missing_axes = [axis for axis in _SERVED_AXES if axis not in axes]
    if missing_axes:
        raise ValueError(f"axes must include X, Y and Z, which this driver moves and reads (missing {missing_axes})")
    missing_steps = [key for key in _STEP_SIZES if key not in stage_properties]
    if missing_steps:
        raise ValueError(f"stage_properties must give the calibrated step sizes in um per step {missing_steps}: the "
                         "upstream defaults them to 1 (ESP32StageManager.py:55-60)")
    if stage_properties.get("frameHomeOnStart"):
        raise ValueError("frameHomeOnStart is refused: the upstream would start frame homing in a background thread "
                         "during construction (ESP32StageManager.py:350-352, 988-992)")

    from imswitch.imcontrol.model.managers.positioners.ESP32StageManager import ESP32StageManager
    from imswitch.imcontrol.model.managers.rs232.ESP32Manager import ESP32Manager
    from imswitch.imcontrol.model.SetupInfo import PositionerInfo, RS232Info

    rs232_info = RS232Info(managerName="ESP32Manager", managerProperties=rs232_properties)
    esp32_manager = ESP32Manager(rs232_info, "ESP32")
    stage_properties["rs232device"] = "ESP32"
    positioner_info = PositionerInfo(
        analogChannel=None,
        digitalLine=None,
        managerName="ESP32StageManager",
        managerProperties=stage_properties,
        axes=axes,
        forPositioning=True,
        forScanning=False,
        resetOnClose=False,
        stageOffsets=stage_offsets,
    )

    class ManagedStage(ESP32StageManager):
        """The upstream manager plus a close hook for the ESP32 client the manager owns."""

        def __init__(self):
            super().__init__(positioner_info, "UC2ESP32Stage",
                             rs232sManager={"ESP32": esp32_manager}, commChannel=_CommChannel())

        def closeEvent(self):
            try:
                esp32_manager.finalize()
            finally:
                super().closeEvent()

    try:
        return ManagedStage()
    except BaseException:
        esp32_manager.finalize()
        raise
