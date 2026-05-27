import time
import psutil
import os
from openwukong.monitor.ai_monitor import MultiProjectAIMonitor

def test_performance():
    print("Starting IDE Monitor Performance Test...")
    monitor = MultiProjectAIMonitor()

    # 记录初始内存
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024 / 1024
    print(f"Initial Memory: {mem_before:.2f} MB")

    print("\nRunning 15 consecutive scans...")
    total_time = 0

    for i in range(15):
        start = time.time()
        # 执行一次快照
        states = monitor.scan_all()
        elapsed = time.time() - start
        total_time += elapsed

        mem_now = process.memory_info().rss / 1024 / 1024
        print(f"Scan {i+1}: {elapsed:.3f} seconds | Found {len(states)} projects | Mem: {mem_now:.2f} MB")

        # 打印一下找到的项目名称
        for state in states:
            print(f"  - {state.project_name}: mode={state.ai_status.value}, progress={state.progress_text}")

    print(f"\nAverage scan time: {total_time / 15:.3f} seconds")

    import gc
    gc.collect()

    mem_after = process.memory_info().rss / 1024 / 1024
    print(f"Final Memory (After GC): {mem_after:.2f} MB")

if __name__ == "__main__":
    test_performance()
