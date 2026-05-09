from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import discord
from discord import app_commands

from remote.runtime_control import PAUSED, RUNNING, read_state, write_state
from common.utils import _config_bool
from remote.discord_notifier import load_webhook_settings
from common.stats_card import generate_stats_card


def _clean_id(value: Any) -> str:
    return str(value or "").strip().strip("<@!>")


def _ids_match(configured: str, actual: int | str | None) -> bool:
    configured = _clean_id(configured)
    if not configured:
        return True
    return configured == str(actual or "").strip()


def command_allowed(settings: dict[str, Any], user_id: int | str, channel_id: int | str | None, guild_id: int | str | None) -> bool:
    allowed_user = _clean_id(settings.get("discord_control_user_id") or settings.get("discord_id"))
    allowed_channel = _clean_id(settings.get("discord_control_channel_id"))
    allowed_guild = _clean_id(settings.get("discord_control_guild_id"))
    return (
        _ids_match(allowed_user, user_id)
        and _ids_match(allowed_channel, channel_id)
        and _ids_match(allowed_guild, guild_id)
    )


def set_runtime_state(state_path: str | Path, paused: bool) -> str:
    state = PAUSED if paused else RUNNING
    write_state(state_path, state)
    return state


class DiscordControlServer:
    def __init__(self, state_path: str | Path, settings_loader=load_webhook_settings):
        self.state_path = Path(state_path)
        self.settings_loader = settings_loader
        self.get_screenshot_cb = None
        self.get_stats_cb = None
        self.get_queue_cb = None
        self.skip_queue_cb = None
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client: discord.Client | None = None

    def start(self) -> bool:
        settings = self.settings_loader()
        if not _config_bool(settings.get("discord_control_enabled"), False):
            return False

        token = str(settings.get("discord_bot_token") or "").strip()
        if not token:
            print("Discord control skipped: enable it only after filling discord_bot_token in cfg/discord_config.toml.")
            return False

        if self.thread and self.thread.is_alive():
            return True

        self.thread = threading.Thread(target=self._thread_main, args=(token,), daemon=True)
        self.thread.start()
        return True

    def close(self) -> None:
        client = self.client
        loop = self.loop
        if client is not None and loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(client.close(), loop).result(timeout=3)
            except Exception:
                pass

    def _thread_main(self, token: str) -> None:
        try:
            asyncio.run(self._run(token))
        except Exception as exc:
            print(f"Discord control stopped: {exc}")

    async def _run(self, token: str) -> None:
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(client)
        self.client = client
        self.loop = asyncio.get_running_loop()
        synced = False

        async def _reply(interaction: discord.Interaction, message: str) -> None:
            try:
                await interaction.response.send_message(message, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(message, ephemeral=True)

        async def _guard(interaction: discord.Interaction) -> bool:
            settings = self.settings_loader()
            if command_allowed(
                settings,
                getattr(interaction.user, "id", ""),
                getattr(interaction.channel, "id", None),
                getattr(interaction.guild, "id", None),
            ):
                return True
            await _reply(interaction, "You are not allowed to control this Pyla-Biomistik bot.")
            return False

        @tree.command(name="stop", description="Pause Pyla-Biomistik.")
        async def stop_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            set_runtime_state(self.state_path, paused=True)
            await _reply(interaction, "Pyla-Biomistik paused.")

        @tree.command(name="start", description="Resume Pyla-Biomistik.")
        async def start_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            set_runtime_state(self.state_path, paused=False)
            await _reply(interaction, "Pyla-Biomistik resumed.")

        @tree.command(name="status", description="Show whether Pyla-Biomistik is running or paused.")
        async def status_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            state = read_state(self.state_path)
            await _reply(interaction, f"Pyla-Biomistik is {'paused' if state == PAUSED else 'running'}.")

        @tree.command(name="stats", description="Show current session statistics.")
        async def stats_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            if not self.get_stats_cb:
                await _reply(interaction, "Stats are not available yet.")
                return
            
            stats = self.get_stats_cb()
            if not stats:
                await _reply(interaction, "Failed to retrieve stats.")
                return
                
            try:
                await interaction.response.defer(ephemeral=True)
                card_path = generate_stats_card("logs/stats_dashboard.png", details=stats)
                file = discord.File(card_path, filename="dashboard.png")
                await interaction.followup.send(content="📊 **Session Statistics**", file=file, ephemeral=True)
            except Exception as e:
                print(f"Error generating stats card: {e}")
                embed = discord.Embed(title="📊 Session Statistics", color=discord.Color.blue())
                embed.add_field(name="🏆 Trophies", value=str(stats.get('trophies', 0)), inline=True)
                embed.add_field(name="🔥 Win Streak", value=str(stats.get('win_streak', 0)), inline=True)
                embed.add_field(name="✅ Total Wins", value=str(stats.get('wins', 0)), inline=True)
                try:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                except discord.InteractionResponded:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                
        @tree.command(name="queue", description="Show the current brawler queue.")
        async def queue_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            if not self.get_queue_cb:
                await _reply(interaction, "Queue functionality is not available.")
                return
                
            queue = self.get_queue_cb()
            if not queue:
                await _reply(interaction, "The queue is currently empty.")
                return
                
            embed = discord.Embed(title="📋 Current Queue", color=discord.Color.green())
            for i, item in enumerate(queue):
                brawler = str(item.get("brawler", "Unknown")).title()
                target = item.get("push_until", "N/A")
                current = item.get("trophies", "N/A")
                
                if i == 0:
                    embed.add_field(name=f"▶️ {brawler} (Active)", value=f"{current}/{target} 🏆", inline=False)
                else:
                    embed.add_field(name=f"⏳ {brawler}", value=f"Target: {target} 🏆", inline=False)
                    
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        @tree.command(name="skip", description="Skip the current brawler in the queue.")
        async def skip_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            if not self.skip_queue_cb:
                await _reply(interaction, "Skip functionality is not available.")
                return
                
            if self.skip_queue_cb():
                await _reply(interaction, "Skipped the current brawler. Loading the next one...")
            else:
                await _reply(interaction, "Failed to skip. Queue might be empty.")

        @tree.command(name="screenshot", description="Get a live screenshot of the bot's screen.")
        async def screenshot_command(interaction: discord.Interaction) -> None:
            if not await _guard(interaction):
                return
            
            await interaction.response.defer(ephemeral=True)
            
            if not self.get_screenshot_cb:
                await interaction.followup.send("Screenshot functionality is not available.", ephemeral=True)
                return
                
            img = self.get_screenshot_cb()
            if img is None:
                await interaction.followup.send("Failed to capture screenshot. The bot might not be running.", ephemeral=True)
                return
                
            import cv2
            import io
            is_success, buffer = cv2.imencode(".png", img)
            if not is_success:
                await interaction.followup.send("Failed to encode screenshot.", ephemeral=True)
                return
                
            file = discord.File(io.BytesIO(buffer.tobytes()), filename="screenshot.png")
            await interaction.followup.send("Here is the current screen:", file=file, ephemeral=True)

        @client.event
        async def on_ready() -> None:
            nonlocal synced
            if synced:
                return
            settings = self.settings_loader()
            guild_id = _clean_id(settings.get("discord_control_guild_id"))
            try:
                if guild_id:
                    guild = discord.Object(id=int(guild_id))
                    tree.copy_global_to(guild=guild)
                    await tree.sync(guild=guild)
                    print(f"Discord control commands synced for guild {guild_id}: /start /stop /status /stats /screenshot /queue /skip")
                else:
                    await tree.sync()
                    print("Discord control commands synced globally: /start /stop /status /stats /screenshot /queue /skip")
                synced = True
            except Exception as exc:
                print(f"Discord control command sync failed: {exc}")

        await client.start(token)
