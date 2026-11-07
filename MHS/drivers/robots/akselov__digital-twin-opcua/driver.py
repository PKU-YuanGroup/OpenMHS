"""OpenMHS driver for gh.akselov/digital-twin-opcua: a KUKA KR C4 controller reached through KUKAVARPROXY.

A direct Driver over ``KUKAVARPROXY_communication:KUKA``.  The upstream class is a small KVP client: ``read(var)``
and ``write(var, value)`` send the KukaVarProxy frame over TCP port 7000, and the thesis scripts use it to read
``$AXIS_ACT`` and to write ``TARGET_AXIS`` for the KRL program that loops ``PTP TARGET_AXIS``
(opcua-control/opcua-control-server.py:187 and opcua-control/opcua_ptp_movement.src:27-31).  The driver therefore:

* reads the six axis values from ``$AXIS_ACT`` and parses the E6AXIS text the same way the upstream reader does
  (xml/KUKAVARPROXY_communication.py:121-127);
* reads the motor velocity, torque and current arrays with the system variables the upstream plotters use
  (``$VEL_AXIS_ACT``, ``$TORQUE_AXIS_ACT``, ``$CURR_ACT``);
* exposes ``x-cap.akselov.joint_position.v1``: it writes ``TARGET_AXIS`` as the E6AXIS string the upstream control
  server writes (opcua-control/opcua-control-server.py:187) and returns the axis values read back afterwards;
* declares ``$STOPMESS``/``IR_STOPM`` in the KRL program as the independent stop
  (opcua-control/opcua_ptp_movement.src:9-10); the ``@estop`` method performs the only stop the KVP client can do,
  writing the last read axis position to ``TARGET_AXIS`` so the KRL loop's next target is where the arm was.

The catalogue's ``cap.motion.joint_position.v1`` fixes its input in radians, while the clone carries the native
KUKA axis values (``$AXIS_ACT`` / ``TARGET_AXIS``) and states no unit or joint range.  The package therefore uses
the extension id ``x-cap.akselov.joint_position.v1`` in the native unit and fills it from the site overlay; the
catalogue request is recorded in RESULT.json.

The clone states no joint travel range, so the numeric input is ``Limit.operator_required``: the runtime refuses
every move with ``MHS.SAFETY.LIMITS_UNSET`` until the operator supplies the travel envelope in ``site-limits.json``.

This package is model-authored and unreviewed.  It is checked on the fake backend only, it claims no hardware run
and no MHS-Device level, and the loader refuses its R2 hardware backend until a human sets ``reviewed_by`` in
driver.lock.json.  The pinned clone commit is adc30f46466595a278f87f23a304a3630deca4da.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

CLONE = "xml/KUKAVARPROXY_communication.py"
CONTROL = "opcua-control/opcua-control-server.py"
KRL = "opcua-control/opcua_ptp_movement.src"
VELOCITY_SERVER = "opcua-server/opcua-server-velocity.py"
TORQUE_SERVER = "opcua-server/opcua-server-torque.py"
CURRENT_SERVER = "opcua-server/opcua-server-current.py"
TEMPERATURE_SERVER = "opcua-server/opcua-server-temperature.py"

AXIS_COUNT = 6
AXIS_NAMES = [f"A{number}" for number in range(1, AXIS_COUNT + 1)]
NATIVE_AXIS = "1"
AXIS_REASON = ("the clone states no travel range for the KUKA axes: it reads and writes the native $AXIS_ACT / "
               "TARGET_AXIS values without a limit; the site supplies the travel envelope of the installed robot")
READ_AXIS_DESCRIPTION = ("A1 to A6 values read from $AXIS_ACT, in the native KUKA axis values; the clone states "
                         "no unit")


class KukaKvp(Driver):
    device_id = "kuka-kr16-2"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "KUKAVARPROXY_communication:KUKA"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKUKA"}
    vendor, model = "KUKA", "KR 16-2 on a KR C4 controller (KUKAVARPROXY)"
    display_name = "KUKA KR 16-2 via KUKAVARPROXY (KUKAVARPROXY_communication.KUKA)"
    tags = ["kuka", "kuka kr 16-2", "kr c4", "kukavarproxy", "kvp", "robot arm", "six axes"]
    facts = [
        Fact("The module is a KUKAVARPROXY communication module used by opcua-server-xml.py for a KUKA KR C4 "
             "robot controller", source="upstream_code", ref=f"{CLONE}:2-5"),
        Fact("KUKA is the module's device class and its constructor connects the module socket to TCP port 7000, "
             "where KukaVarProxy listens", source="upstream_code", ref=f"{CLONE}:22-28"),
        Fact("The module builds the KukaVarProxy frame from a message id, a message length, a read/write byte, a "
             "variable name and an optional value", source="upstream_code", ref=f"{CLONE}:32-59"),
        Fact("read(var) reads one KRL variable and write(var, val) writes one through the same KVP socket",
             source="upstream_code", ref=f"{CLONE}:79-91"),
        Fact("The upstream reader reads $AXIS_ACT, removes the commas and splits the text on spaces, taking the "
             "value token after each axis name", source="upstream_code", ref=f"{CLONE}:121-127"),
        Fact("The upstream control server writes TARGET_AXIS as an E6AXIS string with A1 to A6 entries",
             source="upstream_code", ref=f"{CONTROL}:187"),
        Fact("The KRL program initializes TARGET_AXIS from $AXIS_ACT and then loops PTP to TARGET_AXIS",
             source="upstream_code", ref=f"{KRL}:27-31"),
        Fact("The KRL program declares a global interrupt that calls the controller's IR_STOPM when $STOPMESS is "
             "true", source="upstream_code", ref=f"{KRL}:9-10"),
        Fact("The upstream velocity plotter reads each axis with $VEL_AXIS_ACT [n]",
             source="upstream_code", ref=f"{VELOCITY_SERVER}:198-203"),
        Fact("The upstream torque plotter reads each axis with $TORQUE_AXIS_ACT [n]",
             source="upstream_code", ref=f"{TORQUE_SERVER}:198-203"),
        Fact("The upstream current plotter reads each axis with $CURR_ACT [n]",
             source="upstream_code", ref=f"{CURRENT_SERVER}:198-203"),
        Fact("The upstream temperature plotter reads each axis with $MOT_TEMP [n] and subtracts an offset supplied "
             "to that script", source="upstream_code", ref=f"{TEMPERATURE_SERVER}:212-217"),
        Fact("The upstream error handler closes the socket and raises SystemExit on a network or parsing error; the "
             "driver converts that process-level exit into a normal failed receipt", source="upstream_code",
             ref=f"{CLONE}:98-108"),
        Fact("The KUKA KR 16-2 object XML defines the six axis variables A1 to A6 and an IP property",
             source="upstream_code", ref="xml/KUKA_KR16_2_object.xml:64-140"),
    ]
    safe_state = ("KRL target set to the last read axis position so the loop's next PTP target is where the arm was; "
                  "the controller's $STOPMESS interrupt runs IR_STOPM independently of this driver")
    #: The KRL program's controller-side stop interrupt: $STOPMESS true runs IR_STOPM (SAFE-045 for R2 hardware).
    estop_physical_ref = f"{KRL}:9-10"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("joint_positions", type="array", items="number", length=AXIS_COUNT, unit=NATIVE_AXIS,
          description=READ_AXIS_DESCRIPTION)
    def get_joint_positions(self):
        return self._read_axes()

    @read("motor_velocities", type="array", items="number", length=AXIS_COUNT, unit=NATIVE_AXIS,
          description="A1 to A6 values read from $VEL_AXIS_ACT, in the native KUKA values; the clone states no unit")
    def get_motor_velocities(self):
        return self._read_axis_values("$VEL_AXIS_ACT")

    @read("motor_torques", type="array", items="number", length=AXIS_COUNT, unit=NATIVE_AXIS,
          description="A1 to A6 values read from $TORQUE_AXIS_ACT, in the native KUKA values; the clone states no "
                      "unit")
    def get_motor_torques(self):
        return self._read_axis_values("$TORQUE_AXIS_ACT")

    @read("motor_currents", type="array", items="number", length=AXIS_COUNT, unit=NATIVE_AXIS,
          description="A1 to A6 values read from $CURR_ACT, in the native KUKA values; the clone states no unit")
    def get_motor_currents(self):
        return self._read_axis_values("$CURR_ACT")

    # -- motion ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.akselov.joint_position.v1",
            description="Write the six axis values to TARGET_AXIS as an E6AXIS string; the KRL program moves to it",
            input={"joint_positions": Field(
                "array", items="number", length=AXIS_COUNT, unit=NATIVE_AXIS,
                description="Target A1 to A6 values in the native KUKA axis values; the clone states no unit",
                limit=Limit.operator_required(AXIS_REASON))},
            output={
                "joint_positions": Field(
                    "array", items="number", length=AXIS_COUNT, unit=NATIVE_AXIS,
                    description="A1 to A6 values read from $AXIS_ACT after the TARGET_AXIS write"),
                "target_axis_reply": Field(
                    "string", description="Reply text the KukaVarProxy server returned for the TARGET_AXIS write"),
            })
    def move_joints(self, joint_positions):
        values = [float(value) for value in joint_positions]
        message = self._axis_message(values)
        reply = self._call_native("write", "TARGET_AXIS", message)
        if not isinstance(reply, str):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the KUKAVARPROXY write of TARGET_AXIS returned no reply text")
        try:
            actual = self._read_axes()
        except Exception as exc:  # noqa: BLE001 - the write was sent before the read failed
            raise OutcomeUnknown(
                "TARGET_AXIS was written, but $AXIS_ACT could not be read back: the arm may move to the target"
            ) from exc
        return {"joint_positions": actual, "target_axis_reply": reply}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="write")
    def stop(self):
        """Write the current axis position to TARGET_AXIS and keep the KVP socket open.

        The clone exposes no stop variable, so this is the only hold the KVP client can request.  The independent
        stop is the controller's $STOPMESS interrupt (IR_STOPM), declared in estop_physical_ref.
        """
        axes = self._read_axes()
        self._call_native("write", "TARGET_AXIS", self._axis_message(axes))

    def teardown(self):
        self._call_native("disconnect")

    # -- helpers --------------------------------------------------------------------------------------------------
    def _call_native(self, method, *args):
        """Call one upstream method and turn its process-level abort into a typed failure.

        The upstream ``error_list`` closes the socket and raises SystemExit
        (xml/KUKAVARPROXY_communication.py:98-108); a normal exception is re-raised unchanged so the runtime reports
        it as a failed receipt.
        """
        call = getattr(self.native, method)
        try:
            return call(*args)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:
            if isinstance(exc, Exception):
                raise
            raise DriverFailed(
                "MHS.DEVICE.FAULTED",
                f"the upstream {method} aborted the process through its error handler",
            ) from exc

    def _read_axes(self):
        text = self._call_native("read", "$AXIS_ACT")
        if not isinstance(text, str):
            raise DriverFailed("MHS.DEVICE.FAULTED", "$AXIS_ACT did not return an E6AXIS text")
        tokens = text.replace(",", "").split()
        if tokens:
            tokens[-1] = tokens[-1].rstrip("}")
        values = []
        for index, name in enumerate(AXIS_NAMES):
            value_at = 2 + 2 * index
            if value_at >= len(tokens) or tokens[1 + 2 * index] != name:
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"$AXIS_ACT is not the expected E6AXIS text with A1 to A6: {text!r}",
                )
            try:
                values.append(float(tokens[value_at]))
            except ValueError as exc:
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"$AXIS_ACT has a non-numeric value for {name}: {tokens[value_at]!r}",
                ) from exc
        return values

    def _read_axis_values(self, variable):
        values = []
        for number in range(1, AXIS_COUNT + 1):
            text = self._call_native("read", f"{variable} [{number}]")
            try:
                values.append(float(str(text).strip()))
            except ValueError as exc:
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"{variable} [{number}] returned a non-numeric value: {text!r}",
                ) from exc
        return values

    @staticmethod
    def _axis_message(values):
        """The E6AXIS text the upstream control server writes (opcua-control/opcua-control-server.py:187)."""
        return "{E6AXIS: " + ", ".join(
            f"{name} {value}" for name, value in zip(AXIS_NAMES, values)
        ) + "}"
