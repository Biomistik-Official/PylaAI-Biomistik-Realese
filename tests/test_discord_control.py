import tempfile
import unittest
from pathlib import Path

from remote.discord_control import command_allowed, set_runtime_state
from remote.runtime_control import PAUSED, RUNNING, read_state


class DiscordControlTest(unittest.TestCase):
    def test_command_allowed_uses_discord_id_as_owner_fallback(self):
        settings = {
            "discord_id": "12345",
            "discord_control_user_id": "",
            "discord_control_channel_id": "",
            "discord_control_guild_id": "",
        }

        self.assertTrue(command_allowed(settings, user_id=12345, channel_id=99, guild_id=88))
        self.assertFalse(command_allowed(settings, user_id=54321, channel_id=99, guild_id=88))

    def test_command_allowed_can_restrict_channel_and_guild(self):
        settings = {
            "discord_control_user_id": "12345",
            "discord_control_channel_id": "222",
            "discord_control_guild_id": "333",
        }

        self.assertTrue(command_allowed(settings, user_id=12345, channel_id=222, guild_id=333))
        self.assertFalse(command_allowed(settings, user_id=12345, channel_id=999, guild_id=333))
        self.assertFalse(command_allowed(settings, user_id=12345, channel_id=222, guild_id=999))

    def test_start_stop_commands_write_runtime_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "runtime.state"

            self.assertEqual(set_runtime_state(state_path, paused=True), PAUSED)
            self.assertEqual(read_state(state_path), PAUSED)

            self.assertEqual(set_runtime_state(state_path, paused=False), RUNNING)
            self.assertEqual(read_state(state_path), RUNNING)


if __name__ == "__main__":
    unittest.main()
