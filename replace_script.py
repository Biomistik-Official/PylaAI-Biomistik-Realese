with open("gui/hub.py", "r", encoding="utf-8") as f:
    content = f.read()

start_idx = content.find("    def _init_overview_tab(self):")
end_idx = content.find("    def _init_additional_tab(self):")

new_code = """    def _init_overview_tab(self):
        frame = self.tab_overview

        # Main Grid Container
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=self.S(20), pady=self.S(20))
        
        container.grid_columnconfigure(0, weight=1, uniform="col")
        container.grid_columnconfigure(1, weight=1, uniform="col")
        container.grid_rowconfigure(0, weight=0)
        container.grid_rowconfigure(1, weight=1, uniform="row")
        container.grid_rowconfigure(2, weight=1, uniform="row")

        # -----------------------------------------------------------------
        # Banner
        # -----------------------------------------------------------------
        banner = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, self.S(15)))
        ctk.CTkLabel(banner, text="Community and Support", font=("Arial", self.S(14), "bold"), text_color="#8e8e93").pack(anchor="w", padx=self.S(15), pady=(self.S(10), 0))
        ctk.CTkLabel(banner, text="Join the Discord -> discord.gg/PylaAi", font=("Arial", self.S(14)), text_color="#ffffff").pack(anchor="w", padx=self.S(15), pady=(self.S(5), self.S(10)))

        # -----------------------------------------------------------------
        # Card 1: Configuration
        # -----------------------------------------------------------------
        card1 = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        card1.grid(row=1, column=0, sticky="nsew", padx=(0, self.S(7)), pady=(0, self.S(7)))
        ctk.CTkLabel(card1, text="Step 1: Configuration", font=("Arial", self.S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=self.S(20), pady=(self.S(20), self.S(10)))
        
        self.gamemode_type_var = __import__('tkinter').IntVar(value=self.bot_config.get("gamemode_type", 3))
        orient_frame = ctk.CTkFrame(card1, fg_color="transparent")
        orient_frame.pack(fill="both", expand=True, padx=self.S(20))
        
        def set_gamemode_type(t):
            self.gamemode_type_var.set(t)
            self.bot_config["gamemode_type"] = t
            __import__('utils').save_dict_as_toml(self.bot_config, self.bot_config_path)
            refresh_orientation_buttons()
            self._refresh_gm_frames()
            
        self.btn_type_vertical = ctk.CTkButton(orient_frame, text="Vertical", command=lambda: set_gamemode_type(3), font=("Arial", self.S(14), "bold"), corner_radius=15, height=self.S(45))
        self.btn_type_vertical.pack(fill="x", pady=self.S(5))
        
        self.btn_type_horizontal = ctk.CTkButton(orient_frame, text="Horizontal", command=lambda: set_gamemode_type(5), font=("Arial", self.S(14), "bold"), corner_radius=15, height=self.S(45))
        self.btn_type_horizontal.pack(fill="x", pady=self.S(5))

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
        card2.grid(row=1, column=1, sticky="nsew", padx=(self.S(7), 0), pady=(0, self.S(7)))
        ctk.CTkLabel(card2, text="Step 2: Gamemode", font=("Arial", self.S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=self.S(20), pady=(self.S(20), self.S(10)))
        
        self.gm_buttons_frame = ctk.CTkFrame(card2, fg_color="transparent")
        self.gm_buttons_frame.pack(fill="both", expand=True, padx=self.S(20))
        
        self.gm3_frame = ctk.CTkFrame(self.gm_buttons_frame, fg_color="transparent")
        self.gm5_frame = ctk.CTkFrame(self.gm_buttons_frame, fg_color="transparent")
        
        self.gamemode_var = __import__('tkinter').StringVar(value=self.bot_config.get("gamemode", "showdown"))
        
        def create_gm_btn(parent, gm_value, text_display, orientation=3):
            def on_click():
                self.bot_config["gamemode_type"] = orientation
                self.bot_config["gamemode"] = gm_value
                __import__('utils').save_dict_as_toml(self.bot_config, self.bot_config_path)
                self.gamemode_var.set(gm_value)
                refresh_gm_buttons()
            return ctk.CTkButton(parent, text=text_display, command=on_click, font=("Arial", self.S(14), "bold"), corner_radius=15, height=self.S(40))
            
        self.rb_brawlball_3 = create_gm_btn(self.gm3_frame, "brawlball", "Brawlball", 3)
        self.rb_showdown_3 = create_gm_btn(self.gm3_frame, "showdown", "Showdown Trio", 3)
        self.rb_other_3 = create_gm_btn(self.gm3_frame, "other", "Other", 3)
        self.rb_brawlball_3.pack(fill="x", pady=self.S(2))
        self.rb_showdown_3.pack(fill="x", pady=self.S(2))
        self.rb_other_3.pack(fill="x", pady=self.S(2))
        
        self.rb_basketbrawl_5 = create_gm_btn(self.gm5_frame, "basketbrawl", "Basket Brawl", 5)
        self.rb_bb5v5_5 = create_gm_btn(self.gm5_frame, "brawlball_5v5", "Brawlball 5v5", 5)
        self.rb_basketbrawl_5.pack(fill="x", pady=self.S(5))
        self.rb_bb5v5_5.pack(fill="x", pady=self.S(5))
        
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
        card3.grid(row=2, column=0, sticky="nsew", padx=(0, self.S(7)), pady=(self.S(7), 0))
        ctk.CTkLabel(card3, text="Step 3: Emulator", font=("Arial", self.S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=self.S(20), pady=(self.S(20), self.S(10)))
        
        emu_frame = ctk.CTkFrame(card3, fg_color="transparent")
        emu_frame.pack(fill="both", expand=True, padx=self.S(20))
        
        supported_emulators = {"LDPlayer": 5555, "MuMu": 16384}
        current_emu = self.general_config.get("current_emulator", "LDPlayer")
        self.emu_var = __import__('tkinter').StringVar(value=current_emu)
        
        def set_emu(choice):
            self.emu_var.set(choice)
            self.general_config["current_emulator"] = choice
            self.general_config["emulator_port"] = 5555 if choice == "LDPlayer" else 16384
            __import__('utils').save_dict_as_toml(self.general_config, self.general_config_path)
            refresh_emu()
            
        self.btn_ldplayer = ctk.CTkButton(emu_frame, text="LDPlayer", command=lambda: set_emu("LDPlayer"), font=("Arial", self.S(14), "bold"), corner_radius=15, height=self.S(50))
        self.btn_ldplayer.pack(side="left", fill="x", expand=True, padx=(0, self.S(5)))
        self.btn_mumu = ctk.CTkButton(emu_frame, text="MuMu", command=lambda: set_emu("MuMu"), font=("Arial", self.S(14), "bold"), corner_radius=15, height=self.S(50))
        self.btn_mumu.pack(side="right", fill="x", expand=True, padx=(self.S(5), 0))
        
        def refresh_emu():
            e = self.emu_var.get()
            self.btn_ldplayer.configure(fg_color="#ff204e" if e=="LDPlayer" else "#1a1a1c", hover_color="#1a1a1c" if e=="LDPlayer" else "#ff204e")
            self.btn_mumu.configure(fg_color="#ff204e" if e=="MuMu" else "#1a1a1c", hover_color="#1a1a1c" if e=="MuMu" else "#ff204e")
        refresh_emu()

        # -----------------------------------------------------------------
        # Card 4: Action & Start
        # -----------------------------------------------------------------
        card4 = ctk.CTkFrame(container, fg_color="#141416", corner_radius=15, border_width=1, border_color="#2a2a2f")
        card4.grid(row=2, column=1, sticky="nsew", padx=(self.S(7), 0), pady=(self.S(7), 0))
        
        ctk.CTkLabel(card4, text="Action and Support", font=("Arial", self.S(18), "bold"), text_color="#ffffff").pack(anchor="w", padx=self.S(20), pady=(self.S(20), self.S(10)))

        btn_start = ctk.CTkButton(card4, text="START CONFIGURATION", command=self._on_start, font=("Arial", self.S(20), "bold"), corner_radius=15, height=self.S(70), fg_color="#ff204e", hover_color="#1a1a1c")
        btn_start.pack(expand=True, fill="both", padx=self.S(20), pady=(self.S(10), self.S(20)))

        self._refresh_gamemode_buttons = refresh_gm_buttons

"""

new_content = content[:start_idx] + new_code + content[end_idx:]
with open("gui/hub.py", "w", encoding="utf-8") as f:
    f.write(new_content)
print("SUCCESS")
