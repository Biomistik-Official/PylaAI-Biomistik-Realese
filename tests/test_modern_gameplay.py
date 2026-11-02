import unittest
from types import SimpleNamespace

from core.play import Play, Movement


class ModernGameplayTests(unittest.TestCase):
    def make_play(self):
        play = object.__new__(Play)
        play.wall_box_min_size = 1
        play.wall_box_merge_iou = .25
        play.wall_box_merge_center_distance = 0
        play.wall_history_min_hits = 1
        play.wall_history_length = 1
        play.wall_history = []
        play.wall_path_padding = 0
        play.wall_path_probe_tiles = 1
        play.TILE_SIZE = 60
        play.window_controller = SimpleNamespace(scale_factor=1)
        return play

    def test_water_blocks_movement_without_becoming_an_attack_wall(self):
        play = self.make_play()
        water = [20,0,40,20]
        walls = play.process_tile_data({'wall': [[100,100,140,140]], 'water':[water], 'bush':[[0,100,30,130]]})
        self.assertNotIn(water, walls)
        self.assertTrue(play.is_path_blocked_angle((0,10), 0, walls, distance=60))
        self.assertFalse(play.walls_block_line_of_sight((0,10),(60,10),walls,padding=0))

    def test_enemy_candidates_include_only_hostile_spawnables(self):
        enemy = [10,10,20,20]
        hostile = [30,30,40,40]
        self.assertEqual(Play.enemy_targets({'enemy':[enemy],'enemy_spawnable':[hostile],
                          'teammate_spawnable':[[1,1,2,2]],'ignored_spawnable':[[3,3,4,4]]}),[enemy,hostile])

    def test_selected_spawnable_does_not_consume_super_or_gadget(self):
        movement = object.__new__(Movement)
        movement._selected_enemy_spawnable = True
        movement.super_cooldown = movement.gadget_cooldown = 0
        movement.window_controller = SimpleNamespace(press_key=lambda *args, **kwargs: self.fail('Ability was consumed'))
        self.assertFalse(movement.use_super())
        self.assertFalse(movement.use_gadget())
