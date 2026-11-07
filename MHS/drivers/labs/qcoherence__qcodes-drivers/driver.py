"""OpenMHS driver for gh.qcoherence/qcodes-drivers: the ADwin Gold II real-time controller.

A direct Driver (decorated methods) over the QCoDeS Instrument ``ADwin_Gold2:ADwin_Gold2``
(ADwin_Gold2.py:549).  The card's helper is ``QcodesDriver``, but that family proves one explicit
``self.<name> = Parameter(...)`` assignment per served field (MHS/sdk/docs/qcodes-driver.md).  No class of this
clone constructs a Parameter that way: every instrument here calls ``add_parameter`` (for example
ADwin_Gold2.py:569-709), which the QcodesDriver source proof does not cover.  The ADwin class does expose ordinary
methods for its controls, so this package is a direct Driver; RESULT.json records the deviation from the card.

The package serves the device's primary analog input/output path:

* reads of the configured mode, ramp size, subsampling factor and input/output masks, each the matching ``get_*``
  method of the class;
* writes of those five settings through ``cap.device.configure.v1``, each calling the matching ``set_*`` method and
  observable through the read of the same name;
* ``x-cap.qcoherence.set_output_voltages.v1``: convert eight target voltages with the native ``volt_to_binary``,
  set the output mask to all eight outputs, build the FIFO with ``set_outputs`` and send it with
  ``set_outputs_one_cycle`` (a one-process-cycle ramp; ADwin_Gold2.py:742-744, 754-790);
* ``x-cap.qcoherence.read_input_fifo.v1``: read every value currently in the measurement FIFO with ``read_inputs``
  and convert each with the native ``binary_to_volt`` (ADwin_Gold2.py:750-752, 806-812);
* ``x-cap.qcoherence.zero_outputs.v1`` calls the native ``go_to_zero``: it writes a one-cycle command with 0 V
  targets for all eight outputs into FIFO 1, sleeps two process durations, restores the output mask and clears both
  FIFOs (ADwin_Gold2.py:796-804, 783-790, 814-817).

BLOCKED (model review, 2026-11-05): no stop is proven from the clone.  ``go_to_zero`` only writes a command into
the ADwin's FIFO and returns; nothing acknowledges it or reads an output back.  The real-time process that consumes
FIFO 1 (``acquisition-gold2.TB1``, adwin/adwin_zero.py:15) lives in the ``adwin/nanoqt`` git submodule
(.gitmodules:1-3, README.md:15-29), which is not part of the pinned commit, so what the command does is not in the
clone.  The clone's own script queues several ramp commands in FIFO 1 one after another (adwin/acqui_adwin.py:30-36),
and ``go_to_zero`` clears FIFO 1 two process durations after writing its command: behind a running ramp the zero
command can be cleared unexecuted.  It also keeps the current ``adwin_mode`` as the command's mode word (a lock-in
mode stays a lock-in command), and it rebuilds the instance's ``fifo_list`` and output mask that a running
``set_output_voltages`` also uses (the e-stop does not take the driver lock), so an overlapping e-stop can send that
action's targets.  The e-stop therefore still sends ``go_to_zero`` but then reports
``MHS.SAFETY.SAFE_STATE_UNREACHED`` and keeps the latch; ``zero_outputs`` is an ordinary command, not a safe-state
action.  The ADwin analog outputs are actuators, and an actuator without a source-backed stop stays blocked.

NOT COVERED, each for a reason in the source:

* ``lockin_freq``, ``lockin_amplitude``, ``lockin_bandwidth``, ``lockin_input_port``, ``lockin_output_port`` and
  ``lockin_output2_port`` are Parameters whose set/get callbacks reach ``self.device`` directly
  (ADwin_Gold2.py:648-709); the class defines no wrapper method for them, and a direct Driver may only touch names
  of the class body (G7).  Their behavior is not served.
* ``get_input_size`` divides by the subsampling factor (ADwin_Gold2.py:819-826) and therefore raises at the validator's
  own lower bound of 0 (ADwin_Gold2.py:600); it is not a stable state read.
* the ``outputs`` and ``inputs`` Parameters apply their parsers only inside QCoDeS' Parameter machinery
  (ADwin_Gold2.py:627-646); this driver calls the class methods and applies ``volt_to_binary`` / ``binary_to_volt``
  itself, so it cannot inspect a Parameter cache and does not claim to.

Every Fact cites the clone at the pinned commit 619bdd35bda80f767f42a1681d6dd26819ad09a9.  This package is
model-authored and unreviewed: it is checked on the fake backend only and has never opened an ADwin.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream file of the selected class, relative to the clone root.
MODULE = "ADwin_Gold2.py"

_ADWIN_MODE = Limit(min=0, max=0x80010, source="upstream_code", ref=f"{MODULE}:573")
_RAMP_SIZE = Limit(min=0, max=1000000, source="upstream_code", ref=f"{MODULE}:12")
_SUBSAMPLING = Limit.operator_required(
    "the validator Numbers(0, 2**16) at ADwin_Gold2.py:600 is not a usable range: 0 divides by zero in "
    "get_input_size (:825) and the clone does not show what the real-time process accepts")
_OUTPUT_MASK = Limit(min=1, max=255, source="upstream_code", ref=f"{MODULE}:609")
_INPUT_MASK = Limit(min=0, max=16383, source="upstream_code", ref=f"{MODULE}:620")
_OUTPUT_VOLTAGE = Limit(min=-10, max=10, unit="V", source="upstream_code", ref=f"{MODULE}:630")


class ADwinGold2(Driver):
    device_id = "adwin-gold2"
    device_kind = "process.controller"
    mode = "hardware"
    risk = "R1"
    native = "ADwin_Gold2:ADwin_Gold2"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeADwinGold2"}
    vendor, model = "ADwin", "ADwin Gold II"
    display_name = "ADwin Gold II real-time controller (QCoDeS ADwin_Gold2)"
    tags = ["qcodes", "adwin", "real-time", "analog input", "analog output", "daq"]
    facts = [
        Fact("ADwin_Gold2 is the QCoDeS Instrument class for the ADwin Gold II", source="upstream_code",
             ref=f"{MODULE}:549-552"),
        Fact("The constructor takes the instrument name, a boot file, a process file and an ADwin number that "
             "defaults to 1", source="upstream_code", ref=f"{MODULE}:557"),
        Fact("The constructor opens ADwin.ADwin(adwin_no), boots it, loads and starts the process and clears both "
             "FIFOs", source="upstream_code", ref=f"{MODULE}:711-714"),
        Fact("process_load stops the process, loads the process file, sets a 3000-step process delay (10 us on the "
             "T11 clock) and starts the process", source="upstream_code", ref=f"{MODULE}:727-736"),
        Fact("set_outputs builds the FIFO from the mode, input mask, output mask, ramp size and subsampling, then "
             "appends the targets; it does not reset the outputs to 0 V", source="upstream_code",
             ref=f"{MODULE}:754-779"),
        Fact("set_outputs_one_cycle sends the FIFO with a one-point ramp, waits two process durations and restores "
             "the ramp size", source="upstream_code", ref=f"{MODULE}:783-790"),
        Fact("launch_measurement sends the FIFO and sleeps for ramp_size times the process duration",
             source="upstream_code", ref=f"{MODULE}:792-794"),
        Fact("go_to_zero sets the output mask to all eight outputs, commands 0 V on all eight, sends one cycle, "
             "restores the mask and clears both FIFOs", source="upstream_code", ref=f"{MODULE}:796-804"),
        Fact("read_inputs reads all values in the measurement FIFO at once", source="upstream_code",
             ref=f"{MODULE}:806-812"),
        Fact("clear_fifos clears FIFO 1 and FIFO 2", source="upstream_code", ref=f"{MODULE}:814-817"),
        Fact("volt_to_binary returns int(V / 10 * 2**15 + 2**15) as the DAC binary representation",
             source="upstream_code", ref=f"{MODULE}:742-744"),
        Fact("binary_to_volt converts the ADC binary back to a voltage between -10 V and +10 V",
             source="upstream_code", ref=f"{MODULE}:750-752"),
        Fact("set_mode accepts an integer mode or the strings normal, lockin, lockin2 and lockin2_inv",
             source="upstream_code", ref=f"{MODULE}:848-864"),
        Fact("set_output_mask accepts a mask integer or a list of output indices and sums 2**(i-1) for each list "
             "index", source="upstream_code", ref=f"{MODULE}:884-898"),
        Fact("set_input_mask accepts a mask integer or a list of input indices and sums 2**(i-1) for each list "
             "index", source="upstream_code", ref=f"{MODULE}:904-918"),
        Fact("set_ramp_size and get_ramp_size read and write the internal ramp size rs", source="upstream_code",
             ref=f"{MODULE}:876-882"),
        Fact("set_subsampling and get_subsampling read and write the subsampling factor", source="upstream_code",
             ref=f"{MODULE}:924-930"),
        Fact("The adwin_mode validator accepts 0x0 through 0x80010 or the four mode names", source="upstream_code",
             ref=f"{MODULE}:569-578"),
        Fact("FIFO_SZ is 1000000", source="upstream_code", ref=f"{MODULE}:12"),
        Fact("The ramp_size validator is Numbers(0, FIFO_SZ)", source="upstream_code", ref=f"{MODULE}:580-587"),
        Fact("The subsampling validator is Numbers(0, 2**16)", source="upstream_code", ref=f"{MODULE}:597-603"),
        Fact("The output_mask validator accepts 0b1 through 0b11111111 or a list of indices 1 to 8",
             source="upstream_code", ref=f"{MODULE}:605-614"),
        Fact("The input_mask validator accepts 0b0 through 0b11111111111111 or a list of indices 1 to 14",
             source="upstream_code", ref=f"{MODULE}:616-625"),
        Fact("The outputs Parameter has unit V and the validator Arrays(-10, 10)", source="upstream_code",
             ref=f"{MODULE}:627-636"),
        Fact("The inputs Parameter has unit V and converts each FIFO value with binary_to_volt",
             source="upstream_code", ref=f"{MODULE}:638-646"),
        Fact("The lock-in frequency, amplitude, bandwidth and port Parameters call self.device.Set_FPar, Get_FPar, "
             "Set_Par and Get_Par directly", source="upstream_code", ref=f"{MODULE}:648-709"),
        Fact("The README says the repository holds custom drivers for instruments used with QCoDeS",
             source="vendor_doc", ref="README.md:5"),
        Fact("The README says the ADwin relies on the nanoqt submodule and the external ADwin package must be "
             "installed", source="vendor_doc", ref="README.md:15-29"),
        Fact(".gitmodules declares the submodule adwin/nanoqt", source="upstream_code", ref=".gitmodules:1-3"),
        Fact("adwin_zero.py boots the ADwin from ./nanoqt/ressources and loads the process "
             "./nanoqt/ressources/acquisition-gold2.TB1", source="upstream_code", ref="adwin/adwin_zero.py:10-16"),
        Fact("acqui_adwin.py writes one command into FIFO 1, then queues n_ramp pairs of ramp commands in a loop "
             "and a final command, all with SetFifo_Long", source="upstream_code", ref="adwin/acqui_adwin.py:30-36"),
        Fact("get_input_size divides ramp_size by subsampling", source="upstream_code", ref=f"{MODULE}:819-826"),
    ]
    safe_state = ("none proven: the e-stop sends go_to_zero (a 0 V command for all eight outputs written into FIFO "
                  "1, then both FIFOs cleared, with no acknowledgement or read-back; the process that executes it is "
                  "not in the clone) and reports SAFE_STATE_UNREACHED with the latch held; the real-time process "
                  "keeps running")

    # -- reads --------------------------------------------------------------------------------------------------
    @read("adwin_mode", type="integer", unit="1",
          description="ADwin mode bits as returned by get_mode (0b0 normal; the lock-in bits are defined by the "
                      "loaded process)")
    def adwin_mode(self):
        return int(self.native.get_mode())

    @read("ramp_size", type="integer", unit="1",
          description="Ramp size in process points used for the next FIFO (get_ramp_size)")
    def adwin_ramp_size(self):
        return int(self.native.get_ramp_size())

    @read("subsampling", type="integer", unit="1",
          description="Input subsampling factor: one measurement every S process durations (get_subsampling)")
    def adwin_subsampling(self):
        return int(self.native.get_subsampling())

    @read("output_mask", type="integer", unit="1",
          description="Output mask: bit n-1 selects analog output n (get_output_mask)")
    def adwin_output_mask(self):
        return int(self.native.get_output_mask())

    @read("input_mask", type="integer", unit="1",
          description="Input mask: bit n-1 selects analog input n (get_input_mask)")
    def adwin_input_mask(self):
        return int(self.native.get_input_mask())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("adwin_mode", type="integer", unit="1",
           description="ADwin mode bits passed to set_mode; the class also accepts four mode names, which this "
                       "integer field does not carry",
           limit=_ADWIN_MODE)
    def set_adwin_mode(self, value):
        self.native.set_mode(int(value))
        return int(value)

    @write("ramp_size", type="integer", unit="1",
           description="Ramp size in process points for the next FIFO (set_ramp_size)",
           limit=_RAMP_SIZE)
    def set_ramp_size(self, value):
        self.native.set_ramp_size(int(value))
        return int(value)

    @write("subsampling", type="integer", unit="1",
           description="Input subsampling factor (set_subsampling)",
           limit=_SUBSAMPLING)
    def set_subsampling(self, value):
        self.native.set_subsampling(int(value))
        return int(value)

    @write("output_mask", type="integer", unit="1",
           description="Output mask: bit n-1 selects analog output n (set_output_mask)",
           limit=_OUTPUT_MASK)
    def set_output_mask(self, value):
        self.native.set_output_mask(int(value))
        return int(value)

    @write("input_mask", type="integer", unit="1",
           description="Input mask: bit n-1 selects analog input n (set_input_mask)",
           limit=_INPUT_MASK)
    def set_input_mask(self, value):
        self.native.set_input_mask(int(value))
        return int(value)

    # -- primary actuation ----------------------------------------------------------------------------------------
    @action(name="x-cap.qcoherence.set_output_voltages.v1",
            description="Command all eight analog outputs to the given voltages and send the FIFO for one process "
                        "cycle (set_output_mask 0xFF, set_outputs, set_outputs_one_cycle)",
            input={"targets": Field(
                "array", items="number", length=8, unit="V",
                description="Target voltage for each of the eight analog outputs, in output order 1 to 8",
                limit=_OUTPUT_VOLTAGE)},
            output={
                "targets": Field("array", items="number", length=8, unit="V",
                                 description="The eight commanded voltages, in output order 1 to 8"),
                "output_mask": Field("integer", unit="1",
                                     description="Output mask the FIFO was built with (bit n-1 selects output n)"),
                "sent": Field("boolean",
                              description="True once the native set_outputs_one_cycle returned"),
            })
    def set_output_voltages(self, targets):
        values = [float(value) for value in targets]
        self.check_cancelled()
        binary = [int(self.native.volt_to_binary(value)) for value in values]
        self.check_cancelled()
        self.native.set_output_mask(0xFF)
        self.native.set_outputs(binary)
        self.check_cancelled()
        self.native.set_outputs_one_cycle()
        return {"targets": values, "output_mask": int(self.native.get_output_mask()), "sent": True}

    # -- acquisition ----------------------------------------------------------------------------------------------
    @action(name="x-cap.qcoherence.read_input_fifo.v1",
            description="Read every analog input value currently in the measurement FIFO and convert each ADC "
                        "binary value to volts (read_inputs and binary_to_volt)",
            output={
                "voltages": Field("array", items="number", unit="V",
                                  description="The FIFO values converted to volts, in FIFO order"),
                "count": Field("integer", unit="1", description="Number of values returned"),
            })
    def read_input_fifo(self):
        raw = self.native.read_inputs()
        voltages = [float(self.native.binary_to_volt(int(value))) for value in raw]
        return {"voltages": voltages, "count": len(voltages)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.qcoherence.zero_outputs.v1",
            description="Write a one-cycle 0 V command for all eight analog outputs into the FIFO and clear both "
                        "FIFOs (the native go_to_zero); not acknowledged, not a proven stop",
            output={"zeroed": Field("boolean",
                                    description="True once the native go_to_zero returned (not an output read-back)")})
    def zero_outputs(self):
        self.native.go_to_zero()
        return {"zeroed": True}

    @estop(native="go_to_zero")
    def stop(self):
        """Send go_to_zero, then refuse to certify a safe state (model review, 2026-11-05).

        go_to_zero writes an unacknowledged FIFO command whose consumer is outside the clone and clears the FIFO two
        process durations later; nothing confirms that any output reached 0 V.
        """
        self.native.go_to_zero()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "go_to_zero wrote a 0 V FIFO command without acknowledgement; the process that executes it is not in the "
            "clone and nothing confirms that the outputs reached 0 V")
