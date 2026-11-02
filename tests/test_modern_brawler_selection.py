import unittest
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.brawler_selection import BrawlerSelector
from vision.window_controller import WindowController
from core.stage_manager import StageManager


class MenuWindow:
    width_ratio = 0.5
    height_ratio = 0.5

    def __init__(self, selectable=True):
        self.state = 'lobby'
        self.actions = []
        self.selectable = selectable

    def screenshot(self):
        return self.state

    def click(self, x, y, **kwargs):
        self.actions.append(('click', x, y))
        if (x, y) == (55, 245): self.state = 'brawler_selection'
        if (x, y) == (275, 150): self.state = 'shop'
        if (x, y) == (75, 475) and self.selectable: self.state = 'lobby'

    def type_text(self, text, clear=False):
        self.actions.append(('text', text, clear))
        return True


class ModernSelectionTests(unittest.TestCase):
    def selector(self, window, **kwargs):
        return BrawlerSelector(window, state_reader=lambda frame: frame,
                               sleep=lambda seconds: None, names={'larrylawrie': {'actual_name': 'Larry & Lawrie'}}, **kwargs)

    def test_search_uses_actual_name_and_clears_old_filter_at_scaled_coordinates(self):
        window = MenuWindow()
        self.assertTrue(self.selector(window).select('larrylawrie'))
        self.assertIn(('text', 'Larry & Lawrie', True), window.actions)
        self.assertEqual(window.actions[0], ('click', 55, 245))
        self.assertEqual(window.actions[-1], ('click', 75, 475))

    def test_failed_selection_is_not_reported_as_success(self):
        window = MenuWindow(selectable=False)
        self.assertFalse(self.selector(window).select('shelly'))
        self.assertLess(len(window.actions), 40)

    def test_pause_or_stop_aborts_before_any_click(self):
        window = MenuWindow()
        self.assertFalse(self.selector(window, interrupted=lambda: True).select('shelly'))
        self.assertEqual(window.actions, [])

    def test_typing_failure_does_not_select_first_unfiltered_card(self):
        window = MenuWindow()
        window.type_text = lambda *args, **kwargs: False
        self.assertFalse(self.selector(window).select('shelly'))
        self.assertNotIn(('click', 275, 150), window.actions)

    def test_adb_input_quotes_remote_shell_and_clears_previous_query(self):
        window = object.__new__(WindowController)
        window.connected_serial = '127.0.0.1:5555'
        with patch('vision.window_controller._run_adb', return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(window.type_text('Larry & Lawrie', clear=True))
            commands = [call.args[1] for call in run.call_args_list]
            self.assertEqual(commands[-1], ['shell', 'input', 'text', "'Larry%s&%sLawrie'"])
            self.assertIn('KEYCODE_DEL', commands[1])

    def test_non_ascii_or_control_text_does_not_execute_adb(self):
        window = object.__new__(WindowController)
        with patch('vision.window_controller._run_adb') as run:
            self.assertFalse(window.type_text('shelly\nreboot'))
            self.assertFalse(window.type_text('Шелли'))
            run.assert_not_called()

    def test_queue_selection_retries_by_name_and_does_not_trust_lowest_slot(self):
        manager = object.__new__(StageManager)
        manager.brawlers_pick_data = [{'brawler': 'colt', 'automatically_pick': True, 'selection_method': 'lowest_trophies'}]
        calls = []
        results = iter([False, True])
        manager.Lobby_automation = SimpleNamespace(select_brawler=lambda name: calls.append(name) or next(results))
        self.assertFalse(manager.select_queued_brawler())
        self.assertTrue(manager.select_queued_brawler())
        self.assertTrue(manager.select_queued_brawler())
        self.assertEqual(calls, ['colt', 'colt'])

    def test_lobby_watchdog_cannot_bypass_failed_selection(self):
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8-sig'))
        function=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='handle_lobby_watchdog')
        namespace={'time':SimpleNamespace(time=lambda:100), 'get_state':lambda frame:'lobby'}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'main.py','exec'),namespace)
        fake=SimpleNamespace(in_cooldown=False,lobby_entered_at=None,last_lobby_start_press=0,
            lobby_start_retry_interval=8,lobby_stuck_restart_seconds=120,
            Stage_manager=SimpleNamespace(match_start_requested=False,selection_pending=True),
            control_window=SimpleNamespace(is_paused=lambda:False,is_stopped=lambda:False),
            window_controller=SimpleNamespace(keys_up=lambda keys:None,press_key=lambda key:self.fail('Watchdog started unconfirmed brawler')))
        self.assertFalse(namespace['handle_lobby_watchdog'](fake,'lobby'))

    def test_queue_change_during_search_cannot_authorize_the_new_row(self):
        manager=object.__new__(StageManager)
        manager.brawlers_pick_data=[{'brawler':'shelly','automatically_pick':True}]
        def select(name):
            manager.brawlers_pick_data=[{'brawler':'colt','automatically_pick':True}]
            return True
        manager.Lobby_automation=SimpleNamespace(select_brawler=select)
        self.assertFalse(manager.select_queued_brawler())
        self.assertTrue(manager.selection_pending)
