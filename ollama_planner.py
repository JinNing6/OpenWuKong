# -*- coding: utf-8 -*-
"""
ollama_planner.py - Ollama LLM 驱动的 ReAct 循环规划器

将自然语言任务转换为 UIA 操作序列:
  用户: "在 Antigravity 的终端中输入 git status"
    ↓
  Ollama LLM → JSON 指令 → agent_bridge 执行 → 观察结果 → 下一步
    ↓
  循环直到任务完成或达到最大步数

使用方式:
    python ollama_planner.py "在终端中输入 git pull"
    python ollama_planner.py "点击文件菜单，打开设置"
    python ollama_planner.py --target Antigravity.exe "找到搜索框并输入 hello"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import io
import requests
from typing import Optional

# 确保模块可以互相导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ─────────────────────────── 配置 ───────────────────────────

def load_planner_config() -> dict:
    """加载规划器配置"""
    defaults = {
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "qwen2.5:7b",
        "max_steps": 15,
        "target_process": "Antigravity.exe",
        "temperature": 0.3,
        "verbose": True,
    }
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            for key in defaults:
                if key in user_config:
                    defaults[key] = user_config[key]
        except Exception:
            pass
    return defaults


# ─────────────────────────── System Prompt ───────────────────────────

SYSTEM_PROMPT = """You are a Windows desktop automation agent. You control applications through the UIA (UI Automation) framework.

## Your Capabilities

You can issue JSON commands to interact with desktop applications. Available actions:

### Discovery
- `{"action": "list_processes"}` — List all GUI processes
- `{"action": "snapshot"}` — Get structured UI snapshot of all windows

### Connection
- `{"action": "connect", "target": "<PID or process name>"}` — Connect to a process

### Element Search (requires connection first)
- `{"action": "find_inputs"}` — Find all input fields
- `{"action": "find_buttons"}` — Find all buttons
- `{"action": "find_texts"}` — Find all text elements
- `{"action": "find_by_name", "name": "<partial name>"}` — Find elements by name
- `{"action": "find_by_id", "automation_id": "<id>"}` — Find element by AutomationId
- `{"action": "get_tree"}` — Get full element tree

### Interaction (requires connection + element search first)
- `{"action": "click", "button_name": "<name>"}` — Click a button
- `{"action": "type_text", "field_name": "<name>", "text": "<text>"}` — Type text into a field
- `{"action": "find_and_type", "field_name": "<name>", "text": "<text>"}` — Find input and type
- `{"action": "find_and_click", "button_name": "<name>"}` — Find button and click
- `{"action": "read_value", "name": "<name>"}` — Read element value
- `{"action": "focus", "name": "<name>"}` — Focus an element
- `{"action": "wait_for_element", "name": "<name>", "timeout": 10}` — Wait for element to appear

## Response Format

You MUST respond with a JSON object in this exact format:

```json
{
  "thought": "Brief reasoning about what to do next",
  "action": {"action": "...", ...},
  "is_complete": false
}
```

When the task is fully done, respond:

```json
{
  "thought": "Task completed because...",
  "action": null,
  "is_complete": true
}
```

## Rules

