OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Explicit pinned Python source surfaces

This change adds source-only selectors for upstream modules and filenames that
cannot be represented by an ordinary import path:
`pyfile:path.py#Class` and `pyfile:path.py#*`. Existing dotted class selectors
retain their existing resolution behavior. No source selector is a runtime
factory, and upstream code is parsed rather than imported.

Explicit selectors read an exact regular blob at the pinned Git commit. A missing
pin or blob, symlink, gitlink, wrong card file/line, or absent class fails closed.
Synthetic unpinned tutorials remain supported. The module form checks direct
function membership, fake callable signatures and actual recorded argument
binding; imported, conditional, overwritten and dynamic functions cannot supply
invented members. Fake attribute/call catch-alls and replacement signature metadata
do not bypass the check. Standalone Python 2 print rewrites retain a legacy warning;
other rewritten source is not used to establish signatures.

Registry schemas use a source-specific path rule allowing spaces, leaving package
paths unchanged. Override validation, task-card selection, pinned entry validation
and recon emission share the selector rules. Serial/SCPI explicit selectors are
checked for source identity in addition to their existing transport checks.

Development validation was performed in an isolated copy, not in the live
registry/package tree. New tests cover exact pin/file/line selection, no upstream
execution, legacy source, signatures, missing/reassigned/dynamic members, symlink
and gitlink refusal, card errors and recon emission. Existing driver, isolation,
build, family, triage and task-card regressions were also run; the private import
manifest records exact commands, logs, hashes and validation scope. Read-only probes
resolved all four design cases at their existing pins: as7265x, Keithley 2230G,
Keithley 2200 and Thorlabs TLBC2. All 17 as7265x fake function signatures matched
the parsed source without executing either module.

This does not accept those packages or apply their registry overrides. as7265x
still needs its separate integration-range citation and I2C stop/deadline review;
the three recon cases still need actual package authoring and source review.
Imported class aliases/external-file inherited members, async/decorated/dynamic
module functions, module data objects and factory-built fake namespaces are outside
the first explicit-selector scope. Gitlink traversal and simulation timing are
separate changes. No hardware was run and no human review was claimed or signed.
SDK unit-test success alone is not a passing corpus sweep or physical validation.
