import unittest

from app.ui.identity import get_identity_style, format_identity_badge_html


class TestIdentityHighlighting(unittest.TestCase):

    def test_determinism(self):
        style1 = get_identity_style(21375)
        style2 = get_identity_style(21375)
        self.assertEqual(style1, style2)

    def test_same_value_same_token(self):
        # PID 21375 and PGID 21375 must yield exact same visual styling
        pid_style = get_identity_style(21375)
        pgid_style = get_identity_style(21375)
        self.assertEqual(pid_style, pgid_style)

    def test_none_handling(self):
        style = get_identity_style(None)
        self.assertIsInstance(style, tuple)
        self.assertEqual(len(style), 3)

        html = format_identity_badge_html(None)
        self.assertEqual(html, "-")

    def test_badge_html_preserves_exact_value(self):
        badge = format_identity_badge_html(1000, "UID")
        self.assertIn("UID 1000", badge)
        self.assertIn("border-radius", badge)

    def test_palette_variety_and_dispersion(self):
        # Verify consecutive IDs map to distinct color tokens
        styles = [get_identity_style(i) for i in range(100, 110)]
        unique_styles = set(styles)
        # Should have high variety across consecutive IDs
        self.assertGreater(len(unique_styles), 5)


if __name__ == "__main__":
    unittest.main()
