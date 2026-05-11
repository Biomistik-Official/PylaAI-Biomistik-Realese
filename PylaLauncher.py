import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import winreg

try:
    import customtkinter as ctk
except ImportError:
    print("Error: customtkinter is not installed. Run: pip install customtkinter")
    os.system("pause")
    sys.exit(1)

import tkinter as tk

# ─── ADB helpers ──────────────────────────────────────────────────────────────

ADB_EXE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "adb.exe")
if not os.path.exists(ADB_EXE):
    ADB_EXE = "adb"


def _get_connected_devices():
    try:
        out = subprocess.check_output(
            [ADB_EXE, "devices"], stderr=subprocess.DEVNULL, timeout=5
        ).decode(errors="replace")
    except Exception:
        return []
    devices = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            try:
                port = int(serial.split(":")[-1])
            except ValueError:
                port = int(serial.replace("emulator-", "")) if serial.startswith("emulator-") else 0
            devices.append((serial, port))
    return devices


def _infer_emulator_name(port):
    if port in {16384, 16416, 16448, 16480, 7555}:
        return "MuMu"
    if port in {62001, 62025, 62049, 62073, 62097, 62121} or (
        port >= 62001 and (port - 62001) % 24 == 0
    ):
        return "NoxPlayer"
    if port in {5565, 5575, 5585, 5595} or (
        port >= 5565 and (port - 5565) % 10 == 0
    ):
        return "BlueStacks"
    return "LDPlayer"


# ─── Instance tracking ────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
LOCK_DIR = os.path.join(BASE_DIR, "logs")


def _write_lock(iid, pid):
    os.makedirs(LOCK_DIR, exist_ok=True)
    with open(os.path.join(LOCK_DIR, f"instance_{iid}.lock"), "w") as f:
        f.write(str(pid))


def _remove_lock(iid):
    try:
        os.remove(os.path.join(LOCK_DIR, f"instance_{iid}.lock"))
    except OSError:
        pass


def _state_path(pid):
    return os.path.join(LOCK_DIR, f"runtime_control_{pid}.state")


def _write_state(pid, state):
    os.makedirs(LOCK_DIR, exist_ok=True)
    with open(_state_path(pid), "w", encoding="utf-8") as f:
        f.write(state)


def _read_state(pid):
    try:
        with open(_state_path(pid), encoding="utf-8") as f:
            return f.read().strip().lower()
    except OSError:
        return "running"


def _remove_state(pid):
    try:
        os.remove(_state_path(pid))
    except OSError:
        pass


def _clean_stale_locks():
    if not os.path.exists(LOCK_DIR):
        return
    import ctypes
    for fname in os.listdir(LOCK_DIR):
        if fname.startswith("instance_") and fname.endswith(".lock"):
            fpath = os.path.join(LOCK_DIR, fname)
            try:
                with open(fpath) as f:
                    pid = int(f.read().strip())
                handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
                if handle == 0:
                    os.remove(fpath)
                else:
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                try:
                    os.remove(fpath)
                except Exception:
                    pass


def _active_instance_ids():
    active = set()
    if not os.path.exists(LOCK_DIR):
        return active
    for fname in os.listdir(LOCK_DIR):
        if fname.startswith("instance_") and fname.endswith(".lock"):
            try:
                iid = int(fname.replace("instance_", "").replace(".lock", ""))
                active.add(iid)
            except ValueError:
                pass
    return active


# ─── Config patcher ───────────────────────────────────────────────────────────

def _patch_config(instance_id, emulator_port, emulator_name):
    cfg_dir = os.path.join(BASE_DIR, "cfg" if instance_id == 1 else f"cfg_{instance_id}")
    cfg_src = os.path.join(BASE_DIR, "cfg")
    if instance_id != 1 and not os.path.exists(cfg_dir):
        try:
            shutil.copytree(cfg_src, cfg_dir)
        except Exception as e:
            print(f"[Hub] Failed to copy cfg: {e}")

    general_cfg = os.path.join(cfg_dir, "general_config.toml")
    if os.path.exists(general_cfg):
        try:
            import toml
            with open(general_cfg, "r", encoding="utf-8-sig") as f:
                cfg = toml.load(f)
            cfg["emulator_port"] = emulator_port
            cfg["current_emulator"] = emulator_name
            with open(general_cfg, "w", encoding="utf-8") as f:
                toml.dump(cfg, f)
        except Exception as e:
            print(f"[Hub] Config patch failed: {e}")


