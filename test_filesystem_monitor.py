import time
from pathlib import Path

from app.monitors.filesystem import FileSystemMonitor


if __name__ == "__main__":
    lab_path = Path("/home/dev/LinuxLab")
    lab_path.mkdir(parents=True, exist_ok=True)

    monitor = FileSystemMonitor(str(lab_path))
    monitor.start()

    print("Filesystem monitor running.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop()
