from __future__ import annotations

import io
from pathlib import Path
import time
from typing import Any

import aiohttp
import numpy as np
from PIL import Image

from common.utils import _config_bool, load_toml_as_dict

TELEGRAM_CONFIG_PATH = "cfg/telegram_config.toml"

_match_count = 0
_last_minute_ping = 0.0

FIELD_LABELS = {
    "brawler": "🎮 Brawler",
    "result": "🏁 Result",
    "started_trophies": "📍 Started Trophies",
    "trophies": "🏆 Current Trophies",
    "target": "🎯 Target",
    "wins": "✅ Wins",
    "win_streak": "🔥 Win Streak",
    "brawlers_left": "📋 Brawlers Left",
    "ips": "⚡ IPS",
    "state": "🧭 State",
    "emulator": "🖥️ Emulator",
    "adb_device": "🔌 ADB Device",
    "runtime": "⏱️ Runtime",
}

RESULT_LABELS = {
    "1st": "🥇 1st Place",
    "2nd": "🥈 2nd Place",
    "3rd": "🥉 3rd Place",
    "4th": "4th Place",
    "victory": "🏆 Victory",
    "defeat": "💀 Defeat",
    "draw": "🤝 Draw",
}

def load_telegram_settings() -> dict[str, Any]:
    general_config = load_toml_as_dict("cfg/general_config.toml")
    config_path = TELEGRAM_CONFIG_PATH
    webhook_config = dict(load_toml_as_dict(config_path))
    
    webhook_config["telegram_bot_token"] = str(webhook_config.get("telegram_bot_token", "")).strip()
    webhook_config["telegram_chat_id"] = str(webhook_config.get("telegram_chat_id", "")).strip()
    
    webhook_config.setdefault("send_match_summary", False)
    webhook_config.setdefault("include_screenshot", True)
    webhook_config.setdefault("ping_when_stuck", False)
    webhook_config.setdefault("ping_when_target_is_reached", False)
    webhook_config.setdefault("ping_every_x_match", 0)
    webhook_config.setdefault("ping_every_x_minutes", 0)
    webhook_config.setdefault("telegram_control_enabled", False)
    webhook_config["telegram_control_user_id"] = str(
        webhook_config.get("telegram_control_user_id") or webhook_config.get("telegram_chat_id", "")
    ).strip()
    return webhook_config

def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _format_result(value: Any) -> str:
    result = str(value or "finished").strip()
    return RESULT_LABELS.get(result.lower(), result)

def _title_and_description(event_type: str, details: dict[str, Any]) -> tuple[str, str]:
    brawler = str(details.get("brawler") or "").title()
    if event_type == "match":
        result = _format_result(details.get("result"))
        brawler_text = f" with <b>{brawler}</b>" if brawler else ""
        return "🏁 Match Finished", f"Finished{brawler_text}: <b>{result}</b>"
    if event_type == "brawler_complete":
        if brawler:
            return "✅ Brawler Target Reached", f"<b>{brawler}</b> reached the configured target."
        return "✅ Brawler Target Reached", "A brawler reached the configured target."
    if event_type == "completed":
        return "🏆 All Targets Complete", "Pyla-Biomistik finished every queued target."
    if event_type == "bot_is_stuck":
        reason = str(details.get("reason") or "Pyla-Biomistik could not recover automatically.")
        return "🚨 Bot Needs Attention", reason
    if event_type == "test":
        return "🧪 Webhook Test", "Telegram notification is connected correctly."
    return "📣 Pyla-Biomistik Update", str(details.get("message") or "Bot event received.")

def _format_field_name(key: str) -> str:
    return FIELD_LABELS.get(key, key.replace("_", " ").strip().title())

def _format_field_value(key: str, value: Any) -> str:
    if key == "result":
        return _format_result(value)
    if key == "brawler":
        return str(value).title()
    return str(value)

def _build_html_message(title: str, description: str, details: dict[str, Any]) -> str:
    msg = f"<b>{title}</b>\n{description}\n\n"
    
    hidden = {"message", "reason"}
    ordered_keys = [
        "brawler", "result", "started_trophies", "trophies", "target",
        "wins", "win_streak", "brawlers_left", "ips", "state", "emulator",
        "adb_device", "runtime",
    ]
    keys = ordered_keys + [key for key in details.keys() if key not in ordered_keys]
    
    for key in keys:
        if key in hidden or key not in details:
            continue
        value = details.get(key)
        if value is None or value == "":
            continue
        text = _format_field_value(key, value)
        msg += f"<b>{_format_field_name(key)}:</b> {text}\n"
        
    return msg.strip()

def _image_to_bytes(screenshot: Any) -> io.BytesIO | None:
    if screenshot is None:
        return None
    if isinstance(screenshot, np.ndarray):
        image = Image.fromarray(screenshot)
    elif isinstance(screenshot, Image.Image):
        image = screenshot
    else:
        return None
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

async def async_notify_user(
    event_type: str | None = None,
    screenshot: Any = None,
    details: dict[str, Any] | None = None,
) -> bool:
    settings = load_telegram_settings()
    bot_token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    
    if not bot_token or not chat_id:
        if event_type == "test":
            print("Telegram test failed: Missing Token or Chat ID.")
        return False

    event_type = event_type or "update"
    details = dict(details or {})
    
    global _match_count, _last_minute_ping
    should_ping = False
    
    if event_type == "bot_is_stuck":
        should_ping = _config_bool(settings.get("ping_when_stuck"), False)
    elif event_type in ("completed", "brawler_complete"):
        should_ping = _config_bool(settings.get("ping_when_target_is_reached"), False)

    every_matches = _as_int(settings.get("ping_every_x_match", 0))
    if event_type == "match" and every_matches > 0:
        _match_count += 1
        should_ping = should_ping or (_match_count % every_matches == 0)

    every_minutes = _as_float(settings.get("ping_every_x_minutes", 0))
    if every_minutes > 0:
        now = time.time()
        if now - _last_minute_ping >= every_minutes * 60:
            _last_minute_ping = now
            should_ping = True

    if event_type == "match" and not (_config_bool(settings.get("send_match_summary"), False) or should_ping):
        return False

    title, description = _title_and_description(event_type, details)
    
    if should_ping:
        title = "🔔 " + title
        
    text_message = _build_html_message(title, description, details)
    
    include_screenshot = _config_bool(settings.get("include_screenshot"), True)
    image_bytes = _image_to_bytes(screenshot) if include_screenshot else None

    try:
        async with aiohttp.ClientSession() as session:
            if image_bytes:
                url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                data = aiohttp.FormData()
                data.add_field("chat_id", chat_id)
                data.add_field("photo", image_bytes.getvalue(), filename="screenshot.png", content_type="image/png")
                data.add_field("caption", text_message)
                data.add_field("parse_mode", "HTML")
                
                async with session.post(url, data=data) as resp:
                    resp_data = await resp.json()
                    if not resp_data.get("ok"):
                        print(f"Telegram photo send failed: {resp_data}")
                        return False
            else:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": text_message,
                    "parse_mode": "HTML"
                }
                async with session.post(url, json=payload) as resp:
                    resp_data = await resp.json()
                    if not resp_data.get("ok"):
                        print(f"Telegram message send failed: {resp_data}")
                        return False
                        
        print(f"Telegram notification sent: {event_type}")
        return True
    except Exception as exc:
        print(f"Telegram notification failed ({event_type}): {exc}")
        return False

async def async_send_test_notification() -> bool:
    return await async_notify_user(
        "test",
        details={
            "state": "configured",
            "message": "This is a manual test from the Pyla-Biomistik Hub.",
        },
    )
