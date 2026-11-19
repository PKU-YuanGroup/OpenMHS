"""OpenMHS driver for gh.daylily-informatics/zebra_day: a Zebra label printer over ZPL/TCP.

A direct Driver over the upstream device class ``zebra_day.cmd_mgr:ZebraPrinter``.  The class opens one IPv4 TCP
connection per command to the printer's ZPL port, sends the command and returns the decoded reply or ``None``
(zebra_day/cmd_mgr.py:31-41).  The driver serves:

* reads: the combined status snapshot from ``get_full_status`` (identity, serial, error flags, odometer and the
  paused/paper/head/ribbon flags) and the raw configuration report from ``get_configuration``;
* one write: the raw ZPL configuration body accepted by ``set_configuration``, which the upstream follows with
  ``^XA^JUS^XZ`` to save it;
* no confirmed native stop: the clone provides no acknowledged stop method and does not document ``~JA``.
  The e-stop reports SAFE_STATE_UNREACHED with the latch held. The manual's POWER button also has delayed sleep
  and power-recovery behaviours (page 57); it is not declared as an independent emergency stop by this package.

The printer heats its printhead (the user guide warns of severe burns, page 62), so the risk is R2 even though the
upstream class itself only issues TCP text commands.  Every Fact and Limit cites the pinned clone at
d46df53ff3d9b7fbe78aef837a5299656573ba14.  This package is model-authored and unreviewed: it is checked on the fake
backend only, never on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, OutcomeUnknown, estop, read, write


class ZebraLabelPrinter(Driver):
    device_id = "zebra-label-printer"
    device_kind = "device"
    mode = "hardware"
    risk = "R2"
    native = "zebra_day.cmd_mgr:ZebraPrinter"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeZebraPrinter"}
    vendor, model = "Zebra", "ZPL label printer (TCP 9100)"
    display_name = "Zebra label printer status and configuration (zebra_day.ZebraPrinter)"
    tags = ["zebra", "label-printer", "zpl", "tcp", "printer"]
    facts = [
        Fact("send_command opens one AF_INET/SOCK_STREAM socket per call, connects to the printer address and port, "
             "sends the encoded command with sendall, reads one recv and returns the decoded reply; TimeoutError, "
             "ConnectionRefusedError and OSError are caught and become None",
             source="upstream_code", ref="zebra_day/cmd_mgr.py:31-41"),
        Fact("get_host_identification sends ~HI and parses a comma-separated reply into model, firmware, dpi, "
             "memory and options", source="upstream_code", ref="zebra_day/cmd_mgr.py:60-82"),
        Fact("get_serial_number sends ~HQSN and returns the first non-header line of the reply",
             source="upstream_code", ref="zebra_day/cmd_mgr.py:84-100"),
        Fact("get_error_status sends ~HQES and returns the first non-header line as raw, with errors and warnings "
             "left as empty lists because the flag parsing is not implemented",
             source="upstream_code", ref="zebra_day/cmd_mgr.py:102-133"),
        Fact("get_odometer sends ~HQOD and parses LABEL: and TOTAL INCHES: values into label_count and total_inches",
             source="upstream_code", ref="zebra_day/cmd_mgr.py:135-170"),
        Fact("get_host_status sends ~HS and parses paused, paper_out, head_up and ribbon_out from the first "
             "comma-separated line", source="upstream_code", ref="zebra_day/cmd_mgr.py:172-211"),
        Fact("get_configuration sends ^XA^HH^XZ; set_configuration sends the supplied configuration body and then "
             "^XA^JUS^XZ to save it", source="upstream_code", ref="zebra_day/cmd_mgr.py:43-54"),
        Fact("get_full_status queries host identification, serial number, error status, odometer and host status, "
             "and stamps the result with time.time()", source="upstream_code", ref="zebra_day/cmd_mgr.py:213-276"),
        Fact("The hardware guide says network-attached Zebra printers that obtain an IP address and accept ZPL are "
             "supported, and that USB-only printers are not communicated with",
             source="vendor_doc", ref="zebra_day/docs/hardware_config_guide.md:6-7"),
        Fact("The hardware guide's initial printer configuration list includes increasing the darkness and "
             "decreasing print speed to 2 or 3 IPS", source="vendor_doc",
             ref="zebra_day/docs/hardware_config_guide.md:64-66"),
        Fact("The ZD620/ZD420 user guide lists both shutdown and delayed sleep after a 4-9 second POWER-button hold, "
             "and automatic power-on in Power Failure Recovery Mode", source="vendor_doc",
             ref="zebra_day/docs/zd620-zd420-ug-en.pdf:57"),
        Fact("The ZD620/ZD420 user guide documents PAUSE stopping print and media movement after the current label "
             "and CANCEL cancelling the next format, or all pending formats while paused",
             source="vendor_doc", ref="zebra_day/docs/zd620-zd420-ug-en.pdf:59"),
        Fact("The ZD620/ZD420 user guide warns that the printhead may be hot and could cause severe burns",
             source="vendor_doc", ref="zebra_day/docs/zd620-zd420-ug-en.pdf:62"),
    ]
    safe_state = ("unconfirmed: the endpoint latch refuses new commands, but the upstream has no acknowledged "
                  "printer stop; queued printing and printhead heating may continue and the e-stop reports "
                  "SAFE_STATE_UNREACHED")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("status", type="object",
          description="Combined printer status from get_full_status: online, identity, serial, error flags, "
                      "odometer, paused, paper_out, ribbon_out and head_up (the wall-clock timestamp is omitted so a "
                      "read alone does not change the state hash)")
    def status(self):
        value = self.native.get_full_status()
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the printer did not answer the ZPL status queries")
        if not isinstance(value, dict):
            raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "get_full_status did not return a mapping")
        value = dict(value)
        value.pop("timestamp", None)
        return value

    @read("configuration", type="string",
          description="Raw ZPL configuration report returned by ^HH (get_configuration)")
    def configuration(self):
        value = self.native.get_configuration()
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the printer did not answer the ^HH configuration query")
        return value

    # -- the write ----------------------------------------------------------------------------------------------
    @write("configuration", type="string",
           description="Raw ZPL configuration body (for example the ^MD darkness or ^PR speed commands); the "
                       "upstream sends it and then ^XA^JUS^XZ to save it, without confirming the first write; "
                       "the receipt remains unknown. The raw body can also contain print commands.")
    def set_configuration(self, value):
        self.native.set_configuration(value)
        raise OutcomeUnknown("set_configuration discards the configuration-command result and returns only the "
                             "save-command reply; transport failures also become None, so application of the "
                             "configuration cannot be confirmed")

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Keep the latch held without inventing an undocumented ZPL stop command."""
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "the pinned upstream provides no acknowledged printer stop; the endpoint latch "
                           "does not prove that printing or heating stopped")
