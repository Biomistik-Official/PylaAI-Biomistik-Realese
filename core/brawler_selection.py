"""Current game menu: search by name rather than blind OCR scrolling.

Search/button layout adapted from PylaAI/PylaAI 763c389 (CC BY-NC 4.0).
"""
import time


BUTTONS = {'brawlers_menu': (110, 490), 'brawler_search': (1550, 50),
           'first_brawler_icon': (550, 300), 'select_brawler': (150, 950)}


class BrawlerSelector:
    def __init__(self, window, state_reader, names=None, buttons=None, interrupted=None, sleep=time.sleep):
        self.window = window
        self.state_reader = state_reader
        self.names = names or {}
        self.buttons = dict(BUTTONS, **(buttons or {}))
        self.interrupted = interrupted or (lambda: False)
        self.sleep = sleep

    def wait(self, seconds):
        for _ in range(max(1, round(seconds / .1))):
            if self.interrupted():
                return False
            self.sleep(.1)
        return not self.interrupted()

    def state(self):
        return self.state_reader(self.window.screenshot())

    def tap(self, button):
        if self.interrupted():
            return False
        x, y = self.buttons[button]
        self.window.click(int(x * self.window.width_ratio), int(y * self.window.height_ratio))
        return True

    def wait_state(self, expected, attempts=25):
        for _ in range(attempts):
            if self.interrupted():
                return False
            if self.state() == expected:
                return True
            if not self.wait(.1):
                return False
        return False

    def select(self, brawler):
        if self.interrupted():
            return False
        key = ''.join(c for c in str(brawler).lower() if c.isalnum())
        search_name = self.names.get(key, {}).get('actual_name') or str(brawler)
        initial = self.state()
        if initial == 'lobby':
            if not self.tap('brawlers_menu') or not self.wait(.8):
                return False
        elif initial != 'brawler_selection':
            print(f'Cannot select {brawler}: current screen is {initial}.')
            return False
        if not self.wait_state('brawler_selection'):
            print('Brawler menu did not open; match start is blocked.')
            return False
        if not self.tap('brawler_search') or not self.wait(.3):
            return False
        if not self.window.type_text(search_name, clear=True):
            print('Could not enter search text; no unfiltered card will be selected.')
            return False
        if not self.wait(.8) or not self.tap('first_brawler_icon') or not self.wait(.6):
            return False
        for _ in range(3):
            if not self.tap('select_brawler') or not self.wait(.5):
                return False
            if self.wait_state('lobby', attempts=10):
                print(f'Selected brawler by search: {search_name}')
                return True
        print(f'Selection of {search_name} was not confirmed; match start is blocked.')
        return False
