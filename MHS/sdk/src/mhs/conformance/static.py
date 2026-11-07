"""Static conformance checks: manifest-only tests that never command the device.

They read the device manifests the endpoint publishes and the capability
catalogue (:mod:`mhs.catalog`, the same resolver the runtime and the registry
use), so a driver's declared contract is checked before any command is sent:

* ``TCON-001`` -- the claimed profile matches the subject kind and every
  device mode (CON-004, CON-005);
* ``CAP-035`` -- every bound class is in the catalogue or an extension
  namespace;
* ``CAP-017`` -- no binding lowers its class risk floor;
* ``CAP-016`` -- binding schemas do not drift from their class (advisory in
  this suite version: the reference fixtures still drift until their class
  realignment);
* ``TCAP-002`` -- the bound resource kind is one the class accepts (advisory,
  ``MHS.CAPABILITY.KIND_MISMATCH``);
* ``SAFE-045`` -- hardware R2+ devices declare an independent hardware e-stop
  (``kind: hardware``, or ``kind: both`` with a ``physical_ref``) or a
  non-empty ``achieved_by``; a ``software`` e-stop is never a stop path, with
  or without a ``physical_ref``;
* ``SAFE-029`` -- every ``safe_state.achieved_by`` entry names a bound,
  permit-free capability, and hardware devices declare at least one;
* ``CON-031`` / ``CON-032`` -- suite self-checks run after every other test:
  hardware was not actuated without ``allow_actuation`` and e-stops went only
  to ``software``/``both`` e-stops.  In-process the harness blocks hardware
  write/invoke calls at the bridge, and any call it saw (blocked or not)
  fails ``CON-031``, naming the test; over any transport a command the
  endpoint dispatched to hardware instead of refusing fails it too.
"""

from __future__ import annotations

from typing import Any, Mapping

from mhs.conformance.model import TestOutcome

__all__ = [
    "achieved_by",
    "con_031",
    "con_032",
    "hardware_devices",
    "static_cap_016",
    "static_cap_017",
    "static_cap_035",
    "static_kind",
    "static_profile",
    "static_safe_029",
    "static_safe_045",
]

_RISK = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
HARDWARE_MODES = ("hardware", "hybrid")


def _catalog():
    try:
        from mhs import catalog

        return catalog
    except Exception:  # noqa: BLE001
        return None


def hardware_devices(ctx: Any) -> list[dict[str, Any]]:
    return [manifest for manifest in ctx.devices if manifest.get("mode") in HARDWARE_MODES]


def achieved_by(manifest: Mapping[str, Any]) -> list[str]:
    safe_state = (manifest.get("safety") or {}).get("safe_state") or {}
    return [str(item) for item in safe_state.get("achieved_by") or []]


def _short(items: list[str], limit: int = 6) -> str:
    text = "; ".join(items[:limit])
    if len(items) > limit:
        text += f"; ... ({len(items) - limit} more)"
    return text


# ---------------------------------------------------------------------------
# CL0
# ---------------------------------------------------------------------------


def static_profile(ctx: Any) -> TestOutcome:
    """TCON-001: profile vs subject kind (CON-004) and vs every device mode / manifest claim (CON-005)."""

    profile = ctx.profile
    problems: list[str] = []
    for manifest in ctx.devices:
        device_id = manifest.get("device_id")
        mode = str(manifest.get("mode"))
        if profile == "MHS-Device" and mode not in HARDWARE_MODES:
            problems.append(
                f"{device_id} is {mode}: MHS-Device needs hardware or hybrid devices (a fake or simulated "
                "backend gives contract_checked evidence, never an MHS-Device level)"
            )
        if profile == "MHS-Sim" and mode == "hardware":
            problems.append(f"{device_id} is hardware: test it under MHS-Device, not MHS-Sim")
        claim = manifest.get("conformance")
        declared = claim.get("profile") if isinstance(claim, Mapping) else None
        if declared and declared != profile:
            problems.append(f"{device_id} declares conformance.profile {declared!r}, not {profile!r} (CON-005)")
    if problems:
        return TestOutcome.failed(_short(problems))
    modes = sorted({str(manifest.get("mode")) for manifest in ctx.devices})
    return TestOutcome.passed(f"endpoint subject under {profile}; device modes {', '.join(modes)}")


def static_cap_035(ctx: Any) -> TestOutcome:
    catalog = _catalog()
    if catalog is None:
        return TestOutcome.skipped("capability catalogue unavailable")
    unknown: list[str] = []
    count = 0
    for binding in ctx.bindings:
        count += 1
        capability_id = binding.capability_id
        if catalog.is_extension(capability_id):
            continue
        if catalog.get(capability_id) is None:
            unknown.append(f"{binding.device_id}: {capability_id} is neither a catalogue class nor an "
                           "extension (x-cap.<vendor>.* / cap.x.<vendor>.*)")
    if unknown:
        return TestOutcome.failed(_short(unknown), mhs_code="MHS.CAPABILITY.UNKNOWN")
    return TestOutcome.passed(f"{count} binding(s) name catalogue classes or extension namespaces")