# ─── Instance data class ──────────────────────────────────────────────────────

class InstanceRecord:
    def __init__(self, iid, port, emu_name):
        self.iid = iid
        self.port = port
        self.emu_name = emu_name
        self.process = None
        self.pid = None
        self.status = "stopped"   # running | paused | stopped
        self.log_queue = queue.Queue()

        # UI refs (set by Hub)
        self.status_label = None
        self.log_box = None
        self.btn_start = None
        self.btn_pause = None
        self.btn_stop = None

    def is_alive(self):
        return self.process is not None and self.process.poll() is None


# ─── Hub ──────────────────────────────────────────────────────────────────────

# ─── Python finder (for frozen EXE mode) ─────────────────────────────────────

def _find_python_exe():
    """Return a usable python.exe path (Python 3.9-3.12). Raises RuntimeError if nothing is found."""
    import shutil as _sh

    _MIN_PY = (3, 9)
    _MAX_PY = (3, 12)

    def _version_ok(exe):
        """Returns True if the given python exe is version 3.9-3.12."""
        try:
            import subprocess as _sp
            out = _sp.check_output(
                [exe, "-c", "import sys; print(sys.version_info[:2])"],
                timeout=5, stderr=_sp.DEVNULL
            ).decode().strip()
            ver = tuple(int(x) for x in out.strip("()").split(", "))
            return _MIN_PY <= ver <= _MAX_PY
        except Exception:
            return False

    def _check_and_return(exe):
        """Validate version and return, or raise with a nice message."""
        if _version_ok(exe):
            return exe
        # Found Python but wrong version — show a dialog
        try:
            import subprocess as _sp
            ver_raw = _sp.check_output(
                [exe, "--version"], timeout=5, stderr=_sp.STDOUT
            ).decode().strip()
        except Exception:
            ver_raw = "неизвестная версия"
        msg = (
            f"Обнаружен {ver_raw}\n"
            "Pyla-Biomistik требует Python 3.9 – 3.12\n\n"
            "Скачайте Python 3.11:\n"
            "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe\n\n"
            "При установке отметьте: ✓ Add Python to PATH"
        )
        import ctypes as _ct
        _ct.windll.user32.MessageBoxW(None, msg, "Неподходящая версия Python", 0x10)
        raise RuntimeError(f"Python version mismatch: {ver_raw}. Need 3.9-3.12.")

    # 1. Prefer python on PATH
    found = _sh.which("python") or _sh.which("python3")
    if found:
        return _check_and_return(found)

    # 2. Windows registry — HKLM / HKCU Software\Python\PythonCore
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for root_key in (r"SOFTWARE\Python\PythonCore",
                         r"SOFTWARE\WOW6432Node\Python\PythonCore"):
            try:
                with winreg.OpenKey(hive, root_key) as pk:
                    i = 0
                    while True:
                        try:
                            ver = winreg.EnumKey(pk, i)
                            with winreg.OpenKey(pk, ver + r"\InstallPath") as ip:
                                path = winreg.QueryValue(ip, None)
                                exe = os.path.join(path, "python.exe")
                                if os.path.isfile(exe) and _version_ok(exe):
                                    return exe
                            i += 1
                        except OSError:
                            break
            except OSError:
                continue

    # 3. Common install folders
    candidates = []
    for base in (os.environ.get("LOCALAPPDATA", ""),
                 os.environ.get("APPDATA", ""),
                 r"C:\Python312", r"C:\Python311", r"C:\Python310",
                 r"C:\Python39",  r"C:\Python38"):
        if base:
            candidates.append(os.path.join(base, "Programs", "Python", "python.exe"))
            for sub in ("Python312", "Python311", "Python310", "Python39", "Python38"):
                candidates.append(os.path.join(base, "Programs", "Python", sub, "python.exe"))
    for c in candidates:
        if os.path.isfile(c) and _version_ok(c):
            return c

    raise RuntimeError(
        "Could not find Python 3.9-3.12.\n"
        "Please install Python 3.11:\n"
        "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe\n"
        "Check 'Add Python to PATH' during install."
    )


