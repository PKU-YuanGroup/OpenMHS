"""OpenMHS driver for gh.amsikking/zaber_x_adr130: a Zaber X-ADR130 XY microscope stage over its ASCII serial protocol.

A direct Driver (decorated methods) over zaber_X_ADR130:Controller.  The card's SerialDriver helper cannot express
this interface: every line is assembled at run time from ``'/' + self.device_address + ' ' + cmd``, where the address
is read from the device at connect (``/get device.id``, line 37; ``_send``, lines 73-76), and each motion command
carries an axis token (``'1 move abs'``, line 161; ``'2 move abs'``, line 213).  A command table would have to
reproduce bytes the clone builds, so the driver calls the upstream methods and never builds a line itself.

* reads: the x and y position in mm, and the maximum speed of each axis in mm/s;
* writes: the maximum speed of each axis (0.01 to 750 mm/s, line 277);
* action: an absolute XY move, ``x-cap.amsikking.move_xy.v1``.  ``cap.motion.joint_position.v1`` fixes its positions
  to radians while the stage is addressed in millimetres, so the extension carries the native unit;
* the e-stop sends the upstream stop of each axis (``'1 stop'``, line 171; ``'2 stop'``, line 223).

Every Fact and Limit cites a line of the clone at the pinned commit
7c5926e07929b5c40ea6049ea5bceab28609bb0e.  This package is model-authored and unreviewed: it is checked on the fake
backend only, claims no hardware run and no MHS-Device level.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

CLONE = "zaber_X_ADR130.py"


class ZaberXAdr130(Driver):
    device_id = "zaber-x-adr130"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "zaber_X_ADR130:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeZaberXAdr130"}
    vendor, model = "Zaber", "X-ADR130B100B-SAE53D12"
    display_name = "Zaber X-ADR130 XY microscope stage"
    tags = ["zaber", "x-adr130", "xy stage", "microscope stage", "serial", "ascii protocol"]
    facts = [
        Fact("The repository is a Python device adaptor for the Zaber X-ADR130 linear motor XY microscope stage",
             source="vendor_doc", ref="README.md:1-2"),
        Fact("The adaptor writes the ASCII command '/get device.id' and reads the reply before any motion",
             source="upstream_code", ref=f"{CLONE}:37-63"),
        Fact("Device id 50998 is recognized as an X-ADR130B100B-SAE53D12", source="upstream_code",
             ref=f"{CLONE}:51-52"),
        Fact("The constructor rejects an x limit outside 0 to 130 mm and a y limit outside 0 to 100 mm",
             source="upstream_code", ref=f"{CLONE}:20-25"),
        Fact("A command is sent as '/<device address> <command>\\n'; a reply begins with '@<device address>' and "
             "ends with CRLF", source="upstream_code", ref=f"{CLONE}:73-94"),
        Fact("get_position_mm reads 'get pos' and converts each axis from nm to mm by 1e-6", source="upstream_code",
             ref=f"{CLONE}:236-244"),
        Fact("An x move is sent as '1 move abs <position in nm>' and is not sent when the target is outside the "
             "configured x limits", source="upstream_code", ref=f"{CLONE}:150-166"),
        Fact("A y move is sent as '2 move abs <position in nm>' and is not sent when the target is outside the "
             "configured y limits", source="upstream_code", ref=f"{CLONE}:202-218"),
        Fact("get_maxspeed reads 'get maxspeed' and converts each axis to mm/s with 1e-6 / 1.6384, rounded to three "
             "decimals", source="upstream_code", ref=f"{CLONE}:260-269"),
        Fact("set_maxspeed sends '1 set maxspeed' and '2 set maxspeed' with 1e6 * 1.6384 * mm/s",
             source="upstream_code", ref=f"{CLONE}:271-280"),
        Fact("The x axis is stopped with '1 stop'", source="upstream_code", ref=f"{CLONE}:168-174"),
        Fact("The y axis is stopped with '2 stop'", source="upstream_code", ref=f"{CLONE}:220-226"),
    ]
    safe_state = "both axes stopped with the native stop command of each axis ('1 stop' and '2 stop')"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("x_mm", unit="mm", description="X axis position reported by the stage")
    def x_mm(self):
        return float(self.native.get_position_mm()[0])

    @read("y_mm", unit="mm", description="Y axis position reported by the stage")
    def y_mm(self):
        return float(self.native.get_position_mm()[1])

    @read("x_maxspeed", unit="mm/s", description="Maximum speed of the x axis")
    def x_maxspeed(self):
        return float(self.native.get_maxspeed()[0])

    @read("y_maxspeed", unit="mm/s", description="Maximum speed of the y axis")
    def y_maxspeed(self):
        return float(self.native.get_maxspeed()[1])

    # -- writes -------------------------------------------------------------------------------------------------
    @write("x_maxspeed", unit="mm/s", description="Maximum speed of the x axis",
           limit=Limit(min=0.01, max=750, source="upstream_code", ref=f"{CLONE}:277",
                       reason="set_maxspeed asserts 0.01 <= x_mmps <= 750"))
    def set_x_maxspeed(self, value):
        _x, y = self.native.get_maxspeed()
        applied = round(float(value), 3)        # get_maxspeed publishes three decimals (lines 263-265)
        self.native.set_maxspeed(applied, y)
        return applied

    @write("y_maxspeed", unit="mm/s", description="Maximum speed of the y axis",
           limit=Limit(min=0.01, max=750, source="upstream_code", ref=f"{CLONE}:277",
                       reason="set_maxspeed asserts 0.01 <= y_mmps <= 750"))
    def set_y_maxspeed(self, value):
        x, _y = self.native.get_maxspeed()
        applied = round(float(value), 3)        # get_maxspeed publishes three decimals (lines 263-265)
        self.native.set_maxspeed(x, applied)
        return applied

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.amsikking.move_xy.v1",
            description="Move both axes to absolute positions in millimetres and wait for the move to finish",
            input={
                "x_mm": Field("number", unit="mm", description="Absolute target position of the x axis",
                              limit=Limit(min=0, max=130, source="upstream_code", ref=f"{CLONE}:21",
                                          reason="the constructor asserts 0 <= x <= 130 mm")),
                "y_mm": Field("number", unit="mm", description="Absolute target position of the y axis",
                              limit=Limit(min=0, max=100, source="upstream_code", ref=f"{CLONE}:24",
                                          reason="the constructor asserts 0 <= y <= 100 mm")),
            },
            output={
                "x_mm": Field("number", unit="mm", description="X position reported after the move"),
                "y_mm": Field("number", unit="mm", description="Y position reported after the move"),
            })
    def move_xy(self, x_mm, y_mm):
        self.native.move_mm(x_mm, y_mm, relative=False, block=True)
        position = self.native.get_position_mm()
        return {"x_mm": float(position[0]), "y_mm": float(position[1])}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop of each axis; the runtime latches first, then calls this."""
        try:
            self.native._stop_x()
        finally:
            self.native._stop_y()

    def teardown(self):
        """Close the serial port with the upstream close() (lines 285-288)."""
        self.native.close()
