import os
import subprocess
import sys
import time
import ctypes
from pathlib import Path


RUNNING = "running"
PAUSED = "paused"


def write_state(path, state):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(state, encoding="utf-8")


def read_state(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip().lower()
    except OSError:
        return RUNNING


class RuntimeControlWindow:
    def __init__(self):
        state_dir = Path("logs")
        self.state_path = state_dir / f"runtime_control_{os.getpid()}.state"
        self.process = None
        write_state(self.state_path, RUNNING)

    def start(self):
        # When launched from the Hub, skip the separate popup window.
        # The Hub manages the state file directly.
        if os.environ.get("PYLAAI_HUB_MODE") == "1":
            return

        if self.process and self.process.poll() is None:
            return
        script_path = Path(__file__).resolve()
        self.process = subprocess.Popen(
            [sys.executable, str(script_path), "--window", str(self.state_path)],
            cwd=str(script_path.parent),
            close_fds=True,
        )
        time.sleep(0.2)
        if self.process.poll() is not None:
            print("Runtime pause control window failed to start.")

    def is_paused(self):
        return read_state(self.state_path) == PAUSED

    def close(self):
        write_state(self.state_path, RUNNING)
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()


def process_is_alive(pid):
    if not pid or pid == os.getpid():
        return True
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    process_query_limited_information = 0x1000
    still_active = 259
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def run_window(state_path):
    import tkinter as tk
    import customtkinter as ctk

    ctk.set_appearance_mode("dark")

    root = ctk.CTk()
    root.title("Pyla-Biomistik Control")
    root.geometry("280x170")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    owner_pid = None
    try:
        owner_pid = int(Path(state_path).stem.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        owner_pid = None

    status_var = tk.StringVar(value="Running")
    button_var = tk.StringVar(value="Pause Bot")

    card = ctk.CTkFrame(root, fg_color="#242424", corner_radius=8)
    card.pack(fill="both", expand=True, padx=12, pady=12)

    title = ctk.CTkLabel(
        card,
        text="Pyla-Biomistik Bot Control",
        text_color="#FFFFFF",
        font=("Arial", 17, "bold"),
    )
    title.pack(pady=(14, 2))

    status_label = ctk.CTkLabel(
        card,
        textvariable=status_var,
        text_color="#2FCE66",
        font=("Arial", 14, "bold"),
    )
    status_label.pack(pady=(0, 12))

    def refresh():
        if owner_pid and not process_is_alive(owner_pid):
            root.destroy()
            return
        paused = read_state(state_path) == PAUSED
        status_var.set("Paused" if paused else "Running")
        button_var.set("Resume Bot" if paused else "Pause Bot")
        status_label.configure(text_color="#FFB23F" if paused else "#2FCE66")
        pause_button.configure(
            fg_color="#2F8F4E" if paused else "#AA2A2A",
            hover_color="#3DAF62" if paused else "#BB3A3A",
        )

    def root_exists():
        try:
            return bool(root.winfo_exists())
        except tk.TclError:
            return False

    def refresh_loop():
        if not root_exists():
            return
        refresh()
        if root_exists():
            root.after(750, refresh_loop)

    def toggle_pause():
        write_state(state_path, RUNNING if read_state(state_path) == PAUSED else PAUSED)
        refresh()

    def on_close():
        write_state(state_path, RUNNING)
        root.destroy()

    pause_button = ctk.CTkButton(
        card,
        textvariable=button_var,
        command=toggle_pause,
        width=170,
        height=40,
        corner_radius=8,
        fg_color="#AA2A2A",
        hover_color="#BB3A3A",
        text_color="#FFFFFF",
        font=("Arial", 15, "bold"),
    )
    pause_button.pack(pady=(0, 8))

    hint = ctk.CTkLabel(
        card,
        text="Movement stops instantly while paused.",
        text_color="#BEBEBE",
        font=("Arial", 11),
    )
    hint.pack()

    root.protocol("WM_DELETE_WINDOW", on_close)
    refresh_loop()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--window":
        run_window(sys.argv[2])
