import unittest

from app.process.discovery import find_shell_processes


class TestShellDiscovery(unittest.TestCase):

    def test_find_shell_processes(self):
        # find_shell_processes should return a list without crashing
        shells = find_shell_processes()
        self.assertIsInstance(shells, list)


if __name__ == "__main__":
    shells = find_shell_processes()
    print("Shell processes:")
    for session in shells:
        print(f"PID={session.pid} COMMAND={session.command} TTY={session.tty} CWD={session.cwd}")
