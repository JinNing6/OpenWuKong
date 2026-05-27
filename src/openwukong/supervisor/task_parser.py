# -*- coding: utf-8 -*-
"""
task_parser.py — 自然语言任务解析器

将用户的自然语言描述转化为结构化的 TaskGoal 对象。

    用户输入: "帮我盯着 Cursor 里的 DOW 项目，ASR 要跑到 85% 以上"
        ↓  Ollama LLM 解析
    TaskGoal(window_match="DOW", task_name="安全攻防测试", goal="ASR > 85%", ...)

降级策略:
    Ollama 不可用 → 模板化规则解析（正则提取关键字段）
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from openwukong.core.constants import PROJECT_ALIASES, DEFAULT_SUCCESS_KEYWORDS, DEFAULT_FAILURE_KEYWORDS
from openwukong.core.logger import get_logger, log_event

logger = get_logger("task_parser")

# 模型优先级列表（越靠前越优先，解析任务优先选小模型保证速度）
_MODEL_PRIORITY = [
    "qwen3:4b", "qwen3:8b", "qwen3:14b",
    "qwen3.5:9b", "qwen3.5:35b",
    "qwen2.5:3b", "qwen2.5:latest",
]

_CONNECTOR_HINT_PATTERNS = {
    "codex": (r"\bcodex\b",),
    "cursor": (r"\bcursor\b", r"\bwindsurf\b"),
    "copilot": (r"github copilot", r"\bcopilot\b"),
    "browser": (r"浏览器", r"网页", r"网站", r"url", r"链接", r"https?://"),
    "terminal": (r"终端", r"\bterminal\b", r"powershell", r"\bpwsh\b", r"\bbash\b", r"\bshell\b", r"命令行"),
    "git": (r"\bgit\b", r"\bcommit\b", r"\bbranch\b", r"\brebase\b", r"\bstash\b", r"\bmerge\b", r"\bcheckout\b", r"pull request"),
}

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _detect_connector_hints(text: str) -> list[str]:
    lowered = (text or "").strip().lower()
    if not lowered:
        return []

    hints = []
    for connector_hint, patterns in _CONNECTOR_HINT_PATTERNS.items():
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
            hints.append(connector_hint)
    return hints


def _extract_resource_url(text: str) -> str:
    match = _URL_RE.search(text or "")
    return match.group(0) if match else ""


def _infer_connector_hint(user_input: str, task: dict) -> str:
    task_blob = " ".join(
        str(task.get(field, ""))
        for field in ("window_match", "task_name", "goal", "retry_command", "connector_hint")
    )
    task_hints = list(dict.fromkeys(_detect_connector_hints(task_blob)))
    if len(task_hints) == 1:
        return task_hints[0]

    global_hints = list(dict.fromkeys(_detect_connector_hints(user_input)))
    if len(global_hints) == 1:
        return global_hints[0]

    return ""


def _apply_connector_defaults(user_input: str, tasks: list[dict]) -> list[dict]:
    enriched: list[dict] = []

    for raw_task in tasks:
        task = dict(raw_task)
        hint = (task.get("connector_hint", "") or "").strip().lower()
        if not hint or hint == "auto":
            hint = _infer_connector_hint(user_input, task)

        task["connector_hint"] = hint or "auto"
        task.setdefault("workspace_path", "")
        task.setdefault("resource_url", "")

        if task["connector_hint"] in {"terminal", "git"} and not task["workspace_path"]:
            task["workspace_path"] = "."

        if task["connector_hint"] == "browser" and not task["resource_url"]:
            task_blob = " ".join(
                str(task.get(field, ""))
                for field in ("goal", "retry_command", "window_match")
            )
            task["resource_url"] = _extract_resource_url(task_blob) or _extract_resource_url(user_input)

        enriched.append(task)

    return enriched


# ═══════════════════════════════════════════════
#  Prompt 模板
# ═══════════════════════════════════════════════

TASK_PARSE_PROMPT = """你是一个任务解析器。用户会用自然语言描述他需要督导的 IDE 工作任务。
你需要将其解析为结构化的 JSON 数组。

用户描述可能包含一个或多个任务，用换行、"同时"、"另外"等词分隔。

当前系统检测到以下活跃的 IDE 窗口（可用于辅助匹配 window_match）:
{active_windows}

每个任务必须包含以下字段:
- "window_match": 窗口标题匹配关键词（核心要求：必须从【活跃的 IDE 窗口】列表中提取精确的项目名或窗口标题片段）。
  注意：如果用户说的是别名（如"悟空"、"霜落"、"提莫"），你必须优先将其映射为对应的核心标识符（如"openwukong"、"frostfall"、"timo"）。
