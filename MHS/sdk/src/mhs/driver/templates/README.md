# Driver package templates

Package data of `mhs.driver` (`mhs.driver.scaffold`). Each directory is one
template kind; `common/` holds the files every kind shares, and a file of the
same name in a kind directory replaces the common one. A file named `X.tmpl`
is written as `X`.

Placeholders use `string.Template` syntax (`${name}`; a literal dollar sign is
`$$`). Every placeholder must be given; `mhs.driver.scaffold.render` fails on
a missing one.

| placeholder | meaning |
|---|---|
| `class_name` | the Driver class name (CamelCase) |
| `device_id` | short device name, e.g. `julabo-cf41` |
| `device_kind` | catalogue resource kind, e.g. `thermal.zone` |
| `mode` | `hardware` or `simulated` |
| `risk` | `R0`..`R3`, never below the task card's risk floor |
| `native` | upstream class `package.module:Class` |
| `native_module`, `native_class` | the two halves of `native` |
| `safe_state` | one sentence describing the safe state |
| `package_id`, `repo_url`, `commit`, `license_spdx` | from the task card |
| `model_id`, `run_id`, `date` | `authored_by` of `driver.lock.json` |
| `sdk_version`, `schema_base` | from `mhs._ids` |
| `cap_owner` | owner segment of the scaffold's `x-cap.<owner>.<name>.v1` ids (lowercase) |
| `env_id` | Gymnasium environment id (gymnasium kind) |
| `model_path` | MuJoCo model file relative to the driver directory (mujoco kind) |
| `lock_backends` | derived by `scaffold.render`: the `backends` object of `driver.lock.json` for the kind |

Kinds: `direct` (a decorated `Driver`), `python-object`, `serial`, `scpi`,
`gymnasium`, `mujoco`, `ros` (the config-only family drivers). The ROS template uses a recording transport and
placeholder endpoint references that must be replaced with pinned source citations; see `docs/ros-driver.md`.
`native.py` (the
hardware backend) exists only where the driver opens the upstream SDK itself
(`direct`, `python-object`); the serial and SCPI bridges open their port.
