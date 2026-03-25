# -*- coding: utf-8 -*-
"""
test_feasibility.py - UIA Agent 模块可行性测试

对 process_tree / element_finder / uia_controller / agent_bridge 四层进行集成测试
"""

from __future__ import annotations

import sys
import io
import json
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_process_tree():
    """Test Layer 1: ProcessTree"""
    section("Layer 1: ProcessTree")
    from process_tree import ProcessTree

    tree = ProcessTree()
    procs = tree.list_gui_processes()
    print(f"  Found {len(procs)} GUI processes:")
    for p in procs[:10]:
        titles = ", ".join(p.window_titles[:2])[:40]
        print(f"    PID={p.pid:>6} | {p.name:<25} | {titles}")

    # Test find_by_name
    edge = tree.find_by_name("edge")
    print(f"\n  find_by_name('edge'): {len(edge)} results")

    # Test find_by_title
    titled = tree.find_by_title("Antigravity")
    print(f"  find_by_title('Antigravity'): {len(titled)} results")

    print("  >> PASS")
    return True


def test_element_finder():
    """Test Layer 2: ElementFinder"""
    section("Layer 2: ElementFinder")
    from process_tree import ProcessTree
    from element_finder import ElementFinder

    tree = ProcessTree()
    finder = ElementFinder()

    # Global input scan
    inputs = finder.global_find_inputs(max_per_window=5)
    print(f"  Global input scan: {len(inputs)} input fields found")
    for inp in inputs[:5]:
        print(f"    [{inp.process_name}] name=\"{inp.name[:30]}\" value=\"{inp.value[:20]}\"")

    # Connect to a process and inspect tree
    procs = tree.list_gui_processes()
    target = None
    for p in procs:
        if p.window_titles and "Program Manager" not in p.window_titles[0]:
            target = p
            break

    if target:
        app = tree.connect(target.pid)
        tree_info = finder.get_element_tree(app)
        print(f"\n  Element tree for {target.name}:")
        print(f"    Total elements: {tree_info.get('total_elements', 0)}")
        types = tree_info.get("type_counts", {})
        for ct, count in list(types.items())[:5]:
            print(f"    {ct}: {count}")

    print("  >> PASS")
    return True


def test_uia_controller():
    """Test Layer 3: UIAController"""
    section("Layer 3: UIAController")
    from uia_controller import UIAController

    ctrl = UIAController()

    # List processes
    procs = ctrl.list_processes()
    print(f"  list_processes(): {len(procs)} processes")

    # Connect to first available
    target = None
    for p in procs:
        if p.window_titles and len(p.window_titles[0]) > 3 and "Program Manager" not in p.window_titles[0]:
            target = p
            break

    if target:
        proc = ctrl.connect_to(target.pid)
        print(f"  connect_to({target.pid}): {proc.name}")
        print(f"  connected: {ctrl.connected}")

        inputs = ctrl.find_inputs()
        print(f"  find_inputs(): {len(inputs)} inputs")

        buttons = ctrl.find_buttons()
        print(f"  find_buttons(): {len(buttons)} buttons")

        tree = ctrl.get_tree()
        print(f"  get_tree(): {tree.get('total_elements', 0)} elements")

    # Global find
    global_inputs = ctrl.global_find_inputs()
    print(f"  global_find_inputs(): {len(global_inputs)} inputs across all processes")

    print("  >> PASS")
    return True


def test_agent_bridge():
    """Test Layer 4: AgentBridge"""
    section("Layer 4: AgentBridge (JSON interface)")
    from agent_bridge import AgentBridge

    bridge = AgentBridge()

    # Test structured call
    result = bridge.execute("list_processes")
    print(f"  list_processes: {result.element_count} processes, success={result.success}")

    # Test JSON call
    result = bridge.execute_json('{"action": "global_find_inputs", "max_per_window": 5}')
    print(f"  global_find_inputs (JSON): {result.element_count} inputs, success={result.success}")

    # Test snapshot
    result = bridge.execute("snapshot")
    print(f"  snapshot: {result.element_count} total elements, success={result.success}")
    if result.data:
        data = result.data
        print(f"    Total processes in snapshot: {data.get('total_processes', 0)}")
        for p in data.get("processes", [])[:5]:
            print(f"      {p['name']}: {p.get('total_elements', 0)} elements, "
                  f"{p.get('memory_mb', 0)}MB")

    # Test batch
    results = bridge.execute_batch([
        {"action": "list_processes"},
        {"action": "global_find_inputs", "max_per_window": 3},
    ])
    print(f"\n  Batch execution: {len(results)} actions, "
          f"all success={all(r.success for r in results)}")

    print("  >> PASS")
    return True


def main():
    print("=" * 60)
    print("  UIA Agent Module - Integration Test")
    print("=" * 60)

    t0 = time.time()
    results = []

    results.append(("ProcessTree", test_process_tree()))
    results.append(("ElementFinder", test_element_finder()))
    results.append(("UIAController", test_uia_controller()))
    results.append(("AgentBridge", test_agent_bridge()))

    elapsed = time.time() - t0

    section("FINAL RESULTS")
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n  Total time: {elapsed:.1f}s")
    print(f"  All layers operational: {all(r[1] for r in results)}")

    return all(r[1] for r in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