def static_cap_017(ctx: Any) -> TestOutcome:
    problems: list[str] = []
    checked = 0
    for binding in ctx.bindings:
        entry = binding.class_entry
        if not entry:
            continue
        checked += 1
        floor = str(entry.get("risk_class") or "R0")
        risk = str((binding.manifest.get("safety") or {}).get("risk_class") or "R0")
        if _RISK.get(risk, 0) < _RISK.get(floor, 0):
            problems.append(f"{binding.device_id}: {binding.capability_id} has class risk floor {floor} but the "
                            f"device declares {risk}")
    if problems:
        return TestOutcome.failed(_short(problems))
    if not checked:
        return TestOutcome.passed("no catalogue class is bound (extensions only)")
    return TestOutcome.passed(f"{checked} catalogue binding(s) respect their class risk floor")


def _resolve(binding: Any) -> Any:
    catalog = _catalog()
    if catalog is None or binding.class_entry is None:
        return None
    manifest = binding.manifest
    resources = {item.get("resource_id"): item for item in manifest.get("resources") or [] if isinstance(item, Mapping)}
    resource = resources.get(binding.capability.get("resource")) or {}
    try:
        return catalog.resolve_binding(
            binding.capability_id, binding.capability.get("input_schema"), binding.capability.get("output_schema"),
            resource.get("kind"), manifest.get("mode"), state_schema=resource.get("state_schema"),
            binding_limits=binding.capability.get("limits"), binding_verb=binding.capability.get("verb"),
        )
    except Exception:  # noqa: BLE001 - a resolver error is reported by CAP-035/ADPT-005
        return None


def static_cap_016(ctx: Any) -> TestOutcome:
    problems: list[str] = []
    checked = 0
    for binding in ctx.bindings:
        effective = _resolve(binding)
        if effective is None:
            continue
        checked += 1
        for drift in effective.drift:
            problems.append(f"{binding.device_id}: {binding.capability_id} {drift.kind} at {drift.path}")
    if problems:
        return TestOutcome.failed(_short(problems), mhs_code="MHS.INTERNAL.SCHEMA_DRIFT")
    return TestOutcome.passed(f"{checked} catalogue binding(s) do not widen or drift from their class")


def static_kind(ctx: Any) -> TestOutcome:
    problems: list[str] = []
    checked = 0
    for binding in ctx.bindings:
        effective = _resolve(binding)
        if effective is None:
            continue
        checked += 1
        if not effective.kind_ok:
            resources = {item.get("resource_id"): item for item in binding.manifest.get("resources") or []
                         if isinstance(item, Mapping)}
            kind = (resources.get(binding.capability.get("resource")) or {}).get("kind")
            problems.append(f"{binding.device_id}: {binding.capability_id} bound to resource kind {kind!r}")
    if problems:
        return TestOutcome.failed(_short(problems), mhs_code="MHS.CAPABILITY.KIND_MISMATCH")
    return TestOutcome.passed(f"{checked} catalogue binding(s) target a resource kind their class accepts")


# ---------------------------------------------------------------------------
# CL3 static safety
# ---------------------------------------------------------------------------


def safe_045_required(ctx: Any) -> bool:
    return any(_RISK.get(str((manifest.get("safety") or {}).get("risk_class")), 0) >= 2
               for manifest in hardware_devices(ctx))


def static_safe_045(ctx: Any) -> TestOutcome:
    targets = [manifest for manifest in hardware_devices(ctx)
               if _RISK.get(str((manifest.get("safety") or {}).get("risk_class")), 0) >= 2]
    if not targets:
        return TestOutcome.skipped("no hardware or hybrid device at R2/R3; SAFE-045 is not applicable")
    problems: list[str] = []
    for manifest in targets:
        estop = (manifest.get("safety") or {}).get("estop") or {}
        kind = str(estop.get("kind") or "software")
        physical = str(estop.get("physical_ref") or "").strip()
        if kind == "hardware" or (kind == "both" and physical) or achieved_by(manifest):
            continue
        what = (f"a {kind!r} e-stop (a physical_ref does not make a software e-stop a hardware stop)"
                if kind == "software" else f"a {kind!r} e-stop without a physical_ref")
        problems.append(f"{manifest.get('device_id')}: {manifest.get('safety', {}).get('risk_class')} hardware "
                        f"device with {what} and an empty safe_state.achieved_by")
    if problems:
        return TestOutcome.failed(_short(problems))
    return TestOutcome.passed(f"{len(targets)} hardware R2+ device(s) declare an independent stop path")


