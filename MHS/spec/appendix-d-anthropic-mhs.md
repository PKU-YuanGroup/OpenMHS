# MHS-D — The Anthropic research preview: what is public, what it describes, and how this specification relates

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

| Field | Value |
|---|---|
| Document | MHS-D (informative) |
| Status | Informative appendix to OpenMHS 0.9 |
| Layer | appendix: informative; the only document of the set that cites Anthropic's material ([profiles.md](profiles.md) §2) |
| Sources | Anthropic announcement, 27 Aug 2026; modelhardwarestandard.com (cited as a source only); two Anthropic videos; partner write-ups (Tetsuwan, QuEra, CMU) |
| Verified | 2026-10-20, against the pages fetched while the specification was drafted; the source notes are kept with the project's private research material |

This appendix summarises the public description of Anthropic's Model Hardware
Standard (MHS) research preview and states precisely how this document set
relates to it. It is **informative**: it creates no conformance obligation. The
quotations of Anthropic material in this appendix are short citations for commentary
and comparison; they remain the property of their owners and are not licensed by this
project (`LICENSE-docs`). [00-architecture.md](00-architecture.md) §1.4 repeats the
relationship in the overview.

## 1. Status and publication boundary

Anthropic describes MHS as "a shared specification for AI agents to safely
operate physical devices" and opened it as a **research preview** to selected
labs and manufacturers in August 2026, "ahead of making the standard open
source"[A]. Access is "by application during the preview"[L]. The standard is
model-agnostic and "any agent harness can access it using standard protocols,
such as the Model Context Protocol"[A].

Verified from the public sources: **no wire format, manifest schema, message
set, reference SDK, MCP tool naming, receipt/evidence format, error taxonomy,
conformance levels, simulation story, versioning policy, licence, governance or
open-source date has been published**. Partner write-ups add detail but are
descriptions of deployments, not specifications. Accordingly, OpenMHS 0.9 is an
independent open specification, not a reimplementation or a compatible dialect
of the preview.

## 2. How the preview describes MHS

The announcement describes a **standardized driver**: "software that translates
between a computer's operating system and a hardware device", using "a simple
set of primitives — commands like 'read' … or 'write'"[A]. Devices are
"discoverable in a standard format, so that devices and agents can find each
other and communicate across networks without needing a bespoke 'translator'
program"[A].

Each driver carries **natural-language tags**. Users write them directly, or "by
chatting to an agent that interviews them about their hardware setup". "With the
information from these tags, the MHS driver then automatically produces a
**reference file** with information about a device's general characteristics,
such as what it can measure, what can be adjusted, and what safety limits will be
enforced"[A]. The stated purpose is to make tacit physical knowledge — e.g. the
weight of a robot arm — machine-readable.

Control is provided through **three mechanisms**: "MCP, the command line
interface, and code files (APIs). These work together to enable orchestration
across multiple devices via a single line of code"[A]. For long-running work the
agent "can chain together driver commands from one or more devices in code
files", so devices can run without the model reasoning at every step[A]. In the
documented behaviour, an agent explores a device, then packages what it learned
into a deterministic script so later runs need no per-step reasoning[A][B].

The **origin** is a collaboration between Alek Kemeny (Anthropic Beneficial
Deployments) and Arco Bast (HHMI Janelia). For his multiphoton imaging rig, Bast
"developed a shared memory dictionary that enabled the instruments to
communicate with one another at memory speed"[A]. The short film describes
devices communicating "at bare metal speed"[A-video]. The public sources do not
state how that shared-memory substrate relates to the announced network-wide
discovery and standard driver.

## 3. Safety: assertions, evidence and limits

The strongest written safety statement comes from QuEra: MHS "enforces
device-declared bounds, interlocks, and emergency stops at the hardware
interface, independent of the model"[Q]. The CMU case study reports pre-move
blocking after "six different conditions" were artificially induced, including an
active emergency stop[A]. The documentary shows an operator defining a robotic
arm's "safe range" and an out-of-range command being "refused by MHS"[B-video].