- "task_name": 简短任务名（中文，不超过 10 字）
- "goal": 达标条件描述（一句话）
- "success_keywords": 成功信号关键词数组（3-5个英文关键词或中文短语）
- "failure_keywords": 失败信号关键词数组（2-3个）
- "retry_command": 未达标时发给 AI Agent 的续发指令（中文，100字以内，要具体可执行）

返回严格的 JSON 数组（即使只有一个任务也用数组包裹），不要多余文字。
示例输出格式:
[
  {{
    "window_match": "DOW",
    "task_name": "安全攻防测试",
    "goal": "全部攻击向量 ASR > 85%",
    "success_keywords": ["ASR: 0.9", "ASR: 0.8", "passed", "达标"],
    "failure_keywords": ["Error", "failed", "rate limit"],
    "retry_command": "分析上一轮实验中的失败用例，调整参数后重新执行，直到超过目标。"
  }}
]
注意：必须严格遵守上述格式，不要使用多余的大括号包裹！"""


# ═══════════════════════════════════════════════
#  TaskParser — 自然语言 → TaskGoal
# ═══════════════════════════════════════════════

class TaskParser:
    """
    自然语言任务解析器

    使用示例:
        parser = TaskParser()
        goals_data = parser.parse("帮我盯着 DOW 项目，ASR 要达到 85%")
        # → [{"window_match": "DOW", "task_name": "安全攻防测试", ...}]
    """

    def __init__(
        self,
        model: str = "",
        base_url: str = "",
        timeout: float = 30.0,
    ):
        # 从 config.json 读取默认值
        cfg = self._load_config()
        self._base_url = base_url or cfg.get("ollama_base_url", "http://localhost:11434")
        self._timeout = timeout

        # LLM 可用性标志（启动时前置检查）
        self._llm_available = self._check_ollama_health()

        # 模型选择：参数 > config.json > 自动探测
        requested_model = model or cfg.get("ollama_model", "")
        self._model = self._resolve_model(requested_model)

        # 输出初始化状态
        if self._llm_available:
            log_event(
                logger,
                f"TaskParser 初始化: model={self._model}, base_url={self._base_url}, LLM=✅",
                event_type="parser_init",
            )
        else:
            log_event(
                logger,
                f"[CRITICAL] TaskParser: Ollama 服务不可用 ({self._base_url})，智能解析能力已禁用，仅规则引擎可用",
                event_type="parser_init_no_llm",
                level=40,
            )

    def _check_ollama_health(self) -> bool:
        """前置检查 Ollama 服务是否可用"""
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                return len(models) > 0
        except Exception:
            return False

    @classmethod
    def check_ollama_health_static(cls, base_url: str = "http://localhost:11434") -> tuple[bool, str]:
        """
        静态方法：检查 Ollama 服务健康状态

        Returns:
            (is_healthy, message)
        """
        import urllib.request
        try:
            req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    return True, f"Ollama 正常运行，可用模型: {', '.join(models[:5])}"
                else:
                    return False, "Ollama 服务运行中但无已安装模型"
        except Exception as e:
            return False, f"Ollama 服务不可用: {e}"


    @staticmethod
    def _load_config() -> dict:
        """从项目根目录加载 config.json"""
        # 向上查找 config.json：src/openwukong/supervisor/ → 项目根
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            candidate = os.path.join(here, "config.json")
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    break
            here = os.path.dirname(here)
        return {}

    def _resolve_model(self, requested: str) -> str:
        """
        确定可用模型：
        1. 如果请求的模型在本地可用 → 直接使用
        2. 否则按优先级列表选最佳可用模型
        3. 全部不可用 → 返回请求的原始值（让后续降级逻辑处理）
        """
        available = self._list_local_models()
        if not available:
            # Ollama 可能没运行，返回原始请求值
            return requested or _MODEL_PRIORITY[0]

        # 请求的模型直接可用
        if requested and requested in available:
            return requested

        # 按优先级选择
        for candidate in _MODEL_PRIORITY:
            if candidate in available:
                if requested:
                    log_event(
                        logger,
                        f"请求模型 '{requested}' 不可用, 自动切换到 '{candidate}'",
                        event_type="parser_model_fallback",
                        level=30,
                    )
                return candidate

        # 优先级列表里没有匹配的，但 Ollama 有其他模型 → 选第一个 qwen 系列
        for m in sorted(available):
            if "qwen" in m.lower():
                log_event(
                    logger,
                    f"使用本地 qwen 模型: '{m}'",
                    event_type="parser_model_auto",
                )
                return m

        # 实在没有 qwen 模型，返回原始请求值
        return requested or _MODEL_PRIORITY[0]

    def _list_local_models(self) -> set[str]:
        """快速查询 Ollama 已安装模型列表"""
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {m["name"] for m in data.get("models", [])}
        except Exception:
            return set()

    def parse(
        self,
        user_input: str,
        active_windows: list[str] = None,
    ) -> list[dict]:
        """
        将自然语言描述解析为任务配置数组

        Args:
            user_input: 用户的自然语言描述
            active_windows: 当前活跃的 IDE 窗口标题列表（辅助匹配）

        Returns:
            解析后的任务字典列表，每个字典对应一个 TaskGoal 的初始化参数
            每个结果包含额外字段 _parsed_by: "llm" | "rules"
        """
        if not user_input or len(user_input.strip()) < 2:
            log_event(logger, f"输入 '{user_input}' 过短，放弃解析", level=30)
            return []

        # 构建活跃窗口上下文
        windows_text = "无（未检测到活跃 IDE）"
        if active_windows:
            windows_text = "\n".join(f"  - {w}" for w in active_windows)

        # 尝试 LLM 解析（如果已知不可用则跳过网络请求）
        if self._llm_available:
            result = self._parse_with_llm(user_input, windows_text)
            if result is not None:
                result = _apply_connector_defaults(user_input, result)
                for task in result:
                    task["_parsed_by"] = "llm"
                return result
            # LLM 调用失败（可能是临时网络问题），更新状态
            self._llm_available = self._check_ollama_health()
        else:
            # 重新检查一次（可能 Ollama 刚启动）
            self._llm_available = self._check_ollama_health()
            if self._llm_available:
                result = self._parse_with_llm(user_input, windows_text)
                if result is not None:
                    result = _apply_connector_defaults(user_input, result)
                    for task in result:
                        task["_parsed_by"] = "llm"
                    log_event(logger, "Ollama 服务已恢复，智能解析重新启用", event_type="parser_llm_recovered")
                    return result

        # LLM 不可用，降级为规则解析（明确警告）
        log_event(
            logger,
            "[WARNING] Ollama 不可用，降级为模板规则解析。"
            "解析精度将大幅下降。请确保 Ollama 服务正在运行。",
            event_type="parser_fallback",
            level=30,
        )
        result = _apply_connector_defaults(user_input, self._parse_with_rules(user_input))
        for task in result:
            task["_parsed_by"] = "rules"
        return result

    def _parse_with_llm(
        self,
        user_input: str,
        windows_text: str,
    ) -> Optional[list[dict]]:
        """使用 Ollama LLM 解析"""
        import urllib.request

        system_prompt = TASK_PARSE_PROMPT.format(active_windows=windows_text)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,  # 低温度保证输出稳定
                "num_predict": 1024,
            },
        }

        try:
            t0 = time.perf_counter()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                response_text = result.get("message", {}).get("content", "")

            elapsed = time.perf_counter() - t0
            log_event(
                logger,
                f"LLM 解析完成 ({elapsed:.1f}s)",
                event_type="parser_llm_ok",
            )

            # 提取并验证 JSON
            parsed = self._extract_json_array(response_text)
            validated = self._validate_tasks(parsed)
            return validated if validated else None

        except Exception as e:
            log_event(
                logger,
                f"Ollama 调用失败: {e}",
                event_type="parser_llm_error",
                level=30,
            )
            return None

    def _parse_with_rules(self, user_input: str) -> list[dict]:
        """
        规则降级解析（当 LLM 不可用时）

        使用正则和模板提取关键信息，生成基础配置。
        """
        # 尝试提取窗口/项目名
        window_match = ""
        # 常见模式: "盯着XX项目" / "打开XX" / "监控XX"
        patterns = [
            r"(?:盯着|监控|看着|督导|看下|帮我盯一下|督视)\s*(\S+?)\s*(?:项目|的|里|中|窗口|$)",
            r"(?:在|打开|寻找|定位)\s*(\S+?)\s*(?:项目|里|中|窗口|标题|$)",
            r"项目\s*[：:]\s*(\S+)",
            r"(\S+?)\s*项目",
        ]
        for pattern in patterns:
            m = re.search(pattern, user_input)
            if m:
                window_match = m.group(1).strip()
                # 去掉可能的末尾标点
                window_match = re.sub(r'[，。！？,!?\s]+$', '', window_match)
                break

        # 应用项目别名映射
        if window_match in PROJECT_ALIASES:
            window_match = PROJECT_ALIASES[window_match]
        elif not window_match:
            # 尝试整体匹配别名
            for alias, target in PROJECT_ALIASES.items():
                if alias in user_input:
                    window_match = target
                    break

        if not window_match:
            # 尝试提取英文关键词
            en_words = re.findall(r"[A-Za-z][\w.-]+", user_input)
            if en_words:
                window_match = en_words[0]
            else:
                window_match = "IDE"

        # 提取目标描述
        goal = user_input.strip()
        if len(goal) > 50:
            goal = goal[:50] + "..."

        # 生成默认配置
        # 尝试从用户输入中提取具体的行动指令，使 retry_command 更有针对性
        action_patterns = [
            (r"(?:运行|执行|跑)\s*([\S]+(?:\s+[\S]+){0,3})", "运行 {match}"),
            (r"(?:测试|test)\s*([\S]+(?:\s+[\S]+){0,3})", "重新运行测试: {match}"),
            (r"(?:编译|build|构建)\s*([\S]+(?:\s+[\S]+){0,2})", "重新编译: {match}"),
            (r"(?:修复|fix|解决)\s*([\S]+(?:\s+[\S]+){0,3})", "继续修复: {match}"),
        ]
        retry_cmd = f"请继续完成任务目标：{goal}。分析当前进展和错误日志，针对性修复问题后重试。"
        for pattern, template in action_patterns:
            m = re.search(pattern, user_input)
            if m:
                retry_cmd = (
                    f"检查上一轮的输出和错误日志。"
                    f"{template.format(match=m.group(1).strip())}，"
                    f"确保结果满足目标: {goal}。如有错误请逐一修复后重试。"
                )
                break

        task = {
            "window_match": window_match,
            "task_name": f"督导 {window_match}",
            "goal": goal,
            "success_keywords": DEFAULT_SUCCESS_KEYWORDS.copy(),
            "failure_keywords": DEFAULT_FAILURE_KEYWORDS.copy(),
            "retry_command": retry_cmd,
        }

        return [task]

    # ═══════════════════════════════════════════
    #  JSON 提取与验证
    # ═══════════════════════════════════════════

    @staticmethod
    def _extract_json_array(text: str) -> list[dict]:
        """从 LLM 输出中提取 JSON 数组"""
        text = text.strip()

        # 尝试直接解析（不做任何预处理，保留合法嵌套 JSON）
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        # 从 markdown 代码块中提取
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    result = json.loads(part)
                    if isinstance(result, list):
                        return result
                    if isinstance(result, dict):
                        return [result]
                except json.JSONDecodeError:
                    continue

        # 尝试找到 [...] 区间
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end])
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试找到 {...} 区间（单个任务）
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end])
                if isinstance(result, dict):
                    return [result]
            except json.JSONDecodeError:
                pass

        # Fallback: 清洗 LLM 双大括号幻觉 [ {{ "key"... }} ] -> [ { "key"... } ]
        # 放在最后，避免误伤含合法嵌套对象的 JSON
        cleaned = re.sub(r'\{\s*\{', '{', text)
        cleaned = re.sub(r'\}\s*\}', '}', cleaned)
        if cleaned != text:
            try:
                result = json.loads(cleaned)
                if isinstance(result, list):
                    return result
                if isinstance(result, dict):
                    return [result]
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 LLM 输出中提取 JSON: {text[:100]}")

    @staticmethod
    def _validate_tasks(tasks: list[dict]) -> list[dict]:
        """验证并补全任务字段"""
        REQUIRED_FIELDS = {"window_match", "task_name", "goal"}
        validated = []

        for task in tasks:
            if not isinstance(task, dict):
                continue
            # 检查必填字段
            if not all(task.get(f) for f in REQUIRED_FIELDS):
                continue

            # 补全缺失字段
            task.setdefault("success_keywords", ["done", "passed", "完成"])
            task.setdefault("failure_keywords", ["Error", "failed"])
            task.setdefault(
                "retry_command",
                f"继续完成任务: {task['goal']}。检查当前进展并修复问题。",
            )
            task.setdefault("max_retries", 30)
            task.setdefault("cooldown_sec", 10)
            task.setdefault("stall_timeout", 600)
            task.setdefault("connector_hint", "auto")
            task.setdefault("workspace_path", "")
            task.setdefault("resource_url", "")

            validated.append(task)

        return validated
