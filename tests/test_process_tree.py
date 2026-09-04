import unittest
from pathlib import Path

from app.process.model import Process
from app.process.tree import build_process_tree, flatten_process_tree


class TestProcessTree(unittest.TestCase):

    def setUp(self):
        self.p_init = Process(1, 0, 1, 1, 0, 0, 0, None, "S", "systemd", "systemd", Path("/"))
        self.p_sshd = Process(500, 1, 500, 500, 0, 0, 0, None, "S", "sshd", "sshd", Path("/"))
        self.p_bash = Process(1000, 500, 1000, 1000, 1000, 1000, 1000, "/dev/pts/0", "S", "bash", "bash", Path("/home/dev"))
        self.p_sleep = Process(2000, 1000, 1000, 1000, 1000, 1000, 1000, "/dev/pts/0", "S", "sleep", "sleep 600", Path("/home/dev"))
        self.p_top = Process(2001, 1000, 2001, 1000, 2001, 1000, 1000, "/dev/pts/0", "R", "top", "top", Path("/home/dev"))

    def test_build_process_tree_hierarchy(self):
        """Verify process tree construction strictly from PID and PPID."""
        procs = {
            1: self.p_init,
            500: self.p_sshd,
            1000: self.p_bash,
            2000: self.p_sleep,
            2001: self.p_top,
        }

        roots = build_process_tree(procs)
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual(root.process.pid, 1)
        self.assertEqual(root.depth, 0)
        self.assertEqual(len(root.children), 1)

        sshd_node = root.children[0]
        self.assertEqual(sshd_node.process.pid, 500)
        self.assertEqual(sshd_node.depth, 1)
        self.assertEqual(len(sshd_node.children), 1)

        bash_node = sshd_node.children[0]
        self.assertEqual(bash_node.process.pid, 1000)
        self.assertEqual(bash_node.depth, 2)
        self.assertEqual(len(bash_node.children), 2)

        child_pids = [c.process.pid for c in bash_node.children]
        self.assertEqual(child_pids, [2000, 2001])
        self.assertEqual(bash_node.children[0].depth, 3)
        self.assertEqual(bash_node.children[1].depth, 3)

    def test_flatten_process_tree(self):
        """Verify pre-order depth-first flattening of tree."""
        procs = {
            1: self.p_init,
            500: self.p_sshd,
            1000: self.p_bash,
            2000: self.p_sleep,
            2001: self.p_top,
        }
        roots = build_process_tree(procs)
        flattened = flatten_process_tree(roots)

        expected_pids_depths = [
            (1, 0),
            (500, 1),
            (1000, 2),
            (2000, 3),
            (2001, 3),
        ]
        actual_pids_depths = [(p.pid, d) for p, d in flattened]
        self.assertEqual(actual_pids_depths, expected_pids_depths)

    def test_multiple_roots_and_missing_parents(self):
        """Verify processes with unobserved parents become independent root nodes."""
        procs = {
            1000: self.p_bash,
            2000: self.p_sleep,
            9999: Process(9999, 8888, 9999, 9999, 0, 1000, 1000, None, "S", "orphan", "orphan", Path("/")),
        }
        roots = build_process_tree(procs)
        root_pids = [r.process.pid for r in roots]
        self.assertEqual(root_pids, [1000, 9999])
        self.assertEqual(len(roots[0].children), 1)
        self.assertEqual(roots[0].children[0].process.pid, 2000)


if __name__ == "__main__":
    unittest.main()
