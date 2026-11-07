# L04 — cited local ones-based Box bounds

G4 previously read `high = np.ones(n)` as showing 1, but a following `Box(-high, high)` did not show -1. It now adds
bounded source-only AST evidence for a complete cited span containing these straight-line definitions and their Box.
The existing literal, angle, unit, magnitude, Discrete and direct-ones readers retain their previous behavior.

The new reader accepts simple local names and `self.attribute` definitions, numeric literals, NumPy `ones` with
conventional `np`/`numpy` spelling, unary signs, one multiplication of an array by a locally defined literal scale,
and recognized Box constructors. A separate negated lower array is supported. An intervening observation Box whose
bounds are unresolved contributes no inferred values. Symbolic dimensions are never evaluated; width remains a
separate source-review obligation. No source imports or evaluation run.

The inference rejects spans above 16,384 characters, 512 AST nodes or 64 top-level statements; scopes and control
flow; imports or unknown calls; unpacking, alias assignments, reassignments and mutation; unresolved bounds/scales;
unsupported array arithmetic; and unsupported or nonexact dtype conversions. Only float32/float64 dtype spellings
are supported, with a conservative exact float32 check for default Box output. Hazards anywhere in the span reject
all new inference. This does not turn the legacy text-number reader into semantic execution analysis.

Five fixed-source candidate spans were checked against the existing fake source and reference envelope:

| Package | Cited span | Existing fake action envelope |
|---|---|---|
| benelot/pybullet-gym | `pybulletgym/envs/roboschool/robots/robot_bases.py:24-25` | one value, -1..1 |
| svengronauer/phoenix-drone-simulation | `phoenix_drone_simulation/envs/base.py:148-150` | four values, -1..1 |
| dartsim/gym-dart | `gym_dart/envs/dart_cartpole_env.py:59-66` | one value, -5..5 |
| avisingh599/roboverse | `roboverse/envs/widow250.py:332-335` | eight values, -1..1 |
| alrhub/fancy_gym | `fancy_gym/envs/classic_control/base_reacher/base_reacher_torque.py:16-18` | default two values, -1000..1000 |

The first isolated patch passed 90 helper/scoped tests but did not close the production path: G4 joined the
cited lines with spaces, turning two Python statements into invalid syntax. An independent five-package gate
still emitted REF_VALUE for every proposal; its strict collection failed and was preserved. Parent v2 keeps
newlines at the actual G4 call site. A new production regression fails on v1 and passes on v2; negative cases
still warn when the definition is outside the cited span or is an unknown call.

Validation of v2: 92 scoped tests pass. The five copied packages add exact source citations without changing
fake bounds; their regenerated references and full G1-G9 gates pass with no G4 finding. A fresh strict collection
passes all five with no acceptance warnings. These package changes preserve model authorship and unsigned human
review fields. Fake dynamics and untested native simulator compatibility remain separate limitations. The earlier
helper-only evidence is not presented as successful end-to-end validation. Final corpus and SDK-wide checks are
recorded separately after integration.
