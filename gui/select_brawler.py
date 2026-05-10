import json
import time
import tkinter as tk
from difflib import SequenceMatcher
from math import ceil

import cv2
import customtkinter as ctk
import numpy as np
import pyautogui
from adbutils import adb
from PIL import Image
from customtkinter import CTkImage
from common.utils import (
    extract_text_strings,
    fetch_brawl_stars_player,
    load_brawl_stars_api_config,
    load_toml_as_dict,
    normalize_brawler_name,
    save_brawler_icon,
    get_dpi_scale,
)
from tkinter import filedialog

from gui.main import install_tk_background_error_filter

orig_screen_width, orig_screen_height = 1920, 1080
width, height = pyautogui.size()
width_ratio = width / orig_screen_width
height_ratio = height / orig_screen_height
scale_factor = min(width_ratio, height_ratio)
scale_factor *= 96/get_dpi_scale()

try:
    pyla_version = load_toml_as_dict("./cfg/general_config.toml")['pyla_version']
except Exception:
    pyla_version = "Unknown"

class SelectBrawler:

    def __init__(self, data_setter, brawlers):
        self.app = ctk.CTk()
        install_tk_background_error_filter(self.app)
        tk._default_root = self.app

        # Define the new modern color palette
        self.colors = {
            'bg': '#0a0a0b',
            'frame': '#0a0a0b',
            'border': '#2a2a2f',
            'accent': '#ff204e',
            'accent_hover': '#1a1a1c',
            'text_main': '#ffffff',
            'text_muted': '#8e8e93',
            'input_bg': '#0f0f10',
            'card_bg': '#141416',
            'card_hover': '#1a1a1c',
            'success': '#2ecc71',
            'error': '#e74c3c'
        }

        self.app.configure(fg_color=self.colors['bg'])

        # UI Layout Params
        self.square_size = int(85 * scale_factor)
        window_width = int(1050 * scale_factor)
        window_height = int(720 * scale_factor)
        
        self.app.title(f"Pyla-Biomistik v{pyla_version} - Brawler Queue")
        self.app.geometry(f"{window_width}x{window_height}+{int(450 * scale_factor)}+{int(150 * scale_factor)}")
        self.app.resizable(False, False)

        self.brawlers = brawlers
        self.data_setter = data_setter
        self.images = []
        self.visible_image_labels = []
        self.brawlers_data = []
        self.farm_type = ""
        self.api_trophies_by_brawler = None
        self.api_trophies_by_normalized_brawler = None
        self.api_trophy_error_reported = False
        self._filter_after_id = None
        self._image_render_after_id = None
        self._current_filter_text = None
        self._closing = False
        self._closed = False
        self.current_sort = "In Order"
        
        self.player_name = "Unknown"
        self.player_tag = "N/A"

        # Load API configs and get trophies + player name/tag if available
        self._init_api_data()

        # Load images
        for brawler in self.brawlers:
            img_path = f"./api/assets/brawler_icons/{brawler}.png"
            try:
                img = Image.open(img_path)
            except FileNotFoundError:
                save_brawler_icon(brawler)
                try:
                    img = Image.open(img_path)
                except Exception:
                    img = Image.new('RGBA', (self.square_size, self.square_size), (0, 0, 0, 0))

            img_tk = CTkImage(img, size=(self.square_size, self.square_size))
            self.images.append((brawler, img_tk))

        self.setup_ui()
        self.app.mainloop()

    def _init_api_data(self):
        config_path = "cfg/brawl_stars_api.toml"
        try:
            api_config = load_brawl_stars_api_config(config_path)
            self.player_tag = api_config.get("player_tag", "N/A")
            
            if api_config.get("api_token") and self.player_tag and self.player_tag != "N/A":
                player_data = fetch_brawl_stars_player(
                    api_config.get("api_token", "").strip(),
                    self.player_tag.strip(),
                    int(api_config.get("timeout_seconds", 15)),
                )
                self.player_name = player_data.get("name", "Unknown")
                
                known_by_normalized_name = {
                    normalize_brawler_name(b): b for b in self.brawlers
                }
                
                self.api_trophies_by_brawler = {}
                self.api_trophies_by_normalized_brawler = {}
                
                for api_brawler in player_data.get("brawlers", []):
                    normalized_name = normalize_brawler_name(api_brawler.get("name", ""))
                    brawler = known_by_normalized_name.get(normalized_name)
                    if brawler:
                        trophies = int(api_brawler.get("trophies", 0))
                        self.api_trophies_by_brawler[brawler] = trophies
                        self.api_trophies_by_normalized_brawler[normalize_brawler_name(brawler)] = trophies
                        self.api_trophies_by_normalized_brawler[normalized_name] = trophies
                        
                # Filter brawlers to only those available
                if self.api_trophies_by_brawler:
                    self.brawlers = [b for b in self.brawlers if b in self.api_trophies_by_brawler]
        except Exception as e:
            print(f"API Data init error: {e}")

    def setup_ui(self):
        # Master padding frame
        main_pad = ctk.CTkFrame(self.app, fg_color="transparent")
        main_pad.pack(fill="both", expand=True, padx=int(30 * scale_factor), pady=int(30 * scale_factor))

        # --- Top Header Section ---
        header_frame = ctk.CTkFrame(main_pad, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, int(20 * scale_factor)))

        title_col = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_col.pack(side="left", fill="y")

        ctk.CTkLabel(
            title_col, text="BRAWLER QUEUE", font=("Arial", int(12 * scale_factor), "bold"),
            text_color=self.colors['accent']
        ).pack(anchor="w", pady=(0, int(5 * scale_factor)))
        
        ctk.CTkLabel(
            title_col, text="Select a brawler and add it to the run order", font=("Arial", int(22 * scale_factor), "bold"),
            text_color=self.colors['text_main']
        ).pack(anchor="w")

        # Top Right Profile Box
        profile_box = ctk.CTkFrame(
            header_frame, fg_color=self.colors['frame'], 
            border_color=self.colors['border'], border_width=int(1 * scale_factor), corner_radius=int(8 * scale_factor)
        )
        profile_box.pack(side="right", padx=int(10 * scale_factor), pady=int(5 * scale_factor))
        
        profile_inner = ctk.CTkFrame(profile_box, fg_color="transparent")
        profile_inner.pack(padx=int(15 * scale_factor), pady=int(10 * scale_factor))
        
        ctk.CTkLabel(
            profile_inner, text=self.player_name, font=("Arial", int(14 * scale_factor), "bold"),
            text_color=self.colors['text_main']
        ).pack(anchor="w")
        ctk.CTkLabel(
            profile_inner, text=f"#{self.player_tag.replace('#', '')}", font=("Arial", int(12 * scale_factor)),
            text_color=self.colors['text_muted']
        ).pack(anchor="w")


        # --- Inputs Row 1: Search & Tag ---
        input_row1 = ctk.CTkFrame(main_pad, fg_color="transparent")
        input_row1.pack(fill="x", pady=(0, int(15 * scale_factor)))

        # Search Brawlers
        search_col = ctk.CTkFrame(input_row1, fg_color="transparent")
        search_col.pack(side="left", fill="x", expand=True, padx=(0, int(10 * scale_factor)), anchor="s")
        
        ctk.CTkLabel(
            search_col, text="SEARCH BRAWLERS", font=("Arial", int(11 * scale_factor), "bold"),
            text_color=self.colors['text_muted']
        ).pack(anchor="w", pady=(0, int(5 * scale_factor)))

        self.filter_var = tk.StringVar()
        self.filter_entry = ctk.CTkEntry(
            search_col, textvariable=self.filter_var,
            placeholder_text="Search by brawler name", font=("Arial", int(14 * scale_factor)),
            fg_color=self.colors['input_bg'], border_color=self.colors['border'], border_width=1,
            text_color=self.colors['text_main'], height=int(40 * scale_factor)
        )
        self.filter_entry.pack(fill="x")
        self.filter_var.trace_add("write", lambda *args: self.queue_image_filter_update())

        # Player Tag Input
        tag_col = ctk.CTkFrame(input_row1, fg_color="transparent")
        tag_col.pack(side="right", anchor="s")
        
        ctk.CTkLabel(
            tag_col, text="PLAYER TAG", font=("Arial", int(11 * scale_factor), "bold"),
            text_color=self.colors['text_muted']
        ).pack(anchor="w", pady=(0, int(5 * scale_factor)))

        self.tag_var = tk.StringVar(value=self.player_tag)
        self.tag_entry = ctk.CTkEntry(
            tag_col, textvariable=self.tag_var, width=int(250 * scale_factor),
            placeholder_text="e.g. RG2P9R9YJ", font=("Arial", int(14 * scale_factor)),
            fg_color=self.colors['input_bg'], border_color=self.colors['border'], border_width=1,
            text_color=self.colors['text_main'], height=int(40 * scale_factor)
        )
        self.tag_entry.pack(fill="x")

        # --- Inputs Row 2: Actions & Sort ---
        input_row2 = ctk.CTkFrame(main_pad, fg_color="transparent")
        input_row2.pack(fill="x", pady=(0, int(20 * scale_factor)))

        # Left Actions
        actions_frame = ctk.CTkFrame(input_row2, fg_color="transparent")
        actions_frame.pack(side="left", anchor="s")

        ctk.CTkButton(
            actions_frame, text="Build Queue", command=self.open_queue_builder,
            fg_color=self.colors['frame'], hover_color=self.colors['border'], text_color=self.colors['text_main'],
            border_color=self.colors['border'], border_width=1,
            font=("Arial", int(14 * scale_factor), "bold"), height=int(40 * scale_factor), width=int(140 * scale_factor)
        ).pack(side="left", padx=(0, int(10 * scale_factor)))

        ctk.CTkButton(
            actions_frame, text="Push All to 1000", command=self.open_push_all_target_window,
            fg_color=self.colors['frame'], hover_color=self.colors['border'], text_color=self.colors['text_main'],
            border_color=self.colors['border'], border_width=1,
            font=("Arial", int(14 * scale_factor), "bold"), height=int(40 * scale_factor), width=int(160 * scale_factor)
        ).pack(side="left")
        
        ctk.CTkButton(
            actions_frame, text="Start Selected", command=self.start_bot,
            fg_color=self.colors['accent'], hover_color=self.colors['accent_hover'], text_color=self.colors['text_main'],
            font=("Arial", int(14 * scale_factor), "bold"), height=int(40 * scale_factor), width=int(140 * scale_factor)
        ).pack(side="left", padx=(int(10 * scale_factor), 0))

        # Sort Dropdown
        sort_col = ctk.CTkFrame(input_row2, fg_color="transparent")
        sort_col.pack(side="right", anchor="s")
        
        ctk.CTkLabel(
            sort_col, text="PLAY ORDER", font=("Arial", int(11 * scale_factor), "bold"),
            text_color=self.colors['text_muted']
        ).pack(anchor="w", pady=(0, int(5 * scale_factor)))

        self.sort_var = tk.StringVar(value="In Order")
        self.sort_menu = ctk.CTkOptionMenu(
            sort_col, variable=self.sort_var, command=self.on_sort_change, width=int(250 * scale_factor),
            values=["In Order", "Lowest to Highest", "Highest to Lowest"],
            font=("Arial", int(13 * scale_factor)), dropdown_font=("Arial", int(13 * scale_factor)),
            fg_color=self.colors['input_bg'], button_color=self.colors['input_bg'],
            button_hover_color=self.colors['border'], text_color=self.colors['text_main'],
            dropdown_fg_color=self.colors['frame'], dropdown_hover_color=self.colors['border'],
            height=int(40 * scale_factor)
        )
        self.sort_menu.pack(fill="x")

        # --- Brawler Grid ---
        self.grid_container = ctk.CTkFrame(main_pad, fg_color=self.colors['frame'], border_color=self.colors['border'], border_width=1, corner_radius=int(10 * scale_factor))
        self.grid_container.pack(fill="both", expand=True)

        self.image_frame = ctk.CTkScrollableFrame(
            self.grid_container, fg_color="transparent", 
            scrollbar_button_color=self.colors['border'], scrollbar_button_hover_color=self.colors['text_muted']
        )
        self.image_frame.pack(fill="both", expand=True, padx=int(10 * scale_factor), pady=int(10 * scale_factor))

        self.update_images("")

    def on_sort_change(self, value):
        self.current_sort = value
        self.update_images(self.filter_var.get())

    def queue_image_filter_update(self):
        if self._closing:
            return
        if self._filter_after_id is not None:
            try:
                self.app.after_cancel(self._filter_after_id)
            except Exception:
                pass
        self._filter_after_id = self.app.after(
            120,
            lambda: self.update_images(self.filter_var.get())
        )

    def set_farm_type(self, value):
        self.farm_type = value

    def start_bot(self):
        if self._closing:
            return
        # If user changed player tag, save it to api config
        tag_val = self.tag_var.get().strip()
        if tag_val and tag_val != self.player_tag:
            try:
                config_path = "cfg/brawl_stars_api.toml"
                conf = load_toml_as_dict(config_path)
                conf["player_tag"] = tag_val
                # save_dict_as_toml(conf, config_path)  # Assuming save config logic here or later
            except Exception:
                pass

        brawlers_data = list(self.brawlers_data)
        self._closing = True
        self._cancel_queued_callbacks()
        self._hide_window()
        self.data_setter(brawlers_data)
        try:
            self.app.quit()
        except Exception:
            pass

    def _cancel_queued_callbacks(self):
        for after_id in (self._filter_after_id, self._image_render_after_id):
            if after_id is None:
                continue
            try:
                self.app.after_cancel(after_id)
            except Exception:
                pass
        self._filter_after_id = None
        self._image_render_after_id = None

    def _hide_window(self):
        try:
            self.app.withdraw()
            self.app.update_idletasks()
            self.app.update()
        except Exception:
            pass

    def close_app(self):
        if self._closed:
            return
        self._closing = True
        self._cancel_queued_callbacks()
        self._hide_window()

        try:
            self.app.quit()
        except Exception:
            pass
        try:
            self.app.destroy()
        except Exception:
            pass
        self._closed = True

    def open_queue_builder(self):
        self._queue_builder_top = ctk.CTkToplevel(self.app)
        top = self._queue_builder_top
        top.configure(fg_color=self.colors['bg'])
        win_w = int(700 * scale_factor)
        win_h = int(550 * scale_factor)
        x = self.app.winfo_x() + (self.app.winfo_width() // 2) - (win_w // 2)
        y = self.app.winfo_y() + (self.app.winfo_height() // 2) - (win_h // 2)
        top.geometry(f"{win_w}x{win_h}+{x}+{y}")
        top.title("Build Queue")
        top.transient(self.app)
        top.grab_set()
        top.resizable(False, False)

        header = ctk.CTkFrame(top, fg_color="transparent")
        header.pack(fill="x", padx=int(20*scale_factor), pady=(int(20*scale_factor), int(10*scale_factor)))
        ctk.CTkLabel(header, text="Build Your Queue", font=("Arial", int(20 * scale_factor), "bold"), text_color=self.colors['text_main']).pack(side="left")
        ctk.CTkLabel(header, text="Select brawlers to push sequentially", font=("Arial", int(14 * scale_factor)), text_color=self.colors['text_muted']).pack(side="left", padx=int(10*scale_factor))

        main_split = ctk.CTkFrame(top, fg_color="transparent")
        main_split.pack(fill="both", expand=True, padx=int(20*scale_factor), pady=int(10*scale_factor))

        # Left panel: Available
        left_panel = ctk.CTkFrame(main_split, fg_color=self.colors['frame'], border_color=self.colors['border'], border_width=1, corner_radius=int(8*scale_factor))
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, int(10*scale_factor)))
        ctk.CTkLabel(left_panel, text="Available Brawlers", font=("Arial", int(14*scale_factor), "bold"), text_color=self.colors['text_main']).pack(pady=int(10*scale_factor))
        
        brawler_list_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        brawler_list_frame.pack(fill="both", expand=True, padx=int(5*scale_factor), pady=int(5*scale_factor))

        # Right panel: The Queue
        right_panel = ctk.CTkFrame(main_split, fg_color=self.colors['frame'], border_color=self.colors['border'], border_width=1, corner_radius=int(8*scale_factor))
        right_panel.pack(side="right", fill="both", expand=True, padx=(int(10*scale_factor), 0))
        ctk.CTkLabel(right_panel, text="Your Sequence", font=("Arial", int(14*scale_factor), "bold"), text_color=self.colors['accent']).pack(pady=int(10*scale_factor))
        
        queue_list_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        queue_list_frame.pack(fill="both", expand=True, padx=int(5*scale_factor), pady=int(5*scale_factor))

        temp_queue = []

        def refresh_queue():
            for widget in queue_list_frame.winfo_children():
                widget.destroy()
            if not temp_queue:
                ctk.CTkLabel(queue_list_frame, text="Queue is empty.", text_color=self.colors['text_muted']).pack(pady=int(20*scale_factor))
                return
            for i, item in enumerate(temp_queue):
                item_frame = ctk.CTkFrame(queue_list_frame, fg_color=self.colors['card_bg'], border_color=self.colors['border'], border_width=1)
                item_frame.pack(fill="x", pady=int(3*scale_factor), padx=int(5*scale_factor))
                text = f"{i+1}. {item['brawler']} (Push to {item['push_until']} {item['type']})"
                ctk.CTkLabel(item_frame, text=text, font=("Arial", int(12*scale_factor), "bold"), text_color=self.colors['text_main']).pack(side="left", padx=int(10*scale_factor), pady=int(8*scale_factor))
                
                # Delete btn
                def make_del(idx=i):
                    return lambda: remove_item(idx)
                ctk.CTkButton(item_frame, text="X", width=int(30*scale_factor), font=("Arial", int(12*scale_factor), "bold"), fg_color="transparent", hover_color=self.colors['error'], text_color=self.colors['error'], command=make_del()).pack(side="right", padx=int(5*scale_factor))

        def remove_item(idx):
            temp_queue.pop(idx)
            refresh_queue()

        def add_to_queue(brawler):
            # Inline popup to ask for target
            self._target_dialog = ctk.CTkToplevel(top)
            target_dialog = self._target_dialog
            target_dialog.configure(fg_color=self.colors['bg'])
            target_dialog.title("Set Target")
            target_dialog.geometry(f"{int(300*scale_factor)}x{int(250*scale_factor)}+{x + int(200*scale_factor)}+{y + int(150*scale_factor)}")
            target_dialog.transient(top)
            try:
                target_dialog.grab_set()
            except Exception:
                pass
            try:
                target_dialog.focus()
            except Exception:
                pass
            
            ctk.CTkLabel(target_dialog, text=f"Target for {brawler}:", font=("Arial", int(14*scale_factor), "bold"), text_color=self.colors['text_main']).pack(pady=int(10*scale_factor))
            
            t_var = tk.StringVar(value="trophies")
            c_frame = ctk.CTkFrame(target_dialog, fg_color="transparent")
            c_frame.pack(pady=int(5*scale_factor))
            ctk.CTkRadioButton(c_frame, text="Trophies", variable=t_var, value="trophies", text_color=self.colors['text_main']).pack(side="left", padx=10)
            ctk.CTkRadioButton(c_frame, text="Wins", variable=t_var, value="wins", text_color=self.colors['text_main']).pack(side="left", padx=10)
            
            val_var = tk.StringVar()
            ctk.CTkEntry(target_dialog, textvariable=val_var, placeholder_text="e.g., 1000", fg_color=self.colors['input_bg'], border_color=self.colors['border'], text_color=self.colors['text_main']).pack(pady=int(10*scale_factor))
            
            def confirm():
                if val_var.get().isdigit():
                    temp_queue.append({
                        "brawler": brawler,
                        "push_until": int(val_var.get()),
                        "type": t_var.get(),
                        "automatically_pick": True,
                        "trophies": self.get_api_trophies_for_brawler(brawler) or 0,
                        "wins": 0,
                        "win_streak": 0
                    })
                    refresh_queue()
                    target_dialog.destroy()
            
            ctk.CTkButton(target_dialog, text="Add", command=confirm, fg_color=self.colors['accent'], hover_color=self.colors['accent_hover'], text_color=self.colors['text_main']).pack(pady=int(15*scale_factor))

        # Populate available
        for brawler in self.brawlers:
            btn = ctk.CTkButton(brawler_list_frame, text=brawler, command=lambda b=brawler: add_to_queue(b), fg_color="transparent", hover_color=self.colors['border'], text_color=self.colors['text_main'], border_color=self.colors['border'], border_width=1, anchor="w")
            btn.pack(fill="x", pady=int(2*scale_factor), padx=int(5*scale_factor))

        refresh_queue()

        # Bottom buttons
        footer = ctk.CTkFrame(top, fg_color="transparent")
        footer.pack(fill="x", padx=int(20*scale_factor), pady=(0, int(20*scale_factor)))
        
        def apply_queue():
            if temp_queue:
                self.brawlers_data = temp_queue
                self._show_info_modal("Success", f"Queue built with {len(temp_queue)} characters.")
                top.destroy()
        
        ctk.CTkButton(footer, text="Apply Queue", command=apply_queue, fg_color=self.colors['accent'], hover_color=self.colors['accent_hover'], text_color=self.colors['text_main'], font=("Arial", int(14*scale_factor), "bold"), height=int(40*scale_factor)).pack(side="right")
        ctk.CTkButton(footer, text="Cancel", command=top.destroy, fg_color="transparent", hover_color=self.colors['border'], text_color=self.colors['text_main'], border_color=self.colors['border'], border_width=1, height=int(40*scale_factor)).pack(side="right", padx=int(10*scale_factor))

    def _show_info_modal(self, title, message):
        top = ctk.CTkToplevel(self.app)
        top.configure(fg_color=self.colors['bg'])
        top.title(title)
        top.attributes("-topmost", True)
        top.geometry(f"{int(300*scale_factor)}x{int(150*scale_factor)}+{int(550*scale_factor)}+{int(350*scale_factor)}")
        
        ctk.CTkLabel(top, text=message, font=("Arial", int(14 * scale_factor)), text_color=self.colors['text_main']).pack(pady=int(30*scale_factor))
        ctk.CTkButton(top, text="OK", command=top.destroy, fg_color=self.colors['accent'], hover_color=self.colors['accent_hover']).pack()

    # --- PUSH ALL LOGIC ---
    def get_push_all_data(self, target_trophies=1000):
        target_trophies = int(target_trophies)
        # Force-refresh the token so it always matches the current public IP.
        # This prevents "accessDenied" errors when the user's IP has changed
        # since the token was last generated.
        try:
            api_config = load_brawl_stars_api_config("cfg/brawl_stars_api.toml", force_refresh=True)
        except Exception:
            # If force-refresh fails (e.g. no credentials), fall back to cached token.
            api_config = load_brawl_stars_api_config("cfg/brawl_stars_api.toml")
        
        # Override with UI tag if changed
        current_tag = self.tag_var.get().strip() or api_config.get("player_tag", "").strip()
        
        player_data = fetch_brawl_stars_player(
            api_config.get("api_token", "").strip(),
            current_tag,
            int(api_config.get("timeout_seconds", 15)),
        )
        known_by_normalized_name = {
            normalize_brawler_name(brawler): brawler
            for brawler in self.brawlers
        }
        rows = []
        for index, api_brawler in enumerate(player_data.get("brawlers", [])):
            brawler = known_by_normalized_name.get(normalize_brawler_name(api_brawler.get("name", "")))
            if not brawler:
                continue
            trophies = int(api_brawler.get("trophies", 0))
            if trophies < target_trophies:
                rows.append((trophies, index, brawler))

        rows.sort(key=lambda item: (item[0], item[1]))
        data = []
        for idx, (trophies, _, brawler) in enumerate(rows):
            data.append({
                "brawler": brawler,
                "push_until": target_trophies,
                "trophies": trophies,
                "wins": 0,
                "type": "trophies",
                "automatically_pick": idx != 0,
                "selection_method": "lowest_trophies",
                "win_streak": 0,
            })
        return data

    @staticmethod
    def _match_brawler_from_ocr_texts(texts, known_brawlers):
        best_brawler = None
        best_score = 0.0
        known_names = [(brawler, normalize_brawler_name(brawler)) for brawler in known_brawlers]
        for raw_text in texts:
            normalized_text = normalize_brawler_name(raw_text)
            if not normalized_text:
                continue
            for brawler, normalized_brawler in known_names:
                if normalized_text == normalized_brawler:
                    return brawler
                if normalized_brawler in normalized_text or normalized_text in normalized_brawler:
                    score = min(len(normalized_text), len(normalized_brawler)) / max(
                        len(normalized_text), len(normalized_brawler)
                    )
                else:
                    score = SequenceMatcher(None, normalized_text, normalized_brawler).ratio()
                if score > best_score:
                    best_score = score
                    best_brawler = brawler
        return best_brawler if best_score >= 0.72 else None

    @staticmethod
    def _move_brawler_to_front(data, selected_brawler):
        if not selected_brawler:
            return data
        selected_normalized = normalize_brawler_name(selected_brawler)
        selected_index = None
        for index, row in enumerate(data):
            if normalize_brawler_name(row.get("brawler", "")) == selected_normalized:
                selected_index = index
                break
        if selected_index is None:
            return data
        reordered = [dict(row) for row in data]
        selected_row = reordered.pop(selected_index)
        reordered.insert(0, selected_row)
        for index, row in enumerate(reordered):
            row["automatically_pick"] = index != 0
        return reordered

    def detect_first_sorted_brawler(self, device):
        last_texts = []
        for attempt in range(3):
            try:
                screenshot = device.screenshot()
                frame = np.array(screenshot)
                if frame.ndim == 3 and frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
            except Exception as e:
                print(f"Could not screenshot brawler screen for OCR: {e}")
                return None

            height, width = frame.shape[:2]
            crop = frame[
                int(height * 0.16):int(height * 0.56),
                int(width * 0.10):int(width * 0.36),
            ]
            try:
                texts = extract_text_strings(crop)
            except Exception as e:
                print(f"Could not OCR first sorted brawler card: {e}")
                return None

            last_texts = texts
            detected_brawler = self._match_brawler_from_ocr_texts(texts, self.brawlers)
            if detected_brawler:
                print(f"Detected first sorted brawler from game screen: {detected_brawler} (OCR: {texts})")
                return detected_brawler
            time.sleep(0.35 + attempt * 0.2)

        print(f"Could not match first sorted brawler from OCR: {last_texts}")
        return None

    def get_adb_device_for_quick_select(self):
        general_config = load_toml_as_dict("cfg/general_config.toml")
        configured_port = general_config.get("emulator_port", 0)
        selected_emulator = general_config.get("current_emulator", "LDPlayer")
        brawl_package = general_config.get("brawl_stars_package", "com.supercell.brawlstars").strip()
        emulator_ports = {
            "LDPlayer": [5555, 5557, 5559, 5554],
            "MuMu": [16384, 16416, 16448, 7555, 5558, 5557, 5556, 5555, 5554],
        }
        if selected_emulator not in emulator_ports:
            try:
                configured_port_int = int(configured_port)
            except (TypeError, ValueError):
                configured_port_int = 0
            selected_emulator = "MuMu" if configured_port_int in (16384, 16416, 16448, 7555) else "LDPlayer"
        try:
            configured_port = int(configured_port)
        except (TypeError, ValueError):
            configured_port = 0
        preferred_ports = []
        port_candidates = [configured_port] + emulator_ports[selected_emulator] + emulator_ports["LDPlayer"] + emulator_ports["MuMu"]
        for port in port_candidates:
            try:
                port = int(port)
            except (TypeError, ValueError):
                continue
            if port != 5037 and port not in preferred_ports:
                preferred_ports.append(port)
        configured_ports = []
        try:
            configured_ports = [int(configured_port)]
        except (TypeError, ValueError):
            pass

        def serial_port(serial):
            if serial.startswith("emulator-"):
                try:
                    return int(serial.rsplit("-", 1)[1])
                except ValueError:
                    return None
            if ":" in serial:
                try:
                    return int(serial.rsplit(":", 1)[1])
                except ValueError:
                    return None
            return None

        def online_devices():
            devices = []
            for dev in adb.device_list():
                try:
                    if dev.get_state() == "device":
                        devices.append(dev)
                except Exception:
                    pass
            return devices

        def choose_device(devices):
            best_device = None
            best_score = None
            for index, dev in enumerate(devices):
                port = serial_port(dev.serial)
                try:
                    opened_package = dev.app_current().package.strip()
                except Exception:
                    opened_package = ""
                score = (
                    opened_package == brawl_package,
                    port in configured_ports,
                    port in preferred_ports,
                    -index,
                )
                if best_score is None or score > best_score:
                    best_device = dev
                    best_score = score
            return best_device

        devices = online_devices()
        device = choose_device(devices)
        if device:
            return device

        for port in preferred_ports:
            if port == 5037:
                continue
            try:
                adb.connect(f"127.0.0.1:{port}")
            except Exception:
                pass

        devices = online_devices()
        device = choose_device(devices)
        if not device:
            raise ConnectionError("No ADB device found for Push All.")
        return device

    def quick_select_least_trophies_brawler(self):
        device = self.get_adb_device_for_quick_select()
        size = device.window_size()
        width = size.width
        height = size.height

        def tap_pct(x_pct, y_pct, wait=1.0):
            x = int(width * x_pct)
            y = int(height * y_pct)
            device.shell(f"input tap {x} {y}")
            time.sleep(wait)

        print(f"Push All using ADB device: {device.serial}")
        
        # 1. Tap center of lobby to open brawler list safely
        tap_pct(0.500, 0.500, 1.5)
        
        # 2. Tap Sort Dropdown
        tap_pct(0.630, 0.041, 0.8)
        
        # 3. Least Trophies
        tap_pct(0.630, 0.394, 1.2)
        
        # Detect the first sorted brawler via OCR
        selected_brawler = self.detect_first_sorted_brawler(device)
        
        # 4. First brawler card
        tap_pct(0.260, 0.370, 3.0)
        
        # 5. Select button
        tap_pct(0.135, 0.917, 1.5)
        
        return device.serial, selected_brawler

    def open_push_all_target_window(self):
        top = ctk.CTkToplevel(self.app)
        top.configure(fg_color=self.colors['bg'])
        top.title("Push All Target")
        top.attributes("-topmost", True)
        
        win_w = int(360 * scale_factor)
        win_h = int(230 * scale_factor)
        top.geometry(f"{win_w}x{win_h}+{int(600 * scale_factor)}+{int(300 * scale_factor)}")

        ctk.CTkLabel(
            top,
            text="Push all brawlers to:",
            font=("Arial", int(20 * scale_factor), "bold"),
            text_color=self.colors['text_main'],
        ).pack(pady=(int(20 * scale_factor), int(10 * scale_factor)))

        button_frame = ctk.CTkFrame(top, fg_color="transparent")
        button_frame.pack(pady=int(10 * scale_factor))

        def choose_target(target):
            try:
                top.destroy()
            except Exception:
                pass
            self.push_all(target)

        targets = [250, 500, 750, 1000]
        for index, target in enumerate(targets):
            row = index // 2
            col = index % 2
            ctk.CTkButton(
                button_frame,
                text=str(target),
                command=lambda t=target: choose_target(t),
                fg_color=self.colors['frame'],
                hover_color=self.colors['border'],
                text_color=self.colors['text_main'],
                font=("Arial", int(16 * scale_factor), "bold"),
                border_color=self.colors['border'],
                border_width=int(1 * scale_factor),
                width=int(120 * scale_factor),
                height=int(45 * scale_factor),
            ).grid(row=row, column=col, padx=int(10 * scale_factor), pady=int(10 * scale_factor))

    def push_all(self, target_trophies=1000):
        if self._closing:
            return
        target_trophies = int(target_trophies)
        hidden_for_start = False
        try:
            self.app.withdraw()
            self.app.update_idletasks()
            self.app.update()
            hidden_for_start = True

            data = self.get_push_all_data(target_trophies)
            if not data:
                print(f"Push All: no brawlers below {target_trophies} trophies were found.")
                self._show_info_modal("Finished", f"No brawlers below {target_trophies} trophies.")
                self.app.deiconify()
                return
            print(f"Push All {target_trophies} first brawler (from API data):", data[0])
            self.brawlers_data = data
            self.start_bot()
        except Exception as e:
            print(f"Push All failed: {e}")
            self._show_info_modal("Error", f"Push All failed. Ensure game is running.\n{str(e)[:40]}")
            if hidden_for_start:
                try:
                    self.app.deiconify()
                except Exception:
                    pass

    # --- API DATA & MODAL ---
    def get_api_trophies_by_brawler(self):
        if self.api_trophies_by_brawler is not None:
            return self.api_trophies_by_brawler
        # Fallback to init mechanism
        self._init_api_data()
        return self.api_trophies_by_brawler or {}

    def get_api_trophies_for_brawler(self, brawler):
        api_trophies = self.get_api_trophies_by_brawler()
        if brawler in api_trophies:
            return api_trophies[brawler]
        if self.api_trophies_by_normalized_brawler is None:
            self.api_trophies_by_normalized_brawler = {
                normalize_brawler_name(name): trophies
                for name, trophies in api_trophies.items()
            }
        return self.api_trophies_by_normalized_brawler.get(normalize_brawler_name(brawler))

    def on_image_click(self, brawler):
        self.open_brawler_entry(brawler)

    def open_brawler_entry(self, brawler):
        # Modern sleak modal
        top = ctk.CTkToplevel(self.app)
        top.configure(fg_color=self.colors['bg'])
        win_w = int(360 * scale_factor)
        win_h = int(480 * scale_factor)
        
        # Center over main window
        x = self.app.winfo_x() + (self.app.winfo_width() // 2) - (win_w // 2)
        y = self.app.winfo_y() + (self.app.winfo_height() // 2) - (win_h // 2)
        top.geometry(f"{win_w}x{win_h}+{x}+{y}")
        top.title(f"Configure {brawler}")
        top.attributes("-topmost", True)
        top.resizable(False, False)

        # Variables
        push_until_var = tk.StringVar()
        trophies_var = tk.StringVar()
        wins_var = tk.StringVar()
        current_win_streak_var = tk.StringVar(value="0")
        auto_pick_var = tk.BooleanVar(value=True)
        
        api_trophies = self.get_api_trophies_for_brawler(brawler)
        if api_trophies is not None:
            trophies_var.set(str(api_trophies))

        # Title Area
        header = ctk.CTkFrame(top, fg_color="transparent")
        header.pack(fill="x", padx=int(20*scale_factor), pady=(int(20*scale_factor), int(10*scale_factor)))
        ctk.CTkLabel(
            header, text=f"Configure {brawler}", font=("Arial", int(20 * scale_factor), "bold"),
            text_color=self.colors['text_main']
        ).pack(side="left")

        # Push Type segmented buttons
        type_frame = ctk.CTkFrame(top, fg_color="transparent")
        type_frame.pack(fill="x", padx=int(20*scale_factor), pady=int(10*scale_factor))
        
        def create_input_group(parent, label_text, var):
            grp = ctk.CTkFrame(parent, fg_color="transparent")
            ctk.CTkLabel(grp, text=label_text, font=("Arial", int(12*scale_factor), "bold"), text_color=self.colors['text_muted']).pack(anchor="w")
            ent = ctk.CTkEntry(
                grp, textvariable=var, fg_color=self.colors['input_bg'], border_color=self.colors['border'],
                text_color=self.colors['text_main'], font=("Arial", int(14*scale_factor)), height=int(35*scale_factor)
            )
            ent.pack(fill="x", pady=(int(5*scale_factor), 0))
            return grp, ent

        inputs_frame = ctk.CTkFrame(top, fg_color="transparent")
        inputs_frame.pack(fill="x", padx=int(20*scale_factor), pady=int(10*scale_factor))

        f_target, _ = create_input_group(inputs_frame, "Target Amount", push_until_var)
        f_trophies, _ = create_input_group(inputs_frame, "Current Trophies", trophies_var)
        f_wins, _ = create_input_group(inputs_frame, "Current Wins", wins_var)
        f_streak, _ = create_input_group(inputs_frame, "Current Win Streak", current_win_streak_var)
        
        # Checkbox
        check_frame = ctk.CTkFrame(top, fg_color="transparent")
        check_frame.pack(fill="x", padx=int(20*scale_factor), pady=int(10*scale_factor))
        auto_cb = ctk.CTkCheckBox(
            check_frame, text="Bot auto-selects brawler", variable=auto_pick_var,
            fg_color=self.colors['accent'], hover_color=self.colors['accent_hover'], border_color=self.colors['border'],
            text_color=self.colors['text_main'], font=("Arial", int(13*scale_factor))
        )
        auto_cb.pack(anchor="w")

        # Submit
        submit_btn = ctk.CTkButton(
            top, text="Save to Queue", command=lambda: submit_data(),
            fg_color=self.colors['accent'], hover_color=self.colors['accent_hover'],
            font=("Arial", int(14*scale_factor), "bold"), height=int(40*scale_factor)
        )

        def check_submit_visibility(*args):
            if self.farm_type == "":
                submit_btn.pack_forget()
                return
            target_ok = push_until_var.get().isdigit()
            if self.farm_type == "trophies":
                fields_ok = target_ok and trophies_var.get().isdigit() and current_win_streak_var.get().isdigit()
            else:
                fields_ok = target_ok and wins_var.get().isdigit()
            if fields_ok:
                submit_btn.pack(fill="x", padx=int(20*scale_factor), pady=(int(10*scale_factor), int(20*scale_factor)))
            else:
                submit_btn.pack_forget()

        push_until_var.trace_add("write", check_submit_visibility)
        trophies_var.trace_add("write", check_submit_visibility)
        wins_var.trace_add("write", check_submit_visibility)
        current_win_streak_var.trace_add("write", check_submit_visibility)

        def hide_all():
            f_target.pack_forget()
            f_trophies.pack_forget()
            f_wins.pack_forget()
            f_streak.pack_forget()

        def set_type(t):
            self.farm_type = t
            btn_trophies.configure(fg_color=self.colors['accent'] if t=="trophies" else self.colors['frame'])
            btn_wins.configure(fg_color=self.colors['accent'] if t=="wins" else self.colors['frame'])
            
            hide_all()
            f_target.pack(fill="x", pady=(0, int(10*scale_factor)))
            if t == "trophies":
                f_trophies.pack(fill="x", pady=(0, int(10*scale_factor)))
                f_streak.pack(fill="x", pady=(0, int(10*scale_factor)))
            else:
                f_wins.pack(fill="x", pady=(0, int(10*scale_factor)))
            check_submit_visibility()

        btn_trophies = ctk.CTkButton(
            type_frame, text="Trophies", command=lambda: set_type("trophies"),
            fg_color=self.colors['frame'], hover_color=self.colors['border'], text_color=self.colors['text_main'],
            font=("Arial", int(13*scale_factor), "bold"), border_color=self.colors['border'], border_width=1,
            width=int(140*scale_factor)
        )
        btn_trophies.pack(side="left", padx=(0, int(10*scale_factor)))
        
        btn_wins = ctk.CTkButton(
            type_frame, text="Wins", command=lambda: set_type("wins"),
            fg_color=self.colors['frame'], hover_color=self.colors['border'], text_color=self.colors['text_main'],
            font=("Arial", int(13*scale_factor), "bold"), border_color=self.colors['border'], border_width=1,
            width=int(140*scale_factor)
        )
        btn_wins.pack(side="left")

        def submit_data():
            d = {
                "brawler": brawler,
                "push_until": int(push_until_var.get()),
                "type": self.farm_type,
                "automatically_pick": auto_pick_var.get(),
            }
            if self.farm_type == "trophies":
                d["trophies"] = int(trophies_var.get())
                d["win_streak"] = int(current_win_streak_var.get())
                d["wins"] = 0
            else:
                d["wins"] = int(wins_var.get())
                d["trophies"] = 0
                d["win_streak"] = 0

            self.brawlers_data = [item for item in self.brawlers_data if item["brawler"] != d["brawler"]]
            self.brawlers_data.append(d)
            top.destroy()

    # --- GRID RENDER ---
    def update_images(self, filter_text):
        if self._closing:
            return
        filter_text = (filter_text or "").strip().lower()
        
        if self._image_render_after_id is not None:
            try:
                self.app.after_cancel(self._image_render_after_id)
            except Exception:
                pass
            self._image_render_after_id = None
            
        self.visible_image_labels = []
        for widget in self.image_frame.winfo_children():
            widget.destroy()

        # Filtering
        matches = [
            (brawler, img_tk)
            for brawler, img_tk in self.images
            if brawler.startswith(filter_text)
        ]

        # Sorting
        if self.current_sort == "Lowest to Highest":
            matches.sort(key=lambda x: self.get_api_trophies_for_brawler(x[0]) or 0)
        elif self.current_sort == "Highest to Lowest":
            matches.sort(key=lambda x: self.get_api_trophies_for_brawler(x[0]) or 0, reverse=True)
        # "In Order" does not sort (uses original order from brawlers list)

        # Dynamic columns based on width
        col_count = 10 # approximate max
        
        def render_batch(start_index=0):
            if self._closing:
                return
            for index in range(start_index, min(start_index + 16, len(matches))):
                brawler, img_tk = matches[index]
                row_num = index // col_count
                col_num = index % col_count
                
                # Card Frame
                card = ctk.CTkFrame(
                    self.image_frame, fg_color=self.colors['card_bg'], corner_radius=int(8*scale_factor),
                    border_color=self.colors['border'], border_width=int(1*scale_factor), cursor="hand2"
                )
                card.grid(row=row_num, column=col_num, padx=int(8 * scale_factor), pady=int(8 * scale_factor))
                
                # Image
                lbl_img = ctk.CTkLabel(card, image=img_tk, text="")
                lbl_img.pack(padx=int(8*scale_factor), pady=(int(8*scale_factor), 0))
                
                # Name
                lbl_name = ctk.CTkLabel(
                    card, text=brawler.capitalize(), font=("Arial", int(12*scale_factor), "bold"),
                    text_color=self.colors['text_main']
                )
                lbl_name.pack(pady=(int(4*scale_factor), int(8*scale_factor)))

                # Bindings for hover and click
                def on_enter(e, c=card):
                    c.configure(fg_color=self.colors['card_hover'], border_color=self.colors['accent'])
                def on_leave(e, c=card):
                    c.configure(fg_color=self.colors['card_bg'], border_color=self.colors['border'])
                    
                for w in (card, lbl_img, lbl_name):
                    w.bind("<Enter>", on_enter)
                    w.bind("<Leave>", on_leave)
                    w.bind("<Button-1>", lambda e, b=brawler: self.on_image_click(b))

            next_index = start_index + 16
            if next_index < len(matches):
                self._image_render_after_id = self.app.after(1, lambda: render_batch(next_index))
            else:
                self._image_render_after_id = None

        render_batch()

def dummy_data_setter(data):
    print("Data set:", data)

if __name__ == "__main__":
    SelectBrawler(dummy_data_setter, ["Shelly", "Nita", "Colt", "Bull"])