Where the enforcement code lives, how interlocks are represented, whether e-stop
is latching, and how code files are sandboxed are **not stated**. Anthropic
states that safety evaluations are still being built and that a "physical safety
roadmap" will follow[A]; Genentech reports that bubble-induced pipetting failures
required human guidance because the model first treated them as software
retries[A]. Expert oversight remains required.

## 4. Early ecosystem (as claimed, with modality)

| Partner | Claimed involvement (verbatim modality) |
|---|---|
| Genentech | proof-of-concept BCA protein assay across liquid handler, robotic arm, plate reader; closed-loop flow-rate optimisation |
| HHMI Janelia | origin rig; shared-memory dictionary; microscope control |
| QuEra | laser relock and PID tuning on quantum hardware; "enforces … at the hardware interface" |
| Tetsuwan | ResearchOS "replaced our scheduler and driver stack with MHS commands"; one connector per instrument; hardware-independent centrifuge resolution |
| CMU | six instruments, drivers built with an agent exploring vendor interfaces; GUI-only plate reader |
| Danaher / Leica | "actively exploring how MHS-supported capabilities could enable its smart instruments" |
| QIAGEN | "experimenting with MHS through a working proof-of-concept" on QIAsymphony Connect |
| Tecan | "is adding MHS support" for Fluent |
| Universal Robots | "has had early access … and plans to add support" |
| MBF Bioscience | "is building an MHS driver for ScanImage" |
| AWS | "will support MHS through Strands Robots", private pre-release for preview participants |
| Automata | "adding MHS support to LINQ" |
| Doosan Robotics | "testing MHS with their robotic arms" |
| Hugging Face | "adding MHS support in LeRobot" |
| Raspberry Pi | "enabling MHS integration across a number of their products" after Camera MHS Driver tests |

## 5. What this specification adopts, defines, and rejects

Status vocabulary, for the OpenMHS column below: **implemented** means present in the
0.9 SDK and exercised by its tests; **specified** means described by this document set
but not (fully) implemented by the SDK; **planned** means neither, and scheduled after
the pilot of the driver handoff kit.

**Adopted framing.** The integration-cost argument; physical knowledge as
machine-readable metadata; user-authored tags; a generated, model-readable reference
view of each device; the three control mechanisms; and chaining commands into code files
for long-running work.

| Concept in the public description | OpenMHS 0.9 | Status |
|---|---|---|
| A standardized driver per device | A driver package per upstream repository: a `Driver` class, a fake backend, sourced limits and facts, and a gate ([driver-profile.md](driver-profile.md)). Four exemplars exist; the corpus is not yet implemented | implemented (SDK, gate, four exemplars); planned (the corpus, after the pilot) |
| `read` and `write` primitives | Named parameters (`@read`, `@write`) served by `mhs.resource.read` and `mhs.resource.write` through `cap.device.configure.v1`; other operations are actions ([core.md](core.md) §2) | implemented |
| Natural-language tags that produce a reference file | Tags, sourced facts, the driver's declarations, the capability catalogue and the operator overlay generate `reference.json` and `REFERENCE.md` deterministically ([core.md](core.md) §3) | implemented |
| Tags written by an agent that interviews the user | The `interview` fact source exists in the schema; the interview flow does not | planned |
| Enforced safety limits, independent of the model | One limits engine in the endpoint, sources intersected, operator overlay narrow-only, `LIMITS_UNSET`, latch-first e-stop ([core.md](core.md) §4 to §6) | implemented |
| Discovery in a standard format | `/.well-known/mhs.json`, `MHS_ENDPOINTS`, `~/.mhs/endpoints.json`, `mhs discover`; discovered is not trusted ([core.md](core.md) §9) | implemented |
| Control through MCP, the command line and code files | The MCP projection, the `mhs` CLI and `mhs run` code files ([core.md](core.md) §10) | implemented |
| Orchestration across devices in one line of code | `mhs.run.lab` over several endpoints, with a ledger checked against the evidence | implemented |
| Chaining commands into scripts for long-running work | Code files; the server-side composition method `mhs.composition.run` is reserved | implemented (code files); specified (composition, not implemented) |
| Vendor and partner support | None. No vendor or partner supports OpenMHS | none |

