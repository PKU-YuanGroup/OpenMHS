# Facts and tags for gh.schroederdewitt/multiagent_mujoco

Every fact cites its source at commit `b212ddd74b258e7cea006ff1d642b5ffada4b99d`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The reference file is generated from the
`facts` list in `driver.py`, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a benchmark for continuous multi-agent robotic control based on OpenAI's MuJoCo Gym environments | vendor_doc | README.md:7 |
| The documented requirement is OpenAI Gym 0.10.8 and MuJoCo 2.1 | vendor_doc | README.md:15 |
| The install_requires list is numpy, gym, mujoco-py, scipy, Jinja2, glfw and Cython: there is no serial, VISA, USB or vendor-SDK transport package | upstream_code | setup.py:41-48 |
| MujocoMulti is a MultiAgentEnv subclass | upstream_code | multiagent_mujoco/mujoco_multi.py:29 |
| MujocoMulti reads scenario and agent_conf from env_args | upstream_code | multiagent_mujoco/mujoco_multi.py:33-34 |
| For the coupled_half_cheetah scenario MujocoMulti builds the local CoupledHalfCheetah environment under a TimeLimit and wraps it in NormalizedActions | upstream_code | multiagent_mujoco/mujoco_multi.py:86-90 |
| step maps the per-agent action blocks into one MuJoCo action vector and steps the wrapped environment | upstream_code | multiagent_mujoco/mujoco_multi.py:108-121 |
| reset resets the wrapped environment and returns the per-agent observations | upstream_code | multiagent_mujoco/mujoco_multi.py:188-192 |
| CoupledHalfCheetah builds gym's MuJoCoEnv from assets/coupled_half_cheetah.xml with frame_skip 5 | upstream_code | multiagent_mujoco/coupled_half_cheetah.py:7-9 |
| The scenario observation concatenates qpos[1:] and qvel | upstream_code | multiagent_mujoco/coupled_half_cheetah.py:28-32 |
| The served model is the MJCF root '<mujoco model="cheetah">' | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:31 |
| The default motor class sets ctrllimited true and ctrlrange -1 1 | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:36 |
| The model sets gravity 0 0 -9.81 and the integration timestep 0.01 s | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:39 |
| The first cheetah torso has three root joints: rootx and rootz slides and rooty a hinge | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:53-55 |
| The second cheetah torso torso2 has three root joints: rootx2 and rootz2 slides and rooty2 a hinge | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:88-90 |
| A spatial tendon named tendon1 couples the sites t1 and t2 and is limited to range 1.5 to 3.5 | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:120-124 |
| The actuator block declares twelve motors, bthigh to ffoot on the first cheetah and bthigh2 to ffoot2 on the second | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:126-138 |
| The twelve motors declare no ctrlrange of their own, so they inherit the default motor ctrlrange -1 1 of line 36 | upstream_code | multiagent_mujoco/assets/coupled_half_cheetah.xml:127-138 |

Tags: `cheetah`, `coupled`, `mujoco`, `multi-agent`, `reinforcement-learning`, `simulation`, `world`.

The served model is `models[0]` of the card. Only that model is served; the `manyagent_ant` and
`manyagent_swimmer` assets are other scenario models and are not part of this driver.
