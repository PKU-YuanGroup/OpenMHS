# Facts and tags for gh.yang-zj1026/navila-bench

Every fact cites its source at commit `e9d2db12ce5788c0f987d734c0094100b6bc0d3a`: `vendor_doc` (a text file of the
clone such as README.md, LICENSE or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a benchmark framework for evaluating Visual Language Navigation in Isaac Lab | vendor_doc | README.md:31 |
| Isaac Sim 4.1.0 and Isaac Lab 1.1.0 are installed separately, and the omni.isaac.vlnce and omni.isaac.matterport extensions are symlinked into the Isaac Lab source tree | vendor_doc | README.md:55-69 |
| The benchmark data and Matterport USD assets are downloaded from Hugging Face into the isaaclab_exts/omni.isaac.vlnce/assets directory | vendor_doc | README.md:82 |
| go2_matterport_vision is registered with the external entry point omni.isaac.lab.envs:ManagerBasedRLEnv and the environment configuration Go2MatterportVisionCfg | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/__init__.py:20-28 |
| The card entry symbol Go2MatterportVisionCfg is defined as a subclass of Go2MatterportBaseCfg | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_vision_cfg.py:163 |
| Go2MatterportBaseCfg extends ManagerBasedRLEnvCfg, so the registered environment base is external to the clone | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:350 |
| ManagerBasedRLEnvCfg is imported from omni.isaac.lab.envs, the external Isaac Lab package | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:4 |
| The Go2 robot is loaded from the external Isaac Lab asset {ISAACLAB_NUCLEUS_DIR}/Robots/Unitree/Go2/go2.usd | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:70 |
| The action term is a JointPositionActionCfg over all robot joints (joint_names ['.*']) | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:125 |
| The base post-initialization changes the joint-position action scale to 0.25 | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:372 |
| The simulation step is 0.005 s and the decimation is 4 | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:367-371 |
| The episode length is 200000.0 s | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:369 |
| The rgbd camera is 512 by 512 and returns rgb and distance_to_image_plane data | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:301-308 |
| The visualization camera is 512 by 512 and returns rgb data | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:309-315 |
| The camera_obs group is the rgb measurement of the rgbd_camera and viz_camera_obs is the rgb measurement of the viz_rgb_camera | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_vision_cfg.py:100-115 |
| The vision configuration declares the observation groups policy, proprio, critic, camera_obs, viz_camera_obs and depth_obs | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_vision_cfg.py:133-139 |
| The policy observation group includes a last-action term | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:144 |
| Termination is time_out, an illegal contact of the base above threshold 1.0 or a bad orientation with limit_angle 0.8 | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:230-245 |
| The only reward term is a termination penalty of -200.0 on is_terminated | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py:116-118 |
| The vision scene uses one environment with 2.5 spacing | upstream_code | isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_vision_cfg.py:168 |
| The evaluation creates the environment with gym.make(task, cfg=env_cfg, render_mode=None), so the registered task needs an environment configuration object | upstream_code | scripts/navila_eval.py:271 |
| The evaluation reads camera_obs and viz_camera_obs and takes channel indices 0:3 of each frame | upstream_code | scripts/navila_eval.py:304-315 |
| The repository licence is MIT | vendor_doc | LICENSE:1 |

Limits: the driver declares none. The action space is built by the external `ManagerBasedRLEnv` from the
`JointPositionActionCfg` (`go2_matterport_base_cfg.py:125`), whose bounds and joint count are not in the clone (the
robot is the external USD asset at `:70`); the fake therefore publishes an unbounded 12-value Box and no limit is
invented. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mhs-fake:go2_matterport_vision`, level F0 (an interface
stand-in with no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (sim.dt 0.005 s times
decimation 4, `go2_matterport_base_cfg.py:367-371`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps name the real 512 x 512 cameras, the six observation groups, the external action space, the
reward and termination terms, the absent R2R/Matterport assets and the fact that the fake was never compared with an
Isaac Sim run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the last observation, tick and episode stay
readable.

Tags: navila-bench, visual-language-navigation, go2, isaac-lab, isaac-sim, reinforcement-learning, simulation,
gymnasium
