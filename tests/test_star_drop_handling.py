import unittest
from pathlib import Path

import numpy as np
import cv2

from vision.state_finder import get_in_game_state, get_star_drop_type


class StarDropHandlingTests(unittest.TestCase):
    def test_green_reward_like_screen_does_not_trigger_without_template(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        green_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (58, 230, 230), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[110:850, 430:1330] = green_bgr
        image[30:100, 20:430] = (245, 245, 245)

        self.assertIsNone(get_star_drop_type(image))
        self.assertNotEqual(get_in_game_state(image), "star_drop")

    def test_exact_standard_template_triggers_standard_star_drop(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        green_bgr = cv2.cvtColor(
            np.full((1, 1, 3), (58, 230, 230), dtype=np.uint8),
            cv2.COLOR_HSV2BGR,
        )[0, 0]
        image[75:905, 340:1580] = green_bgr
        image[20:175, 690:1230] = (80, 245, 80)
        template_path = Path("images/star_drop_types/star_drop.png")
        template = cv2.imread(str(template_path))
        self.assertIsNotNone(template)

        x, y, w, h = 790, 350, 350, 350
        th, tw = template.shape[:2]
        px = x + (w - tw) // 2
        py = y + (h - th) // 2
        image[py:py + th, px:px + tw] = template

        self.assertEqual(get_star_drop_type(image), "standard")
        self.assertEqual(get_in_game_state(image), "star_drop")

    def test_standard_template_without_drop_background_is_ignored(self):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        template = cv2.imread("images/star_drop_types/star_drop.png")
        self.assertIsNotNone(template)

        x, y, w, h = 790, 350, 350, 350
        th, tw = template.shape[:2]
        px = x + (w - tw) // 2
        py = y + (h - th) // 2
        image[py:py + th, px:px + tw] = template

        self.assertIsNone(get_star_drop_type(image))
        self.assertNotEqual(get_in_game_state(image), "star_drop")


if __name__ == "__main__":
    unittest.main()
