"""OpenMHS driver for gh.levylabpitt/levylab-qcodes: the LevyLab multichannel lock-in over ZMQ JSON-RPC.

A direct Driver over the upstream ``levylabinst.MCLockin:MCLockin`` QCoDeS instrument.  The upstream object adds its
per-channel parameters from a deployment ``config`` mapping labels to lead numbers (levylabinst/MCLockin.py:31-85);
those names therefore exist only after construction and cannot be declared as static family bindings.  The driver
serves the device's primary output -- the lock-in measurements -- through the catalogue's ``cap.sensing.read.v1``
class: a requested field is the upstream QCoDeS parameter name ``<label>_<X|Y|R|Theta|Mean>`` and is resolved through
the configured channel map and the native ``_get_lockin`` path (levylabinst/MCLockin.py:79-85, 210-215).

This package is model-authored and unreviewed.  It exposes no actuation, so it is R0 and has no native stop; the
channel configuration writes and the ``sweep1d`` routine are not served (see RESULT.json notes).  The fake backend is
an analytic F0 stand-in, not a recording; its readings are placeholders (# placeholder) and nothing here was run
against hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

#: The five lock-in measurement values the upstream class adds for every configured label
#: (levylabinst/MCLockin.py:79).  The order is the upstream list's order.
MEASUREMENTS = ("X", "Y", "R", "Theta", "Mean")


class MCLockin(Driver):
    device_id = "levylab-mclockin"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    native = "levylabinst.MCLockin:MCLockin"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMCLockin"}
    vendor, model = "LevyLab", "MC Lock-in"
    display_name = "LevyLab Multichannel Lock-in (MCLockin)"
    tags = ["lock-in", "multichannel", "zmq", "measurement", "sensor"]
    facts = [
        Fact("MCLockin is the LevyLab multichannel lock-in driver and talks to the instrument over ZMQ",
             source="upstream_code", ref="levylabinst/MCLockin.py:16-22"),
        Fact("The constructor takes the ZMQ server address and a channel configuration mapping each label to a lead "
             "number", source="upstream_code", ref="levylabinst/MCLockin.py:23-36"),
        Fact("Each configured label adds measurement parameters X, Y, R, Theta and Mean, named "
             "<label>_<measurement>", source="upstream_code", ref="levylabinst/MCLockin.py:79-85"),
        Fact("A measurement is read from the getResults dictionary under the key AI<lead>.Ref<ref>.<measurement>",
             source="upstream_code", ref="levylabinst/MCLockin.py:210-215"),
        Fact("get_idn reports vendor LevyLab, model MC Lock-in, serial None and firmware v2.15.4.4",
             source="upstream_code", ref="levylabinst/MCLockin.py:177-186"),
        Fact("The lock-in state parameter allows start, start sweep and stop",
             source="upstream_code", ref="levylabinst/MCLockin.py:87-92"),
        Fact("_set_state sends setState and _get_state returns the result of getStatus",
             source="upstream_code", ref="levylabinst/MCLockin.py:217-223"),
        Fact("The upstream sweep routine treats the getStatus result values idle and sweeping as its state machine",
             source="upstream_code", ref="levylabinst/MCLockin.py:258-270"),
        Fact("The ZMQInstrument constructor allows 5 s for a response by default",
             source="upstream_code", ref="levylabinst/ZMQInstrument.py:42-52"),
    ]
    # The served interface is read-only; it commands nothing that could be left energised.
    safe_state = "read-only measurement path; the driver exposes no actuation"

    @read("identity", type="string", description="Static identity declared by the upstream get_idn override")
    def identity(self):
        idn = self.native.get_idn()
        if not isinstance(idn, dict):
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_idn did not return a dictionary")
        parts = [str(idn[key]) for key in ("vendor", "model") if idn.get(key)]
        text = " ".join(parts) if parts else "unknown"
        firmware = idn.get("firmware")
        if firmware:
            text = f"{text} (firmware {firmware})"
        return text

    @read("status", type="string",
          description="The getStatus result of the lock-in; the upstream sweep code expects idle or sweeping")
    def status(self):
        return self.native._get_state()

    @action(cap="cap.sensing.read.v1",
            input={"fields": Field(
                description="Lock-in measurement fields to read, each in the upstream form <label>_<X|Y|R|Theta|Mean>; "
                            "omit to read every configured channel")},
            description="Read the current value of one or more lock-in measurement fields")
    def read_fields(self, fields=None):
        """Return the requested ``<label>_<measurement>`` fields from the configured channels.

        An omitted or empty ``fields`` list reads every measurement of every configured channel.  A field whose
        channel label or measurement is not configured is refused before any native call; a configured field for
        which the instrument has no result is a native fault, never a fabricated number.
        """
        config = self.native.config
        if not isinstance(config, dict) or not config:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the lock-in has no channel configuration")
        wanted = [str(item) for item in fields] if fields else [
            f"{label}_{measurement}" for label in config for measurement in MEASUREMENTS]
        selected = []
        for name in wanted:
            match = None
            for label in config:
                for measurement in MEASUREMENTS:
                    if name == f"{label}_{measurement}":
                        match = (label, measurement)
                        break
                if match is not None:
                    break
            if match is None:
                raise DriverFailed(
                    "MHS.DEVICE.PRECONDITION_UNMET",
                    f"field {name!r} is not a configured <label>_<measurement> lock-in parameter")
            label, measurement = match
            selected.append((name, label, measurement))
        values = {}
        for name, label, measurement in selected:
            value = self.native._get_lockin(measurement, config[label])
            if value is None:
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"getResults returned no value for field {name!r} (AI{config[label]}.Ref1.{measurement})")
            values[name] = value
        return {"values": values}

    def teardown(self):
        self.native.close()
