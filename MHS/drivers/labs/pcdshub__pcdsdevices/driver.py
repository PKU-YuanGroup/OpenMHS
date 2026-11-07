"""OpenMHS driver for gh.pcdshub/pcdsdevices: one LCLS timing-pattern receiver (TPR) trigger channel.

The card's helper is ``OphydDriver``, but the selected class builds every signal with ``FormattedComponent``
(``pcdsdevices/tpr.py:75-132``), which the classic-Ophyd source proof does not accept.  This is therefore a direct
``Driver`` over ``pcdsdevices.tpr:TprTrigger`` (``pcdsdevices/tpr.py:60``), as ``driver-authoring.md`` permits; the
card's helper is recorded as a deviation in ``RESULT.json``.  The upstream class is concrete: it formats the
``:CHnn_`` and ``:TRGnn_`` PV names in ``__init__`` (``pcdsdevices/tpr.py:137-152``) and implements the channel and
trigger enable/disable calls (``pcdsdevices/tpr.py:154-178``).

Served interface:

* reads: the channel-enable and trigger-enable command values, the channel event rate, the derived trigger delay and
  width, and the channel description label.  Every read is a ``Signal.get`` without ``use_monitor`` (the TPR
  Components declare no ``auto_monitor``); ``delay_ns`` and ``width_ns`` are computed by the upstream from the tick
  and tap PVs (``pcdsdevices/tpr.py:24-31``), not read back from the setpoint, so after a write they show what the
  IOC derived (whole ticks and taps), not the written number.
* writes: trigger delay and width in ns.  ``ns_delay.put`` and ``width.put`` write only their last member, the
  setpoint PV (``_put_last``, ``pcdsdevices/tpr.py:34-36, 95-101, 117-123``), through ``utils.set_many``, which logs
  and drops an exception raised by the member's ``set`` and then returns a finished Status
  (``pcdsdevices/utils.py:556-579``).  The driver therefore calls ``set`` on that same setpoint member
  (``delay_setpoint`` or ``width_setpoint``) with a 5 s timeout and waits for its Status, so a failed set is a failed
  write (model review).  No text of the clone states a numeric range for either one, so both are
  ``Limit.operator_required``: the runtime refuses every write until the site overlay supplies the range.
* one extension action, ``x-cap.pcdshub.tpr_trigger.v1``: enable or disable the channel, the trigger, or both,
  through the upstream ``enable_ch``/``disable_ch``/``enable_trg``/``disable_trg`` methods
  (``pcdsdevices/tpr.py:164-178``).  No catalogue class fits a trigger-channel enable/disable selection: the closest
  one, ``cap.actuation.gpio.v1``, models a general-purpose output pin with a caller-supplied pin number, which this
  fixed-channel timing receiver does not have.  The package requests the extension in ``RESULT.json``.
* the native stop is ``TprTrigger.disable()`` (``pcdsdevices/tpr.py:159-162``), a plain ``put(0)`` on the channel
  and trigger enable commands with no wait or callback (``pcdsdevices/tpr.py:168-178``); the e-stop then reads
  both enable commands back and reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` unless both read 0 (model review).  The
  readback shows the IOC's enable records, not the absence of trigger pulses.  The risk is R1 (the card's floor):
  this is a TTL timing trigger, not a laser, high-voltage contact or high-force actuator, and the class has no
  independent hardware e-stop text; what the trigger fires downstream decides the real hazard of a deployment.

The fake is an in-memory stand-in shaped like the upstream class; the hardware factory imports ``pcdsdevices.tpr``
only when an operator opens the hardware backend.  This package is model-authored and unreviewed (``reviewed_by`` is
null); it has been checked on the fake backend only, and no hardware has been attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_SOURCE = "pcdsdevices/tpr.py"
_SIGNAL = "pcdsdevices/signal.py"
_UTILS = "pcdsdevices/utils.py"

#: seconds the driver lets ophyd's set of one setpoint PV run (passed to Signal.set) and waits for its Status
_SET_TIMEOUT_S = 5.0

#: The one extension capability of this package.
TRIGGER = "x-cap.pcdshub.tpr_trigger.v1"

#: No line of the clone states a trigger-delay range: ns_delay is a derived signal over delay_ticks, delay_taps and
#: delay_setpoint.  The site supplies the ns range of its timing system.
DELAY_LIMIT = Limit.operator_required(
    "no line of the clone states a trigger-delay range: ns_delay is derived from delay_ticks and delay_taps "
    "(pcdsdevices/tpr.py:95-101) and neither the ticks/taps PV limits nor a delay range is written in the clone; the "
    "site supplies the allowed delay range in ns")

#: No line of the clone states a trigger-width range: width is a derived signal over width_ticks and width_setpoint.
WIDTH_LIMIT = Limit.operator_required(
    "no line of the clone states a trigger-width range: width is derived from width_ticks and width_setpoint "
    "(pcdsdevices/tpr.py:117-123) and neither PV limit nor a width range is written in the clone; the site supplies "
    "the allowed width range in ns")


class TprTriggerDriver(Driver):
    device_id = "tpr-trigger"
    device_kind = "io.digital"
    mode = "hardware"
    risk = "R1"
    native = "pcdsdevices.tpr:TprTrigger"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTprTrigger"}
    vendor = "SLAC PCDS"
    model = "LCLS timing-pattern receiver (TPR) trigger channel"
    display_name = "LCLS TPR trigger channel (pcdsdevices.TprTrigger)"
    tags = ["ophyd", "epics", "timing", "trigger", "lcls"]
    safe_state = ("trigger channel and trigger output disabled: disable_ch and disable_trg put 0 to the enable "
                  "commands, and both read back 0 before the stop is reported; the readback is the IOC's enable "
                  "records, not a measured absence of pulses, and equipment fired by other channels is not stopped")
    facts = [
        Fact("TprTrigger is an ophyd BaseInterface/Device for an individual TPR trigger", source="upstream_code",
             ref=f"{_SOURCE}:60-63"),
        Fact("The TprTrigger channel argument is an integer from 0 through 11", source="upstream_code",
             ref=f"{_SOURCE}:71-72"),
        Fact("TimingMode has the members LCLS1 = 1 and LCLS2 = 2", source="upstream_code", ref=f"{_SOURCE}:19-21"),
        Fact("TprTrigger formats the channel as :CHnn_ and the trigger as :TRGnn_ and rejects any other timing mode",
             source="upstream_code", ref=f"{_SOURCE}:137-152"),
        Fact("enable_ch_cmd and enable_trg_cmd are EpicsSignal channel-enable and trigger-enable commands",
             source="upstream_code", ref=f"{_SOURCE}:124-131"),
        Fact("enable() calls enable_ch() then enable_trg(); disable() calls disable_ch() then disable_trg()",
             source="upstream_code", ref=f"{_SOURCE}:154-162"),
        Fact("enable_ch and enable_trg put 1; disable_ch and disable_trg put 0", source="upstream_code",
             ref=f"{_SOURCE}:164-178"),
        Fact("ns_delay is a MultiDerivedSignal over delay_ticks, delay_taps and delay_setpoint with the doc "
             "'Get/set trigger delay in ns'", source="upstream_code", ref=f"{_SOURCE}:95-101"),
        Fact("width is a MultiDerivedSignal over width_ticks and width_setpoint with the doc "
             "'Get/set trigger width in nsec'", source="upstream_code", ref=f"{_SOURCE}:117-123"),
        Fact("TPR_TICK_NS is 70 / 13, from the 1.3 GHz phase-reference line divided by 7, and TPR_TAP_NS is 0.08",
             source="upstream_code", ref=f"{_SOURCE}:13-16"),
        Fact("The delay read is delay_ticks times TPR_TICK_NS plus delay_taps times TPR_TAP_NS, and the width read "
             "is width_ticks times TPR_TICK_NS", source="upstream_code", ref=f"{_SOURCE}:24-31"),
        Fact("_put_last writes the value only to the last signal of a MultiDerivedSignal", source="upstream_code",
             ref=f"{_SOURCE}:34-36"),
        Fact("delay_setpoint is the TDES EpicsSignal and width_setpoint the TWID EpicsSignal of the trigger",
             source="upstream_code", ref=f"{_SOURCE}:92-113"),
        Fact("AggregateSignal.get calls get on every member signal and recalculates the value", source="upstream_code",
             ref=f"{_SIGNAL}:229-241"),
        Fact("MultiDerivedSignal.put calls set, and set passes the calculate_on_put mapping to utils.set_many",
             source="upstream_code", ref=f"{_SIGNAL}:696-750"),
        Fact("set_many logs an exception raised by a member set, re-raises it only with raise_on_set_failure, and "
             "returns a finished Status when no member set started", source="upstream_code",
             ref=f"{_UTILS}:556-579"),
        Fact("eventrate is an EpicsSignalRO for the channel event rates", source="upstream_code",
             ref=f"{_SOURCE}:86"),
        Fact("label is an EpicsSignal for the channel description", source="upstream_code", ref=f"{_SOURCE}:87"),
    ]

    # -- reads -----------------------------------------------------------------------------------------------
    @read("channel_enabled", type="boolean",
          description="True when the channel enable command value is 1 (from enable_ch_cmd)")
    def channel_enabled(self):
        return bool(self.native.enable_ch_cmd.get())

    @read("trigger_enabled", type="boolean",
          description="True when the trigger enable command value is 1 (from enable_trg_cmd)")
    def trigger_enabled(self):
        return bool(self.native.enable_trg_cmd.get())

    @read("eventrate", description="Channel event rate as read from the eventrate signal; the source states no unit")
    def eventrate(self):
        return self.native.eventrate.get()

    @read("delay_ns", unit="ns", description="Trigger delay in nanoseconds from the ns_delay derived signal")
    def delay_ns(self):
        return self.native.ns_delay.get()

    @read("width_ns", unit="ns", description="Trigger width in nanoseconds from the width derived signal")
    def width_ns(self):
        return self.native.width.get()

    @read("label", type="string", description="Channel description from the label signal")
    def label(self):
        return self.native.label.get()

    # -- writes ----------------------------------------------------------------------------------------------
    @write("delay_ns", unit="ns", limit=DELAY_LIMIT,
           description="Set the trigger delay setpoint (delay_setpoint, the member ns_delay.put writes); the read is "
                       "derived from ticks and taps")
    def set_delay_ns(self, value):
        # ns_delay.put writes only delay_setpoint (_put_last) but drops a failed member set inside utils.set_many;
        # setting the member directly keeps the failure (model review).
        self.native.delay_setpoint.set(value, timeout=_SET_TIMEOUT_S).wait(timeout=_SET_TIMEOUT_S + 1.0)

    @write("width_ns", unit="ns", limit=WIDTH_LIMIT,
           description="Set the trigger width setpoint (width_setpoint, the member width.put writes); the read is "
                       "derived from ticks")
    def set_width_ns(self, value):
        # width.put writes only width_setpoint (_put_last); see set_delay_ns.
        self.native.width_setpoint.set(value, timeout=_SET_TIMEOUT_S).wait(timeout=_SET_TIMEOUT_S + 1.0)

    # -- actions ---------------------------------------------------------------------------------------------
    @action(name=TRIGGER,
            description="Enable or disable the configured TPR channel, its trigger output, or both",
            input={
                "enabled": Field("boolean", description="True enables, False disables"),
                "scope": Field("string", enum=["channel", "trigger", "both"],
                               description="Which enable command to change: channel, trigger or both"),
            },
            output={
                "channel_enabled": Field("boolean",
                                         description="Channel enable command value observed after the change"),
                "trigger_enabled": Field("boolean",
                                         description="Trigger enable command value observed after the change"),
            })
    def set_trigger_enabled(self, enabled, scope):
        if scope in ("channel", "both"):
            if enabled:
                self.native.enable_ch()
            else:
                self.native.disable_ch()
        if scope in ("trigger", "both"):
            if enabled:
                self.native.enable_trg()
            else:
                self.native.disable_trg()
        return {"channel_enabled": bool(self.native.enable_ch_cmd.get()),
                "trigger_enabled": bool(self.native.enable_trg_cmd.get())}

    # -- safety ----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: TprTrigger.disable(), then a readback of both enable commands.

        disable() is a plain put(0) on the channel and trigger enable commands with no wait or callback
        (pcdsdevices/tpr.py:159-178); the stop is reported only when both commands read back 0 (model review).
        """
        self.native.disable()
        channel, trigger = self.native.enable_ch_cmd.get(), self.native.enable_trg_cmd.get()
        if channel != 0 or trigger != 0:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"after disable() the enable commands read channel={channel!r}, trigger={trigger!r}")
