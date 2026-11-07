# Security and safety policy

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

OpenMHS software sits between AI agents and equipment that can move, heat,
dispense or otherwise act on the physical world. We therefore treat **safety
defects exactly like security defects**: they are reported privately, fixed
before they are discussed in public, and disclosed with an advisory.

OpenMHS is not a safety certification and is not a safety-rated control
channel. It never replaces a hardware emergency stop, a certified safety
system or a risk assessment by the people operating the equipment.

## Reporting a vulnerability or safety defect

Use **GitHub private vulnerability reporting** on the project repository
(*Security* tab, *Report a vulnerability*). This is a placeholder until the
public repository exists; until then, do not post details in public issues,
pull requests or discussions.

Please include:

- the affected component (specification text, schema, SDK module, driver
  package, registry data, site) and version or commit;
- what an attacker, a model or a faulty driver can make happen, and on which
  kind of device (simulated, hardware, hybrid);
- a minimal reproduction (a script against a reference endpoint or a fake
  backend is ideal; never attach credentials or captured secrets);
- any mitigation you know of.

## What counts

Report privately anything that lets a request, a model, a host or a driver
get past a protection the specification promises, for example:

- a command that executes although it violates a declared limit, or limits
  that are silently ignored (arrays, nested fields, mistyped keys, unit
  confusion);
- an e-stop that does not latch, does not pre-empt running operations, or a
  reset that succeeds while it should be refused;
- an interlock, permit, approval or arming check that fails open;
- a model or agent obtaining operator authority (self-approved permits,
  reset of a latched e-stop, use of another principal's session);
- simulation reported as hardware, or hardware reported as simulation;
- classic security issues: authentication bypass, cross-origin or DNS
  rebinding attacks on local endpoints, path traversal or arbitrary file
  reads, code execution, evidence-chain forgery.

Bugs with no safety or security impact belong in the public issue tracker.

## What to expect

- Acknowledgement within 5 working days.
- An initial assessment, including whether we consider it a safety defect,
  within 10 working days.
- A fix, an advisory and credit (if you want it) in a coordinated release.
  We aim to disclose within 90 days of the report, sooner when a fix is
  available and later only by agreement with the reporter.

## Supported versions

OpenMHS is pre-release software. Only the latest `0.9.x` development line
receives fixes; there are no long-term-support releases yet.

## Scope notes

- Upstream projects described by the registry, and the vendor SDKs that
  driver packages wrap, have their own maintainers and policies. Report
  defects in them upstream; tell us as well if an OpenMHS driver or the
  registry makes the defect reachable.
- Never test against equipment you do not operate, and never disable a
  physical safety system to reproduce a report.
