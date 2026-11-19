"""Hardware backend: open a Rigol MSO/DSO oscilloscope through the upstream SkippyMCP Scope class.

Used only with ``backend="hardware"`` and ``allow_hardware=True``, an operator decision.  The upstream package is
imported inside :func:`connect` (and inside the facade methods), so the fake backend and the acceptance gate never
import or run the clone.  Nothing in this package ran against an instrument.

Options of the backend:

* ``resource_name`` (required): a VISA resource name the upstream transport accepts, e.g.
  ``TCPIP0::192.168.1.50::INSTR`` (pyvisa_transport.py:36-53);
* ``timeout_ms`` (default 10000): the per-exchange timeout passed to the transport and restored by the Scope
  (pyvisa_transport.py:36-53, session.py:18-35);
* ``reset_on_connect`` (default true): the upstream ``establish`` sends ``*RST`` and ``*CLS`` after selecting the
  dialect (session.py:30-35, scope.py:93-95).  Set it false only when the operator wants to keep the setup.

The driver calls the upstream ``Scope`` method names with plain values.  The facade below converts those values to
the upstream dataclasses and enums; it is an adapter in the production path, not a second device interface.
"""


def connect(resource_name, *, timeout_ms=10000, reset_on_connect=True):
    from skippy_mcp.driver.session import establish
    from skippy_mcp.transport.pyvisa_transport import PyVisaTransport

    transport = PyVisaTransport.open(resource_name, timeout_ms=int(timeout_ms))
    scope = establish(
        transport,
        reset_on_connect=bool(reset_on_connect),
        default_timeout_ms=int(timeout_ms),
    )
    return _ScopeFacade(scope)


class _ScopeFacade:
    """Adapt plain driver values to the upstream typed Scope calls (scope.py:102-175, 257-265)."""

    def __init__(self, scope):
        self._scope = scope

    # -- identity / lifecycle -----------------------------------------------------------------------------------
    def identify(self):
        return self._scope.identify()

    def reset(self):
        return self._scope.reset()

    def close(self):
        return self._scope.close()

    # -- analog channel -----------------------------------------------------------------------------------------
    def configure_channel(self, values):
        from skippy_mcp.core.models import ChannelConfig

        coupling = values.get("coupling")
        bandwidth = values.get("bandwidth_limit")
        config = ChannelConfig(
            channel=int(values["channel"]),
            enabled=values.get("enabled"),
            scale_v_per_div=values.get("scale_v_per_div"),
            offset_v=values.get("offset_v"),
            coupling=None if coupling is None else _COUPLINGS[str(coupling)],
            bandwidth_limit=None if bandwidth is None else _BANDWIDTHS[str(bandwidth)],
            probe_ratio=values.get("probe_ratio"),
        )
        return self._scope.configure_channel(config)

    # -- trigger ------------------------------------------------------------------------------------------------
    def configure_trigger(self, values):
        from skippy_mcp.core.models import TriggerConfig

        slope = values.get("slope")
        config = TriggerConfig(
            mode=_TRIGGER_MODES[str(values["mode"])],
            source=values.get("source"),
            slope=None if slope is None else _TRIGGER_SLOPES[str(slope)],
            level_v=values.get("trigger_level_v"),
        )
        return self._scope.configure_trigger(config)

    # -- acquisition --------------------------------------------------------------------------------------------
    def capture(self, action):
        return self._scope.capture(_CAPTURE_ACTIONS[str(action)])

    # -- measurement --------------------------------------------------------------------------------------------
    def measure(self, mtype, source, source2=None):
        return self._scope.measure(_MEASUREMENT_TYPES[str(mtype)], source, source2)

    # -- raw escape hatch ---------------------------------------------------------------------------------------
    def raw_scpi(self, command, expect_response=None):
        return self._scope.raw_scpi(command, expect_response)


def _couplings():
    from skippy_mcp.core.enums import Coupling

    return {"dc": Coupling.DC, "ac": Coupling.AC, "gnd": Coupling.GND}


def _bandwidths():
    from skippy_mcp.core.enums import BandwidthLimit

    return {"off": BandwidthLimit.OFF, "20m": BandwidthLimit.MHZ_20}


def _trigger_modes():
    from skippy_mcp.core.enums import TriggerMode

    return {"edge": TriggerMode.EDGE, "pulse": TriggerMode.PULSE, "pattern": TriggerMode.PATTERN}


def _trigger_slopes():
    from skippy_mcp.core.enums import TriggerSlope

    return {"rising": TriggerSlope.RISING, "falling": TriggerSlope.FALLING, "either": TriggerSlope.EITHER}


def _capture_actions():
    from skippy_mcp.core.enums import CaptureAction

    return {"run": CaptureAction.RUN, "stop": CaptureAction.STOP, "single": CaptureAction.SINGLE}


def _measurement_types():
    from skippy_mcp.core.enums import MeasurementType

    return {
        "vpp": MeasurementType.VPP,
        "vrms": MeasurementType.VRMS,
        "freq": MeasurementType.FREQ,
        "period": MeasurementType.PERIOD,
        "duty": MeasurementType.DUTY,
        "rise": MeasurementType.RISE,
        "fall": MeasurementType.FALL,
        "delay": MeasurementType.DELAY,
        "phase": MeasurementType.PHASE,
    }


class _LazyMap:
    """A map that builds the upstream enum names only when the hardware path first indexes it."""

    def __init__(self, factory):
        self._factory = factory
        self._map = None

    def __getitem__(self, key):
        if self._map is None:
            self._map = self._factory()
        return self._map[key]


#: Enum-name maps, built on the hardware path only (the fake and the gate never import this module).
_COUPLINGS = _LazyMap(_couplings)
_BANDWIDTHS = _LazyMap(_bandwidths)
_TRIGGER_MODES = _LazyMap(_trigger_modes)
_TRIGGER_SLOPES = _LazyMap(_trigger_slopes)
_CAPTURE_ACTIONS = _LazyMap(_capture_actions)
_MEASUREMENT_TYPES = _LazyMap(_measurement_types)
