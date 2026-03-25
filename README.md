# 🐵 OpenWukong — 通用 IDE Agent 全时督导平台

> **火眼金睛** 看穿一切窗口状态 · **七十二变** 全平台适配 · **分身术** 多窗口并行 · **筋斗云** 1ms 切换

OpenWukong 是一个基于 Windows UIA 无障碍接口的 **全自动 IDE Agent 督导系统**，
能够 24/7 不间断监控多个智能 IDE（Cursor / Antigravity / VS Code 等）中的 AI Agent 运行状态，
当 Agent 完成任务时自动检查目标 → 未达标则续发指令（Steer），实现无人值守的持续优化。

## 🔥 核心能力

| 能力 | 描述 | 模块 |
|------|------|------|
| 🔍 火眼金睛 | 实时检测 AI Agent 状态 (Thinking/Idle/Error) | `ai_monitor.py` |
| 🎯 自动督导 | Agent 完成时检查目标 → 未达标自动续发指令 | `agent_supervisor.py` |
| 🪟 多窗口并行 | 同时监控 9+ IDE 窗口，1ms 焦点切换 | `uia_controller.py` |
| 🤖 Steer 续发 | 带速率限制 + 幂等键的安全操控 | `SteerOperator` |
| 🛡️ 24/7 保活 | 崩溃自动重启，持续运行 | `service_wrapper.py` |
| 📊 结构化日志 | JSON 督导报告 + 生命周期事件链 | `logger.py` |
| 🧠 LLM 规划 | Ollama 本地大模型智能决策 | `ollama_planner.py` |

## 🚀 快速开始

```bash
# 1. 初始化环境
start.bat

# 2. 扫描全部 IDE 窗口 AI 状态
start.bat ai scan

# 3. 生成督导配置
start.bat supervisor --gen-config goals.json

# 4. 编辑 goals.json 填入你的任务目标，然后启动
start.bat supervisor --config goals.json

# 5. 24 小时全时督导
start.bat supervisor --config goals.json --max-hours 24
```

## 📁 项目结构

```
openwukong/
├── agent_supervisor.py    # 🎯 核心 — 通用 IDE Agent 全时督导器
├── ai_monitor.py          # 🔍 多项目 AI 状态监控引擎
├── uia_controller.py      # 🎮 UIA 交互控制器（点击/输入/截图）
├── element_finder.py      # 🔎 智能元素定位器
├── ide_monitor.py         # 📊 IDE 状态变化检测器
├── uia_events.py          # ⚡ COM 事件订阅引擎
├── ollama_planner.py      # 🧠 LLM ReAct 规划器
├── agent_bridge.py        # 🌉 Agent 通信桥
├── daemon.py              # 👹 后台守护进程
├── watchdog.py            # 🐕 自愈看门狗
├── service_wrapper.py     # 🛡️ 24/7 服务包装器
├── logger.py              # 📝 结构化 JSON 日志
├── process_tree.py        # 🌳 进程树分析
├── benchmark.py           # ⏱️ 性能基准测试
├── vscode_ai_probe.py     # 🔬 VS Code AI 探针
├── config.json            # ⚙️ 全局配置
├── goals.json             # 🎯 督导目标配置
├── start.bat              # 🚀 统一入口
└── requirements.txt       # 📦 依赖清单
```

## 🧬 设计灵感

- **OpenClaw 龙虾** → LifecycleEvent（细粒度生命周期事件）
- **OpenClaw 龙虾** → Steer 续发机制（速率限制 + 幂等键）
- **Windows UIA** → 无障碍接口，无需视觉模型即可操控 IDE
- **西游记 悟空** → 火眼金睛 = 全域感知，七十二变 = 全平台适配

## 📊 性能基准

| 指标 | 数据 |
|------|------|
| 窗口枚举 | 9 窗口 / 257ms |
| 焦点切换 | avg **1ms** ⚡ |
| 切换准确率 | **100%** |
| 元素读取 | avg 289ms / 窗口 |
| AI 模型检测 | Claude Opus 4.6 ✅ |

## 📜 License

MIT