**Defined beyond the published description.** These are choices of this specification, not claims about
the preview's internals.

| Choice | Status |
|---|---|
| A JSON-RPC wire protocol with receipts, revisions and idempotency | implemented |
| A hash-chained evidence model; detached signatures over a bundle | implemented (chain, export, offline verification); specified (signing) |
| An endpoint-enforced safety envelope with permits, an e-stop that latches first, and an operator-only reset of hardware | implemented |
| A mandatory declared fidelity contract for simulated and hybrid devices, with replay | implemented |
| A declarative adapter and bridge integration model | implemented (python-object, serial, SCPI, Gymnasium, MuJoCo, replay); planned (ROS, HTTP, PyLabRobot, SiLA2, QCoDeS, ophyd, Micro-Manager, LeRobot, MAVLink, tag bridges, MCP client, artifact store) |
| An executable conformance ladder | implemented (CL0 to CL4 for endpoints); specified (CL5, the bridge, host and registry profiles) |
| A registry of catalogue records, task cards and triage | implemented (static index, task cards); specified (federation, signing) |
| Hardware conformance levels from real devices | planned (needs an operator-run check on a real device under supervision; no hardware has been attached) |

**Deliberately rejected as normative mechanisms.** A free-form writable global
state dictionary (least privilege and auditability); a shared-memory bus as the
core transport (MHS is supervisory, not a real-time bus); auto-published
model-authored drivers (a model-authored hardware driver at R2 or above cannot start
its hardware backend until a human has signed `reviewed_by`); model-side
safety-evaluation claims.

## 6. Claims that must not be made

Given the publication boundary, no OpenMHS artefact may claim: compatibility with
or endorsement by Anthropic/the preview; that it implements the preview's wire
format; that it has received preview access; that MHS conformance equals a
safety evaluation or certification; that the preview's described enforcement is
verified; that any vendor listed above supports this specification; that
simulation fidelity is validated by the preview; or that "memory-speed"/"bare
metal speed" is an MHS guarantee.

## 7. Sources and verification status

| Tag | Source | Status |
|---|---|---|
| [A] | https://www.anthropic.com/news/model-hardware-standard-research-preview | fetched live; quotes match saved copy |
| [L] | https://modelhardwarestandard.com/ | fetched; single-page site; `/apply` redirects to a form |
| [Q] | https://www.quera.com/blog-posts/holding-the-light-teaching-an-ai-to-lock-and-tune-our-quantum-computers-lasers | fetched in full |
| [T] | http://tetsuwan.com/blog/mhs | fetched in full |
| [A-video] | https://www.youtube.com/watch?v=UxJZrCFzTHY (2:13 short film) | captions retrieved; no timestamps (blocked) |
| [B-video] | https://www.youtube.com/watch?v=P1zBiAQU1IA (11:10 documentary, chapters 0:00/0:47/2:38/4:30/6:14/8:11) | captions retrieved; no timestamps (blocked) |

Video-derived statements above are labelled `[A-video]`/`[B-video]`; visual-only
claims (e.g. a 3-D safe-range viewer) are not asserted here. The detailed source
notes, per-claim quotes and the gap analysis against this specification are kept
with the project's private research material.

Video identity note: the short film is `UxJZrCFzTHY`; the documentary with the
robot-arm safe-range demonstration, Leica microscope session, diatom tracking and
Genentech liquid-handling loop is `P1zBiAQU1IA`.
