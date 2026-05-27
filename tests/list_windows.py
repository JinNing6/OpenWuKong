from pywinauto import Desktop
import psutil

def list_windows():
    print("--- Listing all Visible Windows ---")
    windows = Desktop(backend="uia").windows()
    for w in windows:
        try:
            pid = w.process_id()
            proc = psutil.Process(pid)
            pname = proc.name()
            title = w.window_text()
            if title:
                print(f"PID: {pid} | Process: {pname} | Title: {title}")
        except Exception as e:
            continue

if __name__ == "__main__":
    list_windows()
