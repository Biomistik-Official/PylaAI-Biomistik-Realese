import unittest

from core.play import Play


class TestWallDetectionPostprocess(unittest.TestCase):
    def make_play(self):
        play = Play.__new__(Play)
        play.wall_box_min_size = 20
        play.wall_box_merge_iou = 0.25
        play.wall_box_merge_center_distance = 35
        play.wall_history_min_hits = 2
        play.wall_history = []
        return play

    def test_merges_jittered_wall_boxes(self):
        play = self.make_play()
        boxes = [
            [100, 100, 160, 160],
            [105, 102, 163, 158],
            [500, 500, 560, 560],
            [10, 10, 20, 20],
        ]

        merged = play.merge_wall_boxes(boxes)

        self.assertEqual(len(merged), 2)
        self.assertTrue(any(abs(box[0] - 102) <= 4 and abs(box[1] - 101) <= 4 for box in merged))
        self.assertTrue(any(box[0] == 500 and box[1] == 500 for box in merged))

    def test_combines_history_without_exact_coordinate_duplicates(self):
        play = self.make_play()
        play.wall_history = [
            [[100, 100, 160, 160]],
            [[103, 98, 162, 161]],
            [[700, 700, 760, 760]],
        ]

        combined = play.combine_walls_from_history()

        self.assertEqual(len(combined), 2)

    def test_current_frame_walls_are_kept_before_history_votes(self):
        play = self.make_play()
        play.wall_history = [
            [[100, 100, 160, 160]],
            [[400, 400, 460, 460]],
        ]

        combined = play.combine_walls_from_history()

        self.assertTrue(any(box[0] == 400 and box[1] == 400 for box in combined))


if __name__ == "__main__":
    unittest.main()
