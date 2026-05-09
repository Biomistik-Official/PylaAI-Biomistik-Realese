import unittest
from unittest.mock import patch

from core.lobby_automation import LobbyAutomation


class DummyWindowController:
    width_ratio = 1.0
    height_ratio = 1.0

    def __init__(self):
        self.clicks = []
        self.back_presses = 0

    def click(self, x, y):
        self.clicks.append((x, y))

    def android_back(self):
        self.back_presses += 1
        return True

    def screenshot(self):
        return None


class LowestTrophySelectionTests(unittest.TestCase):
    @patch("lobby_automation.time.sleep", return_value=None)
    def test_always_clicks_first_lowest_trophy_brawler_card(self, *_):
        automation = object.__new__(LobbyAutomation)
        automation.window_controller = DummyWindowController()
        automation.ensure_lobby_after_selection = lambda: True

        automation.select_lowest_trophy_brawler()

        self.assertEqual(automation.window_controller.clicks[3], (422, 359))

    @patch("lobby_automation.time.sleep", return_value=None)
    @patch("lobby_automation.get_state", side_effect=["match", "lobby"])
    def test_recovers_if_lowest_selection_opens_details_screen(self, *_):
        automation = object.__new__(LobbyAutomation)
        automation.window_controller = DummyWindowController()

        self.assertTrue(automation.ensure_lobby_after_selection())
        self.assertEqual(automation.window_controller.back_presses, 1)


if __name__ == "__main__":
    unittest.main()
