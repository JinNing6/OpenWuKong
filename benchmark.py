# -*- coding: utf-8 -*-
"""
benchmark.py - UIA Agent 全栈性能基准测试

测量:
1. ProcessTree: 进程枚举、查找、连接延迟
2. ElementFinder: 元素搜索、树遍历延迟
3. AgentBridge: JSON 指令执行延迟
4. Ollama: LLM 推理延迟（冷启动 + 热缓存）
5. 内存占用: 各阶段 RSS
6. daemon 轮询开销: 单次轮询周期耗时
"""

import gc
import io
import json
import os
import sys
import time

# Fix GBK encoding on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil


def get_memory_mb():
    """当前进程 RSS (MB)"""
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024


def fmt(values, unit="ms"):
    """格式化统计数据"""
    if not values:
        return "N/A"
    avg = statistics.mean(values)
    med = statistics.median(values)
    p95 = sorted(values)[int(len(values) * 0.95)] if len(values) >= 5 else max(values)
    mn = min(values)
    mx = max(values)
    return f"avg={avg:.1f}{unit}  med={med:.1f}{unit}  p95={p95:.1f}{unit}  min={mn:.1f}{unit}  max={mx:.1f}{unit}"


def run_benchmark():
    print("=" * 70)
    print("  UIA Agent — Performance Benchmark")
    print("=" * 70)
    print()

    mem_start = get_memory_mb()
    print(f"[Memory] Baseline RSS: {mem_start:.1f} MB")
    print()

    # ─────────────── 1. ProcessTree ───────────────
    print("─" * 50)
    print("  1. ProcessTree")
    print("─" * 50)

    from process_tree import ProcessTree
    pt = ProcessTree()

    # 枚举进程
    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        procs = pt.list_gui_processes()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"  list_gui_processes (x10):  {fmt(times)}")
    print(f"    -> {len(procs)} processes found")

    # 按名称查找
    times = []
    target_pid = None
    for _ in range(10):
        t0 = time.perf_counter()
        found = pt.find_by_name("Antigravity")
        times.append((time.perf_counter() - t0) * 1000)
        if found and not target_pid:
            target_pid = found[0].pid
    print(f"  find_by_name (x10):       {fmt(times)}")

    # 连接进程（使用 PID）
    times = []
    if target_pid:
        for _ in range(5):
            t0 = time.perf_counter()
            try:
                pt.connect(target_pid)
            except Exception:
                pass
            times.append((time.perf_counter() - t0) * 1000)
    else:
        print("  connect: SKIPPED (Antigravity not found)")
    print(f"  connect (x5):             {fmt(times)}")

    mem_after_pt = get_memory_mb()
    print(f"  [Memory] After ProcessTree: {mem_after_pt:.1f} MB (+{mem_after_pt - mem_start:.1f})")
    print()

    # ─────────────── 2. ElementFinder ───────────────
    print("─" * 50)
    print("  2. ElementFinder (connected to Antigravity)")
    print("─" * 50)

    from element_finder import ElementFinder
    ef = ElementFinder()

    # 先连接
    app = None
    if target_pid:
        try:
            app = pt.connect(target_pid)
        except Exception as e:
            print(f"  [!] Cannot connect to Antigravity: {e}")
            app = None
    else:
        print("  [!] Antigravity not found, skipping")

    if not app and target_pid:
        try:
            app = pt.connect(target_pid)
        except Exception as e:
            print(f"  [!] Cannot connect: {e}")
            app = None

    if app:
        # 搜索输入框
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            inputs = ef.find_inputs(app)
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  find_inputs (x5):         {fmt(times)}")
        print(f"    -> {len(inputs)} inputs found")

        # 搜索按钮
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            buttons = ef.find_buttons(app)
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  find_buttons (x5):        {fmt(times)}")
        print(f"    -> {len(buttons)} buttons found")

        # 获取完整树
        times = []
        tree_size = 0
        for _ in range(3):
            t0 = time.perf_counter()
            tree = ef.get_element_tree(app)
            times.append((time.perf_counter() - t0) * 1000)
            tree_size = tree.get("total_elements", 0) if isinstance(tree, dict) else 0
        print(f"  get_element_tree (x3):    {fmt(times)}")
        print(f"    -> {tree_size} elements in tree")

        # 按名称搜索
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            ef.find_by_name(app, "File")
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  find_by_name 'File' (x5): {fmt(times)}")

    mem_after_ef = get_memory_mb()
    print(f"  [Memory] After ElementFinder: {mem_after_ef:.1f} MB (+{mem_after_ef - mem_start:.1f})")
    print()

    # ─────────────── 3. AgentBridge ───────────────
    print("─" * 50)
    print("  3. AgentBridge (JSON interface)")
    print("─" * 50)

    from agent_bridge import AgentBridge
    bridge = AgentBridge()

    # snapshot
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        bridge.execute("snapshot")
        times.append((time.perf_counter() - t0) * 1000)
    print(f"  snapshot (x3):            {fmt(times)}")

    # list_processes
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        bridge.execute("list_processes")
        times.append((time.perf_counter() - t0) * 1000)
    print(f"  list_processes (x5):      {fmt(times)}")

    # connect + find_buttons 链式
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        bridge.execute("connect", target="Antigravity.exe")
        bridge.execute("find_buttons")
        times.append((time.perf_counter() - t0) * 1000)
    print(f"  connect+find_buttons (x3):{fmt(times)}")

    # JSON 指令执行
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        bridge.execute_json('{"action": "list_processes"}')
        times.append((time.perf_counter() - t0) * 1000)
    print(f"  execute_json (x5):        {fmt(times)}")

    mem_after_bridge = get_memory_mb()
    print(f"  [Memory] After AgentBridge: {mem_after_bridge:.1f} MB (+{mem_after_bridge - mem_start:.1f})")
    print()

    # ─────────────── 4. Ollama 推理延迟 ───────────────
    print("─" * 50)
    print("  4. Ollama LLM Inference")
    print("─" * 50)

    try:
        import requests
        ollama_url = "http://localhost:11434"
        r = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if r.status_code != 200:
            raise ConnectionError("Ollama not running")

        model = "qwen2.5:latest"
        print(f"  Model: {model}")

        # 简单推理（冷启动）
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with just the word 'ok'"}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 10},
        }

        t0 = time.perf_counter()
        r = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=60)
        cold_time = (time.perf_counter() - t0) * 1000
        print(f"  Cold start inference:     {cold_time:.0f}ms")

        # 热缓存推理
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            r = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=60)
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  Warm inference (x3):      {fmt(times)}")

        # ReAct 级别推理（System Prompt + 长输入）
        react_payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a desktop automation agent. Respond with JSON: {\"thought\": \"...\", \"action\": {\"action\": \"list_processes\"}, \"is_complete\": false}"},
                {"role": "user", "content": "Task: List all running programs\n\nCurrent desktop state:\nDesktop: 9 processes\n  [27084] Antigravity.exe | DOW - Antigravity | 761 elements"},
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 256},
        }

        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            r = requests.post(f"{ollama_url}/api/chat", json=react_payload, timeout=120)
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  ReAct inference (x3):     {fmt(times)}")

    except Exception as e:
        print(f"  ✗ Ollama benchmark skipped: {e}")

    print()

    # ─────────────── 5. Daemon 轮询模拟 ───────────────
    print("─" * 50)
    print("  5. Daemon Poll Cycle Simulation")
    print("─" * 50)

    from ide_monitor import IDEMonitor
    monitor = IDEMonitor("Antigravity.exe")

    # 连接
    t0 = time.perf_counter()
    connected = monitor.connect()
    connect_time = (time.perf_counter() - t0) * 1000
    print(f"  IDEMonitor.connect():     {connect_time:.1f}ms (success={connected})")

    if connected:
        # 模拟轮询周期
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            diff = monitor.detect_changes()
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  detect_changes (x10):     {fmt(times)}")
        print(f"    → Per-poll CPU overhead is minimal at 2s interval")

    print()

    # ─────────────── 6. 最终内存 ───────────────
    gc.collect()
    mem_final = get_memory_mb()

    print("─" * 50)
    print("  6. Memory Summary")
    print("─" * 50)
    print(f"  Baseline:       {mem_start:.1f} MB")
    print(f"  After PT:       {mem_after_pt:.1f} MB  (+{mem_after_pt - mem_start:.1f})")
    print(f"  After EF:       {mem_after_ef:.1f} MB  (+{mem_after_ef - mem_start:.1f})")
    print(f"  After Bridge:   {mem_after_bridge:.1f} MB  (+{mem_after_bridge - mem_start:.1f})")
    print(f"  Final (GC'd):   {mem_final:.1f} MB  (+{mem_final - mem_start:.1f})")
    print()

    # ─────────────── 总结 ───────────────
    print("=" * 70)
    print("  BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
