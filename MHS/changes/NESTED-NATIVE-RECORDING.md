OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Record nested native operations

G6 previously recorded only calls and assignments at the root native object. Calls such as `self.native.motor.stop()` escaped its observation and failure injection. The recorder now shares one event log across nested proxies, preserves identity/aliases and cycles, records full member paths, unwraps arguments, and uses bounded cached proxies.

Compatibility tests exposed SDK data objects that must retain their native meaning. Typed Gym spaces and defining fields, enum identities and value objects such as the Cozmo angle remain values rather than arbitrary control proxies. Ordinary nested control objects remain instrumented. The change is covered by focused nested-call, boundary, cycle, cache and failure-injection cases.

A private regression of 67 affected packages passed; 65 retained their prior finding sets. Two packages legitimately lost `NO_NATIVE_CALL` after their real nested operations became visible: `rwb27/openflexure_nano_motor_controller` and `azdagkas/kinesis-piezo`. Their live gate finding digests and model-review notes were refreshed. Attribution and human review fields remain unchanged.

The later complete collection of the 582-package baseline was not a clean pass: 307 packages passed and 275 stopped at G1 because generated task metadata had changed. All 9,474 frozen inputs stayed unchanged during that run. This is not evidence of 582 successful gates or of a remaining Recorder failure. Exact card synchronization and a new complete collection are required after the current registry rebuild.

Private originals, compatibility regression and digest evidence are under `work/handoff-runs/mhs-build-20261102/development/recorder-regression/`; the complete collection is `collection-582-2-observed.json`. Production source is `sdk/src/mhs/testing/recorder.py` with its driver recorder tests.
