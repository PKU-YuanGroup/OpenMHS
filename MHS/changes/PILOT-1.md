# PILOT-1 — the first session of the 20-repository pilot, and the fixes it led to

A DeepSeek model (`deepseek-v4.1-flash:1017`) ran the typed prompt of `MASTER-PROMPT.md` in an interactive harness over the first
three pilot cards. All three packages passed the gate (`gh.martinhjelmare/leicacam` in 3 runs, `gh.benpruitt/tecancavro` in 4,
`gh.huggingface/gym-aloha` in 3) in about 30 minutes, with `authored_by` naming the model and `reviewed_by` null. `collect.py` printed
no `RESULT_UNTRUSTED`, `RESULT_DIGEST_STALE` or `EXEMPLAR_RESIDUE`; nothing outside the three driver directories and the progress file
changed, except one bytecode file (below). The packages are model output and unreviewed.

## What the first reading found, and what changed

- **Bytecode in the kit.** A run of `render_prompt.py` without `PYTHONDONTWRITEBYTECODE` left `MHS/handoff/tools/__pycache__`, because
  the tools import `dispatch`. `prepare.py`, `render_prompt.py`, `run_wave.py` and `check_recon.py` now set `sys.dont_write_bytecode`
  before that import (`NoBytecodeTests`).
- **A constructor default is not a bound.** The pump package bounds the port 1..9 and the volume 0..1000 uL from `num_ports=9` and
  `syringe_ul=1000`, which are defaults of the upstream's constructor; G4 warned that the cited lines show no such number, as designed.
  The guide said "consider `Limit.operator_required`"; it now says to use it, `PROMPT.md` rule 2 names the constructor default, and
  `REVIEW.md` item 3 tells the reviewer what the warning means.
- **A safe-state action runs during an e-stop.** The microscope package sends `stopscan` from its `@estop` without waiting, but its
  safe-state action calls the upstream `stop_scan`, which waits up to 60 minutes for a reply, so a silent server holds the e-stop until
  its time budget. The guide (section 4) and `REVIEW.md` item 5 now say so. The gate does not measure it.

## Not changed

The three packages stay as the model wrote them: a reviewer decides whether to ask for `operator_required` on the pump's two bounds
and for a bounded wait in the microscope's stop, and signs `reviewed_by`. One session of three cards says little about how often a
weaker model needs the 6 gate runs; the other 17 pilot cards measure that.
