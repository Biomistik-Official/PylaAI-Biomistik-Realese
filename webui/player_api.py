"""Isolate legacy API-token refresh and its instance-specific environment."""
import json
import os
from pathlib import Path
import subprocess
import sys


MARKER = 'PYLAAI_PLAYER_JSON:'

MESSAGES = {
    'login': 'Портал разработчика отклонил вход. Проверь почту и пароль именно от developer.brawlstars.com.',
    'ip': 'API отклонил токен для текущего IP. Укажи почту и пароль портала либо создай токен для этого подключения.',
    'tag': 'Игрок не найден. Проверь тег игрока, включая символ #.',
    'credentials': 'Укажи почту и пароль портала разработчика либо готовый API-токен. API можно пропустить и выбрать бойцов вручную.',
    'connection': 'Не удалось связаться с Brawl Stars API. Проверь подключение и повтори загрузку.',
    'changed': 'Настройки аккаунта изменились во время загрузки. Повтори вход с текущими данными.',
    'rate': 'Достигнут лимит сервиса данных. Повтори позже; суточный лимит сбрасывается в 00:00 UTC.',
}


class PlayerError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])


def load_player(root, instance):
    """Explicit account load; scheduled refresh and key-deletion preferences stay intact."""
    from common.utils import fetch_brawl_stars_player, refresh_brawl_stars_api_token_if_enabled
    from webui.storage import ProjectStore
    store = ProjectStore(root)
    config = store.read_config(instance, 'api')
    tag = str(config.get('player_tag', '')).strip()
    if not tag or tag.upper() == '#YOURTAG':
        raise PlayerError('tag')
    token = config.get('api_token', '')
    credentials = bool(config.get('developer_email') and config.get('developer_password'))
    timeout = int(config.get('timeout_seconds', 15))
    if config.get('player_source', 'relay') == 'relay':
        from common.player_client import fetch_relay_player, RelayError
        try:
            player = fetch_relay_player(tag, timeout)
            latest = store.read_config(instance, 'api')
            if any(latest.get(key) != config.get(key) for key in ('player_tag', 'player_source')):
                raise PlayerError('changed')
            return player
        except RelayError as error:
            raise PlayerError(error.code if error.code in MESSAGES else 'connection') from None
        except ValueError as error:
            if isinstance(error, PlayerError):
                raise
            raise PlayerError('tag') from None
    if config.get('player_source') != 'direct':
        raise PlayerError('connection')
    try:
        if token:
            try:
                player = fetch_brawl_stars_player(token, tag, timeout)
                latest = store.read_config(instance, 'api')
                if any(latest.get(key) != config.get(key) for key in ('player_tag', 'player_source', 'api_token', 'developer_email', 'developer_password')):
                    raise PlayerError('changed')
                return player
            except RuntimeError as error:
                if 'accessDenied' not in str(error) or not credentials:
                    raise
        if not credentials:
            raise PlayerError('credentials')
        # Explicit login may issue a key, but never revokes existing account keys.
        refreshed = refresh_brawl_stars_api_token_if_enabled(
            dict(config, auto_refresh_token=True, delete_all_tokens=False, delete_old_auto_tokens=False),
            str(store.config_dir(instance) / 'brawl_stars_api.toml'), force=True, persist=False)
        player = fetch_brawl_stars_player(refreshed.get('api_token', ''), tag, timeout)
        latest = store.read_config(instance, 'api')
        if any(latest.get(key) != config.get(key) for key in ('player_tag', 'player_source', 'developer_email', 'developer_password', 'api_token')):
            raise PlayerError('changed')
        updates = {'api_token': refreshed['api_token']}
        if 'last_public_ip' in config:
            updates['last_public_ip'] = refreshed.get('last_public_ip', '')
        store.update_settings(instance, 'api', updates)
        return player
    except PlayerError:
        raise
    except Exception as error:
        text = str(error).lower()
        code = ('login' if 'login' in text and ('401' in text or '403' in text) else
                'ip' if 'accessdenied' in text else 'tag' if '404' in text else 'connection')
        raise PlayerError(code) from None


def fetch_player(root, instance):
    env = os.environ.copy()
    env['PYLAAI_INSTANCE'] = str(instance)
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('PYTHONPATH', None)
    try:
        result = subprocess.run([sys.executable, '-m', 'webui.player_api'], cwd=root, env=env,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Player API did not respond. Check the player tag, API settings and connection.') from None
    for line in reversed(result.stdout.splitlines()):
        if result.returncode == 0 and line.startswith(MARKER):
            payload = json.loads(line[len(MARKER):])
            if payload.get('ok') is False:
                raise PlayerError(payload.get('code') if payload.get('code') in MESSAGES else 'connection')
            return payload['player']
    raise PlayerError('connection')


def main():
    os.chdir(Path(__file__).resolve().parents[1])
    try:
        data = load_player(Path(__file__).resolve().parents[1], int(os.environ.get('PYLAAI_INSTANCE', '1')))
        payload = dict(ok=True, player=data)
    except Exception as error:
        payload = dict(ok=False, code=error.code if isinstance(error, PlayerError) else 'connection')
    print(MARKER + json.dumps(payload))


if __name__ == '__main__':
    main()
