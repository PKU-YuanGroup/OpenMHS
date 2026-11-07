"""OpenMHS driver for gh.janelia-python/zaber_device_python: a Zaber motorized linear stage chain.

A direct Driver over the upstream class ``zaber_device.zaber_device:ZaberStage``.  The upstream class owns one or
more Zaber devices on a serial line and maps one actuator alias per device to each of the x, y and z axes
(``zaber_device/zaber_device.py:826-849``).  Every move method converts the caller's stage unit to microsteps with
the microstep size configured for that axis, and the position getters convert the microstep count back
(``zaber_device/zaber_device.py:922-937``, ``989-1012``).

* reads: the x, y and z positions, the configured travel and microstep size of each axis, the actuator id of each
  axis, and whether all configured axes report homed;
* writes: the microstep size and travel of each axis.  The clone does not read either from the device: the README
  tells the operator to look them up for the connected actuator model on the Zaber website
  (``README.org:171-231``), so both are ``Limit.operator_required`` and every write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay supplies the scale and travel of its stage
  (``site-limits.example.json`` shows the overlay);
* actions: home, stop (also the safe-state action), an absolute xyz move, a relative xyz move, and store/move to a
  stored position address.  Stored-position addresses are bounded by the upstream constants
  ``POSITION_ADDRESS_MIN = 0`` and ``POSITION_ADDRESS_MAX = 15`` (``zaber_device/zaber_device.py:35-36``);
* the native stop (command 23 to every device, ``zaber_device/zaber_device.py:368-372``) is the e-stop.

The stage unit is the unit the operator chooses by setting the microstep size: the README sets
``0.49609375e-3`` so that positions are millimetres for a T-LSR450B (``README.org:183-205``).  The driver therefore
declares positions, travel and microstep sizes in the dimensionless UCUM unit ``1``: no text file of the clone
states the physical unit of this particular stage, and the operator's overlay supplies the bounds in the same unit.

The driver serves one Zaber device with the three actuators of an xyz stage; a chain that reports more than one
device is refused by a precondition failure instead of being merged.  Every Fact cites a line of the clone at the
pinned commit (2fec6746359b35acd4cf0c121cff03da8ae0a062).  This package is model-authored and unreviewed: the
acceptance gate runs the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


def _position_output():
    """The x, y and z outputs of the move actions (a fresh schema per action)."""
    return {
        "x": Field("number", unit="1", description="X axis position after the action"),
        "y": Field("number", unit="1", description="Y axis position after the action"),
        "z": Field("number", unit="1", description="Z axis position after the action"),
    }


class ZaberStageDriver(Driver):
    device_id = "zaber-stage"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "zaber_device.zaber_device:ZaberStage"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeZaberStage"}
    vendor, model = "Zaber Technologies", "motorized linear stage chain (ZaberStage)"
    display_name = "Zaber stage (zaber_device.ZaberStage)"
    tags = ["zaber", "linear-stage", "motion", "serial"]
    facts = [
        Fact("ZaberStage maps one actuator alias per device to each of the x, y and z axes; set_x_axis, set_y_axis "
             "and set_z_axis select the actuator by its alias", source="upstream_code",
             ref="zaber_device/zaber_device.py:826-849"),
        Fact("get_positions returns each configured axis position in microsteps multiplied by that axis's microstep "
             "size", source="upstream_code", ref="zaber_device/zaber_device.py:922-937"),
        Fact("move_x_absolute, move_y_absolute and move_z_absolute divide the requested position by the axis's "
             "microstep size before sending it to the actuator", source="upstream_code",
             ref="zaber_device/zaber_device.py:989-1012"),
        Fact("The microstep size is set on the stage object with set_x_microstep_size, set_y_microstep_size and "
             "set_z_microstep_size; the stage does not read it from the device", source="upstream_code",
             ref="zaber_device/zaber_device.py:1128-1156"),
        Fact("The travel is set on the stage object with set_x_travel, set_y_travel and set_z_travel; the stage does "
             "not read it from the device", source="upstream_code", ref="zaber_device/zaber_device.py:1158-1185"),
        Fact("The README tells the operator to look up the microstep size and the travel range of the connected "
             "actuator model on the Zaber website and set them on the stage", source="vendor_doc",
             ref="README.org:171-231"),
        Fact("ZaberStage.home calls home on every device in the chain", source="upstream_code",
             ref="zaber_device/zaber_device.py:959-962"),
        Fact("ZaberStage.stop calls stop on every device in the chain", source="upstream_code",
             ref="zaber_device/zaber_device.py:984-987"),
        Fact("ZaberDevice.stop sends command 23, which stops the actuator by preempting a move", source="upstream_code",
             ref="zaber_device/zaber_device.py:368-372"),
        Fact("Stored-position addresses are bounded by POSITION_ADDRESS_MIN = 0 and POSITION_ADDRESS_MAX = 15",
             source="upstream_code", ref="zaber_device/zaber_device.py:35-36"),
        Fact("get_actuator_ids returns the actuator id reported by each device for the configured axes",
             source="upstream_code", ref="zaber_device/zaber_device.py:1108-1126"),
        Fact("ZaberDevice.homed reads the home-status bit (1 << 7) of each actuator mode", source="upstream_code",
             ref="zaber_device/zaber_device.py:524-530"),
        Fact("ZaberStage.homed selects the configured axes from the device home status", source="upstream_code",
             ref="zaber_device/zaber_device.py:964-982"),
    ]
    safe_state = "all axes stopped (native stop command 23 sent to every device in the chain)"

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _positions(self):
        """The three axis positions, or a precondition failure when the stage does not expose one device with xyz."""
        positions = self.native.get_positions()
        if isinstance(positions, dict):
            if len(positions) != 1:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the stage reports more than one Zaber device; this driver serves one device")
            positions = next(iter(positions.values()))
        if not isinstance(positions, (list, tuple)) or len(positions) != 3:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the stage did not return an x, y and z position; configure the axes first")
        return [float(value) for value in positions]

    def _position_dict(self):
        x, y, z = self._positions()
        return {"x": x, "y": y, "z": z}

    @staticmethod
    def _number(value, what):
        if value is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"{what} is not configured on the stage")
        return float(value)

    def _actuator_id(self, index, what):
        values = self.native.get_actuator_ids()
        if values is None or index >= len(values) or values[index] is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"{what} is not configured on the stage")
        return int(values[index])

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("x_position", unit="1", description="X axis position in the stage unit")
    def x_position(self):
        return self._positions()[0]

    @read("y_position", unit="1", description="Y axis position in the stage unit")
    def y_position(self):
        return self._positions()[1]

    @read("z_position", unit="1", description="Z axis position in the stage unit")
    def z_position(self):
        return self._positions()[2]

    @read("x_microstep_size", unit="1", description="Scale of one x microstep in the stage unit")
    def x_microstep_size(self):
        return self._number(self.native.get_x_microstep_size(), "the x microstep size")

    @read("y_microstep_size", unit="1", description="Scale of one y microstep in the stage unit")
    def y_microstep_size(self):
        return self._number(self.native.get_y_microstep_size(), "the y microstep size")

    @read("z_microstep_size", unit="1", description="Scale of one z microstep in the stage unit")
    def z_microstep_size(self):
        return self._number(self.native.get_z_microstep_size(), "the z microstep size")

    @read("x_travel", unit="1", description="Configured travel of the x axis in the stage unit")
    def x_travel(self):
        return self._number(self.native.get_x_travel(), "the x travel")

    @read("y_travel", unit="1", description="Configured travel of the y axis in the stage unit")
    def y_travel(self):
        return self._number(self.native.get_y_travel(), "the y travel")

    @read("z_travel", unit="1", description="Configured travel of the z axis in the stage unit")
    def z_travel(self):
        return self._number(self.native.get_z_travel(), "the z travel")

    @read("x_actuator_id", type="integer", unit="1", description="Actuator id reported for the x axis")
    def x_actuator_id(self):
        return self._actuator_id(0, "the x actuator id")

    @read("y_actuator_id", type="integer", unit="1", description="Actuator id reported for the y axis")
    def y_actuator_id(self):
        return self._actuator_id(1, "the y actuator id")

    @read("z_actuator_id", type="integer", unit="1", description="Actuator id reported for the z axis")
    def z_actuator_id(self):
        return self._actuator_id(2, "the z actuator id")

    @read("homed", type="boolean", description="True when every configured axis reports homed")
    def homed(self):
        values = self.native.homed()
        if values is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the stage did not report home status")
        return all(values)

    # -- writes ----------------------------------------------------------------------------------------------------
    @write("x_microstep_size", unit="1",
           description="Scale of one x microstep in the stage unit; the operator looks it up for the actuator",
           limit=Limit.operator_required(
               "no text file of the clone states the microstep size of this stage's actuator; the README sends the "
               "operator to the Zaber website for the connected model (README.org:171-186)"))
    def set_x_microstep_size(self, value):
        self.native.set_x_microstep_size(value)

    @write("y_microstep_size", unit="1",
           description="Scale of one y microstep in the stage unit; the operator looks it up for the actuator",
           limit=Limit.operator_required(
               "no text file of the clone states the microstep size of this stage's actuator; the README sends the "
               "operator to the Zaber website for the connected model (README.org:171-186)"))
    def set_y_microstep_size(self, value):
        self.native.set_y_microstep_size(value)

    @write("z_microstep_size", unit="1",
           description="Scale of one z microstep in the stage unit; the operator looks it up for the actuator",
           limit=Limit.operator_required(
               "no text file of the clone states the microstep size of this stage's actuator; the README sends the "
               "operator to the Zaber website for the connected model (README.org:171-186)"))
    def set_z_microstep_size(self, value):
        self.native.set_z_microstep_size(value)

    @write("x_travel", unit="1", description="Travel of the x axis in the stage unit",
           limit=Limit.operator_required(
               "no text file of the clone states the travel of this stage's x axis; the README sends the operator to "
               "the Zaber website for the connected model (README.org:206-231)"))
    def set_x_travel(self, value):
        self.native.set_x_travel(value)

    @write("y_travel", unit="1", description="Travel of the y axis in the stage unit",
           limit=Limit.operator_required(
               "no text file of the clone states the travel of this stage's y axis; the README sends the operator to "
               "the Zaber website for the connected model (README.org:206-231)"))
    def set_y_travel(self, value):
        self.native.set_y_travel(value)

    @write("z_travel", unit="1", description="Travel of the z axis in the stage unit",
           limit=Limit.operator_required(
               "no text file of the clone states the travel of this stage's z axis; the README sends the operator to "
               "the Zaber website for the connected model (README.org:206-231)"))
    def set_z_travel(self, value):
        self.native.set_z_travel(value)

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.janelia-python.home.v1",
            description="Home every device in the chain and report the home status of the configured axes",
            output={"homed": Field("boolean", description="True when every configured axis reports homed")})
    def home(self):
        self.native.home()
        values = self.native.homed()
        return {"homed": bool(values is not None and all(values))}

    @action(name="x-cap.janelia-python.stop.v1", safe_state=True,
            description="Stop every device in the chain immediately (the native stop, the safe state)",
            output={"stopped": Field("boolean", description="True once the native stop was sent")})
    def stop_motion(self):
        self.native.stop()
        return {"stopped": True}

    @action(name="x-cap.janelia-python.move_absolute.v1",
            description="Move the x, y and z axes to absolute positions in the stage unit",
            input={
                "x": Field("number", unit="1", description="Absolute x position",
                           limit=Limit.operator_required(
                               "the x travel is set by the operator for this stage (README.org:206-231); no text "
                               "file of the clone states it")),
                "y": Field("number", unit="1", description="Absolute y position",
                           limit=Limit.operator_required(
                               "the y travel is set by the operator for this stage (README.org:206-231); no text "
                               "file of the clone states it")),
                "z": Field("number", unit="1", description="Absolute z position",
                           limit=Limit.operator_required(
                               "the z travel is set by the operator for this stage (README.org:206-231); no text "
                               "file of the clone states it")),
            },
            output=_position_output())
    def move_absolute(self, x, y, z):
        self.native.move_x_absolute(x)
        self.native.move_y_absolute(y)
        self.native.move_z_absolute(z)
        return self._position_dict()

    @action(name="x-cap.janelia-python.move_relative.v1",
            description="Move the x, y and z axes by relative distances in the stage unit",
            input={
                "x": Field("number", unit="1", description="Relative x distance",
                           limit=Limit.operator_required(
                               "the x travel is set by the operator for this stage (README.org:206-231); no text "
                               "file of the clone states it")),
                "y": Field("number", unit="1", description="Relative y distance",
                           limit=Limit.operator_required(
                               "the y travel is set by the operator for this stage (README.org:206-231); no text "
                               "file of the clone states it")),
                "z": Field("number", unit="1", description="Relative z distance",
                           limit=Limit.operator_required(
                               "the z travel is set by the operator for this stage (README.org:206-231); no text "
                               "file of the clone states it")),
            },
            output=_position_output())
    def move_relative(self, x, y, z):
        self.native.move_x_relative(x)
        self.native.move_y_relative(y)
        self.native.move_z_relative(z)
        return self._position_dict()

    @action(name="x-cap.janelia-python.move_to_stored_position.v1",
            description="Move the x, y and z axes to the positions stored at an address",
            input={
                "address": Field("integer", unit="1", description="Stored-position address (0 to 15)",
                                 limit=Limit(min=0, max=15, source="upstream_code",
                                             ref="zaber_device/zaber_device.py:35-36")),
            },
            output=_position_output())
    def move_to_stored_position(self, address):
        self.native.move_to_stored_x_position(address)
        self.native.move_to_stored_y_position(address)
        self.native.move_to_stored_z_position(address)
        return self._position_dict()

    @action(name="x-cap.janelia-python.store_position.v1",
            description="Store the current x, y and z positions at an address and return the stored positions",
            input={
                "address": Field("integer", unit="1", description="Stored-position address (0 to 15)",
                                 limit=Limit(min=0, max=15, source="upstream_code",
                                             ref="zaber_device/zaber_device.py:35-36")),
            },
            output=_position_output())
    def store_position(self, address):
        self.native.store_x_position(address)
        self.native.store_y_position(address)
        self.native.store_z_position(address)
        return {
            "x": float(self.native.get_stored_x_position(address)),
            "y": float(self.native.get_stored_y_position(address)),
            "z": float(self.native.get_stored_z_position(address)),
        }

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop_axes(self):
        """The native stop: the runtime latches first, then calls ZaberDevice.stop (command 23)."""
        self.native.stop()
