import os
import sys
import tkinter as tk
import time

import customtkinter as ctk
from common import utils
from common.utils import api_base_url

sys.path.append(os.path.abspath('../'))


def patch_tk_cleanup_errors():
    if getattr(tk.Variable, "_pyla_safe_del", False):
        return

    original_del = tk.Variable.__del__

    def safe_del(self):
        try:
            original_del(self)
        except (RuntimeError, tk.TclError) as e:
            message = str(e)
            if (
                    "main thread is not in main loop" in message
                    or "application has been destroyed" in message
                    or "invalid command name" in message
            ):
                return
            raise

    tk.Variable.__del__ = safe_del
    tk.Variable._pyla_safe_del = True

    original_report = tk.Tk.report_callback_exception

    def safe_report(self, exc, val, tb):
        if isinstance(val, tk.TclError) and "bad window path name" in str(val):
            return
        original_report(self, exc, val, tb)

    tk.Tk.report_callback_exception = safe_report


def install_tk_background_error_filter(root):
    def pyla_bgerror(message):
        message = str(message)
        # Suppress harmless CTk animation / cleanup errors
        if (
                "invalid command name" in message
                and (
                    "update" in message
                    or "check_dpi_scaling" in message
                    or "_click_animation" in message
                )
        ):
            return
        # Suppress focus errors on already-destroyed CTkToplevel windows
        if "bad window path name" in message:
            return
        print(message)

    try:
        root.tk.createcommand("pyla_bgerror", pyla_bgerror)
        root.tk.call("proc", "bgerror", "message", "pyla_bgerror $message")
    except Exception:
        pass


class App:

    def __init__(self, login_page, select_brawler_page, pyla_main, brawlers, hub_menu):
        self.login = login_page
        self.select_brawler = select_brawler_page
        self.logged_in = False
        self.brawler_data = None
        self.pyla_main = pyla_main
        self.brawlers = brawlers
        self.hub_menu = hub_menu

    def set_is_logged(self, value):
        self.logged_in = value

    def set_data(self, value):
        self.brawler_data = value

    def start(self, pyla_version, get_latest_version):
        patch_tk_cleanup_errors()
        self.login(self.set_is_logged)
        if self.logged_in:
            if api_base_url == "localhost":
                self.hub_menu(pyla_version, pyla_version)
            else:
                self.hub_menu(pyla_version, get_latest_version())
            utils.clear_toml_cache()
            selector = self.select_brawler(self.set_data, self.brawlers)
            if hasattr(selector, "close_app"):
                try:
                    selector.close_app()
                except Exception:
                    pass
            if self.brawler_data:
                utils.save_brawler_data(self.brawler_data)
                time.sleep(0.05)
                self.pyla_main(self.brawler_data)
