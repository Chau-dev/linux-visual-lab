import unittest

from app.process.focused_session import FocusedSession


class TestFocusedSession(unittest.TestCase):

    def test_initially_none(self):
        focused = FocusedSession()
        self.assertIsNone(focused.pid)
        self.assertFalse(focused.has_session())

    def test_set_and_clear_pid(self):
        focused = FocusedSession()
        focused.set_pid(1234)
        self.assertEqual(focused.pid, 1234)
        self.assertTrue(focused.has_session())

        focused.clear()
        self.assertIsNone(focused.pid)
        self.assertFalse(focused.has_session())


if __name__ == "__main__":
    unittest.main()
