import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ontop import winapi
from ontop.hotkeys import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey
from ontop.pip_window import BOTTOM, LEFT, RIGHT, TOP, resized_rect
from ontop.settings import DEFAULTS, Settings
from ontop.windows_list import is_candidate


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_gives_defaults(self):
        s = Settings(self.path)
        s.load()
        self.assertEqual(s.data, DEFAULTS)

    def test_partial_file_is_merged_and_unknown_keys_survive(self):
        self.path.write_text(json.dumps({"hotkeys": {"pip_foreground": "ctrl+shift+p"}, "custom": 1}))
        s = Settings(self.path)
        s.load()
        self.assertEqual(s.hotkeys["pip_foreground"], "ctrl+shift+p")
        self.assertEqual(s.hotkeys["reset_all"], DEFAULTS["hotkeys"]["reset_all"])
        s.save()
        self.assertEqual(json.loads(self.path.read_text())["custom"], 1)

    def test_corrupt_file_is_moved_aside(self):
        self.path.write_text("{not json")
        s = Settings(self.path)
        s.load()
        self.assertEqual(s.data, DEFAULTS)
        self.assertTrue(self.path.with_suffix(".json.bad").exists())
        self.assertFalse(self.path.exists())

    def test_non_object_json_is_treated_as_corrupt(self):
        self.path.write_text("[1, 2]")
        s = Settings(self.path)
        s.load()
        self.assertEqual(s.data, DEFAULTS)

    def test_invalid_opacity_step_falls_back(self):
        s = Settings(self.path)
        for bad in (0, -5, 99, "x", True, None):
            s.data["opacity_step"] = bad
            self.assertEqual(s.opacity_step, DEFAULTS["opacity_step"], bad)

    def test_profiles_are_case_insensitive_and_roundtrip(self):
        s = Settings(self.path)
        s.update_profile("Chrome.EXE", pip_opacity=60)
        s.save()
        s2 = Settings(self.path)
        s2.load()
        self.assertEqual(s2.profile("chrome.exe")["pip_opacity"], 60)

    def test_empty_exe_profile_is_ignored(self):
        s = Settings(self.path)
        s.update_profile("", pip_opacity=60)
        self.assertEqual(s.data["profiles"], {})


class HotkeyParseTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_hotkey("ctrl+alt+p"), (MOD_CONTROL | MOD_ALT, ord("P")))
        self.assertEqual(parse_hotkey("Ctrl+Shift+Up"), (MOD_CONTROL | MOD_SHIFT, 0x26))
        self.assertEqual(parse_hotkey("alt+f12"), (MOD_ALT, 0x7B))

    def test_invalid(self):
        for bad in ("", "p", "ctrl+", "ctrl+alt+", "hyper+p", "ctrl+nope", "ctrl+f99", "ctrl+é"):
            with self.assertRaises(ValueError, msg=bad):
                parse_hotkey(bad)


class WindowFilterTests(unittest.TestCase):
    base = dict(visible=True, has_owner=False, ex_style=0, title="Doc", cloaked=False,
                class_name="Notepad", pid=10, own_pid=99)

    def test_normal_window_accepted(self):
        self.assertTrue(is_candidate(**self.base))

    def test_rejections(self):
        cases = [
            {"visible": False}, {"has_owner": True}, {"ex_style": winapi.WS_EX_TOOLWINDOW},
            {"title": "  "}, {"cloaked": True}, {"class_name": "Shell_TrayWnd"}, {"pid": 99},
        ]
        for override in cases:
            self.assertFalse(is_candidate(**{**self.base, **override}), override)


class ResizeMathTests(unittest.TestCase):
    rect = (100, 100, 400, 28 + 225)  # 16:9 video, 28px strip
    aspect = 16 / 9

    def test_right_edge_keeps_aspect_and_left_anchor(self):
        x, y, w, h = resized_rect(RIGHT, self.rect, 80, 0, self.aspect)
        self.assertEqual((x, y, w), (100, 100, 480))
        self.assertEqual(h, 28 + 270)

    def test_left_edge_anchors_right_side(self):
        x, y, w, h = resized_rect(LEFT, self.rect, -80, 0, self.aspect)
        self.assertEqual(w, 480)
        self.assertEqual(x + w, 100 + 400)

    def test_top_left_corner_anchors_bottom_right(self):
        x, y, w, h = resized_rect(LEFT | TOP, self.rect, -80, -45, self.aspect)
        self.assertEqual((x + w, y + h), (500, 100 + 253))

    def test_bottom_edge_derives_width_from_height(self):
        _x, _y, w, h = resized_rect(BOTTOM, self.rect, 0, 90, self.aspect)
        self.assertEqual(w, 560)
        self.assertEqual(h, 28 + 315)

    def test_minimum_and_maximum_width(self):
        self.assertEqual(resized_rect(RIGHT, self.rect, -1000, 0, self.aspect)[2], 180)
        self.assertEqual(resized_rect(RIGHT, self.rect, 5000, 0, self.aspect, max_w=1000)[2], 1000)


class OpacityTests(unittest.TestCase):
    def test_clamp_and_alpha(self):
        self.assertEqual(winapi.clamp_percent(5), winapi.MIN_OPACITY)
        self.assertEqual(winapi.clamp_percent(500), 100)
        self.assertEqual(winapi.percent_to_alpha(100), 255)
        self.assertEqual(winapi.alpha_to_percent(255), 100)


if __name__ == "__main__":
    unittest.main()
