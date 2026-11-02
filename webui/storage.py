"""File-backed browser settings without importing the game or loading models."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading

import toml


SECTIONS = {
    'general': 'general_config.toml', 'bot': 'bot_config.toml',
    'timers': 'time_tresholds.toml', 'telegram': 'telegram_config.toml',
    'discord': 'discord_config.toml', 'api': 'brawl_stars_api.toml',
}
SECRET_PATTERN = re.compile(r'token|password|email|webhook|personal_webhook', re.I)
CHOICES = {
    'vision_model_profile': ['upstream-763c389', 'legacy'],
    'brawler_selection_mode': ['search', 'legacy_scroll'],
    'current_emulator': ['LDPlayer', 'MuMu', 'BlueStacks', 'NoxPlayer'],
    'cpu_or_gpu': ['auto', 'gpu', 'cpu', 'cuda', 'directml', 'openvino'],
    'gamemode': ['showdown', 'brawlball'],
}
AUTO_INTEGER_FIELDS = {'used_threads', 'onnx_cpu_threads', 'directml_device_id', 'emulator_profile_index'}


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ProjectStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    @staticmethod
    def instance_id(value):
        if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]?', str(value)):
            raise ValueError('Instance must be a number from 1 to 99.')
        return int(value)

    def config_dir(self, instance):
        instance = self.instance_id(instance)
        return self.root / ('cfg' if instance == 1 else f'cfg_{instance}')

    def instances(self):
        return [1] + sorted(int(p.name[4:]) for p in self.root.glob('cfg_*')
                            if p.is_dir() and re.fullmatch(r'cfg_[2-9]|cfg_[1-9][0-9]', p.name))

    def create_instance(self, instance):
        with self.lock:
            destination = self.config_dir(instance)
            if not destination.exists():
                shutil.copytree(self.root / 'cfg', destination, ignore=shutil.ignore_patterns(
                    'browser_queue.json', 'match_history.toml', 'adaptive_state.json'))
            return self.instance_id(instance)

    def read_config(self, instance, section):
        if section not in SECTIONS:
            raise ValueError('Unknown settings section.')
        folder = self.config_dir(instance)
        if not folder.is_dir():
            raise ValueError('Create the instance first.')
        path = folder / SECTIONS[section]
        config = toml.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
        if section == 'general':
            config.setdefault('vision_model_profile', 'upstream-763c389')
            config.setdefault('brawler_selection_mode', 'search')
        return config

    def settings(self, instance, section):
        config = self.read_config(instance, section)
        fields = []
        for key, value in config.items():
            if isinstance(value, dict):
                continue
            secret = bool(SECRET_PATTERN.search(key))
            field_type = ('bool' if isinstance(value, bool) else 'int' if isinstance(value, int)
                          else 'float' if isinstance(value, float) else 'list' if isinstance(value, list) else 'str')
            if key in AUTO_INTEGER_FIELDS:
                field_type = 'auto_int'
            choices = CHOICES.get(key, ['yes', 'no'] if value in ('yes', 'no') else [])
            fields.append(dict(key=key, value='' if secret else value, type=field_type,
                               secret=secret, configured=bool(value) if secret else False, choices=choices))
        return fields

    @staticmethod
    def _parse_value(key, value, current):
        if key in AUTO_INTEGER_FIELDS:
            if isinstance(value, str) and value.strip().lower() == 'auto':
                return 'auto'
            minimum = 1 if key in {'used_threads', 'onnx_cpu_threads'} else 0
            if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)) or not minimum <= int(value) <= 256:
                raise ValueError(f'{key}: expected auto or an integer from {minimum} to 256.')
            return int(value)
        if isinstance(current, bool):
            if not isinstance(value, bool):
                raise ValueError(f'{key}: expected a boolean.')
        elif isinstance(current, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{key}: expected a finite number.')
            if isinstance(current, int) and int(value) != value:
                raise ValueError(f'{key}: expected an integer.')
            value = int(value) if isinstance(current, int) else float(value)
            if value < 0:
                raise ValueError(f'{key}: must not be negative.')
        elif isinstance(current, list):
            if not isinstance(value, list) or any(not isinstance(v, (str, int, float)) or isinstance(v, bool) for v in value):
                raise ValueError(f'{key}: expected a list of strings or numbers.')
        elif not isinstance(value, str) or len(value) > 4096:
            raise ValueError(f'{key}: expected text up to 4096 characters.')
        if key in CHOICES and value not in CHOICES[key]:
            raise ValueError(f'{key}: unsupported choice.')
        if key == 'emulator_port' and (not 1 <= int(value) <= 65535 or int(value) == 5037):
            raise ValueError('Use the emulator device port, not ADB server port 5037.')
        if key in {'max_ips', 'scrcpy_max_fps'} and float(value) > 1000:
            raise ValueError(f'{key}: maximum is 1000.')
        if ('confidence' in key or key == 'angle_smooth_factor') and not 0 <= float(value) <= 1:
            raise ValueError(f'{key}: must be between 0 and 1.')
        if isinstance(current, str) and current in ('yes', 'no') and value not in ('yes', 'no'):
            raise ValueError(f'{key}: expected yes or no.')
        return value

    def update_settings(self, instance, section, updates, clear_secrets=None):
        if not isinstance(updates, dict) or not isinstance(clear_secrets or [], list):
            raise ValueError('Expected settings object and secret list.')
        with self.lock:
            config = self.read_config(instance, section)
            for key, value in updates.items():
                if key not in config or isinstance(config[key], dict):
                    raise ValueError(f'Unknown setting: {key}')
                if SECRET_PATTERN.search(key) and value == '':
                    continue
                config[key] = self._parse_value(key, value, config[key])
            for key in clear_secrets or []:
                if not isinstance(key, str) or key not in config or not SECRET_PATTERN.search(key):
                    raise ValueError('Only known secret fields can be cleared.')
                config[key] = ''
            if section in ('telegram', 'discord'):
                prefix = section
                token_key = 'telegram_bot_token' if section == 'telegram' else 'discord_bot_token'
                owner = str(config.get(prefix + '_control_user_id') or (config.get('discord_id') if section == 'discord' else '') or '')
                if config.get(prefix + '_control_enabled') and config.get(token_key) and not re.fullmatch(r'[1-9][0-9]*', owner):
                    raise ValueError('Set the owner user ID before enabling remote control.')
            atomic_write(self.config_dir(instance) / SECTIONS[section], toml.dumps(config))
            return self.settings(instance, section)

    def catalog(self):
        return sorted(json.loads((self.root / 'cfg/brawlers_info.json').read_text(encoding='utf-8-sig')))

    def catalog_details(self):
        data = json.loads((self.root / 'cfg/brawlers_info.json').read_text(encoding='utf-8-sig'))
        return [dict(name=name, display_name=data[name].get('actual_name') or name.title(),
                     icon=f'/assets/brawlers/{name}.png') for name in sorted(data)]

    def queue_path(self, instance):
        return self.config_dir(instance) / 'browser_queue.json'

    def queue(self, instance):
        path = self.queue_path(instance)
        if not path.exists() and self.instance_id(instance) == 1:
            path = self.root / 'latest_brawler_data.json'
        if not path.exists():
            return []
        return self.normalize_queue(json.loads(path.read_text(encoding='utf-8-sig')))

    def normalize_queue(self, rows):
        if not isinstance(rows, list) or len(rows) > 300:
            raise ValueError('Queue must contain at most 300 entries.')
        catalog = set(self.catalog())
        seen, result = set(), []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('brawler'), str) or row.get('brawler') not in catalog:
                raise ValueError('Choose a brawler from the catalog.')
            name = row['brawler']
            if name in seen:
                raise ValueError(f'{name}: brawler is already in the queue.')
            seen.add(name)
            if row.get('type', 'trophies') not in ('trophies', 'wins'):
                raise ValueError('Target type must be trophies or wins.')
            clean = dict(brawler=name, type=row.get('type', 'trophies'))
            for key, default in [('push_until', 1000), ('trophies', 0), ('wins', 0), ('win_streak', 0)]:
                value = row.get(key, default)
                if type(value) is not int or not 0 <= value <= 1_000_000:
                    raise ValueError(f'{key}: expected a non-negative integer.')
                clean[key] = value
            if clean['push_until'] == 0:
                raise ValueError('Target must be greater than zero.')
            automatic = row.get('automatically_pick', True)
            if not isinstance(automatic, bool):
                raise ValueError('Automatic selection must be a boolean.')
            clean['automatically_pick'] = automatic
            for key in ('selection_method', 'push_all'):
                if key in row:
                    clean[key] = row[key]
            result.append(clean)
        return result

    def save_queue(self, instance, rows):
        with self.lock:
            clean = self.normalize_queue(rows)
            if not self.config_dir(instance).is_dir():
                raise ValueError('Create the instance first.')
            atomic_write(self.queue_path(instance), json.dumps(clean, indent=2))
            return clean

    def playstyles(self, instance):
        selected = self.read_config(instance, 'bot').get('current_playstyle', '')
        return [dict(name=p.name, active=p.name == selected) for p in sorted((self.root / 'playstyles').glob('*.pyla'))]

    def activate_playstyle(self, instance, name):
        if not isinstance(name, str) or name not in {p['name'] for p in self.playstyles(instance)}:
            raise ValueError('Choose an existing playstyle.')
        return self.update_settings(instance, 'bot', {'current_playstyle': name})

    def history(self, instance):
        path = self.config_dir(instance) / 'match_history.toml'
        return toml.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
