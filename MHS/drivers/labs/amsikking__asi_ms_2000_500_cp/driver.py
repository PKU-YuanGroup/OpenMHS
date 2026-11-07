"""OpenMHS driver for gh.amsikking/asi_ms_2000_500_cp: the ASI MS-2000-500-CP multi-axis stage controller.

A direct Driver over the upstream serial adaptor ``asi_MS_2000_500_CP:Controller``.  The card proposes a
``SerialDriver`` (family ``serial``, decision ``family-config``), but the upstream builds every command from the
configured axis tuple at run time: ``S X? Y? Z?``, ``W X Y Z``, ``M X=... Y=... Z=...`` and ``J X+`` are assembled by
joining the axes with formatting, so a fixed command table cannot reproduce the lines the controller receives.  This
package is a direct Driver over the upstream class with a ``native.py`` hardware factory (DEVIATION FROM THE CARD,
recorded in RESULT.json).

Scope: one controller configured with the three axes ``('X', 'Y', 'Z')``, the configuration the upstream README
describes (an MS-2000 flat top XY stage with standard lead screws and an LS-50 Z stage with a fine lead screw,
README.md:11).  The upstream adaptor also accepts ``('X', 'Y')`` and ``('Z',)`` (asi_MS_2000_500_CP.py:39); those
configurations are out of scope because this resource serves three named position fields and one three-axis move.

* reads: the X, Y and Z stage positions in micrometres, whether a motor is moving, the PWM intensity of the LED output
  in percent, and the PWM state derived from the TTL input and output modes;
* writes: the PWM intensity (1 to 99 percent, the bound the upstream setter asserts) and the PWM state (off, on, pwm or
  external, the values the upstream setter accepts);
* one extension action, ``x-cap.amsikking.move_stage.v1``: an absolute three-axis target in micrometres handed to the
  upstream ``move_um``.  No catalogue class carries a three-axis linear target in micrometres:
  ``cap.motion.joint_position.v1`` declares radians for every joint, and this stage has linear axes whose travel limits
  the site supplies;
* the e-stop switches the PWM state off, the lowest value of the one output this driver sets.  The clone exposes no
  motion-abort command, so a stage move already commanded is not stopped by the controller through this driver; that
  limitation is stated in facts.md and in RESULT.json.

Travel limits are ``Limit.operator_required``: the clone takes them from the constructor arguments ``axes_min_mm`` and
``axes_max_mm`` (asi_MS_2000_500_CP.py:57-64), and the numbers in its test block are example configurations, not
stated bounds (asi_MS_2000_500_CP.py:443-444).  Until the operator's ``site-limits.json`` supplies the travel, every
move is refused ``MHS.SAFETY.LIMITS_UNSET``.

Every Fact and Limit cites a line of the clone at the pinned commit (5f1f6d2cad545d5ae20359fd01e014dfdd21f11f).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream module's path in the clone.
SOURCE = "asi_MS_2000_500_CP.py"

#: The three axes this package serves, in the order of every position tuple.
AXES = ("X", "Y", "Z")

#: The PWM states the upstream setter accepts (asi_MS_2000_500_CP.py:407).
PWM_STATES = ("off", "on", "pwm", "external")

#: The state each PWM mode programs into the TTL input and output modes (asi_MS_2000_500_CP.py:408-419).
_PWM_TTL_MODES = {
    "off": ("disabled", "low"),
    "on": ("disabled", "high"),
    "pwm": ("disabled", "pwm"),
    "external": ("toggle_ttl_out", "low"),
}

#: The reverse map used to read the PWM state back from the TTL modes.
_TTL_MODES_TO_PWM = {modes: state for state, modes in _PWM_TTL_MODES.items()}

_TRAVEL_NOTE = (
    "the clone takes the travel from the caller's axes_min_mm and axes_max_mm (asi_MS_2000_500_CP.py:57-64); the "
    "numbers in its test block are example configurations, not stated bounds (asi_MS_2000_500_CP.py:443-444), and "
    "the connected stage may be configured differently"
)
_X_REASON = "no text file of the clone states the X travel: " + _TRAVEL_NOTE + "; the site supplies the X envelope"
_Y_REASON = "no text file of the clone states the Y travel: " + _TRAVEL_NOTE + "; the site supplies the Y envelope"
_Z_REASON = "no text file of the clone states the Z travel: " + _TRAVEL_NOTE + "; the site supplies the Z envelope"


class AsiMs2000500Cp(Driver):
    device_id = "asi-ms2000"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "asi_MS_2000_500_CP:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAsiMs2000500Cp"}
    vendor = "Applied Scientific Instrumentation"
    model = "MS-2000-500-CP multi-axis stage controller"
    display_name = "ASI MS-2000-500-CP stage controller (asi_MS_2000_500_CP.Controller)"
    tags = ["stage", "motion", "controller", "asi", "ms-2000", "serial", "pwm"]
    facts = [
        Fact("The clone is a Python device adaptor for the ASI MS-2000-500-CP multi-axis stage controller",
             source="vendor_doc", ref="README.md:2"),
        Fact("The constructor opens a serial port at 115200 baud with a 5 s timeout; for that baud rate DIP switches "
             "4 and 5 must be DOWN", source="upstream_code", ref=f"{SOURCE}:24-28"),
        Fact("The controller must answer 'Version: USB-9.2k'; another version is refused by an assertion",
             source="upstream_code", ref=f"{SOURCE}:32-34"),
        Fact("The constructor accepts only the axis tuples ('X','Y'), ('Z',) and ('X','Y','Z')",
             source="upstream_code", ref=f"{SOURCE}:39"),
        Fact("The lead-screw table gives pitch in mm, encoder resolution in nm and maximum velocity in mm/s for UC, "
             "SC, S, F and XF", source="upstream_code", ref=f"{SOURCE}:43-48"),
        Fact("The travel range is required from the caller: axes_min_mm and axes_max_mm become min_position_um and "
             "max_position_um in micrometres", source="upstream_code", ref=f"{SOURCE}:57-64"),
        Fact("The upstream default encoder resolution is 10 counts per micrometre and can be overridden at "
             "construction", source="upstream_code", ref=f"{SOURCE}:65-69"),
        Fact("_get_position returns the axis positions in micrometres, computed as encoder counts divided by the "
             "configured counts per micrometre", source="upstream_code", ref=f"{SOURCE}:279-298"),
        Fact("move_um takes target positions in micrometres, checks them against the configured min_position_um and "
             "max_position_um, and rounds them to 0.001 um", source="upstream_code", ref=f"{SOURCE}:353-365"),
        Fact("The motor-moving query reports False only when the controller answers 'N'",
             source="upstream_code", ref=f"{SOURCE}:300-309"),
        Fact("get_pwm_intensity reads the LED X value as an integer percent", source="upstream_code",
             ref=f"{SOURCE}:382-390"),
        Fact("set_pwm_intensity accepts an integer from 1 to 99", source="upstream_code", ref=f"{SOURCE}:392-398"),
        Fact("set_pwm_state accepts off, on, pwm and external", source="upstream_code", ref=f"{SOURCE}:404-407"),
        Fact("The TTL input mode code is 0 for disabled and 10 for toggle_ttl_out; the TTL output mode code is 0 "
             "for low, 1 for high and 9 for pwm", source="upstream_code", ref=f"{SOURCE}:113-155"),
        Fact("set_pwm_state programs off as disabled/low, on as disabled/high, pwm as disabled/pwm and external as "
             "toggle_ttl_out/low", source="upstream_code", ref=f"{SOURCE}:408-419"),
        Fact("close turns the PWM output off before it closes the serial port", source="upstream_code",
             ref=f"{SOURCE}:425-431"),
        Fact("The README warns that the test block moves the XY and Z stages and asks to remove samples and the "
             "objective before testing", source="vendor_doc", ref="README.md:5"),
        Fact("The README says MS-2000 controllers come in many variants that can connect different devices, so the "
             "attached hardware is configuration data", source="vendor_doc", ref="README.md:10"),
        Fact("The README says the adaptor was tested with an MS-2000-500-CP at firmware USB-9.2k, an MS-2000 flat top "
             "XY stage with standard lead screws, an LS-50 Z stage with a fine lead screw and an ASI PWM transmitted "
             "light LED", source="vendor_doc", ref="README.md:11"),
    ]
    safe_state = ("PWM output off (the lowest value of the one output this driver sets); the clone exposes no "
                  "motion-abort command, so a stage move already commanded runs to its target")

    # -- reads ----------------------------------------------------------------------------------------------------
    def _positions(self):
        values = self.native._get_position()
        if len(values) != len(AXES):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the controller reported {len(values)} positions for the {len(AXES)} served axes")
        return tuple(float(value) for value in values)

    @read("position_x", unit="um", description="X stage position reported by the controller")
    def position_x(self):
        return self._positions()[0]

    @read("position_y", unit="um", description="Y stage position reported by the controller")
    def position_y(self):
        return self._positions()[1]

    @read("position_z", unit="um", description="Z stage position reported by the controller")
    def position_z(self):
        return self._positions()[2]

    @read("motor_moving", type="boolean", description="True while the controller reports a motor moving")
    def motor_moving(self):
        return bool(self.native._get_motor_moving())

    @read("pwm_intensity", type="integer", unit="%", description="PWM intensity of the LED output")
    def pwm_intensity(self):
        return int(self.native.get_pwm_intensity())

    @read("pwm_state", type="string",
          description="PWM state derived from the controller's TTL input and output modes")
    def pwm_state(self):
        modes = (self.native._get_ttl_in_mode(), self.native._get_ttl_out_mode())
        try:
            return _TTL_MODES_TO_PWM[modes]
        except KeyError:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the TTL modes {modes} are not one of the driver's PWM states") from None

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("pwm_intensity", type="integer", unit="%", description="PWM intensity of the LED output",
           limit=Limit(min=1, max=99, unit="%", source="upstream_code", ref=f"{SOURCE}:397",
                       reason="the upstream setter asserts 1 <= intensity <= 99"))
    def set_pwm_intensity(self, value):
        self.native.set_pwm_intensity(int(value))
        return int(value)

    @write("pwm_state", type="string", description="PWM state of the LED output",
           limit=Limit(allowed=list(PWM_STATES), source="upstream_code", ref=f"{SOURCE}:407",
                       reason="the upstream setter asserts state in ('off', 'on', 'pwm', 'external')"))
    def set_pwm_state(self, value):
        self.native.set_pwm_state(value)
        return value

    # -- action ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.amsikking.move_stage.v1", verb="invoke", risk="R1", exclusive=True,
            description="Move the X, Y and Z stage axes to absolute positions in micrometres and wait for the "
                        "controller to verify the target",
            long_running=True, max_duration_ms=600000,
            input={
                "x_um": Field("number", unit="um", description="Absolute X target in micrometres",
                              limit=Limit.operator_required(_X_REASON)),
                "y_um": Field("number", unit="um", description="Absolute Y target in micrometres",
                              limit=Limit.operator_required(_Y_REASON)),
                "z_um": Field("number", unit="um", description="Absolute Z target in micrometres",
                              limit=Limit.operator_required(_Z_REASON)),
            },
            output={
                "x_um": Field("number", unit="um", description="X position reported after the move"),
                "y_um": Field("number", unit="um", description="Y position reported after the move"),
                "z_um": Field("number", unit="um", description="Z position reported after the move"),
                "reached": Field("boolean", description="True when the controller verified the target"),
            })
    def move_stage(self, x_um, y_um, z_um):
        target = tuple(float(value) for value in (x_um, y_um, z_um))
        minimum = tuple(float(value) for value in self.native.min_position_um)
        maximum = tuple(float(value) for value in self.native.max_position_um)
        for axis, value, low, high in zip(AXES, target, minimum, maximum):
            if not low <= value <= high:
                raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION",
                                   f"{axis} target {value} um is outside the controller's configured travel "
                                   f"[{low}, {high}] um")
        self.check_cancelled()
        self.native.move_um(target, relative=False, block=True)
        self.check_cancelled()
        positions = self._positions()
        return {"x_um": positions[0], "y_um": positions[1], "z_um": positions[2], "reached": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="set_pwm_state")
    def stop(self):
        """Switch the PWM output off; the clone has no motion-abort command to send."""
        self.native.set_pwm_state("off")

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()
