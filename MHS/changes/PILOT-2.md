# PILOT-2 — the second pilot session, a model review of the first eight packages, and ten cards at a time

The same DeepSeek model (`deepseek-v4.1-flash:1017`) ran five more pilot cards in an interactive harness: `gh.huggingface/gym-pusht`
(1 gate run), `gh.pymeasure/pymeasure` (1), `gh.ni/nidaqmx-python` (3), `gh.ap/python-seabreeze` (3) and `gh.python-ivi/python-ivi` (1),
in about an hour. All five passed the gate; nothing outside their driver directories changed.

## Model review of the eight packages

The project owner asked for a model review in place of a human one. A different model (`claude-opus-5-5`) went through the checklist
of `REVIEW.md` for all eight packages of the two sessions, made the fixes itself, re-ran the gate, and recorded the outcome as the last
paragraph of each `RESULT.json` (`MODEL REVIEW ...`). `reviewed_by` stays null in every package. The new section 5 of `REVIEW.md`
describes this kind of review.

- `gh.benpruitt/tecancavro`: the port and volume bounds came from constructor defaults and are now `Limit.operator_required`
  (example overlay, facts and tests follow). The card's override now says `direct-driver`, so `DECISION_DEVIATION` is gone.
- `gh.martinhjelmare/leicacam`: the safe-state action no longer calls the upstream `stop_scan` (up to 60 minutes of waiting inside an
  e-stop); it sends `stopscan` and waits at most 6 s, with a test.
- `gh.pymeasure/pymeasure`, `gh.ni/nidaqmx-python`, `gh.martinhjelmare/leicacam`: `native.py` said the loader refuses their R1
  hardware backend until `reviewed_by` is signed. It refuses only R2 and R3; the sentence now says so.
- `gh.ap/python-seabreeze` (intensity at one wavelength, no spectrum array) and `gh.python-ivi/python-ivi` (the oscilloscope's own
  measurements, no waveform) are accepted as scalar drivers; `gh.huggingface/gym-aloha` and `gym-pusht` as they are.

After the review the registry was rebuilt and `prepare.py --sync` run: the eight cards say `package_status: pass`, and
`collect.py --strict` passes all eight with no warning.

## Kit changes

- `PROMPT.md` rule 4: an instrument whose array the standard cannot carry yet passes with its scalar functions and writes
  "NOT COVERED: <the array>"; only a device whose array is all it gives stops with `NEEDS_ARTIFACTS`. Two of five models had
  passed a spectrometer and an oscilloscope against the old wording; `PLAYBOOK.md` section 8 matches.
- `PROMPT.md` rule 9: claim no protection the SDK does not give (the R2 sentence of the exemplars' `native.py` was copied into R1
  packages).
- `run_wave.py --jobs N` runs N cards at a time, each in its own agent process. A row records the tokens of the card when the agent
  writes JSON events with step usage, and the runner lists every file that changed outside its cards' directories during the run
  (`outside-writes.txt`, exit 1). Tests: `ParallelRunWaveTests`.
- `run_wave.py` stops cleanly: the first batch was stopped by an accidental Ctrl-C twice, which left 20 driver directories
  without RESULT.json, no summary rows, and a traceback from the second Ctrl-C. Now Ctrl-C or SIGTERM starts no further card,
  sends SIGINT to every running agent itself (also when only the runner got the signal) and kills it after 20 s, ignores a second
  Ctrl-C meanwhile, records the stopped cards as `interrupted` (no gate run) and exits 130; `--redo-unfinished` moves aside and
  runs again exactly the cards whose directory has no RESULT.json, and the skip message says so.
- Side-by-side typed sessions: the owner wants to watch the model in the harness's window, ten sessions at a time. `dispatch.py
  --only <ids>` limits a session to its own share (`MASTER-PROMPT.md`: `--select="--only ..."` and one `--batch` per session), so two
  sessions never take the same card; the master prompt now forbids sub-agents (in the DeepSeek Harness they start in the background
  without waiting, so one session could make several requests at once) and says that a driver directory another session prepared is
  not this session's. Test: `TodoTests`.
- `HARNESS.md`: the DeepSeek Harness headless example (an overlay that uses the saved key, pins the model and removes the web and
  subagent tools; Seatbelt confines writes to the repository) and the pilot's timings in place of the rehearsal's estimate.
