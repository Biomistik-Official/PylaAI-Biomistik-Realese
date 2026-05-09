import os
import tempfile
import unittest

from common.adaptive_brain import AdaptiveBrain


class AdaptiveBrainTests(unittest.TestCase):
    def test_wins_make_bot_slightly_more_aggressive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "adaptive_state.json")
            brain = AdaptiveBrain(state_path=path, window_size=10)
            for _ in range(8):
                brain.record_result("1st")

            self.assertLess(brain.params["safe_range_multiplier"], 1.0)
            self.assertGreater(brain.params["strafe_blend"], 0.35)
            self.assertLess(brain.params["attack_cooldown"], 0.16)

    def test_losses_make_bot_more_cautious(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "adaptive_state.json")
            brain = AdaptiveBrain(state_path=path, window_size=10)
            for _ in range(8):
                brain.record_result("4th")

            self.assertGreater(brain.params["safe_range_multiplier"], 1.0)
            self.assertLess(brain.params["strafe_blend"], 0.35)
            self.assertGreater(brain.params["attack_cooldown"], 0.16)


if __name__ == "__main__":
    unittest.main()