1. ALWAYS connect to the target process first before interacting with elements
2. Use find_inputs/find_buttons/find_by_name to discover elements before clicking/typing
3. One action per step — observe the result before deciding the next action
4. If an action fails, try an alternative approach (different name, different method)
5. Keep thoughts concise (one sentence)
6. NEVER make up element names — only use names from search results
7. Respond ONLY with the JSON object, no extra text
"""


# ─────────────────────────── Ollama 客户端 ───────────────────────────

class OllamaClient:
    """Ollama REST API 客户端"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def has_model(self, model_name: str) -> bool:
        """检查模型是否已下载"""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                models = r.json().get("models", [])
                # 匹配 model_name 或 model_name:latest
                for m in models:
                    if m["name"] == model_name or m["name"].startswith(model_name + ":"):
                        return True
            return False
        except Exception:
            return False

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        """
        调用 Ollama /api/chat 接口

        Returns: LLM 的文本回复
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 1024,
            },
        }

        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama request timed out (120s)")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}")
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {e}")


# ─────────────────────────── LLM 回复解析 ───────────────────────────

def parse_llm_response(text: str) -> dict:
    """
    从 LLM 回复中提取 JSON 对象

    支持多种格式:
    - 纯 JSON
    - ```json ... ``` 代码块
    - 混合文本中的 JSON
    """
    text = text.strip()

    # 尝试 1: 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试 2: 提取 ```json ... ``` 代码块
    import re
    json_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_block:
        try:
            return json.loads(json_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试 3: 找到第一个 { ... } 块
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    # 无法解析 — 返回错误结构
    return {
        "thought": f"Failed to parse LLM response: {text[:200]}",
        "action": None,
        "is_complete": False,
    }


# ─────────────────────────── ReAct 循环器 ───────────────────────────

class ReActPlanner:
    """
    ReAct (Reasoning + Acting) 循环规划器

    流程: 观察 → 思考 → 行动 → 观察 → ...
    """

    def __init__(self, config: dict):
        self._config = config
        self._ollama = OllamaClient(
            base_url=config["ollama_base_url"],
            model=config["ollama_model"],
        )
        self._verbose = config.get("verbose", True)
        self._max_steps = config.get("max_steps", 15)
        self._temperature = config.get("temperature", 0.3)

        # 延迟导入 agent_bridge（需要 pywinauto 环境）
        from agent_bridge import AgentBridge
        self._bridge = AgentBridge()

    def run(self, task: str, target_process: Optional[str] = None) -> dict:
        """
        执行一个自然语言任务

        Args:
            task: 用户的自然语言指令
            target_process: 可选的目标进程名

        Returns: 执行摘要字典
        """
        self._print(f"\n{'=' * 60}")
        self._print(f"  Task: {task}")
        self._print(f"  Model: {self._config['ollama_model']}")
        self._print(f"  Target: {target_process or 'auto-detect'}")
        self._print(f"{'=' * 60}\n")

        # 构建初始上下文
        target_hint = f"\nTarget process: {target_process}" if target_process else ""
        user_message = f"Task: {task}{target_hint}"

        # 获取初始快照作为观察
        self._print("[Step 0] Taking initial snapshot...")
        snapshot_result = self._bridge.execute("snapshot")
        initial_observation = self._format_observation("snapshot", snapshot_result)

        # 构建消息历史
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{user_message}\n\nCurrent desktop state:\n{initial_observation}"},
        ]

        # ReAct 循环
        steps = []
        start_time = time.time()

        for step_num in range(1, self._max_steps + 1):
            self._print(f"\n[Step {step_num}/{self._max_steps}]")

            # 1. 思考 + 决定行动（调用 LLM）
            self._print("  Thinking...")
            try:
                llm_response = self._ollama.chat(
                    messages=messages,
                    temperature=self._temperature,
                )
            except RuntimeError as e:
                self._print(f"  ✗ LLM error: {e}")
                steps.append({"step": step_num, "error": str(e)})
                break

            # 2. 解析 LLM 回复
            parsed = parse_llm_response(llm_response)
            thought = parsed.get("thought", "")
            action = parsed.get("action")
            is_complete = parsed.get("is_complete", False)

            self._print(f"  Thought: {thought}")

            # 记录 LLM 回复到消息历史
            messages.append({"role": "assistant", "content": llm_response})

            step_record = {
                "step": step_num,
                "thought": thought,
                "action": action,
                "is_complete": is_complete,
            }

            # 3. 检查是否完成
            if is_complete:
                self._print(f"\n  ✓ Task completed: {thought}")
                steps.append(step_record)
                break

            # 4. 执行行动
            if action:
                action_str = json.dumps(action, ensure_ascii=False)
                self._print(f"  Action: {action_str}")

                try:
                    result = self._bridge.execute_json(json.dumps(action))
                    observation = self._format_observation(
                        action.get("action", "unknown"), result
                    )
                    step_record["result_success"] = result.success
                    step_record["observation_preview"] = observation[:200]

                    self._print(f"  Result: success={result.success}")
                    if not result.success and result.error:
                        self._print(f"  Error: {result.error}")

                except Exception as e:
                    observation = f"Execution error: {e}"
                    step_record["result_success"] = False
                    self._print(f"  ✗ Execution error: {e}")

                # 把观察结果反馈给 LLM
                messages.append({
                    "role": "user",
                    "content": f"Observation from action '{action.get('action', '')}\':\n{observation}",
                })
            else:
                self._print("  ⚠ No action specified")
                messages.append({
                    "role": "user",
                    "content": "No action was executed. Please specify an action or mark the task as complete.",
                })

            steps.append(step_record)

        elapsed = time.time() - start_time

        # 生成执行摘要
        summary = {
            "task": task,
            "model": self._config["ollama_model"],
            "total_steps": len(steps),
            "completed": any(s.get("is_complete") for s in steps),
            "elapsed_seconds": round(elapsed, 1),
            "steps": steps,
        }

        self._print(f"\n{'=' * 60}")
        self._print(f"  Summary")
        self._print(f"  Steps: {len(steps)}")
        self._print(f"  Completed: {summary['completed']}")
        self._print(f"  Time: {elapsed:.1f}s")
        self._print(f"{'=' * 60}\n")

        return summary

    def _format_observation(self, action_name: str, result) -> str:
        """将 ActionResult 格式化为 LLM 可读的观察文本"""
        if not result.success:
            return f"FAILED: {result.error}"

        data = result.data

        # 针对不同 action 类型优化输出格式，减少 token 消耗
        if action_name == "snapshot":
            if isinstance(data, dict):
                lines = [f"Desktop: {data.get('total_processes', 0)} processes"]
                for p in data.get("processes", [])[:10]:
                    windows = ", ".join(p.get("windows", [])[:2])[:60]
                    elems = p.get("total_elements", 0)
                    lines.append(f"  [{p['pid']}] {p['name']} | {windows} | {elems} elements")
                return "\n".join(lines)

        elif action_name == "list_processes":
            if isinstance(data, list):
                lines = [f"Found {len(data)} GUI processes:"]
                for p in data[:10]:
                    windows = ", ".join(p.get("windows", [])[:2])[:60]
                    lines.append(f"  [{p['pid']}] {p['name']} | {windows}")
                return "\n".join(lines)

        elif action_name in ("find_inputs", "find_buttons", "find_texts",
                             "find_by_name", "global_find_inputs"):
            if isinstance(data, list):
                lines = [f"Found {len(data)} elements:"]
                for i, e in enumerate(data[:20]):
                    name = e.get("name", "")[:40]
                    ctrl = e.get("control_type", "")
                    val = e.get("value", "")[:30]
                    aid = e.get("automation_id", "")
                    line = f"  [{i}] {ctrl} name=\"{name}\""
                    if val:
                        line += f" value=\"{val}\""
                    if aid:
                        line += f" id=\"{aid}\""
                    lines.append(line)
                return "\n".join(lines)

        elif action_name == "connect":
            if isinstance(data, dict):
                return f"Connected to PID {data.get('pid')} ({data.get('name')})"

        elif action_name in ("type_text", "find_and_type"):
            if isinstance(data, dict):
                return f"Typed \"{data.get('text', '')}\" into \"{data.get('field', data.get('target', ''))}\""

        elif action_name in ("click", "find_and_click"):
            if isinstance(data, dict):
                return f"Clicked \"{data.get('button', data.get('clicked', ''))}\""

        elif action_name == "read_value":
            if isinstance(data, dict):
                return f"Value of \"{data.get('name', '')}\": \"{data.get('value', '')}\""

        # 通用 fallback
        try:
            text = json.dumps(data, ensure_ascii=False, default=str)
            if len(text) > 2000:
                text = text[:2000] + "... (truncated)"
            return f"Success ({result.element_count} elements): {text}"
        except Exception:
            return f"Success ({result.element_count} elements)"

    def _print(self, msg: str):
        """条件输出"""
        if self._verbose:
            print(msg)


# ─────────────────────────── 入口 ───────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="UIA Agent - Ollama LLM Planner",
        epilog="Example: python ollama_planner.py \"在终端中输入 git status\"",
    )
    parser.add_argument(
        "task", nargs="?", default=None,
        help="Natural language task to execute",
    )
    parser.add_argument(
        "--target", type=str, default=None,
        help="Target process name (e.g. Antigravity.exe)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Ollama model name (e.g. qwen2.5:7b, qwen3:4b)",
    )
    parser.add_argument(
        "--max-steps", type=int, default=None,
        help="Maximum ReAct loop steps",
    )
    parser.add_argument(
        "--url", type=str, default=None,
        help="Ollama base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Interactive mode: enter tasks one by one",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()
    config = load_planner_config()

    # 命令行参数覆盖配置
    if args.target:
        config["target_process"] = args.target
    if args.model:
        config["ollama_model"] = args.model
    if args.max_steps is not None:
        config["max_steps"] = args.max_steps
    if args.url:
        config["ollama_base_url"] = args.url
    if args.quiet:
        config["verbose"] = False

    # 检查 Ollama 可用性
    print("Checking Ollama service...")
    client = OllamaClient(config["ollama_base_url"], config["ollama_model"])

    if not client.is_available():
        print(f"✗ Ollama is not running at {config['ollama_base_url']}")
        print("  Start it with: ollama serve")
        sys.exit(1)
    print(f"✓ Ollama is running")

    if not client.has_model(config["ollama_model"]):
        print(f"✗ Model '{config['ollama_model']}' not found")
        print(f"  Pull it with: ollama pull {config['ollama_model']}")
        sys.exit(1)
    print(f"✓ Model '{config['ollama_model']}' is ready")

    # 创建规划器
    planner = ReActPlanner(config)

    if args.interactive or args.task is None:
        # 交互模式
        print(f"\n{'=' * 60}")
        print("  UIA Agent — Interactive Mode")
        print(f"  Model: {config['ollama_model']}")
        print(f"  Target: {config['target_process']}")
        print(f"  Type 'quit' or 'exit' to stop")
        print(f"{'=' * 60}\n")

        while True:
            try:
                task = input(">>> Task: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            if not task:
                continue
            if task.lower() in ("quit", "exit", "q"):
                print("Bye!")
                break

            planner.run(task, target_process=config["target_process"])
            print()
    else:
        # 单次执行模式
        planner.run(args.task, target_process=config["target_process"])


if __name__ == "__main__":
    main()
