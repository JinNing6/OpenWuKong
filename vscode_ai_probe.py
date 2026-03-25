#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
vscode_ai_probe.py — VS Code 多项目 AI 面板 UIA 深度探测

探测目标:
1. 枚举所有 VS Code 进程（每个项目一个进程）
2. 探测每个窗口内的 AI 面板控件（Copilot Chat / Cline / Cursor 等）
3. 分析 Webview 容器的 UIA 可访问性
4. 检测 AI 运行状态（busy/thinking 指示器）

使用:
  python vscode_ai_probe.py
"""

import sys
import io
import json
import time
import psutil
from pywinauto import Desktop
from pywinauto.application import Application

# 强制 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SEPARATOR = "─" * 60


def find_vscode_processes() -> list[dict]:
    """查找所有 VS Code 进程"""
    results = []
    seen_pids = set()

    desktop = Desktop(backend="uia")
    for w in desktop.windows():
        try:
            pid = w.process_id()
            if pid in seen_pids:
                continue

            proc = psutil.Process(pid)
            pname = proc.name().lower()

            # VS Code 判定
            if "code" not in pname:
                continue

            title = w.window_text() or ""
            if not title:
                continue

            seen_pids.add(pid)
            results.append({
                "pid": pid,
                "name": proc.name(),
                "title": title,
                "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            continue

    return results


def probe_ai_panels(pid: int, title: str):
    """深度探测单个 VS Code 窗口中的 AI 相关控件"""
    print(f"\n  探测 PID={pid}: {title[:60]}")

    try:
        app = Application(backend="uia").connect(process=pid)
    except Exception as e:
        print(f"  [ERROR] 无法连接: {e}")
        return

    # 枚举所有窗口
    all_wins = []
    try:
        all_wins = app.windows()
    except Exception:
        try:
            all_wins = [app.top_window()]
        except Exception:
            print("  [ERROR] 无法获取窗口")
            return

    print(f"  窗口数量: {len(all_wins)}")

    for wi, win in enumerate(all_wins):
        try:
            wt = win.window_text() or "(untitled)"
            print(f"\n  === 窗口 {wi}: {wt[:60]} ===")
        except Exception:
            continue

        try:
            descendants = win.descendants()
            print(f"  总元素: {len(descendants)}")
        except Exception as e:
            print(f"  [ERROR] descendants 失败: {e}")
            continue

        # 分类统计
        type_counts = {}
        ai_related = []
        webviews = []
        progress_indicators = []
        tabs = []

        AI_KEYWORDS = [
            "copilot", "chat", "cline", "cursor", "ai", "assistant",
            "github", "gemini", "claude", "gpt", "thinking", "generating",
            "loading", "spinner", "busy", "agent",
        ]

        for d in descendants:
            try:
                ct = d.element_info.control_type or "Unknown"
                name = (d.element_info.name or "").strip()
                aid = (d.element_info.automation_id or "").strip()

                type_counts[ct] = type_counts.get(ct, 0) + 1

                # 检测 Webview 容器
                if "webview" in ct.lower() or "webview" in name.lower() or "webview" in aid.lower():
                    webviews.append({
                        "type": ct, "name": name[:60], "id": aid[:40],
                    })

                # 检测 AI 相关控件
                name_lower = name.lower()
                aid_lower = aid.lower()
                for kw in AI_KEYWORDS:
                    if kw in name_lower or kw in aid_lower:
                        ai_related.append({
                            "type": ct, "name": name[:60], "id": aid[:40],
                            "keyword": kw,
                        })
                        break

                # 检测进度/加载指示器
                if ct in ("ProgressBar", "Spinner") or "progress" in name_lower or "loading" in name_lower:
                    progress_indicators.append({
                        "type": ct, "name": name[:60],
                    })

                # 收集 Tab
                if ct == "TabItem":
                    tabs.append(name[:40])

            except Exception:
                continue

        # 输出
        print(f"\n  控件类型统计:")
        for ct, cnt in sorted(type_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {ct}: {cnt}")

        print(f"\n  标签页 ({len(tabs)}):")
        for t in tabs[:15]:
            print(f"    📄 {t}")

        if webviews:
            print(f"\n  🌐 Webview 容器 ({len(webviews)}):")
            for wv in webviews[:10]:
                print(f"    [{wv['type']}] {wv['name']} | id={wv['id']}")
        else:
            print(f"\n  🌐 Webview 容器: 未检测到")

        if ai_related:
            print(f"\n  🤖 AI 相关控件 ({len(ai_related)}):")
            for ar in ai_related[:20]:
                print(f"    [{ar['type']}] {ar['name']} (keyword={ar['keyword']}) | id={ar['id']}")
        else:
            print(f"\n  🤖 AI 相关控件: 未检测到")

        if progress_indicators:
            print(f"\n  ⏳ 进度指示器 ({len(progress_indicators)}):")
            for pi in progress_indicators:
                print(f"    [{pi['type']}] {pi['name']}")
        else:
            print(f"\n  ⏳ 进度指示器: 未检测到")

        # 尝试读取 Document/Text 类型的长文本（AI 输出区域）
        text_elements = []
        for d in descendants:
            try:
                ct = d.element_info.control_type or ""
                if ct in ("Document", "Edit", "Text"):
                    try:
                        text = d.window_text() or ""
                        if len(text) > 50:
                            name = d.element_info.name or ""
                            text_elements.append({
                                "type": ct,
                                "name": name[:40],
                                "text_len": len(text),
                                "preview": text[:80].replace("\n", "\\n"),
                            })
                    except Exception:
                        pass
            except Exception:
                continue

        if text_elements:
            print(f"\n  📝 有内容的文本区域 ({len(text_elements)}):")
            for te in text_elements[:10]:
                print(f"    [{te['type']}] {te['name']} ({te['text_len']} chars)")
                print(f"      预览: {te['preview']}")


def probe_any_ide():
    """如果没有 VS Code，探测当前可用 IDE 的 AI 面板"""
    desktop = Desktop(backend="uia")
    ide_keywords = ["code", "antigravity", "idea", "webstorm", "pycharm", "cursor"]
    
    for w in desktop.windows():
        try:
            pid = w.process_id()
            proc = psutil.Process(pid)
            pname = proc.name().lower()
            
            for kw in ide_keywords:
                if kw in pname:
                    title = w.window_text() or ""
                    if title:
                        print(f"\n  发现 IDE: {proc.name()} (PID={pid})")
                        probe_ai_panels(pid, title)
                        return True
        except Exception:
            continue
    return False


def main():
    print("=" * 60)
    print("  VS Code 多项目 AI 面板 — UIA 深度探测")
    print("=" * 60)

    t0 = time.perf_counter()

    # 查找 VS Code
    procs = find_vscode_processes()
    
    if procs:
        print(f"\n发现 {len(procs)} 个 VS Code 窗口:")
        for p in procs:
            print(f"  PID={p['pid']}: {p['title'][:60]} ({p['memory_mb']}MB)")
        
        print(f"\n{SEPARATOR}")
        for p in procs:
            probe_ai_panels(p["pid"], p["title"])
            print(f"\n{SEPARATOR}")
    else:
        print("\n⚠ 未发现 VS Code 进程，探测当前可用 IDE...")
        if not probe_any_ide():
            print("  未发现任何 IDE 进程。")

    elapsed = time.perf_counter() - t0
    print(f"\n探测耗时: {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
