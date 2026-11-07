# Explicit QCoDeS Parameter drivers

`QcodesDriver` is a finite configuration helper over `PythonObjectBridge`. It imports no QCoDeS package and does no discovery, connection or native I/O during definition/construction. Backends remain explicit. Native calls retain the existing timeout, cancellation, uncertainty and safety protections.

```python
from mhs.driver import QcodesDriver, Field, Limit

class Source(QcodesDriver):
    device_id, device_kind, mode, risk = "source", "instrument", "hardware", "R2"
    parameters = {
        "frequency": Field("number", unit="Hz", writable=True,
                           limit=Limit.operator_required("Connected-load RF band is an operator decision")),
    }
    parameter_bindings = {
        "frequency": {"parameter": "channel.frequency", "get": True, "set": True,
                      "timeout_ms": 2000, "source_ref": "driver.py:20"},
    }
```

The snippet shows field syntax only; a runnable hardware driver also declares source identity, backends, native stop and acknowledged safe-state paths. A source API validator is not a safe site/load envelope. ERASynth's private pilot preserves the native 250 kHz..6 GHz domain and -60..20 dBm power domain, while site permission to enable RF is independently required.

Native parser transformations must not escape the policy check. The ERASynth adapter refuses fractional-Hz settings and power settings that change under native two-decimal dBm rendering before native I/O. It preserves unmodified fresh diagnostic readback; this input precision rule does not hide anomalous measurements.

A declaration requires an existing Field, explicit booleans `get` and `set`, a public dotted Parameter path, a 1..60000 ms timeout, and a bounded `source_ref`. This measurement profile requires `get=True`; `set` must equal `Field.writable`. Up to 128 selectors, each up to eight segments and 200 characters, are accepted. Duplicate selectors, overlapping explicit reads/writes, unknown metadata, private/indexed paths, and invalid source references are definition errors before any factory call. A same-file factory may add `factory_ref`.

Each read invokes the actual `.get()`. Each write invokes the actual `.set(value)` and waits for the whole setter, including steps/delays. The helper does not infer a sample from `cache`, `get_latest`, metadata, or a successful dispatch. An installed QCoDeS Parameter may itself implement cache-only commands; the source gate therefore requires explicit native get/set commands for the declared operations. The helper does not claim arbitrary QCoDeS subclasses are validated.

G7 checks the exact assignment in the selected native class ancestry, an imported `qcodes.parameters.Parameter`, and explicit get/set commands. A narrow same-file factory may construct one Parameter, optionally give it a literal docstring, and return that exact object. Arbitrary `add_parameter`, channel factories, nested class factories and dynamic discovery are not inferred by this MVP. Undeclared nested members, cache calls and similarly named arbitrary get/set methods are not exempt. Ordinary root-member checks remain enabled.

The accepted source grammar is intentionally finite. Each selected source-visible class has one unconditional module definition, no class decorator or metaclass keyword, at most one base, and a class body containing only methods, docstrings and literal named constants. Its effective `__init__` must be a single direct method with no replacement or decorator. Initializers contain straight-line assignments/calls only: early return, branching, exception control flow, suspension and receiver rebinding are refused. Other local initializers must delegate through an unshadowed `super().__init__`.

The checker inspects the entire selected ancestry and the complete modules that provide its constructor identities. A selected Parameter/prefix may be used only through direct Parameter invocation or `.get()`/`.set()`; aliases, tuple/list/dictionary escape, passing it to another function, cached members and visible member replacement are unsupported. The instance receiver may be passed only as the imported Parameter's `instrument`, to a verified same-file straight-line Parameter factory, or to an unshadowed `isinstance` test. Constructor/factory/class identities cannot escape into aliases, containers or decorators; visible namespace mutation and dynamic namespace access are refused. These refusals are diagnostics requiring a separately reviewed adapter, not an optimistic attempt to interpret arbitrary Python.

Identity/storage special class bindings (including slots and dynamic attribute hooks) are refused whether expressed as methods or literal constants. Explicit dynamic dunder lookup/mutation, including via `super`, is unsupported. Reflection builtins cannot be aliased or shadowed; a direct `getattr`/`setattr`/`delattr` is accepted only on a statically disjoint `self` member with a literal nonmagic attribute, preserving ordinary VISA metadata access. Staticmethod lookup must be unshadowed in both module and class namespaces.

The proof is bounded pinned declaration/lifetime evidence within that source grammar. It does not execute upstream code, prove arbitrary Python effects or inspect the installed QCoDeS implementation. The real pinned ERASynth classes and frequency factory remain the positive control; no get/set name exemption is added.

Model and runtime maps, backend maps and nested options are copied per instance. Class configuration changes cannot redirect an existing instance before lazy open. Source references are provenance evidence, not runtime readback or approval. Safety needs a separately sourced native stop and truthful confirmation; cancellation is not an RF off acknowledgment. The unsigned ERASynth R2 package remains subject to the existing human-review hardware gate. No live upstream/instrument compatibility is claimed by the synthetic native-shaped tests.

The official [QCoDeS Parameter API](https://microsoft.github.io/Qcodes/api/parameters/) documents separate get/set and cache interfaces and optional stepped/delayed setting (observed documentation version 0.63.0.dev126). The pilot does not install or pin that dependency as a tested live combination.

## Registry exemplar

`MHS/drivers/labs/qcodes__qcodes_contrib_drivers` is the family's exemplar: the Thorlabs PM100D power meter class of the contrib driver pack (R1). It binds seven explicit Parameters, writes two of them through `cap.device.configure.v1` (one `Limit.operator_required` with a site overlay example), declares the native stop `write("ABOR")` (the abort command the upstream sends before it re-initializes a measurement) and gives a source reason for every Parameter it does not serve: a `scale` without `get_parser`, a `set_cmd` without a value placeholder, a unit OpenMHS does not know, or a `MEAS:...?` query that reconfigures the meter on every read. Field types follow what `get()` returns after the upstream parsers. Most QCoDeS drivers create Parameters with `add_parameter`, which this source proof does not cover; such cards stop blocked with the G7 finding.
