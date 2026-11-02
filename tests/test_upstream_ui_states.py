from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import cv2
import numpy as np

from vision.upstream_ui import detect_state, REGIONS, ASSET_DIR
from vision.state_finder import get_in_game_state
from core.stage_manager import StageManager


class UpstreamUiTests(unittest.TestCase):
    def screen(self, name):
        image = np.zeros((1080,1920,3),np.uint8)
        template = cv2.imread(str(ASSET_DIR / (name+'.png')))
        x,y,_,_ = REGIONS[name]
        h,w = template.shape[:2]
        image[y:y+h,x:x+w] = template
        return image

    def test_current_search_menu_is_detected_without_old_task_icon(self):
        image = self.screen('brawler_menu_search')
        self.assertEqual(detect_state(image),'brawler_selection')
        self.assertEqual(get_in_game_state(image),'brawler_selection')

    def test_current_rewards_have_distinct_states(self):
        self.assertEqual(detect_state(self.screen('daily_wins')),'daily_wins')
        self.assertEqual(detect_state(self.screen('prestige_continue')),'prestige_milestone')

    def test_empty_or_wrong_sized_regions_do_not_raise(self):
        self.assertIsNone(detect_state(np.zeros((4,4,3),np.uint8)))

    def test_invite_over_dimmed_lobby_is_popup_without_lobby_hud(self):
        frame=np.zeros((1080,1920,3),np.uint8)
        frame[215:860,550:1370]=cv2.cvtColor(np.full((1,1,3),(110,220,230),np.uint8),cv2.COLOR_HSV2BGR)[0,0]
        frame[620:730,615:950]=(0,0,230)
        frame[620:730,970:1305]=(0,230,0)
        self.assertEqual(get_in_game_state(frame),'popup')

    def test_popup_detection_precedes_background_lobby_template(self):
        frame=self.screen('lobby_menu')
        with patch('vision.state_finder.is_in_offer_popup',return_value=True):
            self.assertEqual(get_in_game_state(frame),'popup')

    def test_daily_wins_clicks_center_and_stops_when_screen_changes(self):
        manager=object.__new__(StageManager)
        calls=[]
        manager.window_controller=SimpleNamespace(width_ratio=.5,height_ratio=.5,
            click=lambda x,y: calls.append((x,y)),screenshot=lambda:None)
        manager.Lobby_automation=SimpleNamespace(control=None)
        with patch('core.stage_manager.get_state',side_effect=['daily_wins','lobby']),patch('core.stage_manager.time.sleep'):
            manager.handle_daily_wins()
        self.assertEqual(calls,[(480,270)])
