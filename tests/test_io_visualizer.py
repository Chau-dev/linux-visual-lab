from __future__ import annotations

import sys
import unittest
from PySide6.QtWidgets import QApplication

from app.io.model import (
    FdType,
    FileDescriptor,
    PipeEndpoint,
    ProcessIoSnapshot,
    DerivedProcessIoRates,
    DiskDeviceStat,
    KernelFileLock,
)
from app.io.registry import ProcessIoState
from app.process.model import Process
from app.visualizers.io_view import (
    IoLabWidget,
    FdTableWidget,
    SelectedFdInspector,
    ProcessIoStatsWidget,
    SystemTelemetryWidget,
    format_bytes_human,
    format_rate_human,
)


class TestIoVisualizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_format_helpers(self):
        self.assertEqual(format_bytes_human(None), "N/A")
        self.assertEqual(format_bytes_human(500), "500 B")
        self.assertEqual(format_bytes_human(2048), "2.00 KB")
        self.assertEqual(format_bytes_human(1048576 * 5), "5.00 MB")

        self.assertEqual(format_rate_human(None), "—")
        self.assertEqual(format_rate_human(500), "500.0 B/s")
        self.assertEqual(format_rate_human(2048), "2.00 KB/s")

    def test_fd_table_widget(self):
        table = FdTableWidget()
        fd0 = FileDescriptor(fd=0, target="/dev/pts/1", fd_type=FdType.PTY_TTY, access_mode="O_RDWR", is_standard_stream=True, standard_stream_name="stdin")
        fd1 = FileDescriptor(fd=1, target="pipe:[78123]", fd_type=FdType.PIPE, target_inode=78123, access_mode="O_WRONLY")
        fd3 = FileDescriptor(fd=3, target="/home/dev/file.txt", fd_type=FdType.REGULAR_FILE, pos=4096, access_mode="O_RDONLY", status_flags=("O_CLOEXEC",))

        table.populate([fd0, fd1, fd3])
        self.assertEqual(table.rowCount(), 3)
        self.assertEqual(table.item(0, FdTableWidget.COL_FD).text(), "0")
        self.assertEqual(table.item(0, FdTableWidget.COL_STREAM).text(), "stdin (0)")
        self.assertEqual(table.item(1, FdTableWidget.COL_TYPE).text(), "PIPE")
        self.assertEqual(table.item(2, FdTableWidget.COL_POS).text(), "4,096 B")

    def test_selected_fd_inspector(self):
        inspector = SelectedFdInspector()
        fd1 = FileDescriptor(fd=1, target="pipe:[78123]", fd_type=FdType.PIPE, target_inode=78123, access_mode="O_WRONLY")
        ep1 = PipeEndpoint(inode=78123, pid=1000, fd=1, access_mode="O_WRONLY", endpoint_role="Write end", process_command="cat")
        ep2 = PipeEndpoint(inode=78123, pid=2000, fd=0, access_mode="O_RDONLY", endpoint_role="Read end", process_command="grep")

        inspector.update_fd(fd1, {78123: [ep1, ep2]})
        self.assertFalse(inspector.peer_frame.isHidden())
        self.assertIn("pipe:[78123]", inspector.info_lbl.text())
        self.assertIn("grep", inspector.peer_desc.text())

    def test_process_io_stats_widget(self):
        stats_widget = ProcessIoStatsWidget()
        snap = ProcessIoSnapshot(
            rchar=1048576,
            wchar=524288,
            syscr=200,
            syscw=100,
            read_bytes=4096,
            write_bytes=8192,
            cancelled_write_bytes=0,
            observed_at_timestamp=100.0,
        )
        rates = DerivedProcessIoRates(
            rchar_per_sec=10240.0,
            wchar_per_sec=5120.0,
            syscr_per_sec=20.0,
            syscw_per_sec=10.0,
            read_bytes_per_sec=4096.0,
            write_bytes_per_sec=8192.0,
            cancelled_write_bytes_per_sec=0.0,
            interval_seconds=1.0,
        )

        stats_widget.update_io(snap, rates)
        self.assertIn("1.00 MB", stats_widget.lbl_rchar.text())
        self.assertIn("200 calls", stats_widget.lbl_syscr.text())
        self.assertIn("10.00 KB/s", stats_widget.lbl_rchar_rate.text())
        self.assertIn("4.00 KB/s", stats_widget.lbl_read_rate.text())

    def test_io_lab_category_filtering(self):
        lab = IoLabWidget()
        import os
        my_uid = os.getuid()

        # Create mock processes with diverse kernel states
        p_bash = Process(pid=100, ppid=1, pgid=100, sid=100, tpgid=100, uid=my_uid, gid=1000, tty="/dev/pts/1", tty_nr=34817, command="bash")
        p_detached = Process(pid=200, ppid=1, pgid=200, sid=200, tpgid=0, uid=my_uid, gid=1000, tty=None, tty_nr=0, command="sleep")
        p_daemon_root = Process(pid=300, ppid=1, pgid=300, sid=300, tpgid=0, uid=0, gid=0, tty=None, tty_nr=0, command="systemd-resolved")
        p_child = Process(pid=400, ppid=100, pgid=100, sid=100, tpgid=100, uid=my_uid, gid=1000, tty="/dev/pts/1", tty_nr=34817, command="cat")

        procs = {100: p_bash, 200: p_detached, 300: p_daemon_root, 400: p_child}

        # 1. Test "all" filter
        res_all = lab._filter_processes(procs, "all")
        self.assertEqual(len(res_all), 4)

        # 2. Test "user" filter
        res_user = lab._filter_processes(procs, "user")
        self.assertEqual(len(res_user), 3)
        self.assertNotIn(300, [p.pid for p in res_user])

        # 3. Test "session_leaders_no_tty" filter
        res_sess_no_tty = lab._filter_processes(procs, "session_leaders_no_tty")
        self.assertEqual(len(res_sess_no_tty), 2)
        self.assertEqual(set(p.pid for p in res_sess_no_tty), {200, 300})

        # 4. Test "no_tty" filter
        res_no_tty = lab._filter_processes(procs, "no_tty")
        self.assertEqual(len(res_no_tty), 2)
        self.assertEqual(set(p.pid for p in res_no_tty), {200, 300})

        # 5. Test "pgid_leaders" filter
        res_pgid = lab._filter_processes(procs, "pgid_leaders")
        self.assertEqual(len(res_pgid), 3)
        self.assertEqual(set(p.pid for p in res_pgid), {100, 200, 300})

        # 6. Test "shells" filter
        res_shells = lab._filter_processes(procs, "shells")
        self.assertEqual(len(res_shells), 1)
        self.assertEqual(res_shells[0].pid, 100)

    def test_io_lab_pinning_and_authoritative_exit(self):
        lab = IoLabWidget()
        p1 = Process(pid=100, ppid=1, pgid=100, sid=100, tpgid=100, uid=1000, gid=1000, tty="/dev/pts/1", tty_nr=34817, command="bash")
        p2 = Process(pid=200, ppid=1, pgid=200, sid=200, tpgid=0, uid=1000, gid=1000, tty=None, tty_nr=0, command="sleep")

        # Initial authoritative snapshot with PID 100 (focused) and PID 200
        lab.update_process_list({100: p1, 200: p2}, focused_pid=100)
        self.assertEqual(lab.current_pid, 100)
        self.assertFalse(lab.is_pinned)

        # Pin PID 200
        lab.pin_pid(200)
        self.assertTrue(lab.is_pinned)
        self.assertEqual(lab.pinned_pid, 200)
        self.assertEqual(lab.current_pid, 200)
        self.assertIn("Pinned", lab.proc_title_lbl.text())

        # Give lab some mock FDs
        fd0 = FileDescriptor(fd=0, target="/dev/null", fd_type=FdType.DEVICE, access_mode="O_RDONLY")
        lab.update_io_state(ProcessIoState(pid=200, descriptors=[fd0]))
        self.assertEqual(lab.fd_table.rowCount(), 1)

        # Authoritative snapshot update where PID 200 has exited
        lab.update_process_list({100: p1}, focused_pid=100)

        # Must clear FD table and show exit status
        self.assertEqual(lab.fd_table.rowCount(), 0)
        self.assertIn("exited / no longer present in /proc", lab.proc_title_lbl.text())
        self.assertIsNone(lab.current_pid)

        # Unpin and return to follow mode
        lab.unpin()
        self.assertFalse(lab.is_pinned)
        lab.update_process_list({100: p1}, focused_pid=100)
        self.assertEqual(lab.current_pid, 100)

    def test_io_lab_idempotent_select(self):
        lab = IoLabWidget()
        chosen_pids = []
        lab.process_chosen.connect(lambda pid: chosen_pids.append(pid))

        # First selection
        lab.select_pid(500, "worker")
        self.assertEqual(lab.current_pid, 500)
        # select_pid is programmatic sync and should not trigger feedback signal
        self.assertEqual(len(chosen_pids), 0)

        # Re-selecting same PID should be a no-op
        lab.select_pid(500, "worker")
        self.assertEqual(lab.current_pid, 500)
        self.assertEqual(len(chosen_pids), 0)


if __name__ == "__main__":
    unittest.main()
