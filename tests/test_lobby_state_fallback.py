import unittest

import cv2
import numpy as np

from vision.state_finder import (
    get_in_game_state,
    get_matchmaking_exit_button_center,
    get_starr_nova_got_it_button_center,
    get_team_invite_reject_button_center,
    is_in_match_making,
    is_lobby_currency_bar_visible,
    is_lobby_hud_visible,
    is_lobby_quests_button_visible,
    is_lobby_play_button_visible,
    is_starr_nova_info_screen,
)


class LobbyStateFallbackTests(unittest.TestCase):
    @staticmethod
    def draw_lobby_hud(image):
        yellow_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (28, 230, 245), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        green_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (65, 220, 220), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        cyan_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (96, 190, 220), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        orange_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (20, 220, 220), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[850:1020, 1300:1820] = yellow_bgr
        image[12:76, 1170:1280] = (245, 245, 245)
        image[14:74, 1390:1500] = yellow_bgr
        image[14:74, 1580:1690] = green_bgr
        image[870:1040, 280:520] = (35, 35, 45)
        image[880:965, 300:420] = cyan_bgr
        image[930:1015, 390:500] = orange_bgr
        image[970:1035, 300:500] = (245, 245, 245)
        image[18:78, 1790:1880] = (245, 245, 245)
        image[0:95, 1760:1910] = np.maximum(image[0:95, 1760:1910], 35)

    @staticmethod
    def draw_starr_nova_info_screen(image):
        cyan_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (90, 220, 240), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        green_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (60, 245, 225), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[:] = (118, 118, 118)
        for x in range(0, 1920, 240):
            cv2.line(image, (x, 0), (x + 380, 1080), (92, 92, 92), 9)
        image[50:145, 610:1310] = (245, 245, 245)
        image[135:175, 760:1160] = cyan_bgr
        image[465:525, 70:540] = cyan_bgr
        image[465:525, 690:1230] = cyan_bgr
        image[465:525, 1290:1840] = cyan_bgr
        image[850:1010, 745:1175] = green_bgr
        image[900:960, 855:1070] = (250, 250, 250)
        image[942:972, 855:1070] = (25, 25, 25)

    @staticmethod
    def draw_matchmaking_screen(image):
        red_bg = cv2.cvtColor(
            np.full((1, 1, 3), (3, 155, 140), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[:] = red_bg
        image[0:840, :] = red_bg
        for x in range(0, 1920, 220):
            cv2.line(image, (x, 0), (x + 520, 840), (12, 12, 35), 10)
        image[120:210, 720:1190] = (245, 245, 245)
        exit_template = cv2.imread("images/states/exit_match_making.png")
        th, tw = exit_template.shape[:2]
        image[954:954 + th, 1636:1636 + tw] = exit_template

    def test_detects_lobby_by_large_yellow_play_button(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        yellow_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (28, 230, 245), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[850:1020, 1300:1820] = yellow_bgr

        self.assertTrue(is_lobby_play_button_visible(image))
        self.assertFalse(is_lobby_hud_visible(image))

    def test_rejects_small_yellow_noise(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        yellow_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (28, 230, 245), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[900:930, 1300:1360] = yellow_bgr

        self.assertFalse(is_lobby_play_button_visible(image))

    def test_detects_lobby_only_when_multiple_hud_anchors_are_visible(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.draw_lobby_hud(image)

        self.assertTrue(is_lobby_play_button_visible(image))
        self.assertTrue(is_lobby_currency_bar_visible(image))
        self.assertTrue(is_lobby_quests_button_visible(image))
        self.assertTrue(is_lobby_hud_visible(image))
        self.assertEqual(get_in_game_state(image), "lobby")

    def test_rejects_match_like_noise_without_full_lobby_hud(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        yellow_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (28, 230, 245), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        cyan_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (96, 190, 220), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[850:1020, 1300:1820] = yellow_bgr
        image[300:500, 700:1000] = cyan_bgr
        image[620:730, 615:950] = (0, 0, 230)

        self.assertFalse(is_lobby_hud_visible(image))
        self.assertEqual(get_in_game_state(image), "match")

    def test_team_invite_popup_is_detected_as_popup(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        blue_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (105, 220, 230), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        red_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (2, 220, 230), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        green_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (60, 220, 230), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        self.draw_lobby_hud(image)
        image[220:860, 550:1370] = blue_bgr
        image[620:730, 615:950] = red_bgr
        image[620:730, 970:1305] = green_bgr

        center = get_team_invite_reject_button_center(image)

        self.assertIsNotNone(center)
        self.assertEqual(get_in_game_state(image), "popup")

    def test_team_invite_detector_accepts_live_probe_shape(self):
        image = cv2.imread("debug_frames/lobby_probe/127.0.0.1_5555.png")
        if image is None:
            self.skipTest("live lobby probe frame is not available")

        self.assertIsNotNone(get_team_invite_reject_button_center(image))
        self.assertNotEqual(get_in_game_state(image), "lobby")

    def test_starr_nova_info_screen_detects_got_it_button(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.draw_starr_nova_info_screen(image)

        center = get_starr_nova_got_it_button_center(image)

        self.assertIsNotNone(center)
        self.assertTrue(is_starr_nova_info_screen(image))
        self.assertTrue(850 <= center[0] <= 1070)
        self.assertTrue(900 <= center[1] <= 960)

    def test_starr_nova_info_screen_rejects_plain_green_button(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        green_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (60, 245, 225), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[850:1010, 745:1175] = green_bgr
        image[900:960, 855:1070] = (250, 250, 250)

        self.assertFalse(is_starr_nova_info_screen(image))

    def test_matchmaking_screen_is_own_state(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.draw_matchmaking_screen(image)

        center = get_matchmaking_exit_button_center(image)

        self.assertIsNotNone(center)
        self.assertTrue(is_in_match_making(image))
        self.assertEqual(get_in_game_state(image), "match_making")

    def test_matchmaking_rejects_plain_red_button(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        red_button = cv2.cvtColor(
            np.full((1, 1, 3), (2, 220, 230), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[935:1045, 1625:1890] = red_button
        image[960:1018, 1710:1845] = (250, 250, 250)

        self.assertFalse(is_in_match_making(image))
        self.assertNotEqual(get_in_game_state(image), "match_making")


if __name__ == "__main__":
    unittest.main()
