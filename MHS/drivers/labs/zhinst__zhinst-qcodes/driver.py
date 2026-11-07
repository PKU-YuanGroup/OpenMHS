"""OpenMHS driver for gh.zhinst/zhinst-qcodes: the Zurich Instruments PQSC trigger-generation device.

DEVIATION FROM THE CARD: the card names the ``QcodesDriver`` family helper, but the
zhinst-qcodes classes do not construct explicit ``self.<name> = Parameter(...)``
members.  ``ZIBaseInstrument.__init__`` calls ``init_nodetree``, which creates the
node Parameters in a loop from the LabOne node tree
(src/zhinst/qcodes/driver/devices/base.py:46, src/zhinst/qcodes/qcodes_adaptions.py:772).
The QcodesDriver source proof binds only explicit Parameter assignments, so this
package is a direct ``Driver`` over the card's entry class
``zhinst.qcodes.driver.devices.pqsc:PQSC``.

The PQSC is the trigger-generation device of a Zurich Instruments setup.  This
package serves the device-level functions of that class: identity and streaming-node
observations, the reference-clock check, and the trigger lifecycle (arm, run,
arm-and-run, stop, factory reset, wait-for-done) through extension actions.  The
dynamically generated LabOne node parameters (``system/...``, ``triggers/...``,
``zsync/...``) are NOT served: their names and units come from the node tree of the
connected device, not from a source line this package can cite.

Stop (model review): the e-stop calls ``PQSC.stop(deep=True)``.  The clone documents ``stop`` as stopping the
trigger generation, with ``deep`` performing a synchronization between the device and the data server after the
disable (src/zhinst/qcodes/driver/devices/pqsc.py:52-61), and documents ``deep`` on a node operation as blocking
until the device has acknowledged it (src/zhinst/qcodes/qcodes_adaptions.py:279-282).  The author's ``deep=False`` returned
before that synchronization, so a completed e-stop proved only that the request was handed to the session.  The
method forwards to the zhinst-toolkit object (pqsc.py:61); toolkit (``zhinst-toolkit>=1.4.0``, pyproject.toml:22-27)
is not in the clone, so what the device does is documented, not code-proven, here.  A deep stop that takes longer
than the runtime's e-stop budget is reported ``MHS.SAFETY.SAFE_STATE_UNREACHED`` and retried in the background.

The identity and streaming-node values come from the toolkit and the device node tree, whose value types the clone
does not show; the ``firmware`` and ``streaming_nodes`` reads therefore return their text form (model review).

All Facts cite the pinned clone at commit 042dd17a5bf492cc4c573e465b2bc399e68d3203.
The package is model-authored and unreviewed (``reviewed_by`` is null); it has run on
the fake backend only and has never opened a LabOne data-server session.

NOT COVERED:

* ``set_transaction`` is a context manager that bundles node sets into one
  transaction (src/zhinst/qcodes/driver/devices/base.py:92-112); it is not a device
  value setter and cannot be expressed by ``@write``.
* ``arm`` and ``arm_and_run`` accept optional ``repetitions`` and ``holdoff``.  No
  source states their bounds; the hold-off docstring gives only a minimum value and
  a granularity of 100 ns (src/zhinst/qcodes/driver/devices/pqsc.py:44-46,175-177).
  The package calls the methods without these arguments ("If they are not specified,
  they are not changed"), so the device keeps its configured trigger count and
  hold-off; an operator configures them in LabOne.
* ``check_zsync_connection`` and ``find_zsync_worker_port`` need a concrete port or
  toolkit instrument object, which this device-level package does not own.
* The node-tree Parameters, their units and their per-node ranges are generated from
  the connected device's node tree; serving them would require an explicit source
  line per parameter, which this clone does not have.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: The card's entry class.  The hardware factory constructs it through
#: ``device_creator.PQSC``, the subclass whose constructor opens the session.
NATIVE = "zhinst.qcodes.driver.devices.pqsc:PQSC"
PQSC_SOURCE = "src/zhinst/qcodes/driver/devices/pqsc.py"
BASE_SOURCE = "src/zhinst/qcodes/driver/devices/base.py"
CREATOR_SOURCE = "src/zhinst/qcodes/device_creator.py"

TRIGGER_CAP = "x-cap.zhinst.pqsc_trigger.v1"
WAIT_DONE_CAP = "x-cap.zhinst.pqsc_wait_done.v1"

TRIGGER_OPERATIONS = ["arm", "run", "arm_and_run", "stop", "factory_reset"]

WAIT_TIMEOUT = Limit.operator_required(
    "no source states a wait_done timeout bound; the deployment sets the maximum wait for its trigger sequence")


class ZhinstPQSC(Driver):
    """Zurich Instruments PQSC trigger-generation device (QCoDeS driver class)."""

    device_id = "zhinst-pqsc"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = NATIVE
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePQSC"}
    vendor, model = "Zurich Instruments", "PQSC"
    display_name = "Zurich Instruments PQSC trigger distributor (zhinst-qcodes)"
    tags = ["qcodes", "zhinst", "labone", "pqsc", "trigger-distributor", "zsync"]
    safe_state = ("trigger generation stopped by the native PQSC stop(deep=True), documented to synchronize the "
                  "device and the data server after the disable (the implementation is zhinst-toolkit's, outside the "
                  "clone); the device settings and the connected instruments are not reset, so their configuration "
                  "and any sequence they run on their own are left as they were")
    facts = [
        Fact("PQSC is the QCoDeS driver class for the Zurich Instruments PQSC", source="upstream_code",
             ref=f"{PQSC_SOURCE}:10-11"),
        Fact("run() starts sending out triggers and activates trigger generation over the ZSync ports",
             source="upstream_code", ref=f"{PQSC_SOURCE}:18-30"),
        Fact("arm() configures the execution engine and clears the register bank; repetitions and holdoff "
             "optionally set the number of triggers and the time between repeated triggers, and the hold-off "
             "has a minimum value and a granularity of 100 ns", source="upstream_code",
             ref=f"{PQSC_SOURCE}:149-181"),
        Fact("arm_and_run() combines arm and run and synchronizes between the device and the data server after "
             "arming and running", source="upstream_code", ref=f"{PQSC_SOURCE}:32-50"),
        Fact("stop() is documented to stop the trigger generation; deep (default True) performs a synchronization "
             "between the device and the data server after the disable, and the call forwards to the toolkit object",
             source="upstream_code", ref=f"{PQSC_SOURCE}:52-61"),
        Fact("A deep operation on a node blocks until the device has acknowledged it and returns the acknowledged "
             "value", source="upstream_code", ref="src/zhinst/qcodes/qcodes_adaptions.py:279-282"),
        Fact("zhinst-qcodes requires zhinst-toolkit>=1.4.0 and qcodes>=0.35.0", source="upstream_code",
             ref="pyproject.toml:22-27"),
        Fact("wait_done() waits until trigger generation and feedback processing is done, bounded by timeout in "
             "seconds, and raises TimeoutError when the sequence is not done before it", source="upstream_code",
             ref=f"{PQSC_SOURCE}:63-76"),
        Fact("check_ref_clock() checks whether the reference clock is locked successfully, bounded by timeout in "
             "seconds", source="upstream_code", ref=f"{PQSC_SOURCE}:78-93"),
        Fact("get_idn() returns the vendor, model, serial and firmware of the connected device",
             source="upstream_code", ref=f"{BASE_SOURCE}:48-55"),
        Fact("factory_reset() loads the factory default settings", source="upstream_code",
             ref=f"{BASE_SOURCE}:60-68"),
        Fact("get_streamingnodes() returns the streaming nodes available on the device", source="upstream_code",
             ref=f"{BASE_SOURCE}:88-90"),
        Fact("set_transaction() returns the toolkit transaction context manager that bundles node set commands; "
             "it is not a value setter", source="upstream_code", ref=f"{BASE_SOURCE}:92-112"),
        Fact("serial and device_type are properties of the instrument", source="upstream_code",
             ref=f"{BASE_SOURCE}:114-122"),
        Fact("the device-creator PQSC constructor creates a ZISession for host and port and connects the serial "
             "with connect_device(serial, interface=interface)", source="upstream_code",
             ref=f"{CREATOR_SOURCE}:255-276"),
    ]

    @read("device_type", type="string", description="Instrument type reported by the upstream device property")
    def device_type(self):
        return self.native.device_type

    @read("serial", type="string", description="Serial number reported by the upstream device property")
    def serial(self):
        return self.native.serial

    @read("firmware", type="string",
          description="Firmware revision from get_idn() (the system/fwrevision node), as text")
    def firmware(self):
        # get_idn() returns self.system.fwrevision() (base.py:48-55); the node's value type is not in the clone.
        return str(self.native.get_idn()["firmware"])

    @read("streaming_nodes", type="array", items="string",
          description="Text form of each entry get_streamingnodes() returns; the clone does not show the entry type")
    def streaming_nodes(self):
        return [str(node) for node in self.native.get_streamingnodes()]

    @read("ref_clock_locked", type="boolean",
          description="Reference clock locked, from check_ref_clock(); the read waits at most one second")
    def ref_clock_locked(self):
        # A state read must not block for the upstream default 30 s when no reference clock is present.
        return bool(self.native.check_ref_clock(timeout=1.0, sleep_time=0.1))

    @action(name=TRIGGER_CAP, description="Arm, run, stop or factory-reset the PQSC trigger generation",
            input={
                "operation": Field("string", enum=TRIGGER_OPERATIONS,
                                   description="arm, run, arm_and_run, stop or factory_reset"),
                "deep": Field("boolean",
                              description="synchronize with the data server after the operation; ignored by "
                                          "arm_and_run"),
            },
            output={
                "operation": Field("string", description="the operation that was issued"),
                "issued": Field("boolean", description="true once the native call returned"),
            })
    def trigger(self, operation, deep=True):
        self.check_cancelled()
        if operation == "arm":
            self.native.arm(deep=deep)
        elif operation == "run":
            self.native.run(deep=deep)
        elif operation == "arm_and_run":
            self.native.arm_and_run()
        elif operation == "stop":
            self.native.stop(deep=deep)
        elif operation == "factory_reset":
            self.native.factory_reset(deep=deep)
        else:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unsupported trigger operation {operation!r}")
        return {"operation": operation, "issued": True}

    @action(name=WAIT_DONE_CAP, description="Wait until trigger generation and feedback processing is done",
            input={
                "timeout": Field("number", unit="s",
                                 description="maximum wait in seconds; omitted uses the upstream default",
                                 limit=WAIT_TIMEOUT),
            },
            output={"done": Field("boolean", description="true once wait_done() returned")})
    def wait_done(self, timeout=None):
        self.check_cancelled()
        if timeout is None:
            self.native.wait_done()
        else:
            self.native.wait_done(timeout=timeout)
        return {"done": True}

    @estop
    def stop(self):
        """The native stop: PQSC.stop(deep=True), which returns after the documented device/data-server sync.

        The author's deep=False returned before that synchronization (model review); a slow sync is reported
        SAFE_STATE_UNREACHED by the runtime's e-stop budget and retried in the background.
        """
        self.native.stop(deep=True)