class MultiInstanceHub:

    POLL_MS = 400          # UI refresh interval
    MAX_LOG_LINES = 500    # per-instance console line limit

    def __init__(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title("Pyla-Biomistik · Multi-Instance Hub")
        self.root.geometry("1280x760")
        self.root.minsize(900, 560)
        self.root.configure(fg_color="#0a0a0b")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # All running/stopped instances
        self.instances: dict[int, InstanceRecord] = {}

        # Cache last ADB scan so we can redraw cards without rescanning
        self._last_devices: list = []
        self._last_assignments: list = []
        self._emu_redraw_ctr: int = 0

        self._build_ui()
        self._refresh_devices()
        self._poll_loop()

    # ── Build UI (unified dashboard — no tabs) ────────────────────────────────

    def _build_ui(self):
        # ── Top header bar ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self.root, height=58, fg_color="#141416",
                              corner_radius=0)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Pyla-Biomistik",
            font=("Arial", 20, "bold"), text_color="#ff204e"
        ).pack(side="left", padx=(20, 6), pady=14)
        ctk.CTkLabel(
            header, text="Multi-Instance Hub",
            font=("Arial", 12), text_color="#555560"
        ).pack(side="left", pady=14)

        # Global controls on the right
        for txt, fg, hv, cmd in [
            ("⏹  Stop All",   "#6b1515", "#aa2020", self._stop_all),
            ("⏸  Pause All",  "#2a2a2f", "#3a3a4f", self._pause_all),
            ("▶  Resume All", "#1a4a2a", "#206030", self._resume_all),
        ]:
            ctk.CTkButton(
                header, text=txt, width=118, height=32,
                font=("Arial", 12, "bold"), corner_radius=8,
                fg_color=fg, hover_color=hv,
                command=cmd
            ).pack(side="right", padx=6, pady=13)

        ctk.CTkLabel(
            header, text="Hub v2.0",
            font=("Arial", 10), text_color="#2a2a2f"
        ).pack(side="right", padx=(0, 4), pady=14)

        # ── Separator ─────────────────────────────────────────────────────────
        ctk.CTkFrame(self.root, height=1, fg_color="#1e1e22",
                     corner_radius=0).pack(fill="x")

        # ── Body: left emulators panel + right instances panel ─────────────────
        body = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True)

        # Left panel — Emulators
        left = ctk.CTkFrame(body, width=300, fg_color="#0d0d0f", corner_radius=0)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._build_emulators_panel(left)

        # Vertical divider
        ctk.CTkFrame(body, width=1, fg_color="#1e1e22",
                     corner_radius=0).pack(side="left", fill="y")

        # Right panel — Instances
        right = ctk.CTkFrame(body, fg_color="#0a0a0b", corner_radius=0)
        right.pack(side="left", fill="both", expand=True)
        self._build_instances_panel(right)

    # ── Emulators panel ───────────────────────────────────────────────────────

    def _build_emulators_panel(self, parent):
        # Section header
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(14, 4))

        ctk.CTkLabel(
            hdr, text="Emulators",
            font=("Arial", 15, "bold"), text_color="#ffffff"
        ).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            hdr, text="↻", width=32, height=28,
            font=("Arial", 14, "bold"), corner_radius=8,
            fg_color="#1e1e22", hover_color="#ff204e",
            command=self._refresh_devices
        )
        self.refresh_btn.pack(side="right")

        # Scrollable list
        self.emu_scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent"
        )
        self.emu_scroll.pack(fill="both", expand=True, padx=10, pady=(4, 4))
        self.emu_scroll.grid_columnconfigure(0, weight=1)

        # Status label at bottom
        self.emu_status = ctk.CTkLabel(
            parent, text="Scanning…",
            font=("Arial", 11), text_color="#444448"
        )
        self.emu_status.pack(side="bottom", pady=6)

    def _refresh_devices(self):
        self.refresh_btn.configure(state="disabled", text="…")
        for w in self.emu_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.emu_scroll, text="Scanning…",
                     font=("Arial", 12), text_color="#8e8e93"
                     ).grid(row=0, column=0, pady=30)

        def _scan():
            _clean_stale_locks()
            devices = _get_connected_devices()

            # Map port → existing running IID (so the same port keeps its ID)
            port_to_iid = {rec.port: iid for iid, rec in self.instances.items()}

            assignments = []
            used_iids = set(port_to_iid.values())
            next_free = 1
            for serial, port in devices:
                if port in port_to_iid:
                    # Already a running instance on this port — keep its IID
                    assignments.append((serial, port, port_to_iid[port]))
                else:
                    # Find smallest unused IID
                    while next_free in used_iids:
                        next_free += 1
                    assignments.append((serial, port, next_free))
                    used_iids.add(next_free)
                    next_free += 1
            self.root.after(0, lambda: self._show_devices(devices, assignments))

        threading.Thread(target=_scan, daemon=True).start()

    def _show_devices(self, devices, assignments):
        for w in self.emu_scroll.winfo_children():
            w.destroy()
        self.refresh_btn.configure(state="normal", text="↻")

        # Cache for auto-redraw
        self._last_devices = devices
        self._last_assignments = assignments
        if not devices:
            ctk.CTkLabel(
                self.emu_scroll,
                text="⚠ No emulators\ndetected.",
                font=("Arial", 12), text_color="#8e8e93", justify="center"
            ).grid(row=0, column=0, pady=40)
            self.emu_status.configure(text="No emulators found.")
            return

        for row_idx, (serial, port, iid) in enumerate(assignments):
            emu_name = _infer_emulator_name(port)
            card = ctk.CTkFrame(
                self.emu_scroll, fg_color="#141416",
                corner_radius=10, border_width=1, border_color="#2a2a2f"
            )
            card.grid(row=row_idx, column=0, sticky="ew", padx=2, pady=5)
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                card, text=f"#{iid}",
                font=("Arial", 18, "bold"), text_color="#ff204e", width=38
            ).grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=10)

            ctk.CTkLabel(
                card, text=f"{emu_name} · {port}",
                font=("Arial", 12, "bold"), text_color="#ffffff", anchor="w"
            ).grid(row=0, column=1, sticky="w", pady=(10, 0))
            ctk.CTkLabel(
                card, text=serial[:20],
                font=("Arial", 10), text_color="#666670", anchor="w"
            ).grid(row=1, column=1, sticky="w", pady=(0, 10))

            already_running = iid in self.instances and self.instances[iid].is_alive()
            if already_running:
                ctk.CTkLabel(
                    card, text="● Running",
                    font=("Arial", 11, "bold"), text_color="#30d158"
                ).grid(row=0, column=2, rowspan=2, padx=10)
            else:
                def _make_cb(i=iid, p=port, n=emu_name):
                    return lambda: self._launch(i, p, n)
                ctk.CTkButton(
                    card, text="▶ Launch", width=82, height=32,
                    font=("Arial", 12, "bold"), corner_radius=8,
                    fg_color="#ff204e", hover_color="#cc1a3f",
                    command=_make_cb()
                ).grid(row=0, column=2, rowspan=2, padx=10)

        self.emu_status.configure(
            text=f"{len(devices)} emulator(s) found")

    # ── Instances panel ───────────────────────────────────────────────────────

    def _build_instances_panel(self, parent):
        # Section header
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            hdr, text="Running Instances",
            font=("Arial", 15, "bold"), text_color="#ffffff"
        ).pack(side="left")

        # Scrollable instance list
        self.inst_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.inst_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.inst_scroll.grid_columnconfigure(0, weight=1)

        self.inst_placeholder = ctk.CTkLabel(
            self.inst_scroll,
            text="No instances running.\nSelect an emulator on the left and press ▶ Launch.",
            font=("Arial", 13), text_color="#555560", justify="center"
        )
        self.inst_placeholder.grid(row=0, column=0, pady=80)

    def _add_instance_card(self, rec: InstanceRecord):
        """Create a card UI for an instance in the instances panel."""
        if self.inst_placeholder.winfo_exists():
            self.inst_placeholder.grid_forget()

        row = len(self.instances) - 1

        outer = ctk.CTkFrame(self.inst_scroll, fg_color="#141416", corner_radius=14,
                             border_width=1, border_color="#2a2a2f")
        outer.grid(row=row, column=0, sticky="ew", padx=4, pady=8)
        outer.grid_columnconfigure(0, weight=1)

        # ── Header row ──
        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text=f"Instance #{rec.iid}",
                     font=("Arial", 16, "bold"), text_color="#ff204e").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text=f"{rec.emu_name}  ·  Port {rec.port}",
                     font=("Arial", 12), text_color="#8e8e93").grid(
            row=0, column=1, sticky="w", padx=12)

        rec.status_label = ctk.CTkLabel(hdr, text="● Running",
                                        font=("Arial", 12, "bold"), text_color="#30d158")
        rec.status_label.grid(row=0, column=2, sticky="e")

        # ── Buttons ──
        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))

        rec.btn_pause = ctk.CTkButton(
            btn_row, text="⏸  Pause", width=100, height=30,
            font=("Arial", 12, "bold"), corner_radius=8,
            fg_color="#2a2a2f", hover_color="#3a3a4f",
            command=lambda r=rec: self._toggle_pause(r)
        )
        rec.btn_pause.pack(side="left", padx=(0, 6))

        rec.btn_stop = ctk.CTkButton(
            btn_row, text="⏹  Stop", width=90, height=30,
            font=("Arial", 12, "bold"), corner_radius=8,
            fg_color="#6b1515", hover_color="#aa2020",
            command=lambda r=rec: self._stop_instance(r)
        )
        rec.btn_stop.pack(side="left")

        # ── Copy log button ──
        def _make_copy_btn(r):
            btn_ref = [None]
            def _do_copy():
                if r.log_box is None:
                    return
                content = r.log_box.get("1.0", "end").strip()
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                btn_ref[0].configure(text="✓ Copied", fg_color="#1a4a2a")
                self.root.after(2000, lambda: btn_ref[0].configure(
                    text="📋 Copy Log", fg_color="#1e2a1e"
                ))
            btn = ctk.CTkButton(
                btn_row, text="📋 Copy Log", width=100, height=30,
                font=("Arial", 12, "bold"), corner_radius=8,
                fg_color="#1e2a1e", hover_color="#206030",
                command=_do_copy
            )
            btn_ref[0] = btn
            return btn
        _make_copy_btn(rec).pack(side="left", padx=(6, 0))

        # ── Log console ──
        rec.log_box = ctk.CTkTextbox(
            outer, height=180, font=("Consolas", 11),
            fg_color="#0d0d0f", text_color="#c8c8cc",
            corner_radius=8, border_width=1, border_color="#1e1e22",
            wrap="word", state="disabled"
        )
        rec.log_box.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))

    # ── Launch ────────────────────────────────────────────────────────────────

    def _launch(self, iid, port, emu_name):
        if iid in self.instances and self.instances[iid].is_alive():
            return  # already running

        _patch_config(iid, port, emu_name)

        main_script = os.path.join(BASE_DIR, "main.py")
        if not os.path.exists(main_script):
            self.emu_status.configure(text="Error: main.py not found!")
            return

        env = os.environ.copy()
        for k in [k for k in env if k.upper() in
                  ("PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY")]:
            env.pop(k, None)
        env["PYLAAI_INSTANCE"] = str(iid)
        env["PYLAAI_HUB_MODE"] = "1"

        if getattr(sys, 'frozen', False):
            try:
                python_exe = _find_python_exe()
            except RuntimeError as e:
                self.emu_status.configure(text=str(e))
                return
        else:
            python_exe = sys.executable

        proc = subprocess.Popen(
            [python_exe, "main.py"],
            cwd=BASE_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        rec = InstanceRecord(iid, port, emu_name)
        rec.process = proc
        rec.pid = proc.pid
        rec.status = "running"
        self.instances[iid] = rec

        _write_state(proc.pid, "running")
        _write_lock(iid, proc.pid)
        self._add_instance_card(rec)
        threading.Thread(target=self._read_output, args=(rec,), daemon=True).start()

    # ── Log reader ────────────────────────────────────────────────────────────

    def _read_output(self, rec: InstanceRecord):
        """Background thread: reads stdout from the instance process."""
        try:
            for line in rec.process.stdout:
                rec.log_queue.put(line.rstrip("\n"))
        except Exception:
            pass
        rec.log_queue.put(None)  # sentinel: process finished

    # ── Poll loop ─────────────────────────────────────────────────────────────

    def _poll_loop(self):
        """Called every POLL_MS ms on main thread to update UI."""
        for rec in list(self.instances.values()):
            self._flush_log(rec)
            self._update_status(rec)
        # Redraw emulator cards every ~2s so Running/Paused/Stopped status updates
        self._emu_redraw_ctr += 1
        if self._emu_redraw_ctr % 5 == 0 and self._last_devices:
            self._show_devices(self._last_devices, self._last_assignments)
        self.root.after(self.POLL_MS, self._poll_loop)

    def _flush_log(self, rec: InstanceRecord):
        if rec.log_box is None:
            return
        lines = []
        try:
            while True:
                item = rec.log_queue.get_nowait()
                lines.append(item)
        except queue.Empty:
            pass

        if not lines:
            return

        rec.log_box.configure(state="normal")
        for item in lines:
            if item is None:
                rec.log_box.insert("end", "\n[Process exited]\n")
            else:
                rec.log_box.insert("end", item + "\n")

        # Trim to MAX_LOG_LINES
        content = rec.log_box.get("1.0", "end-1c").split("\n")
        if len(content) > self.MAX_LOG_LINES:
            excess = len(content) - self.MAX_LOG_LINES
            rec.log_box.delete("1.0", f"{excess + 1}.0")

        rec.log_box.see("end")
        rec.log_box.configure(state="disabled")

    def _update_status(self, rec: InstanceRecord):
        if rec.status_label is None:
            return

        if not rec.is_alive():
            if rec.status != "stopped":
                rec.status = "stopped"
                _remove_lock(rec.iid)
                _remove_state(rec.pid)
            rec.status_label.configure(text="● Stopped", text_color="#ff453a")
            if rec.btn_pause:
                rec.btn_pause.configure(state="disabled")
            if rec.btn_stop:
                rec.btn_stop.configure(state="disabled")
            return

        file_state = _read_state(rec.pid)
        if file_state == "paused":
            rec.status = "paused"
            rec.status_label.configure(text="● Paused", text_color="#ffd60a")
            if rec.btn_pause:
                rec.btn_pause.configure(text="▶  Resume")
        else:
            rec.status = "running"
            rec.status_label.configure(text="● Running", text_color="#30d158")
            if rec.btn_pause:
                rec.btn_pause.configure(text="⏸  Pause")

    # ── Controls ──────────────────────────────────────────────────────────────

    def _toggle_pause(self, rec: InstanceRecord):
        if not rec.is_alive():
            return
        current = _read_state(rec.pid)
        _write_state(rec.pid, "running" if current == "paused" else "paused")

    def _stop_instance(self, rec: InstanceRecord):
        if rec.is_alive():
            _write_state(rec.pid, "running")  # resume before kill so bot cleans up
            time.sleep(0.1)
            rec.process.terminate()
        rec.status = "stopped"
        _remove_lock(rec.iid)

    def _stop_all(self):
        for rec in self.instances.values():
            if rec.is_alive():
                self._stop_instance(rec)

    def _pause_all(self):
        for rec in self.instances.values():
            if rec.is_alive() and rec.status != "paused":
                _write_state(rec.pid, "paused")

    def _resume_all(self):
        for rec in self.instances.values():
            if rec.is_alive() and rec.status == "paused":
                _write_state(rec.pid, "running")

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        for rec in self.instances.values():
            if rec.is_alive():
                try:
                    rec.process.terminate()
                except Exception:
                    pass
        # Завершаем ADB-сервер чтобы adb.exe не висел после закрытия Hub
        try:
            subprocess.run(
                [ADB_EXE, "kill-server"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ─── Single-instance guard ────────────────────────────────────────────────────

def _acquire_single_instance_mutex():
    """Create a named Windows mutex so only one Hub process can run.
    Returns the mutex handle (keep it alive for the process lifetime)."""
    import ctypes
    MUTEX_NAME = "Global\\PylaAiXXZ_MultiInstanceHub_v2"
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last_err = ctypes.windll.kernel32.GetLastError()
    if last_err == 183:  # ERROR_ALREADY_EXISTS
        return None  # another instance is running
    return handle  # we own the mutex


if __name__ == "__main__":
    _mutex = _acquire_single_instance_mutex()
    if _mutex is None:
        # Another Hub is already running — bring it to foreground and exit
        import ctypes as _ct
        _ct.windll.user32.MessageBoxW(
            None,
            "Pyla-Biomistik Hub is already running.\nCheck your taskbar or system tray.",
            "Already running",
            0x40,  # MB_ICONINFORMATION
        )
        sys.exit(0)
    MultiInstanceHub().run()
