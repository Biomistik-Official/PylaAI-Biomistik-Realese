from difflib import SequenceMatcher
import time

import cv2
import numpy as np

from typization import BrawlerName
from vision.state_finder import get_state
from common.utils import extract_text_and_positions, count_hsv_pixels, load_toml_as_dict, find_template_center, clear_toml_cache

debug = load_toml_as_dict("cfg/general_config.toml")['super_debug'] == "yes"
gray_pixels_treshold = load_toml_as_dict("./cfg/bot_config.toml")['idle_pixels_minimum']
class LobbyAutomation:

    def __init__(self, window_controller):
        clear_toml_cache("./cfg/lobby_config.toml")
        self.coords_cfg = load_toml_as_dict("./cfg/lobby_config.toml")
        self.window_controller = window_controller

    def check_for_idle(self, frame):
        general_config = load_toml_as_dict("cfg/general_config.toml")
        bot_config = load_toml_as_dict("./cfg/bot_config.toml")
        debug_enabled = str(general_config.get("super_debug", "no")).lower() in ("yes", "true", "1")
        gray_pixels_threshold = bot_config.get("idle_pixels_minimum", gray_pixels_treshold)
        wr = self.window_controller.width_ratio
        hr = self.window_controller.height_ratio
        # Tight ROI centered on the Idle Disconnect dialog body, so we don't
        # pick up dark gameplay pixels outside the box. V range is wide enough
        # to cover both LDPlayer (bright overlay, V~82) and MuMu (dark overlay, V~28).
        x_start, x_end = int(700 * wr), int(1220 * wr)
        y_start, y_end = int(470 * hr), int(620 * hr)
        gray_pixels = count_hsv_pixels(frame[y_start:y_end, x_start:x_end], (0, 0, 18), (10, 20, 100))
        if debug_enabled: print(f"gray pixels (if > {gray_pixels_threshold} then bot will try to unidle) :", gray_pixels)
        if gray_pixels > gray_pixels_threshold:
            self.window_controller.click(int(535 * wr), int(615 * hr))

    def select_brawler(self, brawler):
        self.window_controller.screenshot()
        wr = self.window_controller.width_ratio
        hr = self.window_controller.height_ratio
        general_config = load_toml_as_dict("cfg/general_config.toml")
        debug_enabled = str(general_config.get("super_debug", "no")).lower() in ("yes", "true", "1")
        try:
            ocr_scale = float(general_config.get("ocr_scale_down_factor", 0.65))
        except (TypeError, ValueError):
            ocr_scale = 0.65
        ocr_scale = max(0.35, min(1.0, ocr_scale))
        target_key = self.normalize_ocr_name(brawler)

        x, y = self.coords_cfg['lobby']['brawler_btn'][0]*wr, self.coords_cfg['lobby']['brawler_btn'][1]*hr
        self.window_controller.click(x, y)
        time.sleep(0.6)
        c = 0
        found_brawler = False
        for i in range(50):
            screenshot_full = self.window_controller.screenshot()
            full_h = screenshot_full.shape[0]
            screenshot = cv2.resize(
                screenshot_full,
                (int(screenshot_full.shape[1] * ocr_scale), int(screenshot_full.shape[0] * ocr_scale)),
                interpolation=cv2.INTER_AREA,
            )

            if debug_enabled: print("extracting text on current screen...")
            results = extract_text_and_positions(screenshot)
            reworked_results = {}
            for key in results.keys():
                orig_key = key
                key = self.normalize_ocr_name(key)
                key = self.resolve_ocr_typos(key)
                reworked_results[key] = results[orig_key]
            if debug_enabled:
                print("All detected text while looking for brawler name:", reworked_results.keys())
                print()
            matches = []
            for detected_name, text_box in reworked_results.items():
                if self.names_match(detected_name, target_key):
                    score = self.name_match_score(detected_name, target_key)
                    matches.append((score, detected_name, text_box))
            if matches:
                matches.sort(key=lambda item: item[0], reverse=True)
                _, detected_name, text_box = matches[0]
                x, y = text_box['center']
                click_x = int(x / ocr_scale)
                y_offset = int(full_h * 0.088)  # ~95px at 1080p height
                click_y = int((y / ocr_scale) - y_offset)
                click_y = max(0, min(full_h - 1, click_y))
                self.window_controller.click(click_x, click_y)
                print(f"Found brawler {brawler} (OCR: {detected_name}) clicking icon at ({click_x}, {click_y}), y_offset={y_offset}")
                time.sleep(1.0)

                # Verify we opened the correct brawler's detail card
                verify_screenshot = self.window_controller.screenshot()
                verify_state = get_state(verify_screenshot)

                # "shop" is what get_state returns for the brawler detail card — treat it same as brawler_selection
                card_is_open = verify_state in ("brawler_selection", "shop")

                # Double-check with OCR: if "select" / "selegt" visible → card is definitely open
                if not card_is_open:
                    try:
                        from common.utils import extract_text_strings
                        _quick_texts = extract_text_strings(verify_screenshot)
                        _select_words = {"select", "selegt", "selec", "selct", "selert"}
                        if any(self.normalize_ocr_name(t) in _select_words for t in _quick_texts):
                            card_is_open = True
                            print(f"Card detected via OCR 'select' text (state was {verify_state}).")
                    except Exception:
                        pass

                if not card_is_open:
                    # Tap didn't open a brawler card — likely missed; try again without scroll
                    print(f"Brawler card did not open after tap (state={verify_state}); retrying tap.")
                    time.sleep(0.5)
                    continue

                # Confirm the brawler name on the card with OCR
                card_crop = verify_screenshot[
                    int(full_h * 0.05):int(full_h * 0.22),
                    0:verify_screenshot.shape[1]
                ]
                try:
                    card_texts = []
                    from common.utils import extract_text_strings
                    card_texts = extract_text_strings(card_crop)
                except Exception:
                    pass
                card_name_match = any(
                    self.names_match(self.normalize_ocr_name(t), target_key)
                    for t in card_texts
                ) if card_texts else True  # if OCR fails, trust the original match

                if not card_name_match:
                    print(f"Card OCR shows {card_texts} but expected '{brawler}'; re-tapping with adjusted offset.")
                    self.press_back()
                    time.sleep(0.5)
                    # Try with a smaller offset (card was above the one we wanted)
                    click_y2 = int((y / ocr_scale) - int(full_h * 0.04))
                    click_y2 = max(0, min(full_h - 1, click_y2))
                    self.window_controller.click(click_x, click_y2)
                    time.sleep(1.0)

                select_x, select_y = self.coords_cfg['lobby']['select_btn'][0], self.coords_cfg['lobby']['select_btn'][1]
                self.window_controller.click(select_x, select_y, already_include_ratio=False)
                time.sleep(0.5)
                print(f"Selected brawler {brawler}")
                found_brawler = True
                break   # <-- exit loop immediately, no scroll after this

            else:
                # Brawler not found on screen — scroll down and try again
                if c == 0:
                    # First iteration: small scroll to stabilise view
                    self.window_controller.swipe(int(1760 * wr), int(900 * hr), int(1760 * wr), int(850 * hr), duration=0.8)
                    c += 1
                else:
                    self.window_controller.swipe(int(1760 * wr), int(900 * hr), int(1760 * wr), int(650 * hr), duration=0.8)
                time.sleep(1)

        if not found_brawler:
            print(f"WARNING: Brawler '{brawler}' was not found after 50 scroll attempts. "
                  f"The bot will continue with the currently selected brawler.")
            raise ValueError(f"Brawler '{brawler}' could not be found in the brawler selection menu.")

    def select_lowest_trophy_brawler(self):
        print("Selecting next brawler by sorting lowest trophies... (Robust ADB Percentage Logic)")
        time.sleep(2.0)
        
        # Get actual ADB reported dimensions to bypass any scrcpy/emulator scaling mismatches
        size = self.window_controller.device.window_size()
        width = size.width
        height = size.height

        def tap_pct(x_pct, y_pct, wait=1.0):
            # Calculates exact ADB coordinates based on the reported screen size
            x = int(width * x_pct)
            y = int(height * y_pct)
            self.window_controller.device.shell(f"input tap {x} {y}")
            time.sleep(wait)

        # 1. Open Brawler List (Tap center of lobby to avoid UI side-banner overlaps)
        tap_pct(0.500, 0.500, 1.5)
        
        # 2. Tap Sort Dropdown (Top right)
        tap_pct(0.630, 0.041, 0.8)
        
        # 3. Select 'Least Trophies' (Middle right dropdown option)
        tap_pct(0.630, 0.394, 1.2)
        
        # 4. Tap the first brawler card after sorting (Left middle)
        # Added a massive 3.0s delay to guarantee the Brawler Detail card is fully rendered
        tap_pct(0.260, 0.370, 3.0)
        
        # 5. Tap the SELECT button (Bottom left)
        tap_pct(0.135, 0.917, 1.5)
        
        if self.ensure_lobby_after_selection():
            return True

        print("Lowest-trophy brawler selection did not return to lobby; trying one recovery pass.")
        self.press_back()
        time.sleep(1.0)
        return False

    def ensure_lobby_after_selection(self, timeout=6.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                state = get_state(self.window_controller.screenshot())
            except Exception as e:
                print(f"Could not verify lobby after brawler selection: {e}")
                return False
            if state == "lobby":
                return True
            
            # Rely strictly on the initial ADB percentage blind tap. Do not spam SELECT here
            # because state misidentification ("brawler_selection" instead of "lobby")
            # causes rogue clicks that can hit the Brawl Pass.
            
            if state == "match":
                # Immediately after selecting a brawler, "match" usually means
                # an unrecognized brawler details/stats screen, not a real game.
                self.press_back()
            time.sleep(0.7)
        return False

    def press_back(self):
        if hasattr(self.window_controller, "android_back") and self.window_controller.android_back():
            return
        self.window_controller.click(
            int(100 * self.window_controller.width_ratio),
            int(60 * self.window_controller.height_ratio),
        )

    @staticmethod
    def resolve_ocr_typos(potential_brawler_name: str) -> str:
        """
        Matches well known 'typos' from OCR to the correct brawler's name
        or returns the original string
        """

        matched_typo: str | None = {
            'shey': BrawlerName.Shelly.value,
            'shlly': BrawlerName.Shelly.value,
            'larryslawrie': BrawlerName.Larry.value,
            '[eon': BrawlerName.Leon.value,
        }.get(potential_brawler_name, None)

        return matched_typo or potential_brawler_name

    @staticmethod
    def normalize_ocr_name(value: str) -> str:
        normalized = str(value).lower()
        for symbol in [' ', '-', '.', "&", "'", "`", "_"]:
            normalized = normalized.replace(symbol, "")
        return normalized

    @staticmethod
    def bounded_edit_distance(left: str, right: str, limit: int) -> int:
        if abs(len(left) - len(right)) > limit:
            return limit + 1
        previous = list(range(len(right) + 1))
        for i, left_char in enumerate(left, 1):
            current = [i]
            best = current[0]
            for j, right_char in enumerate(right, 1):
                cost = 0 if left_char == right_char else 1
                value = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
                current.append(value)
                best = min(best, value)
            if best > limit:
                return limit + 1
            previous = current
        return previous[-1]

    @classmethod
    def names_match(cls, detected_name: str, target_name: str) -> bool:
        if detected_name == target_name:
            return True
        if len(target_name) >= 4 and (target_name in detected_name or detected_name in target_name):
            return True
        limit = 2 if len(target_name) <= 5 else 3
        if cls.bounded_edit_distance(detected_name, target_name, limit) <= limit:
            return True
        return SequenceMatcher(None, detected_name, target_name).ratio() >= 0.72

    @classmethod
    def name_match_score(cls, detected_name: str, target_name: str) -> float:
        if detected_name == target_name:
            return 2.0
        ratio = SequenceMatcher(None, detected_name, target_name).ratio()
        distance = cls.bounded_edit_distance(detected_name, target_name, 3)
        return ratio - (distance * 0.05)
