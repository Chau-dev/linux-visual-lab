import time

from app.monitors.filesystem import FileSystemMonitor


monitor = FileSystemMonitor("/home/dev/LinuxLab")

monitor.start()

print("Filesystem monitor running.")
print("Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping monitor...")
    monitor.stop()
