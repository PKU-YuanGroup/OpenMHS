# Facts and tags for gh.kautenja/gym-super-mario-bros

Every fact cites the clone at commit `7ba17c778e1df8240fd1cf99dbe5238d0e9b93aa`; `vendor_doc` is documentation text
of the clone and `upstream_code` is code or a test of the clone. The same facts are written into `driver.py`
(`facts = [...]`), and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is a Gymnasium environment for Super Mario Bros., Super Mario Bros. 2 (Lost Levels), Super Mario Bros. 2 (USA) and Super Mario Bros. 3 on the NES, running through the nes-py emulator | vendor_doc | README.md:20-24 |
| By default the environments use the full NES action space of 256 discrete actions | vendor_doc | README.md:50-53 |
| The legal reward range is -15 to 15 | upstream_code | gym_super_mario_bros/smb_env.py:32-33 |
| A step's reward is the sum of the progress, time, score, coins, powerup, completion and death components; the info dictionary also reports the unclipped and the clipped total | upstream_code | gym_super_mario_bros/smb_env.py:564-577 |
| The death reward component is -25 while Mario is dying or dead | upstream_code | gym_super_mario_bros/smb_env.py:415-421 |
| The completion reward component is 50, paid once when the flag is reached | upstream_code | gym_super_mario_bros/smb_env.py:450-456 |
| The game is over when the life counter is 0xff (255), the value it holds when no lives are left | upstream_code | gym_super_mario_bros/smb_env.py:277-281 |
| A full-game environment terminates on game over; a single-stage environment also terminates on dying, dead or flag reached | upstream_code | gym_super_mario_bros/smb_env.py:579-583 |
| The info dictionary reports area, coins, enemy types, flag_get, is_dead, is_dying, is_game_over, is_stage_over, is_world_over, left_x_pos, level, life, player_state, powerup_level, score, stage, status, status_value, time, world, x_pos, x_pos_max, y_pixel, y_pos and y_viewport | upstream_code | gym_super_mario_bros/smb_env.py:585-616 |
| A reset returns a two-item tuple and a step returns a five-item tuple (observation, reward, terminated, truncated, info) | upstream_code | gym_super_mario_bros/tests/test_smv_env.py:68-80 |
| The documented 1-1 opening info has 0 coins, 2 lives, world 1, score 0, stage 1, time 400 and x_pos 40 | upstream_code | gym_super_mario_bros/tests/test_smv_env.py:81-90 |
| The registered time limit is 9999999 steps | upstream_code | gym_super_mario_bros/_registration.py:7 |
| SuperMarioBros-v0 is registered as a Super Mario Bros. environment | upstream_code | gym_super_mario_bros/_registration.py:92-93 |
| The registered entry point is gym_super_mario_bros:SuperMarioBrosEnv and the environment is marked nondeterministic | upstream_code | gym_super_mario_bros/_registration.py:33-42 |
| A target world is 1 to 8 (1 to 13 for Lost Levels) and a target stage is 1 to 4 | upstream_code | gym_super_mario_bros/_roms/decode_target.py:31-41 |

Limits: the driver declares none of its own. The only bound is the action space, which the bridge derives from the
environment (`Discrete(256)`: `action.index` from 0 to 255, with no source and the ref
`action_space of the fake backend .fake:FakeSuperMarioBrosEnv`), and `ticks` (1 to `max_ticks`, 10000 by default).
The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:SuperMarioBros-v0`, level F0 (the model
transitions state directly; no dynamics are claimed), determinism `seeded` with `seed_control` `parameter` (the fake
uses the seed for its starting offset; upstream registers `nondeterministic=True`, so upstream's emulator RNG is not
claimed to follow the seed), `timestep_ms` 0 (the pinned clone states no frame duration; one step is one NES frame),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled,
including that the real observation is a 240 x 256 x 3 uint8 NES screen (nes-py `_native.pyx:21-22,31` and
`nes_env.py:61-65` at commit `8d27b099f24a57afaac7339fab7ec0f1f96a59c8`) while the fake returns a 2 x 2 x 3 stand-in
of the same type and rank.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. No hardware is attached and none is claimed.

Tags: super-mario-bros, nes, reinforcement-learning, simulation, gymnasium