def static_safe_029(ctx: Any) -> TestOutcome:
    problems: list[str] = []
    for manifest in ctx.devices:
        device_id = manifest.get("device_id")
        bound = {str(capability.get("capability_id")): capability for capability in manifest.get("capabilities") or []
                 if isinstance(capability, Mapping)}
        actions = achieved_by(manifest)
        if manifest.get("mode") in HARDWARE_MODES and not actions:
            problems.append(f"{device_id}: hardware device with an empty safe_state.achieved_by")
        for action in actions:
            capability = bound.get(action)
            if capability is None:
                problems.append(f"{device_id}: achieved_by names {action}, which the device does not bind")
                continue
            binding = ctx.binding(str(device_id), action)
            if (binding is not None and binding.requires_permit) or capability.get("requires_permit"):
                problems.append(f"{device_id}: achieved_by action {action} is permit-gated (SAFE-029 exempts it)")
    if problems:
        return TestOutcome.failed(_short(problems))
    return TestOutcome.passed(f"safe_state.achieved_by resolves on {len(ctx.devices)} device(s)")


# ---------------------------------------------------------------------------
# suite self-checks (run after every other test)
# ---------------------------------------------------------------------------


def con_031(ctx: Any) -> TestOutcome:
    targets = hardware_devices(ctx)
    log = ctx.run_log
    if not targets:
        return TestOutcome.passed("no hardware or hybrid device: the actuation gate was not engaged")
    ids = sorted(str(manifest.get("device_id")) for manifest in targets)
    if ctx.options.allow_actuation:
        return TestOutcome.passed(f"operator allowed actuation of {', '.join(ids)} (--allow-actuation); "
                                  "actuating tests ran")
    calls = [record for harness in log.harnesses for record in harness.actuations() if record.device_id in ids]
    dispatched = [item for item in log.hardware_dispatches if item[1] in ids]
    withheld = [item for item in log.withheld if item[1] in ids]
    if calls or dispatched:
        problems = []
        blocked = [record for record in calls if record.faulted == "blocked"]
        reached = [record for record in calls if record.faulted != "blocked"]
        if blocked:
            listing = ", ".join(f"{record.test_id or '?'}: {record.method}({record.capability_id})"
                                for record in blocked[:5])
            problems.append(f"the endpoint dispatched {len(blocked)} command(s) to the hardware bridge instead "
                            f"of refusing them; the harness blocked them before the driver: {listing}")
        if reached:
            listing = ", ".join(f"{record.test_id or '?'}: {record.method}({record.capability_id})"
                                for record in reached[:5])
            problems.append(f"{len(reached)} bridge write/invoke call(s) reached hardware without "
                            f"--allow-actuation: {listing}")
        if dispatched:
            listing = ", ".join(f"{test_id}: {capability_id} on {device_id} ({status})"
                                for test_id, device_id, capability_id, status in dispatched[:5])
            problems.append(f"{len(dispatched)} command(s) sent by negative tests were dispatched to hardware "
                            f"instead of refused: {listing}")
        return TestOutcome.failed("; ".join(problems))
    unproven = sorted({f"{device_id}:{name}" for harness in log.harnesses for device_id in ids
                       for name in (getattr(harness, "uninstrumented_for", None) or (lambda _device: []))(device_id)})
    if unproven:
        return TestOutcome.skipped(
            "inconclusive: the call recorder could not instrument " + ", ".join(unproven)
            + ", so zero bridge write/invoke calls on hardware cannot be shown (CON-031)")
    observed = ("the call recorder saw 0 bridge write/invoke calls" if log.harnesses
                else "bridge calls are not observable over this transport, so negative tests were not sent "
                     "and no command was dispatched")
    detail = (f"actuation refused for {', '.join(ids)}: {len(log.gated)} actuating or negative test(s) "
              f"skipped; {observed}")
    if withheld:
        detail += (f"; the send guard withheld {len(withheld)} command(s): "
                   + ", ".join(f"{test_id}: {what}" for test_id, _device, what in withheld[:5]))
    return TestOutcome.passed(detail)


def con_032(ctx: Any) -> TestOutcome:
    log = ctx.run_log
    bad = [(device_id, kind) for device_id, kind in log.estop_targets + log.reset_targets
           if kind not in ("software", "both")]
    if bad:
        return TestOutcome.failed("mhs.safety.estop/reset was sent to hardware-only e-stops: "
                                  + ", ".join(f"{device} ({kind})" for device, kind in bad))
    skipped = sorted(set(log.estop_withheld))
    detail = (f"mhs.safety.estop sent {len(log.estop_targets)} time(s) and mhs.safety.reset "
              f"{len(log.reset_targets)} time(s), only to software/both e-stops")
    if skipped:
        detail += f"; withheld from hardware-only e-stops of {', '.join(skipped)} (a human exercises those)"
    return TestOutcome.passed(detail)
