from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any
import aiohttp
import cv2
import io
import json

from remote.runtime_control import read_state, write_state, RUNNING, PAUSED
from remote.telegram_notifier import load_telegram_settings
from common.utils import _config_bool

def set_runtime_state(state_path: str | Path, paused: bool) -> str:
    state = PAUSED if paused else RUNNING
    write_state(state_path, state)
    return state

class TelegramControlServer:
    def __init__(self, state_path: str | Path, settings_loader=load_telegram_settings):
        self.state_path = Path(state_path)
        self.settings_loader = settings_loader
        self.get_screenshot_cb = None
        self.get_stats_cb = None
        self.get_queue_cb = None
        self.skip_queue_cb = None
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self.offset = 0

    def start(self) -> bool:
        settings = self.settings_loader()
        if not _config_bool(settings.get("telegram_control_enabled"), False):
            return False

        token = str(settings.get("telegram_bot_token") or "").strip()
        if not token:
            print("Telegram control skipped: enable it only after filling telegram_bot_token.")
            return False

        if self.thread and self.thread.is_alive():
            return True

        self._running = True
        self.thread = threading.Thread(target=self._thread_main, args=(token,), daemon=True)
        self.thread.start()
        return True

    def close(self) -> None:
        self._running = False

    def _thread_main(self, token: str) -> None:
        try:
            asyncio.run(self._run(token))
        except Exception as exc:
            print(f"Telegram control stopped: {exc}")

    async def _run(self, token: str) -> None:
        self.loop = asyncio.get_running_loop()
        url = f"https://api.telegram.org/bot{token}/"
        
        print("Telegram control commands active: /start /stop /status /stats /screenshot /queue /skip")
        
        async with aiohttp.ClientSession() as session:
            # Set bot menu commands
            commands = [
                {"command": "start", "description": "Resume Pyla-Biomistik"},
                {"command": "stop", "description": "Pause Pyla-Biomistik"},
                {"command": "status", "description": "Check if bot is running or paused"},
                {"command": "stats", "description": "View current session statistics"},
                {"command": "queue", "description": "Show the current brawler queue"},
                {"command": "skip", "description": "Skip the current brawler in the queue"},
                {"command": "screenshot", "description": "Get a live screenshot"}
            ]
            await session.post(url + "setMyCommands", json={"commands": commands})
            
            while self._running:
                try:
                    params = {"offset": self.offset, "timeout": 20}
                    async with session.get(url + "getUpdates", params=params, timeout=25) as resp:
                        if not resp.ok:
                            await asyncio.sleep(2)
                            continue
                        
                        data = await resp.json()
                        if not data.get("ok"):
                            await asyncio.sleep(2)
                            continue
                            
                        updates = data.get("result", [])
                        for update in updates:
                            self.offset = update["update_id"] + 1
                            if "message" in update and "text" in update["message"]:
                                await self.handle_message(session, url, update["message"])
                                
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    if self._running:
                        await asyncio.sleep(2)

    async def handle_message(self, session, url, message):
        settings = self.settings_loader()
        allowed_user = str(settings.get("telegram_control_user_id")).strip()
        
        chat_id = message["chat"]["id"]
        user_id = str(message["from"]["id"])
        text = message.get("text", "").strip()
        
        # Map keyboard buttons to commands
        button_map = {
            "▶️ Start": "/start",
            "⏸️ Stop": "/stop",
            "ℹ️ Status": "/status",
            "📊 Stats": "/stats",
            "📋 Queue": "/queue",
            "⏭️ Skip": "/skip",
            "📸 Screenshot": "/screenshot"
        }
        
        if text in button_map:
            text = button_map[text]
        
        if not text.startswith("/"):
            return
            
        if allowed_user and user_id != allowed_user:
            await self.send_message(session, url, chat_id, "You are not allowed to control this Pyla-Biomistik bot.")
            return
            
        command = text.split("@")[0].lower()
        
        if command == "/start":
            set_runtime_state(self.state_path, paused=False)
            await self.send_message(session, url, chat_id, "Pyla-Biomistik resumed.")
            
        elif command == "/stop":
            set_runtime_state(self.state_path, paused=True)
            await self.send_message(session, url, chat_id, "Pyla-Biomistik paused.")
            
        elif command == "/status":
            state = read_state(self.state_path)
            await self.send_message(session, url, chat_id, f"Pyla-Biomistik is {'paused' if state == PAUSED else 'running'}.")
            
        elif command == "/stats":
            if not self.get_stats_cb:
                await self.send_message(session, url, chat_id, "Stats are not available yet.")
                return
            stats = self.get_stats_cb()
            if not stats:
                await self.send_message(session, url, chat_id, "Failed to retrieve stats.")
                return
            
            msg = f"📊 <b>Session Statistics</b>\n\n"
            msg += f"🏆 Trophies: {stats.get('trophies', 0)}\n"
            msg += f"🔥 Win Streak: {stats.get('win_streak', 0)}\n"
            msg += f"✅ Total Wins: {stats.get('wins', 0)}"
            await self.send_message(session, url, chat_id, msg)
            
        elif command == "/queue":
            if not self.get_queue_cb:
                await self.send_message(session, url, chat_id, "Queue functionality is not available.")
                return
            queue = self.get_queue_cb()
            if not queue:
                await self.send_message(session, url, chat_id, "The queue is currently empty.")
                return
            
            msg = f"📋 <b>Current Queue</b>\n\n"
            for i, item in enumerate(queue):
                brawler = str(item.get("brawler", "Unknown")).title()
                target = item.get("push_until", "N/A")
                current = item.get("trophies", "N/A")
                if i == 0:
                    msg += f"▶️ <b>{brawler}</b> ({current}/{target} 🏆)\n"
                else:
                    msg += f"⏳ <b>{brawler}</b> (target {target} 🏆)\n"
            await self.send_message(session, url, chat_id, msg)
            
        elif command == "/skip":
            if not self.skip_queue_cb:
                await self.send_message(session, url, chat_id, "Skip functionality is not available.")
                return
            if self.skip_queue_cb():
                await self.send_message(session, url, chat_id, "Skipped the current brawler. Loading the next one...")
            else:
                await self.send_message(session, url, chat_id, "Failed to skip. Queue might be empty.")
            
        elif command == "/screenshot":
            if not self.get_screenshot_cb:
                await self.send_message(session, url, chat_id, "Screenshot functionality is not available.")
                return
                
            img = self.get_screenshot_cb()
            if img is None:
                await self.send_message(session, url, chat_id, "Failed to capture screenshot. The bot might not be running.")
                return
                
            is_success, buffer = cv2.imencode(".png", img)
            if not is_success:
                await self.send_message(session, url, chat_id, "Failed to encode screenshot.")
                return
                
            await self.send_photo(session, url, chat_id, buffer.tobytes(), "Here is the current screen:")
            
        # Optional: command to just show the keyboard if someone hides it
        elif command == "/menu":
            await self.send_message(session, url, chat_id, "Here are your controls:")

    def get_keyboard(self):
        return {
            "keyboard": [
                [{"text": "▶️ Start"}, {"text": "⏸️ Stop"}],
                [{"text": "ℹ️ Status"}, {"text": "📊 Stats"}],
                [{"text": "📋 Queue"}, {"text": "⏭️ Skip"}],
                [{"text": "📸 Screenshot"}]
            ],
            "resize_keyboard": True,
            "persistent": True
        }

    async def send_message(self, session, url, chat_id, text):
        payload = {
            "chat_id": chat_id, 
            "text": text, 
            "parse_mode": "HTML",
            "reply_markup": self.get_keyboard()
        }
        await session.post(url + "sendMessage", json=payload)
        
    async def send_photo(self, session, url, chat_id, raw_bytes, caption):
        data = aiohttp.FormData()
        data.add_field("chat_id", str(chat_id))
        data.add_field("photo", raw_bytes, filename="screenshot.png", content_type="image/png")
        data.add_field("caption", caption)
        data.add_field("reply_markup", json.dumps(self.get_keyboard()))
        await session.post(url + "sendPhoto", data=data)
