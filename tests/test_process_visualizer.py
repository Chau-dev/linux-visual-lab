import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.process.model import Process
from app.visualizers.process_view import ProcessTreeWidget, ProcessInspectorWidget, ProcessLabWidget
from app.ui.identity import get_identity_style


class TestProcessVisualizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.p_bash = Process(
            pid=21375,
            ppid=21155,
            pgid=21375,
            sid=21155,
            tpgid=21155,
            uid=1000,
            gid=1000,
            tty="/dev/pts/1",
            state="S",
            command="bash",
            cmdline="/bin/bash",
            cwd=Path("/home/dev"),
        )
        self.p_sleep = Process(
            pid=21400,
            ppid=21375,
            pgid=21375,
            sid=21155,
            tpgid=21155,
            uid=1000,
            gid=1000,
            tty="/dev/pts/1",
            state="S",
            command="sleep",
            cmdline="sleep 600",
            cwd=Path("/home/dev"),
        )
        self.p_cat = Process(
            pid=21450,
            ppid=21375,
            pgid=21375,
            sid=21155,
            tpgid=21155,
            uid=1000,
            gid=1000,
            tty="/dev/pts/2",
            state="S",
            command="cat",
            cmdline="cat /dev/urandom",
            cwd=Path("/home/dev"),
        )


    def test_tree_widget_rendering_and_selection(self):
        """Verify ProcessTreeWidget item population and hierarchy."""
        tree = ProcessTreeWidget()
        procs = {21375: self.p_bash, 21400: self.p_sleep}
        tree.update_processes(procs)

        self.assertEqual(tree.topLevelItemCount(), 1)
        root_item = tree.topLevelItem(0)
        self.assertEqual(root_item.data(1, 0x0100), 21375)
        self.assertEqual(root_item.childCount(), 1)
        child_item = root_item.child(0)
        self.assertEqual(child_item.data(1, 0x0100), 21400)

        # Select sleep process
        selected = tree.select_pid(21400)
        self.assertTrue(selected)
        self.assertEqual(tree.currentItem().data(1, 0x0100), 21400)

    def test_deterministic_identity_highlighting(self):
        """Verify identical IDs (PID 21375 == PGID 21375) share identical visual tokens."""
        pid_style = get_identity_style(self.p_bash.pid)
        pgid_style = get_identity_style(self.p_bash.pgid)
        ppid_style = get_identity_style(self.p_bash.ppid)
        sid_style = get_identity_style(self.p_bash.sid)
        tpgid_style = get_identity_style(self.p_bash.tpgid)

        # PID == PGID -> must have identical style
        self.assertEqual(pid_style, pgid_style)
        # PPID == SID == TPGID -> must have identical style
        self.assertEqual(ppid_style, sid_style)
        self.assertEqual(sid_style, tpgid_style)
        # Different values -> different styles
        self.assertNotEqual(pid_style, ppid_style)

    def test_inspector_widget_rendering(self):
        """Verify ProcessInspectorWidget context details, factual job control roles, controlling TTY, and stdin."""
        inspector = ProcessInspectorWidget()
        inspector.set_context(self.p_bash)

        self.assertIn("bash", inspector.name_label.text())
        self.assertIn("21375", inspector.lbl_pid.text())
        self.assertIn("21155", inspector.lbl_ppid.text())
        self.assertIn("Process Group Leader", inspector.lbl_roles.text())
        self.assertIn("1000", inspector.lbl_user.text())
        self.assertIn("/dev/pts/1", inspector.lbl_tty.text())
        self.assertIn("tty_nr", inspector.lbl_tty.text())
        self.assertIsNotNone(inspector.lbl_stdin.text())


    def test_lab_widget_filter(self):
        """Verify ProcessLabWidget search filtering."""
        lab = ProcessLabWidget()
        procs = {21375: self.p_bash, 21400: self.p_sleep}
        lab.update_processes(procs)

        # Filter for sleep
        lab.search_edit.setText("sleep")
        root = lab.tree_widget.topLevelItem(0)
        child = root.child(0)

        # Sleep child is visible, root is visible because it contains matching child
        self.assertFalse(child.isHidden())

        # Filter for non-existent
        lab.search_edit.setText("nonexistent_command_xyz")
        self.assertTrue(root.isHidden())

    def test_multi_term_simultaneous_filtering(self):
        """Verify multi-term filtering simultaneously matches multiple programs across branches."""
        lab = ProcessLabWidget()
        procs = {21375: self.p_bash, 21400: self.p_sleep, 21450: self.p_cat}
        lab.update_processes(procs)

        root = lab.tree_widget.topLevelItem(0)
        self.assertEqual(root.childCount(), 2)
        child_sleep = root.child(0)
        child_cat = root.child(1)

        # 1. Comma-separated multi-filter: 'sleep, cat'
        lab.search_edit.setText("sleep, cat")
        self.assertFalse(root.isHidden())
        self.assertFalse(child_sleep.isHidden())
        self.assertFalse(child_cat.isHidden())

        # 2. Pipe-separated multi-filter: 'sleep | cat'
        lab.search_edit.setText("sleep | cat")
        self.assertFalse(child_sleep.isHidden())
        self.assertFalse(child_cat.isHidden())

        # 3. Mixed command and PID: 'cat, 21400'
        lab.search_edit.setText("cat, 21400")
        self.assertFalse(child_sleep.isHidden())
        self.assertFalse(child_cat.isHidden())

        # 4. Multi-filter matching only one: 'sleep, nginx, redis'
        lab.search_edit.setText("sleep, nginx, redis")
        self.assertFalse(child_sleep.isHidden())
        self.assertTrue(child_cat.isHidden())



    def test_tree_auto_expansion_and_persistence(self):
        """Verify focused branch auto-expansion and expand/collapse state persistence."""
        lab = ProcessLabWidget()
        procs = {21375: self.p_bash, 21400: self.p_sleep}
        lab.update_processes(procs, focused_pid=21375)

        root = lab.tree_widget.topLevelItem(0)
        # Root is expanded because it is depth 0 and also ancestor of focused PID
        self.assertTrue(root.isExpanded())

        # Test collapse all
        lab.tree_widget.collapseAll()
        self.assertFalse(root.isExpanded())

        # Verify subsequent background update preserves user collapsed state
        lab.update_processes(procs)
        self.assertFalse(root.isExpanded())

        # Test expand all
        lab.tree_widget.expandAll()
        self.assertTrue(root.isExpanded())

        # Verify subsequent background update preserves user expanded state
        lab.update_processes(procs)
        self.assertTrue(root.isExpanded())

        # Test expand_to_pid specifically
        lab.tree_widget.collapseAll()
        self.assertFalse(root.isExpanded())
        expanded = lab.tree_widget.expand_to_pid(21400)
        self.assertTrue(expanded)
        self.assertTrue(root.isExpanded())

    def test_search_auto_expansion(self):
        """Verify search filtering automatically expands parent chain to matching node."""
        lab = ProcessLabWidget()
        procs = {21375: self.p_bash, 21400: self.p_sleep}
        lab.update_processes(procs)

        # Collapse all first
        lab.tree_widget.collapseAll()
        root = lab.tree_widget.topLevelItem(0)
        self.assertFalse(root.isExpanded())

        # Search for child command 'sleep'
        lab.search_edit.setText("sleep")
        self.assertTrue(root.isExpanded())
        self.assertFalse(root.child(0).isHidden())



    def test_inspector_toggle_button(self):
        """Verify inspector toggle button collapses/expands inspector widget."""
        lab = ProcessLabWidget()
        self.assertFalse(lab.inspector_widget.isHidden())

        # Click to hide
        lab.toggle_inspector_btn.setChecked(False)
        self.assertTrue(lab.inspector_widget.isHidden())

        # Click to show
        lab.toggle_inspector_btn.setChecked(True)
        self.assertFalse(lab.inspector_widget.isHidden())

    def test_pause_live_updates(self):
        """Verify pausing updates freezes the tree so the learner can inspect without table changing."""
        lab = ProcessLabWidget()
        procs1 = {21375: self.p_bash}
        lab.update_processes(procs1)
        self.assertEqual(lab.tree_widget.topLevelItemCount(), 1)

        # Pause updates
        lab.pause_btn.setChecked(True)
        self.assertTrue(lab.is_paused)
        self.assertIn("Resume", lab.pause_btn.text())

        # Incoming snapshot with new sleep process
        procs2 = {21375: self.p_bash, 21400: self.p_sleep}
        lab.update_processes(procs2)

        # Tree should remain frozen with only 1 process
        root = lab.tree_widget.topLevelItem(0)
        self.assertEqual(root.childCount(), 0)

        # Unpause / Resume
        lab.pause_btn.setChecked(False)
        self.assertFalse(lab.is_paused)
        self.assertIn("Pause", lab.pause_btn.text())

        # Now tree reflects updated snapshot
        root = lab.tree_widget.topLevelItem(0)
        self.assertEqual(root.childCount(), 1)

    def test_filter_presets(self):
        """Verify quick category filter presets in Process Lab."""
        lab = ProcessLabWidget()
        import os
        my_uid = os.getuid()

        p_shell = Process(pid=1000, ppid=1, pgid=1000, sid=1000, tpgid=1000, uid=my_uid, gid=1000, tty="/dev/pts/1", tty_nr=34817, command="bash")
        p_child = Process(pid=2000, ppid=1000, pgid=2000, sid=1000, tpgid=1000, uid=my_uid, gid=1000, tty="/dev/pts/1", tty_nr=34817, command="sleep", state="S")
        p_daemon = Process(pid=3000, ppid=1, pgid=3000, sid=3000, tpgid=0, uid=0, gid=0, tty=None, tty_nr=0, command="systemd-udevd", state="S")
        p_active = Process(pid=4000, ppid=1, pgid=4000, sid=4000, tpgid=0, uid=my_uid, gid=1000, tty=None, tty_nr=0, command="worker", state="R", derived_cpu_percent=15.0)

        procs = {1000: p_shell, 2000: p_child, 3000: p_daemon, 4000: p_active}
        lab.update_processes(procs, focused_pid=1000)

        # 1. Preset 'shell_tree' -> only shell 1000 and child 2000 visible
        lab.preset_combo.setCurrentIndex(1)  # shell_tree
        self.assertFalse(lab.tree_widget._tree_items[1000].isHidden())
        self.assertFalse(lab.tree_widget._tree_items[2000].isHidden())
        self.assertTrue(lab.tree_widget._tree_items[3000].isHidden())
        self.assertTrue(lab.tree_widget._tree_items[4000].isHidden())

        # 2. Preset 'user' -> root daemon 3000 hidden
        lab.preset_combo.setCurrentIndex(2)  # user
        self.assertFalse(lab.tree_widget._tree_items[1000].isHidden())
        self.assertFalse(lab.tree_widget._tree_items[2000].isHidden())
        self.assertTrue(lab.tree_widget._tree_items[3000].isHidden())
        self.assertFalse(lab.tree_widget._tree_items[4000].isHidden())

        # 3. Preset 'active' -> only active worker 4000 visible
        lab.preset_combo.setCurrentIndex(3)  # active
        self.assertFalse(lab.tree_widget._tree_items[4000].isHidden())
        self.assertTrue(lab.tree_widget._tree_items[3000].isHidden())

    def test_selection_pinning_and_io_jump(self):
        """Verify process pinning and direct jump to I/O lab."""
        lab = ProcessLabWidget()
        procs = {21375: self.p_bash, 21400: self.p_sleep}
        lab.update_processes(procs)

        # Select sleep process
        lab.tree_widget.select_pid(21400)
        self.assertEqual(lab.inspector_widget._current_process.pid, 21400)

        # Pin selection
        lab.pin_btn.setChecked(True)
        self.assertTrue(lab._is_pinned)
        self.assertEqual(lab._pinned_pid, 21400)

        # Background update with changed focus should not unselect pinned process
        lab.update_processes(procs, focused_pid=21375)
        self.assertEqual(lab.tree_widget._selected_pid, 21400)

        # Jump to I/O lab
        requested_pids = []
        lab.inspect_io_requested.connect(lambda pid: requested_pids.append(pid))

        lab.inspector_widget.inspect_io_btn.click()
        self.assertEqual(requested_pids, [21400])


if __name__ == "__main__":
    unittest.main()


