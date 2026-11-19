OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Re-triage wave 1: 72 repositories the heuristics had skipped, 53 new passing packages

On 2026-11-17 the owner asked to adapt more repositories for the Playground. 1,364 registry cards had been decided
only by the scanner's keyword and file-pattern heuristics (skip 1,070, reference 190, bridge-runtime 104); no model or
person had read them. DeepSeek (deepseek-v4.1-flash:1017, a model) read each one and wrote a recon proposal; Codex
(gpt-6.1-sol, a model) reviewed every proposal that turned a card into a driver task; DeepSeek wrote the driver
packages; Codex reviewed each package against its clone. The orchestrator was claude-opus-5-5 (a model). Nothing here
was checked by a person, and every pass is `contract_checked` on a fake.

## What ran

- **Re-triage** (recon prompt with a preface saying the card's decision is a heuristic guess; `check_recon.py --force`):
  a 30-card pilot, then the other 1,333 cards. 1,358 valid proposals; 5 cards have no pinned commit and were not read.
  About 740M DeepSeek tokens, 93% cached.
- **Proposal review**: 98 proposals made a card a driver task (gymnasium 33, mujoco 23, python-object 20, scpi 15,
  ros 3, ophyd 2, qcodes 1, plus kscalelabs/ksim-legacy). Codex accepted 49, changed 25 (family, role or entry
  symbol), rejected 24 (20 stay skip, 3 reference, 1 bridge-runtime).
- **Overrides** (`MHS/registry/overrides/retriage-wave1.json`): 71 entries. Left out: lagadic/visp (the reviewer's
  entry is a C++ header; no Python entry at the pin) and papercodein/openopc-pymodbus-snap7-mqtt, which the registry
  itself refused because it is quarantined (committed installers and a URL-shortener download link); neither model
  had flagged it. btownshend/pytecan had a curated skip in `partners.json` ("does not talk to the instrument"); both
  models found its Gemini pipe client (`Gemini/gemini.py:23`) and the owner decided to make it a driver task.
- **Driver waves** `retriage-drivers-1` (71 cards) and `-2` (pytecan): 68 gate passes, 4 blocked by their authors.
  About 900M DeepSeek tokens, 99% cached.
- **Package review** (Codex, 18 sessions of four packages, the brief of the 2026-11 waves): 53 fix, 19 block, none
  accepted unchanged. 21 reviews refined the card's override (mostly MCP-wrapped oscilloscopes whose own class holds
  the SCPI protocol: python-object direct drivers; dobot_6axis_ros2_v4 routed to ros).

## What the review found

- Unsourced bounds turned into `Limit.operator_required(...)` (for example a 1X vertical-scale range on a Rigol
  DHO824), citations corrected to the lines that show the claim, stop paths described as what they confirm (a write,
  not observed cessation), fakes brought closer to the upstream, and regression tests added that failed first.
- qcodes-plus-plus (qcodespp): output enable and source-mode writes bypassed every operator-required level limit;
  the reviewer raised the risk to R3, added three failing regressions and blocked it (code QUARANTINE).
- Blocks: 12 NO_HARDWARE_FREE_PATH (hardware with no source-backed stop, or no free path to exercise it), 4
  HELPER_MISSING (pytecan's pipe has no stop; Isaac and engine environments), 1 ENTRY_UNVERIFIED, 1 SDK_BUG (mrpt),
  1 QUARANTINE.

## Result

72 new driver records: 53 pass and 19 blocked (risk after review across all 72: R0 43, R1 13, R2 15, R3 1), each
RESULT.json with its gate digest and the reviewer's MODEL REVIEW paragraph; `reviewed_by` stays null. New
cards renumber the ranks of the others, so the registry cards and the packages' `task.json` copies change by `rank`
only. `MHS/drivers/market.json` gains the 53 passes. Checks are listed in the pull request that carries this record.

## Found, not fixed

- 5 heuristic cards have no pinned commit and could not be read.
- The 735 heuristic cards that already had a model recon were not re-read in this wave.
- Hardware packages here are fake-backed contracts; any hardware use stays the operator's decision and a human's
  `reviewed_by` signature.
