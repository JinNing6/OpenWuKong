#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_multi_window_ops.py — 多窗口自动化操作测试

验证内容:
1. 枚举全部 IDE 窗口
2. 窗口间快速切换（焦点切换）
3. 在不同窗口执行只读操作（读取标签页、元素、状态）
4. 窗口切换准确性（切换后验证焦点是否正确）
5. 延迟基准测量
"""

from __future__ import annotations

import sys
import io
import time
import statistics

# 强制 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import psutil
from pywinauto import Desktop
from pywinauto.application import Application

SEP = "─" * 60


def perf(func, *args, **kwargs):
    """测量函数执行耗时"""
    t0 = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = (time.perf_counter() - t0) * 1000
    return result, elapsed


def format_stats(timings: list[float]) -> str:
    if not timings:
        return "N/A"
    avg = statistics.mean(timings)
    med = statistics.median(timings)
    mn = min(timings)
    mx = max(timings)
    return f"avg={avg:.0f}ms  med={med:.0f}ms  min={mn:.0f}ms  max={mx:.0f}ms"


def main():
    print("=" * 60)
    print("  多窗口自动化操作测试")
    print("=" * 60)

    desktop = Desktop(backend="uia")

    # ─────────────────────────────────────────
    # 1. 枚举全部 IDE 窗口
    # ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  1. 枚举全部 IDE 窗口")
    print(SEP)

    ide_windows = []  # (pid, title, window_wrapper)
    seen_titles = set()

    t0 = time.perf_counter()
    for w in desktop.windows():
        try:
            pid = w.process_id()
            proc = psutil.Process(pid)
            pname = proc.name().lower()
            if "antigravity" not in pname and "code" not in pname and "cursor" not in pname:
                continue
            title = w.window_text() or ""
            if not title or "Program Manager" in title or title in seen_titles:
                continue
            seen_titles.add(title)
            ide_windows.append((pid, title, w))
        except Exception:
            continue
    enum_ms = (time.perf_counter() - t0) * 1000

    print(f"  发现 {len(ide_windows)} 个 IDE 窗口 ({enum_ms:.0f}ms)")
    for i, (pid, title, _) in enumerate(ide_windows):
        project = title.split(" - ")[0] if " - " in title else title[:30]
        print(f"  [{i}] PID={pid}: {project}")

    if len(ide_windows) < 2:
        print("\n  ⚠ 需要至少 2 个 IDE 窗口来测试多窗口切换")
        print("  当前可用窗口不足，但仍会测试单窗口操作。")

    # ─────────────────────────────────────────
    # 2. 窗口焦点切换速度
    # ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  2. 窗口焦点切换速度")
    print(SEP)

    switch_timings = []
    if len(ide_windows) >= 2:
        # 在前 4 个窗口间来回切换
        test_windows = ide_windows[:min(4, len(ide_windows))]
        rounds = 3

        for rnd in range(rounds):
            for i, (pid, title, w) in enumerate(test_windows):
                t0 = time.perf_counter()
                try:
                    w.set_focus()
                    elapsed = (time.perf_counter() - t0) * 1000
                    switch_timings.append(elapsed)
                except Exception as e:
                    elapsed = (time.perf_counter() - t0) * 1000
                    switch_timings.append(elapsed)
                # 短暂等待确保切换完成
                time.sleep(0.1)

        print(f"  切换 {len(switch_timings)} 次: {format_stats(switch_timings)}")
    else:
        print("  ⚠ 仅 1 个窗口，跳过切换测试")

    # ─────────────────────────────────────────
    # 3. 切换后焦点验证（准确性测试）
    # ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  3. 窗口切换准确性验证")
    print(SEP)

    accuracy_results = []
    if len(ide_windows) >= 2:
        test_windows = ide_windows[:min(4, len(ide_windows))]

        for i, (pid, title, w) in enumerate(test_windows):
            project = title.split(" - ")[0] if " - " in title else title[:25]
            try:
                # 切换到目标窗口
                w.set_focus()
                time.sleep(0.15)

                # 验证焦点是否正确
                app = Application(backend="uia").connect(process=pid)
                try:
                    active = app.active_()
                    active_title = active.window_text() or ""
                    match = title[:20] in active_title or active_title[:20] in title
                except Exception:
                    # fallback: 检查 top_window
                    top = app.top_window()
                    top_title = top.window_text() or ""
                    match = title[:20] in top_title or top_title[:20] in title

                result = "✅" if match else "❌"
                accuracy_results.append(match)
                print(f"  {result} [{i}] {project[:25]} → 焦点验证 {'通过' if match else '失败'}")
            except Exception as e:
                accuracy_results.append(False)
                print(f"  ❌ [{i}] {project[:25]} → 异常: {str(e)[:40]}")

        correct = sum(1 for r in accuracy_results if r)
        total = len(accuracy_results)
        print(f"\n  准确率: {correct}/{total} ({correct/total*100:.0f}%)")
    else:
        print("  ⚠ 仅 1 个窗口，跳过准确性测试")

    # ─────────────────────────────────────────
    # 4. 跨窗口元素读取速度
    # ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  4. 跨窗口元素读取速度")
    print(SEP)

    read_timings = []
    test_windows = ide_windows[:min(3, len(ide_windows))]

    for i, (pid, title, w) in enumerate(test_windows):
        project = title.split(" - ")[0] if " - " in title else title[:25]

        try:
            app = Application(backend="uia").connect(process=pid)
            wins = app.windows()

            # 只读第一个窗口的控件
            target_win = wins[0] if wins else app.top_window()

            t0 = time.perf_counter()
            descendants = target_win.descendants()
            elapsed = (time.perf_counter() - t0) * 1000
            read_timings.append(elapsed)

            # 统计关键元素
            tabs = []
            buttons_count = 0
            edits_count = 0
            for d in descendants:
                try:
                    ct = d.element_info.control_type or ""
                    name = d.element_info.name or ""
                    if ct == "TabItem" and name:
                        tabs.append(name[:30])
                    elif ct == "Button":
                        buttons_count += 1
                    elif ct == "Edit":
                        edits_count += 1
                except Exception:
                    continue

            print(f"  [{i}] {project[:25]}: {len(descendants)} elements in {elapsed:.0f}ms")
            print(f"      Tabs:{len(tabs)} Buttons:{buttons_count} Edits:{edits_count}")
        except Exception as e:
            print(f"  [{i}] {project[:25]}: ERROR {str(e)[:40]}")

    if read_timings:
        print(f"\n  元素读取: {format_stats(read_timings)}")

    # ─────────────────────────────────────────
    # 5. 连续切换+读取循环（模拟巡检）
    # ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  5. 模拟巡检循环（切换+读取 × 全部窗口）")
    print(SEP)

    if len(ide_windows) >= 2:
        test_windows = ide_windows[:min(4, len(ide_windows))]
        patrol_timings = []

        for rnd in range(2):  # 2 轮巡检
            rnd_start = time.perf_counter()

            for i, (pid, title, w) in enumerate(test_windows):
                try:
                    # 切换
                    w.set_focus()
                    time.sleep(0.05)

                    # 读取
                    app = Application(backend="uia").connect(process=pid)
                    win = app.windows()[0] if app.windows() else app.top_window()

                    # 快速扫描：只读 TabItem 和 Button 数量
                    tab_count = 0
                    btn_count = 0
                    for d in win.descendants():
                        try:
                            ct = d.element_info.control_type or ""
                            if ct == "TabItem":
                                tab_count += 1
                            elif ct == "Button":
                                btn_count += 1
                        except Exception:
                            continue
                except Exception:
                    continue

            rnd_elapsed = (time.perf_counter() - rnd_start) * 1000
            patrol_timings.append(rnd_elapsed)
            print(f"  巡检轮 {rnd+1}: {len(test_windows)} 窗口 in {rnd_elapsed:.0f}ms"
                  f" ({rnd_elapsed/len(test_windows):.0f}ms/窗口)")

        if patrol_timings:
            avg_per_window = statistics.mean(patrol_timings) / len(test_windows)
            print(f"\n  平均每窗口耗时: {avg_per_window:.0f}ms")
            print(f"  总巡检耗时: {format_stats(patrol_timings)}")

            # 推算能力上限
            max_windows_per_sec = 1000 / avg_per_window if avg_per_window > 0 else 999
            print(f"  理论上限: 每秒可巡检 {max_windows_per_sec:.1f} 个窗口")
    else:
        print("  ⚠ 仅 1 个窗口，跳过巡检测试")

    # ─────────────────────────────────────────
    # 6. 安全操作测试（只读）
    # ─────────────────────────────────────────
    print(f"\n{SEP}")
    print("  6. 安全操作测试（读取 AI 状态）")
    print(SEP)

    # 回到第一个窗口
    if ide_windows:
        pid, title, w = ide_windows[0]
        try:
            w.set_focus()
            time.sleep(0.1)

            app = Application(backend="uia").connect(process=pid)
            wins = app.windows()

            ai_signals = []
            for win in wins[:3]:
                try:
                    for d in win.descendants():
                        try:
                            ct = d.element_info.control_type or ""
                            name = (d.element_info.name or "").strip()
                            if not name:
                                continue

                            name_lower = name.lower()

                            # 检测 AI 模型按钮
                            if ct == "Button":
                                for model in ["claude", "gpt", "gemini", "copilot"]:
                                    if model in name_lower:
                                        ai_signals.append(f"🤖 Model: {name}")
                                        break

                            # 检测 Agent 开关
                            if ct == "CheckBox" and "agent" in name_lower:
                                try:
                                    state = d.get_toggle_state()
                                    status = "ON" if state == 1 else "OFF"
                                    ai_signals.append(f"🔘 Agent: {status}")
                                except Exception:
                                    ai_signals.append(f"🔘 Agent: {name}")

                        except Exception:
                            continue
                except Exception:
                    continue

            if ai_signals:
                for sig in ai_signals[:5]:
                    print(f"  {sig}")
            else:
                print("  未检测到 AI 信号（可能该窗口没有 AI 面板）")
        except Exception as e:
            print(f"  读取失败: {e}")

    # ─────────────────────────────────────────
    # 总结
    # ─────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  测试总结")
    print("=" * 60)
    print(f"  IDE 窗口数: {len(ide_windows)}")
    if switch_timings:
        print(f"  焦点切换: {format_stats(switch_timings)}")
    if accuracy_results:
        correct = sum(1 for r in accuracy_results if r)
        print(f"  切换准确率: {correct}/{len(accuracy_results)}")
    if read_timings:
        print(f"  元素读取: {format_stats(read_timings)}")
    print()


if __name__ == "__main__":
    main()
