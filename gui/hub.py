import customtkinter as ctk
import asyncio
import threading
import webbrowser
import os
import pyautogui
from pathlib import Path
from PIL import Image
import tkinter as tk
from common.utils import load_toml_as_dict, save_dict_as_toml, get_discord_link, get_dpi_scale, resolve_instance_path
from packaging import version
from common.performance_profile import apply_performance_profile
from remote.discord_notifier import async_send_test_notification
from remote.telegram_notifier import async_send_test_notification as async_send_telegram_test_notification

orig_screen_width, orig_screen_height = 1920, 1080
width, height = pyautogui.size()
width_ratio = width / orig_screen_width
height_ratio = height / orig_screen_height
scale_factor = min(width_ratio, height_ratio)
scale_factor *= 96/get_dpi_scale()

def S(value):
    """Helper to scale integer sizes based on the user's screen."""
    return int(value * scale_factor)


class Hub:
    """
    Updated, more user-friendly interface for the Pyla-Biomistik bot.
    """

    def __init__(self,
                 version_str,
                 latest_version_str,
                 correct_zoom=True,
                 on_close_callback=None):

        self.version_str = version_str
        self.latest_version_str = latest_version_str
        self.correct_zoom = correct_zoom
        self.on_close_callback = on_close_callback

        # -----------------------------------------------------------------------------------------
        # Load configs
        # -----------------------------------------------------------------------------------------
        self.bot_config_path = "cfg/bot_config.toml"
        self.time_tresholds_path = "cfg/time_tresholds.toml"
        self.match_history_path = "cfg/match_history.toml"
        self.general_config_path = "cfg/general_config.toml"
        self.webhook_config_path = "cfg/discord_config.toml"
        self.telegram_config_path = "cfg/telegram_config.toml"
        legacy_webhook_config_path = "cfg/webhook_config.toml"

        self.bot_config = load_toml_as_dict(self.bot_config_path)
        self.time_tresholds = load_toml_as_dict(self.time_tresholds_path)
        self.match_history = load_toml_as_dict(self.match_history_path)
        self.general_config = load_toml_as_dict(self.general_config_path)
        if not Path(self.webhook_config_path).exists() and Path(legacy_webhook_config_path).exists():
            self.webhook_config = load_toml_as_dict(legacy_webhook_config_path)
            save_dict_as_toml(self.webhook_config, self.webhook_config_path)
        else:
            self.webhook_config = load_toml_as_dict(self.webhook_config_path)
            
        self.telegram_config = load_toml_as_dict(self.telegram_config_path)

        # -----------------------------------------------------------------------------------------
        # Defaults
        # -----------------------------------------------------------------------------------------
        # Bot config defaults
        self.bot_config.setdefault("gamemode_type", 3)
        self.bot_config.setdefault("gamemode", "brawlball")
        self.bot_config.setdefault("bot_uses_gadgets", "yes")
        self.bot_config.setdefault("minimum_movement_delay", 0.4)
        self.bot_config.setdefault("wall_detection_confidence", 0.9)
        self.bot_config.setdefault("entity_detection_confidence", 0.6)
        self.bot_config.setdefault("unstuck_movement_delay", 3.0)
        self.bot_config.setdefault("unstuck_movement_hold_time", 1.5)
        self.bot_config.setdefault("play_again_on_win", "no")
        self.bot_config.setdefault("current_playstyle", "default.pyla")


        # Time thresholds defaults
        self.time_tresholds.setdefault("state_check", 3)
        self.time_tresholds.setdefault("no_detections", 10)
        self.time_tresholds.setdefault("idle", 10)
        self.time_tresholds.setdefault("super", 0.1)
        self.time_tresholds.setdefault("gadget", 0.5)
        self.time_tresholds.setdefault("hypercharge", 2)

        # General config defaults
        self.general_config.setdefault("max_ips", "auto")
        self.general_config.setdefault("scrcpy_max_fps", 15)
        self.general_config.setdefault("onnx_cpu_threads", "auto")
        self.general_config.setdefault("used_threads", self.general_config.get("onnx_cpu_threads", "auto"))
        self.general_config.setdefault("super_debug", "no")
        self.general_config.setdefault("cpu_or_gpu", "auto")
        self.general_config.setdefault("directml_device_id", "auto")
        self.general_config.setdefault("long_press_star_drop", "no")
        self.general_config.setdefault("trophies_multiplier", 1.0)
        self.general_config.setdefault("ocr_scale_down_factor", 0.5)
        current_emu = self.general_config.setdefault("current_emulator", "LDPlayer")
        
        # Dynamic port assignment based on instance ID
        import os
        instance_id = int(os.environ.get("PYLAAI_INSTANCE", "1"))
        idx = instance_id - 1
        
        if current_emu == "LDPlayer":
            ports = [5555, 5557, 5559, 5554]
            port = ports[idx % len(ports)]
        else:
            ports = [16384, 16416, 16448, 7555]
            port = ports[idx % len(ports)]
            
        self.general_config["emulator_port"] = port
        self.general_config.setdefault("terminal_logging", "no")
        self.general_config.setdefault("visual_debug", "no")
        self.general_config.setdefault("visual_debug_scale", 0.6)
        self.general_config.setdefault("visual_debug_max_fps", 30)
        self.general_config.setdefault("visual_debug_max_boxes", 120)
        self.general_config.setdefault("capture_bad_vision_frames", "no")

        self.webhook_config.setdefault("webhook_url", self.general_config.get("personal_webhook", ""))
        self.webhook_config.setdefault("discord_id", self.general_config.get("discord_id", ""))
        self.webhook_config.setdefault("username", "Pyla-Biomistik")
        self.webhook_config.setdefault("send_match_summary", False)
        self.webhook_config.setdefault("include_screenshot", True)
        self.webhook_config.setdefault("ping_when_stuck", False)
        self.webhook_config.setdefault("ping_when_target_is_reached", False)
        self.webhook_config.setdefault("ping_every_x_match", 0)
        self.webhook_config.setdefault("ping_every_x_minutes", 0)
        self.webhook_config.setdefault("discord_control_enabled", False)
        self.webhook_config.setdefault("discord_bot_token", "")
        self.webhook_config.setdefault("discord_control_user_id", "")
        self.webhook_config.setdefault("discord_control_channel_id", "")
        self.webhook_config.setdefault("discord_control_guild_id", "")
        
        self.telegram_config.setdefault("telegram_bot_token", "")
        self.telegram_config.setdefault("telegram_chat_id", "")
        self.telegram_config.setdefault("send_match_summary", False)
        self.telegram_config.setdefault("include_screenshot", True)
        self.telegram_config.setdefault("ping_when_stuck", False)
        self.telegram_config.setdefault("ping_when_target_is_reached", False)
        self.telegram_config.setdefault("ping_every_x_match", 0)
        self.telegram_config.setdefault("ping_every_x_minutes", 0)
        self.telegram_config.setdefault("telegram_control_enabled", False)
        self.telegram_config.setdefault("telegram_control_user_id", "")

        # -----------------------------------------------------------------------------------------
        # Appearance
        # -----------------------------------------------------------------------------------------
        ctk.set_appearance_mode("dark")

        # For showing tooltips in Toplevel windows
        # For showing tooltips
        self.tooltip_window = None
        self._tooltip_after_id = None
        self._tooltip_owner = None
        self._tooltip_text = ""

        # -----------------------------------------------------------------------------------------
        # Main window
        # -----------------------------------------------------------------------------------------
        self.app = ctk.CTk()
        self.app.configure(fg_color="#0a0a0b")
        self.app.title(f"Pyla-Biomistik Hub – {self.version_str}")
        self.app.geometry(f"{S(1000)}x{S(750)}")
        self.app.resizable(False, False)

        # Hide tooltip on "global" interactions (tab switch, clicks, scroll, key press, focus loss, etc.)
        for seq in ("<ButtonPress>", "<MouseWheel>", "<KeyPress>", "<FocusOut>"):
            self.app.bind_all(seq, self._hide_tooltip, add="+")
        self.app.bind("<Configure>", self._hide_tooltip, add="+")  # window move/resize

        # -----------------------------------------------------------------------------------------
        # Main Sidebar Layout
        # -----------------------------------------------------------------------------------------
        self.main_container = ctk.CTkFrame(self.app, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        self.sidebar_frame = ctk.CTkFrame(self.main_container, width=S(220), fg_color="#141416", corner_radius=0, )
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # Title/Logo in sidebar
        logo_label = ctk.CTkLabel(self.sidebar_frame, text="Pyla-Biomistik", font=("Arial", S(22), "bold"), text_color="#ff204e")
        logo_label.pack(pady=(S(30), S(30)))

        # Content Frame
        self.content_frame = ctk.CTkFrame(self.main_container, fg_color="#0a0a0b", corner_radius=0)
        self.content_frame.pack(side="left", fill="both", expand=True, padx=S(20), pady=S(20))

        # Frame for each tab
        self.tab_overview = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_additional = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_webhook = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_telegram = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_timers = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_history = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_debug = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        self.tabs = {
            "Overview": self.tab_overview,
            "Settings": self.tab_additional,
            "Discord": self.tab_webhook,
            "Telegram": self.tab_telegram,
            "Timers": self.tab_timers,
            "History": self.tab_history,
            "Debug": self.tab_debug,
        }

        self.tab_buttons = {}

        def select_tab(name):
            for t_name, frame in self.tabs.items():
                if t_name == name:
                    frame.pack(fill="both", expand=True)
                    self.tab_buttons[t_name].configure(fg_color="#1a1a1c", border_color="#ff204e")
                else:
                    frame.pack_forget()
                    self.tab_buttons[t_name].configure(fg_color="transparent", border_color="#141416")

        # Sidebar Buttons
        for name in self.tabs.keys():
            btn = ctk.CTkButton(
                self.sidebar_frame, text=name, anchor="w",
                font=("Arial", S(15), "bold"), fg_color="transparent", text_color="#ffffff",
                hover_color="#1a1a1c", border_width=S(2), border_color="#141416",
                height=S(45), command=lambda n=name: select_tab(n)
            )
            btn.pack(fill="x", pady=S(5), padx=S(15))
            self.tab_buttons[name] = btn

        # Init each tab
        self._init_overview_tab()
        self._init_additional_tab()
        self._init_webhook_tab()
        self._init_telegram_tab()
        self._init_timers_tab()
        self._init_history_tab()
        self._init_debug_tab()

        # Select first tab
        select_tab("Overview")

        # Main loop
        self.app.mainloop()

    # ---------------------------------------------------------------------------------------------
    #  Tooltip Handler
    # ---------------------------------------------------------------------------------------------
    def _pointer_over_widget(self, widget) -> bool:
        if widget is None or not widget.winfo_exists():
            return False
        try:
            px, py = widget.winfo_pointerx(), widget.winfo_pointery()
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            w, h = widget.winfo_width(), widget.winfo_height()
            return x <= px <= x + w and y <= py <= y + h
        except tk.TclError:
            return False

    def _hide_tooltip(self, _event=None):
        # cancel delayed show if pending
        if self._tooltip_after_id is not None:
            try:
                self.app.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None

        # destroy current tooltip window
        if self.tooltip_window is not None:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None

        self._tooltip_owner = None
        self._tooltip_text = ""

    def attach_tooltip(self, widget, text, delay_ms: int = 250):
        """
        Robust tooltip:
        - shows after delay
        - hides on Leave, Unmap (tab switch), Destroy, clicks/scroll/keys (via global binds)
        - prevents stuck tooltips when switching tabs
        """

        def schedule_show(event=None):
            # reset any existing tooltip
            self._hide_tooltip()

            self._tooltip_owner = widget
            self._tooltip_text = text

            def do_show():
                # widget may have disappeared / tab switched
                if (self._tooltip_owner is None
                        or not self._tooltip_owner.winfo_exists()
                        or not self._tooltip_owner.winfo_viewable()
                        or not self._pointer_over_widget(self._tooltip_owner)):
                    self._hide_tooltip()
                    return

                # create tooltip
                self.tooltip_window = ctk.CTkToplevel(self.app)
                self.tooltip_window.overrideredirect(True)
                self.tooltip_window.attributes("-topmost", True)

                # position near cursor
                px = self.app.winfo_pointerx()
                py = self.app.winfo_pointery()
                self.tooltip_window.geometry(f"+{px + 12}+{py + 12}")

                label = ctk.CTkLabel(
                    self.tooltip_window,
                    text=self._tooltip_text,
                    fg_color="#141416",
                    text_color="#FFFFFF",
                    corner_radius=S(6),
                    font=("Arial", S(12))
                )
                label.pack(padx=S(6), pady=S(4))

                # if mouse enters tooltip itself, hide (avoids "stuck" hovering on tooltip)
                self.tooltip_window.bind("<Enter>", self._hide_tooltip)
                self.tooltip_window.bind("<Leave>", self._hide_tooltip)

            self._tooltip_after_id = self.app.after(delay_ms, do_show)

        def on_leave(_event=None):
            self._hide_tooltip()

        # Bindings
        widget.bind("<Enter>", schedule_show, add="+")
        widget.bind("<Leave>", on_leave, add="+")
        widget.bind("<Unmap>", on_leave, add="+")  # IMPORTANT: tab switching / frame hidden
        widget.bind("<Destroy>", on_leave, add="+")  # safety
        widget.bind("<ButtonPress>", on_leave, add="+")  # click on the widget -> hide

    # ---------------------------------------------------------------------------------------------
    #  Overview Tab
    # ---------------------------------------------------------------------------------------------
    def _init_overview_tab(self):
        frame = self.tab_overview

        # Main Grid Container
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=S(20), pady=S(20))
        
        container.grid_columnconfigure(0, weight=1, uniform="col")
        container.grid_columnconfigure(1, weight=1, uniform="col")
        container.grid_rowconfigure(0, weight=0)
        container.grid_rowconfigure(1, weight=1, uniform="row")
        container.grid_rowconfigure(2, weight=1, uniform="row")

        # -----------------------------------------------------------------
        # Banner
        # -----------------------------------------------------------------
        banner = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, S(15)))
        ctk.CTkLabel(banner, text="Community and Support", font=("Arial", S(14), "bold"), text_color="#8e8e93").pack(anchor="w", padx=S(15), pady=(S(10), 0))
        ctk.CTkLabel(banner, text="Join the Discord -> discord.gg/PylaAi", font=("Arial", S(14)), text_color="#ffffff").pack(anchor="w", padx=S(15), pady=(S(5), S(10)))

        # -----------------------------------------------------------------
        # Card 1: Configuration
        # -----------------------------------------------------------------
        card1 = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        card1.grid(row=1, column=0, sticky="nsew", padx=(0, S(7)), pady=(0, S(7)))
        ctk.CTkLabel(card1, text="Step 1: Configuration", font=("Arial", S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=S(20), pady=(S(20), S(10)))
        
        self.gamemode_type_var = __import__('tkinter').IntVar(value=self.bot_config.get("gamemode_type", 3))
        orient_frame = ctk.CTkFrame(card1, fg_color="transparent")
        orient_frame.pack(fill="both", expand=True, padx=S(20))
        
        def set_gamemode_type(t):
            self.gamemode_type_var.set(t)
            self.bot_config["gamemode_type"] = t
            __import__('common.utils').utils.save_dict_as_toml(self.bot_config, self.bot_config_path)
            refresh_orientation_buttons()
            self._refresh_gm_frames()
            
        self.btn_type_vertical = ctk.CTkButton(orient_frame, text="Vertical", command=lambda: set_gamemode_type(3), font=("Arial", S(14), "bold"), corner_radius=15, height=S(45))
        self.btn_type_vertical.pack(fill="x", pady=S(5))
        
        self.btn_type_horizontal = ctk.CTkButton(orient_frame, text="Horizontal", command=lambda: set_gamemode_type(5), font=("Arial", S(14), "bold"), corner_radius=15, height=S(45))
        self.btn_type_horizontal.pack(fill="x", pady=S(5))

        def refresh_orientation_buttons():
            t = self.gamemode_type_var.get()
            if t == 3:
                self.btn_type_vertical.configure(fg_color="#ff204e", hover_color="#1a1a1c")
                self.btn_type_horizontal.configure(fg_color="#1a1a1c", hover_color="#ff204e")
            else:
                self.btn_type_vertical.configure(fg_color="#1a1a1c", hover_color="#ff204e")
                self.btn_type_horizontal.configure(fg_color="#ff204e", hover_color="#1a1a1c")
        
        self._refresh_orientation_buttons = refresh_orientation_buttons

        # -----------------------------------------------------------------
        # Card 2: Gamemode
        # -----------------------------------------------------------------
        card2 = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        card2.grid(row=1, column=1, sticky="nsew", padx=(S(7), 0), pady=(0, S(7)))
        ctk.CTkLabel(card2, text="Step 2: Gamemode", font=("Arial", S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=S(20), pady=(S(20), S(10)))
        
        self.gm_buttons_frame = ctk.CTkFrame(card2, fg_color="transparent")
        self.gm_buttons_frame.pack(fill="both", expand=True, padx=S(20))
        
        self.gm3_frame = ctk.CTkFrame(self.gm_buttons_frame, fg_color="transparent")
        self.gm5_frame = ctk.CTkFrame(self.gm_buttons_frame, fg_color="transparent")
        
        self.gamemode_var = __import__('tkinter').StringVar(value=self.bot_config.get("gamemode", "showdown"))
        
        def create_gm_btn(parent, gm_value, text_display, orientation=3):
            def on_click():
                self.bot_config["gamemode_type"] = orientation
                self.bot_config["gamemode"] = gm_value
                __import__('common.utils').utils.save_dict_as_toml(self.bot_config, self.bot_config_path)
                self.gamemode_var.set(gm_value)
                refresh_gm_buttons()
            return ctk.CTkButton(parent, text=text_display, command=on_click, font=("Arial", S(14), "bold"), corner_radius=15, height=S(40))
            
        self.rb_brawlball_3 = create_gm_btn(self.gm3_frame, "brawlball", "Brawlball", 3)
        self.rb_showdown_3 = create_gm_btn(self.gm3_frame, "showdown", "Showdown Trio", 3)
        self.rb_other_3 = create_gm_btn(self.gm3_frame, "other", "Other", 3)
        self.rb_brawlball_3.pack(fill="x", pady=S(2))
        self.rb_showdown_3.pack(fill="x", pady=S(2))
        self.rb_other_3.pack(fill="x", pady=S(2))
        
        self.rb_basketbrawl_5 = create_gm_btn(self.gm5_frame, "basketbrawl", "Basket Brawl", 5)
        self.rb_bb5v5_5 = create_gm_btn(self.gm5_frame, "brawlball_5v5", "Brawlball 5v5", 5)
        self.rb_basketbrawl_5.pack(fill="x", pady=S(5))
        self.rb_bb5v5_5.pack(fill="x", pady=S(5))
        
        def refresh_gm_buttons():
            gm_now = self.gamemode_var.get()
            for btn, val in [(self.rb_brawlball_3, "brawlball"), (self.rb_showdown_3, "showdown"), (self.rb_other_3, "other"), (self.rb_basketbrawl_5, "basketbrawl"), (self.rb_bb5v5_5, "brawlball_5v5")]:
                if val == gm_now:
                    btn.configure(fg_color="#ff204e", hover_color="#1a1a1c")
                else:
                    btn.configure(fg_color="#1a1a1c", hover_color="#ff204e")
                    
        def _refresh_gm_frames():
            self.gm3_frame.pack_forget()
            self.gm5_frame.pack_forget()
            if self.gamemode_type_var.get() == 3:
                self.gm3_frame.pack(fill="both", expand=True)
            else:
                self.gm5_frame.pack(fill="both", expand=True)
                
        self._refresh_gm_frames = _refresh_gm_frames
        
        refresh_orientation_buttons()
        refresh_gm_buttons()
        _refresh_gm_frames()

        # -----------------------------------------------------------------
        # Card 3: Emulator
        # -----------------------------------------------------------------
        card3 = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        card3.grid(row=2, column=0, sticky="nsew", padx=(0, S(7)), pady=(S(7), 0))
        ctk.CTkLabel(card3, text="Step 3: Emulator", font=("Arial", S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=S(20), pady=(S(20), S(10)))
        
        emu_frame = ctk.CTkFrame(card3, fg_color="transparent")
        emu_frame.pack(fill="both", expand=True, padx=S(20))
        
        supported_emulators = {"LDPlayer": 5555, "MuMu": 16384}
        current_emu = self.general_config.get("current_emulator", "LDPlayer")
        self.emu_var = __import__('tkinter').StringVar(value=current_emu)
        
        def set_emu(choice):
            self.emu_var.set(choice)
            self.general_config["current_emulator"] = choice
            import os
            instance_id = int(os.environ.get("PYLAAI_INSTANCE", "1"))
            idx = instance_id - 1
            if choice == "LDPlayer":
                ports = [5555, 5557, 5559, 5554]
                port = ports[idx % len(ports)]
            else:
                ports = [16384, 16416, 16448, 7555]
                port = ports[idx % len(ports)]
            self.general_config["emulator_port"] = port
            __import__('common.utils').utils.save_dict_as_toml(self.general_config, self.general_config_path)
            refresh_emu()
            
        self.btn_ldplayer = ctk.CTkButton(emu_frame, text="LDPlayer", command=lambda: set_emu("LDPlayer"), font=("Arial", S(14), "bold"), corner_radius=15, height=S(50))
        self.btn_ldplayer.pack(side="left", fill="x", expand=True, padx=(0, S(5)))
        self.btn_mumu = ctk.CTkButton(emu_frame, text="MuMu", command=lambda: set_emu("MuMu"), font=("Arial", S(14), "bold"), corner_radius=15, height=S(50))
        self.btn_mumu.pack(side="right", fill="x", expand=True, padx=(S(5), 0))
        
        def refresh_emu():
            e = self.emu_var.get()
            self.btn_ldplayer.configure(fg_color="#ff204e" if e=="LDPlayer" else "#1a1a1c", hover_color="#1a1a1c" if e=="LDPlayer" else "#ff204e")
            self.btn_mumu.configure(fg_color="#ff204e" if e=="MuMu" else "#1a1a1c", hover_color="#1a1a1c" if e=="MuMu" else "#ff204e")
        refresh_emu()

        # -----------------------------------------------------------------
        # Card 4: Player Account + Start
        # -----------------------------------------------------------------
        card4 = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        card4.grid(row=2, column=1, sticky="nsew", padx=(S(7), 0), pady=(S(7), 0))
        card4.pack_propagate(False)

        ctk.CTkLabel(card4, text="Step 4: Account", font=("Arial", S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=S(20), pady=(S(15), S(5)))

        # ── Player info display card ──
        player_card = ctk.CTkFrame(card4, fg_color="#1c1c1f", corner_radius=10, border_width=1, border_color="#2a2a2f")
        player_card.pack(fill="x", padx=S(20), pady=(0, S(8)))

        self._player_name_lbl = ctk.CTkLabel(
            player_card, text="—", font=("Arial", S(15), "bold"),
            text_color="#ffffff", anchor="w"
        )
        self._player_name_lbl.pack(anchor="w", padx=S(14), pady=(S(10), 0))

        self._player_tag_display = ctk.CTkLabel(
            player_card, text="Enter a tag below", font=("Arial", S(12)),
            text_color="#8e8e93", anchor="w"
        )
        self._player_tag_display.pack(anchor="w", padx=S(14), pady=(0, S(10)))

        # ── Tag input row ──
        tag_row = ctk.CTkFrame(card4, fg_color="transparent")
        tag_row.pack(fill="x", padx=S(20), pady=(0, S(8)))
        tag_row.grid_columnconfigure(0, weight=1)

        _api_cfg_path = resolve_instance_path("cfg/brawl_stars_api.toml")
        _api_cfg = load_toml_as_dict(_api_cfg_path)
        _saved_tag = _api_cfg.get("player_tag", "#YOURTAG")

        self._tag_var = __import__('tkinter').StringVar(value=_saved_tag)
        tag_entry = ctk.CTkEntry(
            tag_row, textvariable=self._tag_var,
            placeholder_text="#YOURTAG",
            font=("Arial", S(13)), height=S(38), corner_radius=8
        )
        tag_entry.grid(row=0, column=0, sticky="ew", padx=(0, S(6)))

        _lookup_btn = ctk.CTkButton(
            tag_row, text="Lookup", width=S(90), height=S(38),
            font=("Arial", S(13), "bold"), corner_radius=8,
            fg_color="#2a2a2f", hover_color="#ff204e",
            command=lambda: _do_lookup()
        )
        _lookup_btn.grid(row=0, column=1, padx=(0, S(5)))

        def _open_profile():
            import webbrowser
            tag = self._tag_var.get().strip().upper()
            if not tag or tag == "#YOURTAG":
                _status_lbl.configure(text="Введите тег перед открытием профиля.", text_color="#ff204e")
                return
            if not tag.startswith("#"):
                tag = "#" + tag
            url = "https://brawlify.com/profile/" + tag.replace("#", "")
            webbrowser.open(url)

        _profile_btn = ctk.CTkButton(
            tag_row, text="👤", width=S(38), height=S(38),
            font=("Arial", S(16)), corner_radius=8,
            fg_color="#1c2a3a", hover_color="#1a6aaa",
            command=_open_profile
        )
        _profile_btn.grid(row=0, column=2)

        _status_lbl = ctk.CTkLabel(card4, text="", font=("Arial", S(11)), text_color="#8e8e93")
        _status_lbl.pack(anchor="w", padx=S(20))

        def _do_lookup():
            import threading
            tag_raw = self._tag_var.get().strip().upper()
            if not tag_raw or tag_raw == "#YOURTAG":
                _status_lbl.configure(text="Please enter a valid player tag.", text_color="#ff204e")
                return
            if not tag_raw.startswith("#"):
                tag_raw = "#" + tag_raw
                self._tag_var.set(tag_raw)

            _lookup_btn.configure(state="disabled", text="...")
            _status_lbl.configure(text="Looking up...", text_color="#8e8e93")

            def _fetch():
                try:
                    from common.utils import fetch_brawl_stars_player, load_toml_as_dict, save_dict_as_toml, resolve_instance_path
                    cfg_path = resolve_instance_path("cfg/brawl_stars_api.toml")
                    api_cfg = load_toml_as_dict(cfg_path)
                    token = api_cfg.get("api_token", "")
                    data = fetch_brawl_stars_player(token, tag_raw, timeout=10)
                    name = data.get("name", "Unknown")
                    tag_ret = data.get("tag", tag_raw)
                    # Save tag to instance config
                    api_cfg["player_tag"] = tag_ret
                    save_dict_as_toml(api_cfg, cfg_path)
                    card4.after(0, lambda: _apply_result(name, tag_ret, None))
                except Exception as exc:
                    card4.after(0, lambda e=exc: _apply_result(None, None, str(e)))

            def _apply_result(name, tag, err):
                _lookup_btn.configure(state="normal", text="Lookup")
                if err:
                    _status_lbl.configure(text=f"Error: {err[:60]}", text_color="#ff204e")
                else:
                    self._player_name_lbl.configure(text=name)
                    self._player_tag_display.configure(text=tag, text_color="#8e8e93")
                    _status_lbl.configure(text="Account loaded ✓", text_color="#30d158")

            threading.Thread(target=_fetch, daemon=True).start()

        # Auto-load if tag already saved
        def _auto_load():
            tag = self._tag_var.get().strip().upper()
            if tag and tag != "#YOURTAG":
                _do_lookup()
        card4.after(800, _auto_load)

        # ── Start button ──
        btn_start = ctk.CTkButton(
            card4, text="START CONFIGURATION", command=self._on_start,
            font=("Arial", S(17), "bold"), corner_radius=15, height=S(55),
            fg_color="#ff204e", hover_color="#1a1a1c"
        )
        btn_start.pack(fill="x", padx=S(20), pady=(S(6), S(15)))

        self._refresh_gamemode_buttons = refresh_gm_buttons
    def _add_version_label(self, parent_frame):
        lbl = ctk.CTkLabel(parent_frame, text=f"v{self.version_str}", font=("Arial", S(12)), text_color="#8e8e93")
        lbl.pack(side="bottom", anchor="se", padx=S(10), pady=S(10))

    def _init_additional_tab(self):
        frame = self.tab_additional
        container = ctk.CTkScrollableFrame(frame, width=S(900), height=S(620), fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        container.pack(expand=True, fill="both", padx=S(20), pady=S(20))

        # Extra space to avoid tooltip clipping
        container.grid_rowconfigure(0, minsize=S(10))

        row_idx = 0
        entry_vars = {}

        # -----------------------------------------------------------------------------------------
        # Helper to create labeled entries in either bot_config or general_config
        # -----------------------------------------------------------------------------------------
        def create_labeled_entry(label_text,
                                 config_key,
                                 convert_func,
                                 use_general_config=False,
                                 tooltip_text=None):
            nonlocal row_idx
            lbl = ctk.CTkLabel(container, text=label_text, font=("Arial", S(18)))
            lbl.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))

            # Decide which dictionary to read/write
            if use_general_config:
                current_config = self.general_config
                current_path = self.general_config_path
            else:
                current_config = self.bot_config
                current_path = self.bot_config_path
            var_str = tk.StringVar(value=str(current_config[config_key]))
            entry_vars[(use_general_config, config_key)] = var_str

            def on_save(*_):
                val_str = var_str.get().strip()
                if val_str == "":
                    var_str.set(str(current_config[config_key]))
                    return
                try:
                    val = convert_func(val_str)
                    current_config[config_key] = val
                    save_dict_as_toml(current_config, current_path)
                except ValueError:
                    var_str.set(str(current_config[config_key]))

            entry = ctk.CTkEntry(
                container, textvariable=var_str, width=S(120), font=("Arial", S(16))
            )
            entry.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
            entry.bind("<FocusOut>", on_save)
            entry.bind("<Return>", on_save)

            if tooltip_text:
                self.attach_tooltip(entry, tooltip_text)

            row_idx += 1


        # 6) Minimum Movement Delay (bot_config)
        create_labeled_entry(
            label_text="Minimum Movement Delay:",
            config_key="minimum_movement_delay",
            convert_func=float,
            use_general_config=False,
            tooltip_text="How long (in seconds) the bot must maintain a movement before changing it."
        )

        # 9) Wall Detection Confidence (bot_config)
        create_labeled_entry(
            label_text="Wall Detection Confidence:",
            config_key="wall_detection_confidence",
            convert_func=float,
            use_general_config=False,
            tooltip_text="On a scale between 0 and 1, how sure must the bot be to detect a wall  (lower means it can detect more things but increases false detections and mistakes)."
        )

        # 9) Wall Detection Confidence (bot_config)
        create_labeled_entry(
            label_text="Player/Enemy Detection Confidence:",
            config_key="entity_detection_confidence",
            convert_func=float,
            use_general_config=False,
            tooltip_text="On a scale between 0 and 1, how sure must the bot be to detect the player/enemies/allies. (lower means it can detect more things but increases false detections and mistakes)."
        )

        # 7) Unstuck Movement Delay (bot_config)
        create_labeled_entry(
            label_text="Unstuck Movement Delay:",
            config_key="unstuck_movement_delay",
            convert_func=float,
            use_general_config=False,
            tooltip_text="How long (in seconds) can the bot maintain a movement before trying to unstuck itself."
        )

        # 8) Unstucking Duration (bot_config)
        create_labeled_entry(
            label_text="Unstucking Duration:",
            config_key="unstuck_movement_hold_time",
            convert_func=float,
            use_general_config=False,
            tooltip_text="For how long (in seconds) will the bot try to go in a different position to unstuck itself before going back to normal."
        )

        # 4) CPU/GPU (store in general_config)
        lbl_gpu = ctk.CTkLabel(container, text="Inference device:", font=("Arial", S(18)))
        lbl_gpu.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))

        gpu_values = ["auto", "directml", "cuda", "openvino", "cpu"]
        gpu_var = tk.StringVar(value=self.general_config["cpu_or_gpu"])

        def on_gpu_change(choice):
            self.general_config["cpu_or_gpu"] = choice
            save_dict_as_toml(self.general_config, self.general_config_path)

        gpu_menu = ctk.CTkOptionMenu(
            container,
            values=gpu_values,
            command=on_gpu_change,
            variable=gpu_var,
            font=("Arial", S(16)),
            fg_color="#141416",
            button_color="#ff204e",
            button_hover_color="#d41940",
            width=S(100),
            height=S(35)
        )
        gpu_menu.grid(row=row_idx, column=1, padx=S(20), pady=S(10), sticky="w")
        row_idx += 1

        create_labeled_entry(
            label_text="DirectML GPU ID:",
            config_key="directml_device_id",
            convert_func=str,
            use_general_config=True,
            tooltip_text="DirectML adapter index. Keep auto unless DirectML uses the wrong GPU; try 0 or 1 on laptops with two GPUs."
        )

        lbl_long_press = ctk.CTkLabel(container, text="Longpress star_drop:", font=("Arial", S(18)))
        lbl_long_press.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        long_press_var = tk.BooleanVar(
            value=(str(self.general_config["long_press_star_drop"]).lower() in ["yes", "true"])
        )

        def toggle_long_press_detection():
            self.general_config["long_press_star_drop"] = "yes" if long_press_var.get() else "no"
            save_dict_as_toml(self.general_config, self.general_config_path)

        long_press_cb = ctk.CTkCheckBox(
            container,
            text="",
            variable=long_press_var,
            command=toggle_long_press_detection,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            width=S(30),
            height=S(30)
        )
        long_press_cb.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        row_idx += 1

        lbl_play_again = ctk.CTkLabel(container, text="Play Again On Win:", font=("Arial", S(18)))
        lbl_play_again.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        play_again_var = tk.BooleanVar(
            value=(str(self.bot_config["play_again_on_win"]).lower() in ["yes", "true"])
        )

        def toggle_play_again():
            self.bot_config["play_again_on_win"] = "yes" if play_again_var.get() else "no"
            save_dict_as_toml(self.bot_config, self.bot_config_path)

        play_again_cb = ctk.CTkCheckBox(
            container,
            text="",
            variable=play_again_var,
            command=toggle_play_again,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            width=S(30),
            height=S(30)
        )
        play_again_cb.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        self.attach_tooltip(
            play_again_cb,
            "If enabled, the bot presses 'Play Again' after a win instead of returning to the lobby."
        )
        row_idx += 1

        lbl_term_log = ctk.CTkLabel(container, text="Terminal Logging:", font=("Arial", S(18)))
        lbl_term_log.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        term_log_var = tk.BooleanVar(
            value=(str(self.general_config["terminal_logging"]).lower() in ["yes", "true"])
        )

        def toggle_terminal_logging():
            self.general_config["terminal_logging"] = "yes" if term_log_var.get() else "no"
            save_dict_as_toml(self.general_config, self.general_config_path)

        term_log_cb = ctk.CTkCheckBox(
            container,
            text="",
            variable=term_log_var,
            command=toggle_terminal_logging,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            width=S(30),
            height=S(30)
        )
        term_log_cb.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        self.attach_tooltip(
            term_log_cb,
            "If enabled, terminal output is saved to logs/pyla_<date>.log files. Takes effect on next launch."
        )
        row_idx += 1

        lbl_debug_screen = ctk.CTkLabel(container, text="Debug Screen:", font=("Arial", S(18)))
        lbl_debug_screen.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        debug_screen_var = tk.BooleanVar(
            value=(str(self.general_config["visual_debug"]).lower() in ["yes", "true"])
        )

        def toggle_debug_screen():
            self.general_config["visual_debug"] = "yes" if debug_screen_var.get() else "no"
            save_dict_as_toml(self.general_config, self.general_config_path)

        debug_screen_cb = ctk.CTkCheckBox(
            container,
            text="",
            variable=debug_screen_var,
            command=toggle_debug_screen,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            width=S(30),
            height=S(30)
        )
        debug_screen_cb.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        self.attach_tooltip(
            debug_screen_cb,
            "Shows a live OpenCV debug window with detected player, teammate, enemy, wall, fog, and range overlays. Takes effect on next bot start."
        )
        row_idx += 1

        lbl_capture_vision = ctk.CTkLabel(container, text="Capture Vision Frames:", font=("Arial", S(18)))
        lbl_capture_vision.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        capture_vision_var = tk.BooleanVar(
            value=(str(self.general_config["capture_bad_vision_frames"]).lower() in ["yes", "true"])
        )

        def toggle_capture_vision():
            self.general_config["capture_bad_vision_frames"] = "yes" if capture_vision_var.get() else "no"
            save_dict_as_toml(self.general_config, self.general_config_path)

        capture_vision_cb = ctk.CTkCheckBox(
            container,
            text="",
            variable=capture_vision_var,
            command=toggle_capture_vision,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            width=S(30),
            height=S(30)
        )
        capture_vision_cb.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
        self.attach_tooltip(
            capture_vision_cb,
            "Saves bad vision frames for model training when the player is lost or wall-stuck. Takes effect on next bot start."
        )
        row_idx += 1


        create_labeled_entry(
            label_text="Super Detection Pixel Treshold:",
            config_key="super_pixels_minimum",
            convert_func=float,
            use_general_config=False,
            tooltip_text='Amount of "yellow" pixels the bot must detect to consider the super is ready.'
        )

        create_labeled_entry(
            label_text="Trophies Multiplier:",
            config_key="trophies_multiplier",
            convert_func=int,
            use_general_config=True,
            tooltip_text="Enter the multiplier for trophies gained per match (for example : 2 for brawl arena)."
        )

        create_labeled_entry(
            label_text="OCR Scale:",
            config_key="ocr_scale_down_factor",
            convert_func=float,
            use_general_config=True,
            tooltip_text="Scale used for brawler-name OCR in the select menu. Lower is faster; adjust if it taps the wrong card."
        )

        create_labeled_entry(
            label_text="Current Playstyle:",
            config_key="current_playstyle",
            convert_func=str,
            use_general_config=False,
            tooltip_text="Filename from the playstyles folder used for editable match logic."
        )

        # 10) Gadget Detection Pixel Threshold (bot_config)
        create_labeled_entry(
            label_text="Gadget Detection Pixel Treshold:",
            config_key="gadget_pixels_minimum",
            convert_func=float,
            use_general_config=False,
            tooltip_text='Amount of "green" pixels the bot must detect to consider a gadget is ready.'
        )

        # 11) Hypercharge Detection Pixel Threshold (bot_config)
        create_labeled_entry(
            label_text="Hypercharge Detection Pixel Treshold:",
            config_key="hypercharge_pixels_minimum",
            convert_func=float,
            use_general_config=False,
            tooltip_text='Amount of "purple" pixels the bot must detect to consider a hypercharge is ready.'
        )

        # 1) Max IPS (store in general_config)
        create_labeled_entry(
            label_text="Max IPS (0 = unlimited):",
            config_key="max_ips",
            convert_func=int,
            use_general_config=True,
            tooltip_text="Maximum Images per second the bot processes. Set 0 for no bot-side IPS cap."
        )

        create_labeled_entry(
            label_text="Scrcpy Max FPS:",
            config_key="scrcpy_max_fps",
            convert_func=int,
            use_general_config=True,
            tooltip_text="Maximum emulator video frames per second captured by scrcpy."
        )

        create_labeled_entry(
            label_text="Used Threads:",
            config_key="used_threads",
            convert_func=lambda s: s if s.lower() == "auto" else int(s),
            use_general_config=True,
            tooltip_text="CPU threads used by the detection models. Lower values reduce CPU usage."
        )

        lbl_profile = ctk.CTkLabel(container, text="Performance Profile:", font=("Arial", S(18)))
        lbl_profile.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
        profile_var = tk.StringVar(value="balanced")
        profile_menu = ctk.CTkOptionMenu(
            container,
            values=["balanced", "low-end", "quality"],
            variable=profile_var,
            font=("Arial", S(16)),
            fg_color="#ff204e",
            button_color="#ff204e",
            button_hover_color="#1a1a1c",
            width=S(120),
            height=S(35)
        )
        profile_menu.grid(row=row_idx, column=1, padx=S(20), pady=S(10), sticky="w")
        row_idx += 1

        profile_status = ctk.CTkLabel(container, text="", font=("Arial", S(14)), text_color="#AAAAAA")
        profile_status.grid(row=row_idx, column=0, columnspan=2, sticky="n", padx=S(20), pady=(0, S(4)))
        row_idx += 1

        def refresh_profile_fields(result):
            self.general_config.clear()
            self.general_config.update(result["general_config"])
            self.bot_config.clear()
            self.bot_config.update(result["bot_config"])
            for key in result["changed_general_keys"]:
                var = entry_vars.get((True, key))
                if var is not None:
                    var.set(str(self.general_config[key]))
            for key in result["changed_bot_keys"]:
                var = entry_vars.get((False, key))
                if var is not None:
                    var.set(str(self.bot_config[key]))
            gpu_var.set(str(self.general_config.get("cpu_or_gpu", "auto")))

        def on_apply_performance_profile():
            try:
                result = apply_performance_profile(
                    profile_var.get(),
                    general_config_path=self.general_config_path,
                    bot_config_path=self.bot_config_path,
                )
                refresh_profile_fields(result)
                profile_status.configure(
                    text=f"Applied {result['profile']} profile. Restart the bot to use it.",
                    text_color="#2ECC71"
                )
            except Exception as exc:
                profile_status.configure(text=f"Could not apply profile: {exc}", text_color="#E74C3C")

        apply_profile_btn = ctk.CTkButton(
            container,
            text="Apply Performance Mode",
            command=on_apply_performance_profile,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            font=("Arial", S(16), "bold"),
            corner_radius=S(6),
            width=S(220),
            height=S(40)
        )
        apply_profile_btn.grid(row=row_idx, column=0, columnspan=2, padx=S(20), pady=S(10))
        self.attach_tooltip(
            apply_profile_btn,
            "Applies safe bot-side capture, FPS, GPU, and detection settings. It does not edit emulator files."
        )
        row_idx += 1

        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        self._add_version_label(frame)

    def _init_webhook_tab(self):
        frame = self.tab_webhook
        container = ctk.CTkScrollableFrame(frame, width=S(900), height=S(620), fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        container.pack(expand=True, fill="both", padx=S(20), pady=S(20))

        row_idx = 0

        def create_webhook_entry(label_text, config_key, convert_func=str, width=360, show=None):
            nonlocal row_idx
            lbl = ctk.CTkLabel(container, text=label_text, font=("Arial", S(18)))
            lbl.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
            var_str = tk.StringVar(value=str(self.webhook_config.get(config_key, "")))

            def on_save(*_):
                val_str = var_str.get().strip()
                try:
                    self.webhook_config[config_key] = convert_func(val_str)
                    save_dict_as_toml(self.webhook_config, self.webhook_config_path)
                except ValueError:
                    var_str.set(str(self.webhook_config.get(config_key, "")))

            entry = ctk.CTkEntry(container, textvariable=var_str, width=S(width), font=("Arial", S(16)), show=show)
            entry.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
            entry.bind("<FocusOut>", on_save)
            entry.bind("<Return>", on_save)
            row_idx += 1

        def create_webhook_toggle(label_text, config_key):
            nonlocal row_idx
            lbl = ctk.CTkLabel(container, text=label_text, font=("Arial", S(18)))
            lbl.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
            var_bool = tk.BooleanVar(value=bool(self.webhook_config.get(config_key, False)))

            def on_toggle():
                self.webhook_config[config_key] = bool(var_bool.get())
                save_dict_as_toml(self.webhook_config, self.webhook_config_path)

            checkbox = ctk.CTkCheckBox(
                container,
                text="",
                variable=var_bool,
                command=on_toggle,
                fg_color="#ff204e",
                hover_color="#1a1a1c",
                width=S(30),
                height=S(30),
            )
            checkbox.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
            row_idx += 1

        create_webhook_entry("Webhook URL:", "webhook_url", str, width=440)
        create_webhook_entry("Discord ID:", "discord_id", str, width=220)
        create_webhook_entry("Webhook Name:", "username", str, width=220)
        create_webhook_toggle("Send Match Summary:", "send_match_summary")
        create_webhook_toggle("Include Screenshots:", "include_screenshot")
        create_webhook_toggle("Ping When Stuck:", "ping_when_stuck")
        create_webhook_toggle("Ping On Target:", "ping_when_target_is_reached")
        create_webhook_entry("Ping Every X Matches:", "ping_every_x_match", lambda s: 0 if s == "" else int(s), width=120)
        create_webhook_entry("Ping Every X Minutes:", "ping_every_x_minutes", lambda s: 0 if s == "" else int(s), width=120)
        create_webhook_toggle("Discord Remote Control:", "discord_control_enabled")
        create_webhook_entry("Bot Token:", "discord_bot_token", str, width=440, show="*")
        create_webhook_entry("Allowed User ID:", "discord_control_user_id", str, width=220)
        create_webhook_entry("Allowed Channel ID:", "discord_control_channel_id", str, width=220)
        create_webhook_entry("Guild ID:", "discord_control_guild_id", str, width=220)

        webhook_status = ctk.CTkLabel(container, text="", font=("Arial", S(14)), text_color="#AAAAAA")
        webhook_status.grid(row=row_idx, column=0, columnspan=2, sticky="n", padx=S(20), pady=(S(6), 0))
        row_idx += 1

        def send_test_webhook():
            webhook_status.configure(text="Sending Discord test...", text_color="#AAAAAA")

            def worker():
                try:
                    ok = asyncio.run(async_send_test_notification())
                    message = "Discord test sent." if ok else "Discord test failed. Check URL and Discord permissions."
                    color = "#2ECC71" if ok else "#E74C3C"
                except Exception as exc:
                    message = f"Discord test failed: {exc}"
                    color = "#E74C3C"
                try:
                    self.app.after(0, lambda: webhook_status.configure(text=message, text_color=color))
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        test_btn = ctk.CTkButton(
            container,
            text="Send Discord Test",
            command=send_test_webhook,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            font=("Arial", S(16), "bold"),
            corner_radius=S(6),
            width=S(220),
            height=S(40)
        )
        test_btn.grid(row=row_idx, column=0, columnspan=2, padx=S(20), pady=S(12))
        self.attach_tooltip(test_btn, "Sends a Discord test message using the current Discord settings.")
        row_idx += 1

        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        self._add_version_label(frame)

    def _init_telegram_tab(self):
        frame = self.tab_telegram
        container = ctk.CTkScrollableFrame(frame, width=S(900), height=S(620), fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        container.pack(expand=True, fill="both", padx=S(20), pady=S(20))

        row_idx = 0

        def create_telegram_entry(label_text, config_key, convert_func=str, width=360, show=None):
            nonlocal row_idx
            lbl = ctk.CTkLabel(container, text=label_text, font=("Arial", S(18)))
            lbl.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
            var_str = tk.StringVar(value=str(self.telegram_config.get(config_key, "")))

            def on_save(*_):
                val_str = var_str.get().strip()
                try:
                    self.telegram_config[config_key] = convert_func(val_str)
                    save_dict_as_toml(self.telegram_config, self.telegram_config_path)
                except ValueError:
                    var_str.set(str(self.telegram_config.get(config_key, "")))

            entry = ctk.CTkEntry(container, textvariable=var_str, width=S(width), font=("Arial", S(16)), show=show)
            entry.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
            entry.bind("<FocusOut>", on_save)
            entry.bind("<Return>", on_save)
            row_idx += 1

        def create_telegram_toggle(label_text, config_key):
            nonlocal row_idx
            lbl = ctk.CTkLabel(container, text=label_text, font=("Arial", S(18)))
            lbl.grid(row=row_idx, column=0, sticky="e", padx=S(20), pady=S(10))
            var_bool = tk.BooleanVar(value=bool(self.telegram_config.get(config_key, False)))

            def on_toggle():
                self.telegram_config[config_key] = bool(var_bool.get())
                save_dict_as_toml(self.telegram_config, self.telegram_config_path)

            checkbox = ctk.CTkCheckBox(
                container,
                text="",
                variable=var_bool,
                command=on_toggle,
                fg_color="#ff204e",
                hover_color="#1a1a1c",
                width=S(30),
                height=S(30),
            )
            checkbox.grid(row=row_idx, column=1, sticky="w", padx=S(20), pady=S(10))
            row_idx += 1

        create_telegram_entry("Bot Token:", "telegram_bot_token", str, width=440, show="*")
        create_telegram_entry("Chat ID:", "telegram_chat_id", str, width=220)
        create_telegram_toggle("Send Match Summary:", "send_match_summary")
        create_telegram_toggle("Include Screenshots:", "include_screenshot")
        create_telegram_toggle("Ping When Stuck:", "ping_when_stuck")
        create_telegram_toggle("Ping On Target:", "ping_when_target_is_reached")
        create_telegram_entry("Ping Every X Matches:", "ping_every_x_match", lambda s: 0 if s == "" else int(s), width=120)
        create_telegram_entry("Ping Every X Minutes:", "ping_every_x_minutes", lambda s: 0 if s == "" else int(s), width=120)
        create_telegram_toggle("Telegram Remote Control:", "telegram_control_enabled")
        create_telegram_entry("Allowed User ID:", "telegram_control_user_id", str, width=220)

        telegram_status = ctk.CTkLabel(container, text="", font=("Arial", S(14)), text_color="#AAAAAA")
        telegram_status.grid(row=row_idx, column=0, columnspan=2, sticky="n", padx=S(20), pady=(S(6), 0))
        row_idx += 1

        def send_test_telegram():
            telegram_status.configure(text="Sending Telegram test...", text_color="#AAAAAA")

            def worker():
                try:
                    ok = asyncio.run(async_send_telegram_test_notification())
                    message = "Telegram test sent." if ok else "Telegram test failed. Check Token and Chat ID."
                    color = "#2ECC71" if ok else "#E74C3C"
                except Exception as exc:
                    message = f"Telegram test failed: {exc}"
                    color = "#E74C3C"
                try:
                    self.app.after(0, lambda: telegram_status.configure(text=message, text_color=color))
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        test_btn = ctk.CTkButton(
            container,
            text="Send Telegram Test",
            command=send_test_telegram,
            fg_color="#ff204e",
            hover_color="#1a1a1c",
            font=("Arial", S(16), "bold"),
            corner_radius=S(6),
            width=S(220),
            height=S(40)
        )
        test_btn.grid(row=row_idx, column=0, columnspan=2, padx=S(20), pady=S(12))
        self.attach_tooltip(test_btn, "Sends a Telegram test message using the current Telegram settings.")
        row_idx += 1

        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        self._add_version_label(frame)

    # ---------------------------------------------------------------------------------------------
    #  Timers Tab
    # ---------------------------------------------------------------------------------------------
    def _init_timers_tab(self):
        frame = self.tab_timers
        container = ctk.CTkFrame(frame, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        container.pack(expand=True, fill="both", padx=S(20), pady=S(20))

        container.grid_rowconfigure(0, minsize=S(70))  # extra top space for tooltips

        row_idx = 1

        def create_timer_setting(param_name, label_text, tooltip_text=None, disabled=False):
            nonlocal row_idx

            lbl = ctk.CTkLabel(container, text=label_text, font=("Arial", S(18)))
            lbl.grid(row=row_idx, column=0, padx=S(20), pady=S(10), sticky="e")

            # Frame to hold slider & entry side by side
            slider_entry_frame = ctk.CTkFrame(container, fg_color="transparent")
            slider_entry_frame.grid(row=row_idx, column=1, padx=S(20), pady=S(10), sticky="w")

            val_var = tk.StringVar(value=str(self.time_tresholds[param_name]))

            # The slider
            sld = ctk.CTkSlider(
                slider_entry_frame,
                from_=0.1,
                to=10,
                number_of_steps=99,
                width=S(200),
                command=lambda v: on_slider_change(v, val_var, param_name),
                state=("disabled" if disabled else "normal")
            )
            sld.pack(side="left", padx=S(5))

            # The text entry
            entry = ctk.CTkEntry(
                slider_entry_frame,
                textvariable=val_var,
                width=S(80),
                font=("Arial", S(16)),
                state=("disabled" if disabled else "normal")
            )
            entry.pack(side="left", padx=S(10))

            def on_save(_):
                if disabled:
                    return
                new_val_str = val_var.get().strip()
                if new_val_str == "":
                    val_var.set(str(self.time_tresholds[param_name]))
                    return
                try:
                    val = float(new_val_str)
                    self.time_tresholds[param_name] = val
                    save_dict_as_toml(self.time_tresholds, self.time_tresholds_path)
                    # Update slider visually
                    if val < 0.1:
                        sld.set(0.1)
                    elif val > 10:
                        sld.set(10)
                    else:
                        sld.set(val)
                except ValueError:
                    val_var.set(str(self.time_tresholds[param_name]))

            entry.bind("<FocusOut>", on_save)
            entry.bind("<Return>", on_save)

            def on_slider_change(value, v_var, p_name):
                if disabled:
                    return
                v = float(value)
                # update entry text
                v_var.set(f"{v:.2f}")
                self.time_tresholds[p_name] = v
                save_dict_as_toml(self.time_tresholds, self.time_tresholds_path)

            # Initialize slider
            try:
                init_val = float(self.time_tresholds[param_name])
                if init_val < 0.1:
                    init_val = 0.1
                elif init_val > 10:
                    init_val = 10
                sld.set(init_val)
            except:
                sld.set(1.0)

            # NOTE: We removed "self.attach_tooltip(lbl, tooltip_text)" so the label has no tooltip.
            if tooltip_text and not disabled:
                self.attach_tooltip(sld, tooltip_text)
                self.attach_tooltip(entry, tooltip_text)

            row_idx += 1

        create_timer_setting(
            param_name="super",
            label_text="Super Delay:",
            tooltip_text="How often (in seconds) the bot checks if super is ready."
        )
        create_timer_setting(
            param_name="hypercharge",
            label_text="Hypercharge Delay:",
            tooltip_text="How often (in seconds) the bot checks if hypercharge is ready."
        )
        create_timer_setting(
            param_name="gadget",
            label_text="Gadget Check Delay:",
            tooltip_text="How often (in seconds) the bot checks if gadget is ready."
        )
        create_timer_setting(
            param_name="wall_detection",
            label_text="Wall Detection:",
            tooltip_text="How often (in seconds) the bot detects the walls around it."
        )
        create_timer_setting(
            param_name="no_detection_proceed",
            label_text="No detections proceed Delay:",
            tooltip_text="How often (in seconds) does the bot press Q to proceed when it doesn't find the player but doesn't know in what state it is."
        )

        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        self._add_version_label(frame)

    # ---------------------------------------------------------------------------------------------
    #  Match History Tab
    # ---------------------------------------------------------------------------------------------
    def _init_history_tab(self):
        frame = self.tab_history

        scroll_frame = ctk.CTkScrollableFrame(
            frame, width=S(900), height=S(600), fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f"
        )
        scroll_frame.pack(fill="both", expand=True, padx=S(20), pady=S(20))

        max_cols = 4
        row_idx = 0
        col_idx = 0

        icon_size = S(100)  # bigger icons
        for brawler, stats in self.match_history.items():
            if brawler == "total":
                continue
            icon_path = f"./api/assets/brawler_icons/{brawler}.png"
            if not os.path.exists(icon_path):
                icon_img = None
            else:
                pil_img = Image.open(icon_path).resize((icon_size, icon_size))
                icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(icon_size, icon_size))

            total_games = stats["victory"] + stats["defeat"]
            if total_games == 0:
                wr = lr = dr = 0
            else:
                wr = round(100 * stats["victory"] / total_games, 1)
                lr = round(100 * stats["defeat"] / total_games, 1)

            cell_frame = ctk.CTkFrame(
                scroll_frame,
                width=S(200),
                height=S(220),
                corner_radius=S(8)
            )
            cell_frame.grid(row=row_idx, column=col_idx, padx=S(15), pady=S(15))

            # Icon
            if icon_img:
                icon_label = ctk.CTkLabel(cell_frame, image=icon_img, text="")
                icon_label.pack(pady=S(5))

            # Brawler name & total games
            text_label = ctk.CTkLabel(
                cell_frame,
                text=f"{brawler}\n{total_games} games",
                font=("Arial", S(16), "bold")
            )
            text_label.pack()

            stats_frame = ctk.CTkFrame(cell_frame, fg_color="transparent")
            stats_frame.pack(pady=S(5))

            # Win in green
            color_win = "#2ecc71"

            # Loss in red
            color_loss = "#d41940"

            lbl_win = ctk.CTkLabel(
                stats_frame,
                text=f"{wr}%",
                font=("Arial", S(14), "bold"),
                text_color=color_win
            )
            lbl_win.pack(side="left", padx=S(5))

            lbl_loss = ctk.CTkLabel(
                stats_frame,
                text=f"{lr}%",
                font=("Arial", S(14), "bold"),
                text_color=color_loss
            )
            lbl_loss.pack(side="left", padx=S(5))

            col_idx += 1
            if col_idx >= max_cols:
                col_idx = 0
                row_idx += 1

        self._add_version_label(frame)

    # ---------------------------------------------------------------------------------------------
    #  On Start => close window + callback
    # ---------------------------------------------------------------------------------------------
    def _on_start(self):
        try:
            for after_id in self.app.tk.call("after", "info"):
                try:
                    self.app.after_cancel(after_id)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.app.withdraw()
            self.app.update_idletasks()
        except Exception:
            pass
        try:
            self.app.quit()
        except Exception:
            pass
        try:
            self.app.destroy()
        except Exception:
            pass

        if callable(self.on_close_callback):
            self.on_close_callback()

    # ---------------------------------------------------------------------------------------------
    #  Debug Tab — live console with Copy button
    # ---------------------------------------------------------------------------------------------
    def _init_debug_tab(self):
        import sys
        frame = self.tab_debug

        # ── Header row ─────────────────────────────────────────────────────
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=S(20), pady=(S(16), S(6)))

        ctk.CTkLabel(
            header, text="Console Output",
            font=("Arial", S(20), "bold"), text_color="#ffffff"
        ).pack(side="left")

        # Clear button
        def _clear_log():
            self._debug_box.configure(state="normal")
            self._debug_box.delete("1.0", "end")
            self._debug_box.configure(state="disabled")

        ctk.CTkButton(
            header, text="Clear", width=S(80), height=S(32),
            font=("Arial", S(13), "bold"),
            fg_color="#2a2a2f", hover_color="#ff204e",
            command=_clear_log
        ).pack(side="right", padx=(S(6), 0))

        # Copy button
        def _copy_log():
            content = self._debug_box.get("1.0", "end").strip()
            self.app.clipboard_clear()
            self.app.clipboard_append(content)
            _copy_btn.configure(text="Copied ✓", fg_color="#30d158")
            self.app.after(2000, lambda: _copy_btn.configure(text="Copy All", fg_color="#2a2a2f"))

        _copy_btn = ctk.CTkButton(
            header, text="Copy All", width=S(90), height=S(32),
            font=("Arial", S(13), "bold"),
            fg_color="#2a2a2f", hover_color="#ff204e",
            command=_copy_log
        )
        _copy_btn.pack(side="right", padx=(S(6), 0))

        # Max lines indicator
        self._debug_max_lines = 800
        ctk.CTkLabel(
            header, text=f"(max {self._debug_max_lines} lines)",
            font=("Arial", S(11)), text_color="#8e8e93"
        ).pack(side="right", padx=S(10))

        # ── Textbox ────────────────────────────────────────────────────────
        self._debug_box = ctk.CTkTextbox(
            frame,
            font=("Courier", S(12)),
            fg_color="#0d0d0f",
            text_color="#e0e0e0",
            corner_radius=12,
            border_width=1,
            border_color="#2a2a2f",
            wrap="none",
            state="disabled",
        )
        self._debug_box.pack(fill="both", expand=True, padx=S(20), pady=(0, S(20)))

        # ── stdout/stderr redirect ──────────────────────────────────────────
        _original_stdout = sys.stdout
        _original_stderr = sys.stderr

        class _Redirector:
            def __init__(self_r, widget, original):
                self_r.widget = widget
                self_r.original = original
                self_r._buf = ""

            def write(self_r, text):
                # Always pass through to real terminal
                try:
                    self_r.original.write(text)
                except Exception:
                    pass
                # Append to GUI box
                self_r._buf += text
                if "\n" in self_r._buf:
                    lines = self_r._buf.split("\n")
                    self_r._buf = lines[-1]
                    to_add = "\n".join(lines[:-1]) + "\n"
                    try:
                        self_r.widget.after(0, lambda t=to_add: self_r._append(t))
                    except Exception:
                        pass

            def _append(self_r, text):
                try:
                    w = self_r.widget
                    w.configure(state="normal")
                    w.insert("end", text)
                    # Trim to max lines
                    lines = int(w.index("end-1c").split(".")[0])
                    if lines > self._debug_max_lines:
                        w.delete("1.0", f"{lines - self._debug_max_lines}.0")
                    w.see("end")
                    w.configure(state="disabled")
                except Exception:
                    pass

            def flush(self_r):
                try:
                    self_r.original.flush()
                except Exception:
                    pass

            def fileno(self_r):
                return self_r.original.fileno()

        sys.stdout = _Redirector(self._debug_box, _original_stdout)
        sys.stderr = _Redirector(self._debug_box, _original_stderr)

        # Restore on window close
        def _restore(event=None):
            sys.stdout = _original_stdout
            sys.stderr = _original_stderr
        self.app.bind("<Destroy>", _restore, add="+")
