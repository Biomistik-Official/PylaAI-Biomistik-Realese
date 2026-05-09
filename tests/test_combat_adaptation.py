import math
import unittest

from core.play import Play


class CombatAdaptationTests(unittest.TestCase):
    def setUp(self):
        self.movement = object.__new__(Play)
        self.movement._strafe_started_at = 0.0
        self.movement._strafe_side = 1
        self.movement._strafe_current_interval = 0.0
        self.movement.strafe_interval = 1.0
        self.movement.strafe_enabled = True
        self.movement.combat_dodge_blend = 0.65
        self.movement.combat_dodge_jitter_degrees = 0.0
        self.movement.projectile_speed_px_s = 900.0

    def test_strafe_angle_smoothly_flips_after_interval(self):
        first = self.movement.get_strafe_angle(0, 10.0)
        second = self.movement.get_strafe_angle(0, 11.2)
        self.assertAlmostEqual(first, 49.5)
        self.assertGreater(second, 180)
        self.assertLess(second, 360)

    def test_lead_shot_falls_back_to_direct_when_unsolvable(self):
        angle = self.movement.lead_shot_angle((0, 0), (100, 0), (3000, 0), projectile_speed_px_s=100)
        self.assertAlmostEqual(angle, 0.0)

    def test_lead_shot_aims_ahead_of_moving_target(self):
        angle = self.movement.lead_shot_angle((0, 0), (900, 0), (0, 300), projectile_speed_px_s=900)
        self.assertGreater(angle, 0.0)
        self.assertLess(angle, 45.0)
        self.assertFalse(math.isnan(angle))

    def test_combat_dodge_biases_shooting_movement_sideways(self):
        desired = self.movement.apply_combat_dodge(
            desired_angle=0,
            toward_enemy_angle=0,
            current_time=10.0,
            enemy_distance=180,
            safe_range=120,
        )

        self.assertGreater(desired, 25)
        self.assertLess(desired, 90)

    def test_movement_to_vector_converts_legacy_keys(self):
        self.assertEqual(self.movement.movement_to_vector("wd"), (1, -1))
        self.assertEqual(self.movement.movement_to_vector("as"), (-1, 1))


if __name__ == "__main__":
    unittest.main()
