"""OpenMHS driver for gh.michel4j/aunt-isara: the ISARA Automounter sample-handling robot.

A direct Driver (decorated methods) over the upstream application class ``auntisara.ioc:AuntISARAApp``.  The class is
a Soft IOC: it owns an ``AuntISARA`` process-variable model in ``self.ioc`` (auntisara/ioc.py:561-585), queues each
controller command through ``send_command`` (auntisara/ioc.py:968-978) and turns a dewar port into the low-level
mount parameters through ``set_mount_params`` (auntisara/ioc.py:1160-1177).  The driver reads the PVs through
``self.native.ioc`` and never imports the upstream package (gate G7 parses it).

* reads: controller status and action bitmask, position, tool, the two safety inputs, lid, mounted sample, next
  port, and the two dewar temperatures;
* one action that prepares a mount: ``x-cap.michel4j.select_mount_port.v1`` converts a PUCK_LIST port into the tool,
  puck and sample parameters and stores it as the next port;
* ``cap.motion.home.v1`` sends the native home command with the current tool and waits for HOME;
* ``cap.motion.stop.v1`` is the safe-state action (the native ``panic`` command) and the ``@estop`` method queues
  the same command.  No text of the clone documents an independent hardware e-stop, so no ``estop_physical_ref`` is
  set and the safe-state action satisfies SAFE-045.

Every Fact cites a line of the clone at the pinned commit f95cff5e6cec38e0b9945ae5673251fa5d11466f.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read

#: A dewar port is a prefix of the upstream PUCK_LIST (auntisara/ioc.py:34-40) plus a pin 1 to 16
#: (auntisara/ioc.py:43-44, 52); this pattern spells out the 29 prefixes instead of an invented range.
_PORT_PATTERN = r"^(1[A-F]|2[A-F]|3[A-E]|4[A-E]|5[A-E]|6[BD])([1-9]|1[0-6])$"


class AuntIsara(Driver):
    device_id = "isara"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "auntisara.ioc:AuntISARAApp"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAuntIsara"}
    vendor, model = "michel4j", "ISARA Automounter"
    display_name = "ISARA sample automounter (AuntISARAApp)"
    tags = ["sample-handler", "automounter", "robot-arm", "cryo", "dewar"]
    facts = [
        Fact("AuntISARAApp builds the AuntISARA process-variable model in self.ioc and connects the command and "
             "status clients to the controller", source="upstream_code", ref="auntisara/ioc.py:561-585"),
        Fact("The controller status and action are the STATUS and ACTION process variables", source="upstream_code",
             ref="auntisara/ioc.py:210-211"),
        Fact("ActionType bits are MOUNT, DISMOUNT, PREFETCH and ABORTING", source="upstream_code",
             ref="auntisara/ioc.py:172-178"),
        Fact("StatusType values are IDLE, WAITING, BUSY, STANDBY and FAULT (0 to 4)", source="upstream_code",
             ref="auntisara/msgs.py:5-6"),
        Fact("The emergency input is INP:emerg and the collision sensor input is INP:colSensor", source="upstream_code",
             ref="auntisara/ioc.py:225-226"),
        Fact("position_fbk is STATE:pos, tool_fbk is STATE:tool and the mounted sample is STATE:onDiff",
             source="upstream_code", ref="auntisara/ioc.py:241-277"),
        Fact("lid_fbk is STATE:lidOpen (0 CLOSED, 1 OPEN)", source="upstream_code", ref="auntisara/ioc.py:261"),
        Fact("dewar_temp1_fbk and dewar_temp2_fbk are STATE:dewarT1 and STATE:dewarT2", source="upstream_code",
             ref="auntisara/ioc.py:280-281"),
        Fact("next_port is PAR:nextPort; tool_param, puck_param and sample_param are PAR:tool, PAR:puck and PAR:smpl",
             source="upstream_code", ref="auntisara/ioc.py:285-289"),
        Fact("do_next_port validates a port and stores it in next_port, or empties it", source="upstream_code",
             ref="auntisara/ioc.py:2069-2073"),
        Fact("A puck port is a PUCK_LIST prefix and a pin 1 to 16; PUCK_LIST holds 29 prefixes and NUM_PUCK_SAMPLES "
             "is 16", source="upstream_code", ref="auntisara/ioc.py:34-44"),
        Fact("PORT_PATT accepts a puck prefix and a pin 1 to 16", source="upstream_code", ref="auntisara/ioc.py:52"),
        Fact("send_command queues a command and formats arguments as command(arg,arg)",
             source="upstream_code", ref="auntisara/ioc.py:968-978"),
        Fact("set_mount_params converts a port with port2args and writes tool_param, puck_param and sample_param",
             source="upstream_code", ref="auntisara/ioc.py:1160-1170"),
        Fact("port2args converts a port such as 1A16 to puck, sample and tool for a UNIPUCK or DOUBLE tool",
             source="upstream_code", ref="auntisara/ioc.py:356-369"),
        Fact("do_panic_cmd sends the native panic command", source="upstream_code", ref="auntisara/ioc.py:1753-1755"),
        Fact("do_home_cmd sends the native home command with the current tool", source="upstream_code",
             ref="auntisara/ioc.py:1821-1823"),
        Fact("abort_to_home sends abort, reset and safe and waits for HOME and IDLE", source="upstream_code",
             ref="auntisara/ioc.py:1179-1190"),
        Fact("is_idle compares the controller status with StatusType.IDLE", source="upstream_code",
             ref="auntisara/ioc.py:1665-1669"),
    ]
    safe_state = ("sample-operation motion stopped: the native panic command is queued on the controller command link "
                  "(auntisara/ioc.py:1753-1755); the controller emergency input and collision sensor remain its own "
                  "independent protections (auntisara/ioc.py:225-226)")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("status", type="integer",
          description="Controller status code: 0 IDLE, 1 WAITING, 2 BUSY, 3 STANDBY, 4 FAULT")
    def status(self):
        return int(self.native.ioc.status.get())

    @read("action", type="integer",
          description="Active-operation bitmask: MOUNT=1, DISMOUNT=2, PREFETCH=4, ABORTING=8")
    def action_bits(self):
        return int(self.native.ioc.action.get())

    @read("position", type="string", description="Controller position name (for example HOME or SOAK)")
    def position(self):
        return str(self.native.ioc.position_fbk.get())

    @read("tool", type="integer", description="Controller tool code (ToolType: 0 NONE to 5 DOUBLE)")
    def tool(self):
        return int(self.native.ioc.tool_fbk.get())

    @read("emergency_ok", type="boolean",
          description="True while the controller emergency/air input INP:emerg reports GOOD")
    def emergency_ok(self):
        return bool(self.native.ioc.emergency_ok.get())

    @read("collision_ok", type="boolean",
          description="True while the controller collision sensor INP:colSensor reports GOOD")
    def collision_ok(self):
        return bool(self.native.ioc.collision_ok.get())

    @read("lid_open", type="boolean", description="True while the controller reports the lid open")
    def lid_open(self):
        return bool(self.native.ioc.lid_fbk.get())

    @read("mounted_sample", type="string", description="Port of the sample reported on the goniometer, or empty")
    def mounted_sample(self):
        return str(self.native.ioc.mounted_fbk.get())

    @read("next_port", type="string", description="Port stored in the controller next-port parameter")
    def next_port(self):
        return str(self.native.ioc.next_port.get())

    @read("dewar_temperature_1", type="number",
          description="Dewar temperature 1 as reported by the controller (the clone states no unit)")
    def dewar_temperature_1(self):
        return float(self.native.ioc.dewar_temp1_fbk.get())

    @read("dewar_temperature_2", type="number",
          description="Dewar temperature 2 as reported by the controller (the clone states no unit)")
    def dewar_temperature_2(self):
        return float(self.native.ioc.dewar_temp2_fbk.get())

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.michel4j.select_mount_port.v1",
            description="Convert a dewar port into the native tool, puck and sample mount parameters and store it as "
                        "the next port; this prepares a mount and does not move the robot",
            input={"port": Field("string", max_length=40, pattern=_PORT_PATTERN,
                                 description="Dewar port: a PUCK_LIST puck prefix and a pin 1 to 16, for example 1A16")},
            output={"port": Field("string", description="Port stored in the controller next-port parameter"),
                    "tool": Field("integer", description="Native tool parameter selected for the port"),
                    "puck": Field("integer", description="Native puck parameter selected for the port"),
                    "sample": Field("integer", description="Native sample parameter selected for the port")})
    def select_mount_port(self, port):
        self.native.do_next_port(self.native.ioc.next_port, port, self.native.ioc)
        stored = str(self.native.ioc.next_port.get())
        if not stored or not self.native.set_mount_params(stored):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the controller rejected mount port {port!r}: a PUCK_LIST prefix and a pin 1 to 16 "
                               "are required, and the upstream next-port check must accept it")
        return {"port": stored,
                "tool": int(self.native.ioc.tool_param.get()),
                "puck": int(self.native.ioc.puck_param.get()),
                "sample": int(self.native.ioc.sample_param.get())}

    @action(name="x-cap.michel4j.home.v1", long_running=True, max_duration_ms=120000, cancellable=True,
            description="Home the automounter with the current tool and report whether the controller reached HOME "
                        "and is idle",
            output={"homed": Field("boolean", description="True when the controller reports HOME and idle")})
    def home(self):
        self.native.send_command("home", self.native.ioc.tool_fbk.get())
        homed = self.native.wait_for_position("HOME", timeout=60)
        if not homed or not self.native.is_idle():
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the controller did not report HOME and idle after the home command")
        return {"homed": True}

    @action(name="x-cap.michel4j.panic.v1", safe_state=True,
            description="Stop all sample-operation motion by queueing the native panic command; it takes no input",
            output={"stopped": Field("boolean", description="True once the panic command was queued")})
    def stop_all_motion(self):
        self.native.send_command("panic")
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then queues the controller panic command."""
        self.native.send_command("panic")

    def teardown(self):
        self.native.shutdown()
