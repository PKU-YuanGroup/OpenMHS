"""Classification data for the MHS registry generator (stdlib only).

All tables here are *explicit, deterministic rules*.  This module contains:

* ``PHRASE_EN`` / ``TOKEN_EN`` - a fixed English glossary used to build short
  English descriptions from the Chinese catalog text.  The glossary is
  deliberately small: it translates catalog *fields* (category, role, domain)
  and common technical nouns, it does not add facts.
* ``FAMILY_RULES`` - ordered (family, regex) table used to score an adapter
  family for every repo.  Sources are weighted in ``build_registry.py``.
* ``FAMILY_CAPS`` - candidate MHS capability classes per family (skeletons
  only; ``native`` symbols are only emitted when a real entry point was
  detected elsewhere).
* ``FAMILY_BRIDGE`` / ``FAMILY_ENGINE`` / ``FAMILY_RISK`` - planning defaults.

Changing a rule here changes registry output; regenerate with
``python3 MHS/registry/build_registry.py`` and re-run ``validate.py``.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# English glossary.  Longest phrase first is not needed: PHRASE_EN is matched
# as a whole value, TOKEN_EN is a greedy longest-match segmenter for any
# remaining Chinese text.
# ---------------------------------------------------------------------------
PHRASE_EN = {
    # category values (top of the catalog distribution)
    "完整环境": "complete environment",
    "设备后端": "device backend",
    "自动分类/发现": "catalog/discovery tooling",
    "辅助工具": "auxiliary tooling",
    "协议实现/桥接": "protocol implementation/bridge",
    "策略/算法": "policy/algorithm",
    "控制框架": "control framework",
    "模型资产": "model assets",
    "编排调度": "orchestration/scheduling",
    "物理引擎": "physics engine",
    "Agent框架": "agent framework",
    "操作任务环境": "manipulation task environment",
    "数据集": "dataset",
    "移动导航": "mobile navigation",
    "无人机": "UAV",
    "多机器人": "multi-robot",
    "腿足与人形": "legged and humanoid robots",
    "通用机器人平台": "general robot platform",
    "外围工具": "peripheral tooling",
    "数字孪生": "digital twin",
    "直接模拟后端": "direct simulation backend",
    "专用仪器协议模拟": "instrument protocol simulation",
    "仪器SDK": "instrument SDK",
    "实验编排": "experiment orchestration",
    "数值光学/测量模型": "numerical optics/measurement model",
    "场景资产": "scene assets",
    "软体与多物理": "soft-body and multiphysics",
    "海洋机器人": "marine robotics",
    "协议桥接": "protocol bridge",
    "科学成像模型": "scientific imaging model",
    "具体 SiLA2 仪器连接器": "concrete SiLA2 instrument connector",
    "DDS中间件": "DDS middleware",
    "显微控制与mock": "microscope control and mock",
    "设备Web协议": "device web protocol",
    "显微设备SDK": "microscope device SDK",
    "控制器": "controller",
    "显微镜状态与图像仿真": "microscope state and image simulation",
    "连接器目录": "connector catalog",
    "实验室场景资产": "lab scene assets",
    # adapter_role values
    "任务环境": "task environment",
    "设备SDK": "device SDK",
    "设备 SDK": "device SDK",
    "物理引擎": "physics engine",
    "场景资产": "scene assets",
    "测量模型": "measurement model",
    "辅助工具": "auxiliary tooling",
    "控制框架": "control framework",
    # domain values
    "通用": "general",
    "机械臂操作": "robot arm manipulation",
    "电子测量": "electronic measurement",
    "移动机器人": "mobile robots",
    "显微成像": "microscopy imaging",
    "人形": "humanoid robots",
    "无人机": "UAVs",
    "液体处理": "liquid handling",
    "光学": "optics",
    "足式": "legged robots",
    "多机器人": "multi-robot systems",
    "生物": "biology",
    "化学": "chemistry",
    "材料": "materials",
    "水下": "underwater robotics",
    "移动导航": "mobile navigation",
    "物理引擎": "physics engines",
    "物理": "physics",
    "机械": "mechanics",
    "数字孪生": "digital twins",
    "湿实验室自动化与化学过程": "wet-lab automation and chemistry",
    "共享接入与协议基础设施": "shared access and protocol infrastructure",
    "通用机器人平台": "general robot platforms",
    "robot_manipulation": "robot manipulation",
    "腿足与人形": "legged and humanoid robots",
}

TOKEN_EN = {
    # generic nouns / verbs
    "实验": "experiment", "实验室": "laboratory", "自动": "automated",
    "自动化": "automation", "设备": "device", "仪器": "instrument",
    "后端": "backend", "模拟": "simulation", "仿真": "simulation",
    "模型": "model", "引擎": "engine", "物理": "physics", "控制": "control",
    "框架": "framework", "协议": "protocol", "桥接": "bridge", "桥": "bridge",
    "工具": "tooling", "辅助": "auxiliary", "外围": "peripheral",
    "完整": "complete", "环境": "environment", "任务": "task",
    "操作": "manipulation", "策略": "policy", "算法": "algorithm",
    "模型资产": "model assets", "资产": "assets", "场景": "scene",
    "数据集": "dataset", "数据": "data", "编排": "orchestration",
    "调度": "scheduling", "工作流": "workflow", "工作单元": "workcell",
    "机器人": "robot", "机械臂": "robot arm", "移动": "mobile",
    "导航": "navigation", "人形": "humanoid", "足式": "legged",
    "腿足": "legged", "机械": "mechanical", "电子": "electronic",
    "测量": "measurement", "显微": "microscopy", "成像": "imaging",
    "图像": "image", "液体": "liquid", "处理": "handling", "光学": "optics",
    "激光": "laser", "相机": "camera", "视觉": "vision", "多": "multi",
    "化学": "chemistry", "生物": "biology", "材料": "materials",
    "物理引擎": "physics engine", "数采": "DAQ", "采集": "acquisition",
    "状态": "state", "命令": "command", "接口": "interface", "驱动": "driver",
    "平台": "platform", "通用": "general", "具体": "concrete",
    "专用": "dedicated", "标准": "standard", "规范": "specification",
    "历史": "historical", "归档": "archived", "旧版": "legacy",
    "教学": "teaching", "研究": "research", "基准": "benchmark",
    "评测": "evaluation", "训练": "training", "学习": "learning",
    "强化学习": "reinforcement learning", "生成": "generation",
    "合成": "synthetic", "虚拟": "virtual", "数字": "digital",
    "孪生": "twin", "服务": "service", "服务器": "server", "客户端": "client",
    "代码": "code", "软件": "software", "硬件": "hardware", "固件": "firmware",
    "嵌入式": "embedded", "运动": "motion", "轨迹": "trajectory",
    "规划": "planning", "执行": "execution", "管理": "management",
    "监控": "monitoring", "记录": "logging", "回放": "replay",
    "可视化": "visualization", "文档": "documentation", "示例": "example",
    "演示": "demo", "插件": "plugin", "扩展": "extension", "生态": "ecosystem",
    "索引": "index", "目录": "catalog", "发现": "discovery",
    "分类": "classification", "配置": "configuration", "集成": "integration",
    "适配": "adaptation", "包装": "wrapper", "迁移": "migration",
    "通讯": "communication", "通信": "communication", "传输": "transport",
    "网络": "network", "无线": "wireless", "射频": "RF", "波形": "waveform",
    "时序": "timing", "信号": "signal", "传感器": "sensor", "传感": "sensing",
    "执行器": "actuator", "电机": "motor", "舵机": "servo", "泵": "pump",
    "阀": "valve", "加热": "heating", "温控": "thermal control",
    "孵育": "incubation", "离心": "centrifugation", "移液": "pipetting",
    "吸头": "pipette tip", "点样": "spotting", "微流控": "microfluidics",
    "芯片": "chip", "工作台": "workbench", "桌面": "desktop",
    "物体": "object", "抓取": "grasping", "装配": "assembly",
    "拆卸": "disassembly", "碰撞": "collision", "接触": "contact",
    "刚体": "rigid body", "粒子": "particle", "流体": "fluid",
    "软体": "soft body", "多物理": "multiphysics", "可微": "differentiable",
    "连续": "continuum", "动力学": "dynamics", "运动学": "kinematics",
    "控制器": "controller", "轨迹优化": "trajectory optimization",
    "状态估计": "state estimation", "模型预测控制": "model predictive control",
    "底层": "low-level", "高层": "high-level", "抽象": "abstract",
    "硬件抽象": "hardware abstraction", "资源": "resource",
    "账本": "ledger", "安全": "safety", "急停": "e-stop",
    "联锁": "interlock", "故障": "fault", "注入": "injection",
    "异常": "exception", "错误": "error", "重试": "retry",
    "幂等": "idempotency", "回执": "receipt", "版本": "version",
    "修订": "revision", "哈希": "hash", "快照": "snapshot",
    "恢复": "restore", "重置": "reset", "种子": "seed",
    "确定性": "deterministic", "可复现": "reproducible", "校准": "calibration",
    "读数": "readout", "测量响应": "measurement response",
    "光谱": "spectrum", "光谱仪": "spectrometer", "示波器": "oscilloscope",
    "万用表": "multimeter", "电源": "power supply", "放大器": "amplifier",
    "信号发生器": "signal generator", "数据采集": "data acquisition",
    "波形发生器": "waveform generator", "电子显微镜": "electron microscope",
    "原子": "atomic", "量子": "quantum", "脉冲": "pulse", "序列": "sequence",
    "加速器": "accelerator", "束线": "beamline", "光学平台": "optical table",
    "荧光": "fluorescence", "共聚焦": "confocal", "物镜": "objective",
    "相机": "camera", "深度": "depth", "点云": "point cloud",
    "惯性": "inertial", "力": "force", "力矩": "torque", "触觉": "tactile",
    "飞行": "flight", "飞控": "flight control", "无人机": "UAV",
    "无人车": "UGV", "水下": "underwater", "海洋": "marine",
    "多机器人": "multi-robot", "协作": "collaboration",
    "工业": "industrial", "产线": "production line", "工厂": "factory",
    "医疗": "medical", "手术": "surgical", "康复": "rehabilitation",
    "家居": "household", "厨房": "kitchen", "服务机器人": "service robot",
    "自动驾驶": "autonomous driving", "交通": "traffic", "车辆": "vehicle",
    "电网": "power grid", "电力": "electric power", "能源": "energy",
    "电池": "battery", "光伏": "photovoltaic", "材料科学": "materials science",
    "化学反应": "chemical reaction", "反应": "reaction", "催化": "catalysis",
    "分离": "separation", "蒸馏": "distillation", "合成生物": "synthetic biology",
    "生物实验": "biology experiment", "细胞": "cell", "培养": "culture",
    "样本": "sample", "试管": "test tube", "微孔板": "microplate",
    "孔板": "plate", "读板": "plate reading", "洗板": "plate washing",
    "移液头": "pipette head", "分液": "dispensing", "振荡": "shaking",
    "搅拌": "stirring", "加热": "heating", "冷却": "cooling",
    "温度": "temperature", "压力": "pressure", "流量": "flow rate",
    "质量": "mass", "体积": "volume", "浓度": "concentration",
    "pH": "pH", "电导率": "conductivity", "电压": "voltage",
    "电流": "current", "电阻": "resistance", "功率": "power",
    "频率": "frequency", "波长": "wavelength", "强度": "intensity",
    "噪声": "noise", "漂移": "drift", "误差": "error", "精度": "accuracy",
    "标定": "calibration", "测试": "test", "验证": "verification",
    "一致性": "conformance", "标准": "standard", "规范": "spec",
    "MHS": "MHS", "OpenAI4S": "OpenAI4S", "ROS": "ROS", "ROS2": "ROS 2",
    "ROS1": "ROS 1", "Gazebo": "Gazebo", "MuJoCo": "MuJoCo",
    "PyBullet": "PyBullet", "Isaac": "Isaac", "Unity": "Unity",
    "Unreal": "Unreal", "Webots": "Webots", "CoppeliaSim": "CoppeliaSim",
    "AirSim": "AirSim", "SAPIEN": "SAPIEN", "Drake": "Drake",
    "Habitat": "Habitat", "Genesis": "Genesis", "PyVISA": "PyVISA",
    "SCPI": "SCPI", "QCoDeS": "QCoDeS", "Ophyd": "Ophyd",
    "Bluesky": "Bluesky", "EPICS": "EPICS", "Tango": "Tango",
    "OPC": "OPC", "UA": "UA", "MCP": "MCP", "SiLA": "SiLA",
    "Opentrons": "Opentrons", "PyLabRobot": "PyLabRobot",
    "Flowchem": "Flowchem", "MADSci": "MADSci", "Micro-Manager": "Micro-Manager",
    "pymmcore": "pymmcore", "LabVIEW": "LabVIEW", "MATLAB": "MATLAB",
    "Arduino": "Arduino", "Raspberry": "Raspberry Pi", "Pi": "Pi",
    "树莓派": "Raspberry Pi", "嵌入式": "embedded", "固件": "firmware",
    "云": "cloud", "本地": "local", "远程": "remote", "分布式": "distributed",
    "实时": "real-time", "异步": "asynchronous", "同步": "synchronous",
    "并行": "parallel", "串行": "serial", "串口": "serial port",
    "总线": "bus", "以太网": "Ethernet", "蓝牙": "Bluetooth",
    "无线": "wireless", "网络": "network", "数据库": "database",
    "文件": "file", "格式": "format", "解析": "parsing", "转换": "conversion",
    "生成器": "generator", "编译器": "compiler", "仿真器": "simulator",
    "模拟器": "simulator", "虚拟机": "virtual machine", "容器": "container",
    "镜像": "image", "部署": "deployment", "安装": "installation",
    "依赖": "dependency", "构建": "build", "编译": "compile",
    "源码": "source code", "代码": "code", "库": "library", "包": "package",
    "模块": "module", "组件": "component", "系统": "system",
    "子": "sub", "主": "main", "新": "new", "旧": "old",
    "第一": "first", "第二": "second", "三": "three", "维": "-D",
    "二维": "2-D", "三维": "3-D", "四": "four", "六": "six",
    "轴": "axis", "关节": "joint", "末端": "end-effector", "位姿": "pose",
    "位置": "position", "速度": "velocity", "加速度": "acceleration",
    "力控": "force control", "阻抗": "impedance", "导纳": "admittance",
    "抓取": "grasp", "放置": "place", "拾取": "pick", "搬运": "transport",
    "堆叠": "stacking", "开合": "open/close", "盖": "lid",
    "抽屉": "drawer", "门": "door", "开关": "switch", "按钮": "button",
    "面板": "panel", "界面": "interface", "用户": "user",
    "交互": "interaction", "自然语言": "natural language", "智能体": "agent",
    "大模型": "large model", "语言": "language", "推理": "reasoning",
    "规划器": "planner", "任务规划": "task planning", "技能": "skill",
    "组合": "composition", "场景": "scenario", "布局": "layout",
    "地图": "map", "定位": "localization", "建图": "mapping",
    "路径": "path", "避障": "obstacle avoidance", "SLAM": "SLAM",
    "激光雷达": "LiDAR", "雷达": "radar", "视觉": "vision",
    "识别": "recognition", "检测": "detection", "分割": "segmentation",
    "跟踪": "tracking", "估计": "estimation", "预测": "prediction",
    "学习": "learning", "模仿": "imitation", "强化": "reinforcement",
    "数据驱动": "data-driven", "神经网络": "neural network",
    "深度": "deep", "卷积": "convolution", "变换器": "transformer",
    "策略": "policy", "奖励": "reward", "环境": "environment",
    "回合": "episode", "终止": "termination", "截断": "truncation",
    "步": "step", "帧": "frame", "时钟": "clock", "时间": "time",
    "墙钟": "wall clock", "仿真时间": "simulated time", "步长": "step size",
    "固定": "fixed", "步": "step", "子步": "substep", "频率": "frequency",
    "控制频率": "control frequency", "物理频率": "physics frequency",
    "渲染": "rendering", "离屏": "off-screen", "头less": "headless",
    "无头": "headless", "显示": "display", "窗口": "window",
    "图形": "graphics", "GPU": "GPU", "CPU": "CPU", "内存": "memory",
    "显存": "VRAM", "许可": "license", "授权": "licensing",
    "商业": "commercial", "开源": "open source", "免费": "free",
    "非商业": "non-commercial", "学术": "academic", "专有": "proprietary",
    "公司": "company", "厂商": "vendor", "社区": "community",
    "官方": "official", "第三方": "third-party", "参考": "reference",
    "实现": "implementation", "概念": "concept", "风格": "style",
    "预研": "pre-study", "草案": "draft", "早期": "early", "稳定": "stable",
    "实验性": "experimental", "维护": "maintenance", "弃用": "deprecated",
    "更新": "update", "版本": "version", "发布": "release",
    # extra glue / boundary words used by catalog prose
    "与": "and", "及": "and", "或": "or", "的": "", "基于": "based on",
    "用于": "for", "提供": "provides", "支持": "supports", "包括": "including",
    "以及": "as well as", "通过": "via", "使用": "using", "实现": "implements",
    "边界": "boundary", "任务板": "task board", "工作单元": "workcell",
    "物料": "material", "搬运": "transport", "实验室设备": "lab equipment",
    "微流控": "microfluidics", "数字微流控": "digital microfluidics",
    "状态机": "state machine", "属性": "attribute", "参数": "parameter",
    "读数": "readout", "设定值": "setpoint", "反馈": "feedback",
    "队列": "queue", "历史": "history", "日志": "log", "事件": "event",
    "通知": "notification", "订阅": "subscription", "发布": "publish",
    "超时": "timeout", "截止": "deadline", "取消": "cancel",
    "终止": "terminate", "完成": "completion", "成功": "success",
    "失败": "failure", "未知": "unknown", "状态": "state", "模式": "mode",
    "仿真": "simulation", "模拟": "simulation", "真实": "real",
    "硬件": "hardware", "软件": "software", "系统": "system",
    "工程": "engineering", "项目": "project", "仓库": "repository",
    "工具链": "toolchain", "流水线": "pipeline", "流程": "workflow",
    "协议栈": "protocol stack", "中间件": "middleware", "网关": "gateway",
    "客户端": "client", "服务端": "server", "节点": "node",
    "进程": "process", "容器": "container", "环境变量": "environment variable",
    "配置文件": "configuration file", "命令行": "command line",
    "图形界面": "graphical interface", "用户界面": "user interface",
    "浏览器": "browser", "web": "web", "桌面": "desktop",
}


# Greedy longest-match segmenter: max Chinese token length in TOKEN_EN.
_MAX_TOKEN_LEN = max(len(k) for k in TOKEN_EN)


def translate_zh(text: str) -> str:
    """Deterministic, glossary-only English rendering of catalog Chinese text.

    This is *not* a general translator.  It translates known technical terms
    and leaves unknown fragments in place (in brackets) so the result never
    invents a fact the catalog did not state.
    """
    if not text:
        return ""
    text = text.strip()
    if text in PHRASE_EN:
        return PHRASE_EN[text]
    # multi-value cells: split on the catalog's separators and translate parts
    parts = re.split(r"\s*[;|、,，；]\s*", text)
    if len(parts) > 1:
        translated = [translate_zh(p) for p in parts if p.strip()]
        return "; ".join(t for t in translated if t)
    out = []
    i = 0
    pending_ascii = []
    while i < len(text):
        ch = text[i]
        if ch.isascii():
            pending_ascii.append(ch)
            i += 1
            continue
        if pending_ascii:
            chunk = "".join(pending_ascii)
            if out and out[-1] and out[-1][-1].isalnum():
                out.append(" " + chunk)
            else:
                out.append(chunk)
            pending_ascii = []
        matched = None
        for size in range(min(_MAX_TOKEN_LEN, len(text) - i), 0, -1):
            chunk = text[i:i + size]
            if chunk in TOKEN_EN:
                matched = chunk
                break
        if matched:
            out.append(" " + TOKEN_EN[matched])
            i += len(matched)
        else:
            out.append(ch)
            i += 1
    if pending_ascii:
        chunk = "".join(pending_ascii)
        if out and out[-1] and out[-1][-1].isalnum():
            out.append(" " + chunk)
        else:
            out.append(chunk)
    rendered = "".join(out)
    rendered = re.sub(r"\s+", " ", rendered).strip()
    if re.search(r"[\u4e00-\u9fff]", rendered):
        rendered += " [zh]"
    return rendered


# ---------------------------------------------------------------------------
# Adapter family rules (adapter.schema.json enum), highest priority first.
# Each entry: (family, [regex, ...]).  The generator scores a match in
# `backend_family` 10 points, `integration_interfaces` 7, capability-table
# API hints 5, build/README markers 4, README text 3, name/description 2.
# Highest score wins; ties are broken by this order.
# ---------------------------------------------------------------------------
FAMILY_RULES = [
    ("micromanager", [r"micro[- ]?manager", r"\bmicromanager\b", r"pymmcore", r"\bmmcore\b", r"\buseq\b"]),
    ("qcodes", [r"\bqcodes\b"]),
    ("bluesky-ophyd", [r"\bophyd\b", r"\bbluesky\b", r"runengine", r"queueserver", r"ophyd[-_]async"]),
    ("scpi-visa", [r"\bpyvisa\b", r"\bscpi\b", r"\bvisa\b", r"\bpymeasure\b", r"instrumentkit", r"\blabscript\b", r"sinstruments", r"\blewis\b"]),
    ("pylabrobot", [r"pylabrobot", r"pylablib", r"\bplr\b"]),
    ("opentrons", [r"opentrons", r"\bot[- ]?2\b", r"protocol engine", r"\bflex\b.*robot"]),
    ("flowchem", [r"flowchem"]),
    ("madsci", [r"madsci"]),
    ("sila2", [r"sila ?2", r"sila2"]),
    ("mcp-proxy", [r"\bmcp\b", r"model context protocol", r"fastmcp", r"mcp[-_ ]server"]),
    ("airsim", [r"airsim"]),
    ("isaac-lab", [r"isaac lab", r"isaaclab", r"omniisaacgym", r"omniverse lab"]),
    ("isaac-gym", [r"isaac gym", r"isaacgym", r"isaac-gym", r"legged[_-]?gym"]),
    ("isaac-sim", [r"isaac sim", r"isaac-sim", r"isaacsim", r"omniverse", r"omni\.isaac"]),
    ("gazebo", [r"gazebo", r"gz[-_]sim", r"gazebosim", r"ros_gz", r"gz[-_]transport", r"\bgz\b"]),
    ("ros2", [r"\bros ?2\b", r"\bros2\b", r"\brclpy\b", r"\brclcpp\b", r"rosbridge", r"\bnav2\b", r"moveit2", r"ros2_control", r"\bament\b", r"\bcolcon\b", r"\brmw\b", r"\bdds\b", r"zenoh"]),
    ("ros1", [r"\bros ?1\b", r"\bros1\b", r"\broscpp\b", r"\brospy\b", r"roslaunch", r"\bcatkin\b", r"\bros\b"]),
    ("webots", [r"\bwebots\b"]),
    ("unity", [r"unity3d", r"unity engine", r"\bunity\b"]),
    ("sapien", [r"\bsapien\b", r"mani[- ]?skill"]),
    ("drake", [r"\bdrake\b", r"pydrake", r"multibodyplant"]),
    ("brax-mjx", [r"\bbrax\b", r"\bmjx\b", r"mujoco mjx"]),
    ("habitat", [r"\bhabitat\b", r"\bigibson\b", r"omnigibson"]),
    ("mujoco", [r"\bmujoco", r"\bmjcf\b", r"mjwarp", r"mujoco playground"]),
    ("pybullet", [r"\bpybullet", r"\bbullet3?\b"]),
    ("dm-env", [r"\bdm[_-]env\b", r"dm[_-]control"]),
    ("gymnasium", [r"\bgymnasium\b", r"\bgym\b", r"\bgym[-_]?", r"farama", r"\bgym-\w+"]),
    ("lerobot-real", [r"\blerobot\b"]),
    ("http-api", [r"rest api", r"restful", r"http api", r"\bfastapi\b", r"\bflask\b", r"\btornado\b", r"aiohttp", r"json[- ]rpc", r"\bgrpc\b", r"openapi", r"websocket", r"web of things", r"\bwot\b"]),
    ("serial", [r"pyserial", r"serial port", r"serial communication", r"\bmodbus\b", r"\buart\b", r"\brs-?232\b", r"\busb[- ]serial\b"]),
    ("cli-process", [r"command[- ]line", r"\bcli\b", r"console script", r"\bsubprocess\b", r"entry[_ ]points"]),
    ("docker", [r"\bdocker\b", r"containerfile", r"\bcontainer(ized)?\b"]),
    ("replay", [r"\bmcap\b", r"\brosbag\b", r"\bfoxglove\b", r"\brerun\b", r"\breplay\b"]),
    ("python-object", [r"python ?sdk", r"python ?api", r"python ?client",
                       r"python ?library", r"python ?framework",
                       r"python ?package", r"python object"]),
    # Everything that is a protocol/engine with no v1.0 bridge family of its
    # own is classified `other` (honest: needs a shim or a future bridge).
    ("other", [r"coppelia", r"pyrep", r"\bunreal\b", r"opc[- ]?ua", r"opcua",
               r"\bepics\b", r"caproto", r"pyepics",
               r"\btango\b", r"mavlink", r"\bpx4\b", r"ardupilot",
               r"arducopter", r"\bsitl\b", r"\bmqtt\b", r"zeromq", r"\bzmq\b",
               r"\bgenesis\b", r"\bdart\b", r"dartpy", r"\bargos\b",
               r"stonefish", r"\bchrono\b", r"raisim", r"agx",
               r"\bsofa\b", r"\bblender\b", r"flightmare", r"flightgoggles",
               r"\bmatlab\b", r"\blabview\b", r"\bros\b", r"\bwebots\b",
               r"\bgodot\b", r"\bphysx\b", r"\bode\b", r"\bwarp\b",
               r"\bnewton\b", r"\btaichi\b", r"\bflex\b", r"\bfem\b"]),
]
# compile once; the ordered list is the rule table
FAMILY_RULES = [(family, [re.compile(p, re.IGNORECASE) for p in patterns])
                for family, patterns in FAMILY_RULES]
FAMILY_RULES_ORDER = list(dict.fromkeys(
    [family for family, _ in FAMILY_RULES] + ["python-object"]))

# family -> candidate MHS capability classes (core v1.0 set only)
_WORLD = ["cap.world.reset.v1", "cap.world.step.v1", "cap.world.state.v1"]
FAMILY_CAPS = {
    "gymnasium": _WORLD + ["cap.world.seed.v1", "cap.world.render.v1"],
    "dm-env": _WORLD + ["cap.world.seed.v1"],
    "mujoco": _WORLD + ["cap.world.snapshot.v1", "cap.world.restore.v1", "cap.world.seed.v1", "cap.world.render.v1"],
    "pybullet": _WORLD + ["cap.world.snapshot.v1", "cap.world.restore.v1", "cap.world.render.v1"],
    "isaac-sim": _WORLD + ["cap.world.snapshot.v1", "cap.world.restore.v1", "cap.world.render.v1"],
    "isaac-lab": _WORLD + ["cap.world.seed.v1", "cap.world.render.v1", "cap.motion.joint_position.v1"],
    "isaac-gym": _WORLD + ["cap.motion.joint_position.v1", "cap.motion.joint_velocity.v1"],
    "gazebo": _WORLD + ["cap.motion.joint_position.v1", "cap.motion.cartesian_pose.v1", "cap.motion.stop.v1"],
    "ros2": ["cap.motion.joint_position.v1", "cap.motion.cartesian_pose.v1", "cap.motion.mobile_base.v1", "cap.motion.stop.v1", "cap.sensing.read.v1", "cap.device.describe.v1"],
    "ros1": ["cap.motion.joint_position.v1", "cap.motion.cartesian_pose.v1", "cap.motion.mobile_base.v1", "cap.motion.stop.v1", "cap.sensing.read.v1", "cap.device.describe.v1"],
    "webots": _WORLD + ["cap.motion.joint_position.v1", "cap.sensing.read.v1"],
    "unity": _WORLD + ["cap.sensing.image.v1"],
    "sapien": _WORLD + ["cap.motion.joint_position.v1", "cap.manipulation.grasp.v1", "cap.sensing.image.v1"],
    "drake": _WORLD + ["cap.motion.joint_position.v1", "cap.motion.cartesian_pose.v1"],
    "brax-mjx": _WORLD + ["cap.motion.joint_position.v1"],
    "habitat": _WORLD + ["cap.motion.mobile_base.v1", "cap.sensing.image.v1"],
    "airsim": _WORLD + ["cap.motion.mobile_base.v1", "cap.sensing.image.v1"],
    "lerobot-real": ["cap.motion.joint_position.v1", "cap.manipulation.grasp.v1", "cap.sensing.image.v1", "cap.device.describe.v1"],
    "http-api": ["cap.device.describe.v1", "cap.sensing.read.v1", "cap.process.run.v1"],
    "mcp-proxy": ["cap.device.describe.v1", "cap.process.run.v1"],
    "scpi-visa": ["cap.sensing.read.v1", "cap.measure.voltage.v1", "cap.device.describe.v1", "cap.device.self_test.v1"],
    "serial": ["cap.sensing.read.v1", "cap.actuation.gpio.v1", "cap.device.describe.v1"],
    "sila2": ["cap.device.describe.v1", "cap.sensing.read.v1", "cap.fluid.aspirate.v1", "cap.fluid.dispense.v1"],
    "opentrons": ["cap.fluid.aspirate.v1", "cap.fluid.dispense.v1", "cap.fluid.transfer.v1", "cap.sample.move.v1", "cap.device.describe.v1"],
    "micromanager": ["cap.imaging.capture.v1", "cap.imaging.focus.v1", "cap.imaging.illumination.v1", "cap.device.describe.v1"],
    "flowchem": ["cap.fluid.aspirate.v1", "cap.fluid.dispense.v1", "cap.thermal.setpoint.v1", "cap.sensing.read.v1", "cap.device.describe.v1"],
    "madsci": ["cap.process.run.v1", "cap.compute.submit.v1", "cap.device.describe.v1"],
    "pylabrobot": ["cap.fluid.aspirate.v1", "cap.fluid.dispense.v1", "cap.fluid.transfer.v1", "cap.sample.move.v1", "cap.device.describe.v1"],
    "bluesky-ophyd": ["cap.sensing.read.v1", "cap.measure.voltage.v1", "cap.device.describe.v1", "cap.device.self_test.v1"],
    "qcodes": ["cap.sensing.read.v1", "cap.measure.voltage.v1", "cap.device.describe.v1", "cap.device.self_test.v1"],
    "cli-process": ["cap.process.run.v1", "cap.compute.submit.v1"],
    "docker": ["cap.process.run.v1", "cap.device.describe.v1"],
    "replay": ["cap.world.state.v1", "cap.world.restore.v1"],
    "python-object": ["cap.device.describe.v1", "cap.device.self_test.v1"],
    "other": ["cap.device.describe.v1"],
}

# Capability risk floors and verbs are not tabled here: they come from the
# normative catalogue through mhs.catalog (catalog_view.py).  The former private
# risk table disagreed with MHS/spec/capabilities.json for 24 classes and the
# keyword-regex capability hints produced template noise (FIT-06, REGQ-05).

# family -> planned bridge (from MHS spec 9.3; "shim" families need new code)
FAMILY_BRIDGE = {
    "python-object": "python-object", "gymnasium": "gymnasium",
    "dm-env": "dm-env", "mujoco": "mujoco", "pybullet": "pybullet",
    "isaac-sim": "isaac-sim", "isaac-lab": "isaac-lab",
    "isaac-gym": "isaac-gym", "gazebo": "gazebo", "ros2": "ros2",
    "ros1": "ros1", "webots": "webots", "unity": "unity",
    "sapien": "sapien", "drake": "drake", "brax-mjx": "brax-mjx",
    "habitat": "habitat", "airsim": "airsim", "lerobot-real": "lerobot-real",
    "http-api": "http-api", "mcp-proxy": "mcp-proxy", "scpi-visa": "scpi-visa",
    "serial": "serial", "sila2": "sila2", "opentrons": "opentrons",
    "micromanager": "micromanager", "flowchem": "flowchem",
    "madsci": "madsci", "pylabrobot": "pylabrobot",
    "bluesky-ophyd": "bluesky-ophyd", "qcodes": "qcodes",
    "cli-process": "cli-process", "docker": "docker", "replay": "replay",
    "other": "shim",
}
# bridge modules that exist (or are planned) in MHS/sdk/src/mhs/bridge/
IMPLEMENTED_BRIDGES = {"python-object": "mhs.bridge.python:main",
                       "gymnasium": "mhs.bridge.gymnasium:main",
                       "mujoco": "mhs.bridge.mujoco:main",
                       "serial": "mhs.bridge.serial:main",
                       "replay": "mhs.bridge.replay:main"}

# family -> simulator engine hint for fidelity.engine (only for sim families)
FAMOUS_ENGINE = {
    "gymnasium": "gymnasium", "dm-env": "dm_control", "mujoco": "mujoco",
    "pybullet": "pybullet", "isaac-sim": "isaac-sim/physx",
    "isaac-lab": "isaac-lab/physx", "isaac-gym": "isaac-gym/physx",
    "gazebo": "gazebo", "webots": "webots", "unity": "unity",
    "sapien": "sapien", "drake": "drake", "brax-mjx": "brax/mjx",
    "habitat": "habitat", "airsim": "airsim/unreal", "lerobot-real": "real-robot",
}

SIM_FAMILIES = {"gymnasium", "dm-env", "mujoco", "pybullet", "isaac-sim",
                "isaac-lab", "isaac-gym", "gazebo", "webots", "unity",
                "sapien", "drake", "brax-mjx", "habitat", "airsim"}
HARDWARE_FAMILIES = {"scpi-visa", "serial", "opentrons", "micromanager",
                     "flowchem", "pylabrobot", "bluesky-ophyd", "qcodes",
                     "sila2", "lerobot-real", "ros2", "ros1"}

# Package-specific mode overrides (MHS-007 §3 `modes`; REG-004).  A *pure*
# simulator that was verified from its own source/recon notes must not inherit
# the hardware default of its adapter family.  Package evidence beats family
# defaults; every entry cites the source that justifies the override.
# `modes` is the complete declared mode set for that package.
SIMULATOR_ONLY_PACKAGES = {
    "gh.pyvisa/pyvisa-sim": {
        "modes": ["simulated", "replay"],
        "evidence": ("work/recon/labs/pyvisa__pyvisa-sim.md:84 (Mode: simulated/replay; "
                     "no hardware); labs/pyvisa/pyvisa-sim/README.rst:34-39 (implements "
                     "Message Based communication in a simulated environment); catalog "
                     "adapter_role=直接模拟后端"),
    },
    "gh.automatedchemistry/flowchem-virtual": {
        "modes": ["simulated"],
        "evidence": ("work/recon/labs/automatedchemistry__flowchem-virtual.md:41,67 "
                     "(no hardware open; Mode: simulated)"),
    },
    "gh.bluitz/mhsbench": {
        "modes": ["simulated"],
        "evidence": ("work/recon/labs/bluitz__mhsbench.md:100 (Mode: simulated/replay; "
                     "bench simulator, no hardware path)"),
    },
}


def pure_simulator(package_id: str):
    """Return the source-backed pure-simulator spec for a package id, or None."""
    return SIMULATOR_ONLY_PACKAGES.get((package_id or "").lower())


def apply_mode_override(package_id: str, modes):
    """Apply package-specific source evidence over the family mode default."""
    spec = pure_simulator(package_id)
    if not spec:
        return list(modes), None
    meta = {
        "rule": "package-specific-pure-simulator",
        "modes": list(spec["modes"]),
        "evidence": spec["evidence"],
    }
    return list(spec["modes"]), meta


# Which capability prefixes are plausible for which adapter family.  This keeps
# generic keyword hits (e.g. the word "place" in a README) from producing
# nonsense capability claims.  "device.*" is always allowed.
CAP_PREFIX_FAMILY = {
    "world.": SIM_FAMILIES,
    "motion.": {"ros2", "ros1", "gazebo", "mujoco", "pybullet", "isaac-sim",
                "isaac-lab", "isaac-gym", "webots", "unity", "sapien", "drake",
                "drake", "brax-mjx", "habitat", "airsim", "lerobot-real",
                "gymnasium", "dm-env", "python-object", "other", "http-api",
                "mcp-proxy"},
    "manipulation.": {"ros2", "ros1", "gazebo", "mujoco", "pybullet",
                      "isaac-sim", "isaac-lab", "isaac-gym", "webots", "unity",
                      "sapien", "drake", "habitat", "lerobot-real",
                      "gymnasium", "dm-env", "python-object", "other"},
    "sensing.": {"ros2", "ros1", "gazebo", "mujoco", "pybullet", "isaac-sim",
                 "isaac-lab", "isaac-gym", "webots", "unity", "sapien",
                 "drake", "brax-mjx", "habitat", "airsim (unreal)",
                 "airsim", "lerobot-real", "python-object", "other",
                 "http-api", "mcp-proxy", "serial", "scpi-visa", "qcodes",
                 "bluesky-ophyd", "micromanager", "sila2", "flowchem",
                 "opentrons", "pylabrobot", "cli-process", "madsci"},
    "fluid.": {"pylabrobot", "opentrons", "flowchem", "sila2", "python-object",
               "other", "http-api", "mcp-proxy"},
    "sample.": {"pylabrobot", "opentrons", "flowchem", "python-object",
                "other", "http-api", "mcp-proxy"},
    "imaging.": {"micromanager", "python-object", "other", "http-api",
                 "mcp-proxy", "ros2", "ros1"},
    "optics.": {"micromanager", "python-object", "other", "http-api"},
    "measure.": {"scpi-visa", "qcodes", "bluesky-ophyd", "serial", "sila2",
                 "micromanager", "python-object", "other", "http-api",
                 "mcp-proxy", "flowchem", "opentrons", "pylabrobot"},
    "thermal.": {"flowchem", "opentrons", "pylabrobot", "python-object",
                 "other", "http-api", "serial"},
    "actuation.": {"serial", "http-api", "mcp-proxy", "python-object", "other",
                   "flowchem", "pylabrobot", "opentrons", "sila2"},
    "compute.": {"cli-process", "docker", "http-api", "mcp-proxy", "madsci",
                 "python-object", "other", "replay"},
    "process.": {"cli-process", "docker", "http-api", "mcp-proxy", "madsci",
                 "python-object", "other", "replay"},
}


def caps_allowed(family: str, cap: str) -> bool:
    if cap.startswith("device."):
        return True
    prefix = cap.split(".")[1] + "."
    allowed = CAP_PREFIX_FAMILY.get(prefix)
    if allowed is None:
        return True
    return family in allowed


def filter_caps(family: str, caps) -> list:
    out = []
    for cap in caps:
        if caps_allowed(family, cap) and cap not in out:
            out.append(cap)
    return out
