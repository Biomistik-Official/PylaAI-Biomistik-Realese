import unittest
from unittest.mock import patch

from vision.window_controller import WindowController, _foreground_package_from_text


class LongRunWatchdogTests(unittest.TestCase):
    def test_foreground_package_parser_handles_current_focus(self):
        text = "mCurrentFocus=Window{123 u0 com.supercell.brawlstars/com.supercell.titan.GameApp}"
        self.assertEqual(_foreground_package_from_text(text), "com.supercell.brawlstars")

    def test_foreground_package_parser_handles_focused_app(self):
        text = "mFocusedApp=ActivityRecord{123 u0 com.android.launcher/.Launcher t1}"
        self.assertEqual(_foreground_package_from_text(text), "com.android.launcher")

    @patch("window_controller.time.time")
    def test_emulator_restart_respects_cooldown(self, mock_time):
        controller = object.__new__(WindowController)
        controller.last_emulator_restart_time = 100.0
        controller.emulator_restart_cooldown = 180.0
        mock_time.return_value = 150.0

        self.assertFalse(controller.restart_emulator_profile())

    @patch.object(WindowController, "launch_saved_emulator_profile", return_value=False)
    @patch.object(WindowController, "keys_up")
    @patch("window_controller.time.time")
    def test_emulator_restart_failure_does_not_raise(self, mock_time, _mock_keys_up, _mock_launch):
        controller = object.__new__(WindowController)
        controller.selected_emulator = "LDPlayer"
        controller.emulator_profile_index = 0
        controller.configured_serial = "emulator-5554"
        controller.scrcpy_client = None
        controller.last_emulator_restart_time = 0.0
        controller.emulator_restart_cooldown = 180.0
        mock_time.return_value = 300.0

        self.assertFalse(controller.restart_emulator_profile())

    def test_restart_brawl_stars_returns_false_when_adb_is_offline(self):
        controller = object.__new__(WindowController)
        controller.ensure_emulator_online = lambda: False

        self.assertFalse(controller.restart_brawl_stars())

    def test_slow_feed_fallback_lowers_capture_load_without_config_change(self):
        controller = object.__new__(WindowController)
        controller.scrcpy_max_width = 960
        controller.scrcpy_max_fps = 60
        controller.scrcpy_bitrate = 3000000
        controller.capture_fallback_level = 0

        self.assertTrue(controller.reduce_capture_load_for_slow_feed())
        self.assertEqual(controller.scrcpy_max_width, 854)
        self.assertEqual(controller.scrcpy_max_fps, 30)
        self.assertEqual(controller.scrcpy_bitrate, 2000000)

        self.assertTrue(controller.reduce_capture_load_for_slow_feed())
        self.assertEqual(controller.scrcpy_max_width, 720)
        self.assertEqual(controller.scrcpy_max_fps, 30)
        self.assertEqual(controller.scrcpy_bitrate, 1500000)

        self.assertFalse(controller.reduce_capture_load_for_slow_feed())

    def test_restart_scrcpy_client_returns_false_when_start_fails_offline(self):
        controller = object.__new__(WindowController)
        controller.scrcpy_client = None
        controller.scrcpy_generation = 0
        controller.is_emulator_online = lambda: False
        controller.ensure_calls = 0

        def ensure_emulator_online():
            controller.ensure_calls += 1
            return controller.ensure_calls == 1

        controller.ensure_emulator_online = ensure_emulator_online
        controller.start_scrcpy_client = lambda: (_ for _ in ()).throw(Exception("device offline"))

        self.assertFalse(controller.restart_scrcpy_client())
        self.assertEqual(controller.ensure_calls, 2)


if __name__ == "__main__":
    unittest.main()
