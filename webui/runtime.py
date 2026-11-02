"""Own bot processes, while retaining the fork's per-PID pause protocol."""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from remote.runtime_control import process_is_alive, read_state
from webui.storage import SECRET_PATTERN, SECTIONS, atomic_write


class ProcessManager:
    def __init__(self, store, command_factory=None):
        self.store = store
        self.lock = store.lock
        self.command_factory = command_factory or (lambda instance: [sys.executable, '-u', '-m', 'webui.worker'])
        self.records = {}

    def _lock_path(self, instance):
        return self.store.root / 'logs' / f'instance_{self.store.instance_id(instance)}.lock'

    def _external_pid(self, instance):
        try:
            pid = int(self._lock_path(instance).read_text().strip())
            return pid if process_is_alive(pid) else None
        except (OSError, ValueError):
            return None

    def status(self, instance):
        with self.lock:
            instance = self.store.instance_id(instance)
            record = self.records.get(instance)
            if not record:
                pid = self._external_pid(instance)
                return dict(instance=instance, state='external' if pid else 'idle', pid=pid, returncode=None, started_at=None)
            process = record['process']
            code = process.poll()
            if code is None:
                shared_state = read_state(record['state_path'])
                state = record['state']
                if state != 'stopping' and shared_state in {'running', 'paused', 'stopped'}:
                    state = 'stopping' if shared_state == 'stopped' else shared_state
            else:
                state = 'error' if code and not record.get('stop_requested') else 'stopped'
            if code is not None:
                self._remove_lock(instance, process.pid)
            return dict(instance=instance, state=state, pid=process.pid if code is None else None,
                        returncode=code, started_at=record['started_at'])

    def is_active(self, instance):
        return self.status(instance)['state'] not in ('idle', 'stopped', 'error')

    def assert_editable(self, instance):
        if self.is_active(instance):
            raise ValueError('Stop this instance before editing its queue or settings.')

    def start(self, instance):
        with self.lock:
            instance = self.store.instance_id(instance)
            if self.is_active(instance):
                raise ValueError('This instance is already running.')
            queue = self.store.queue(instance)
            if not queue:
                raise ValueError('Add a brawler to the queue before starting.')
            self.store.save_queue(instance, queue)
            config = self.store.read_config(instance, 'general')
            port = config.get('emulator_port')
            for other in self.store.instances():
                if other != instance and self.is_active(other) and self.store.read_config(other, 'general').get('emulator_port') == port:
                    raise ValueError('Another running instance already uses this emulator port.')
            lock_path = self._lock_path(instance)
            lock_path.parent.mkdir(exist_ok=True)
            # An exclusive reservation also prevents two browser servers starting the same instance.
            try:
                if lock_path.exists() and not self._external_pid(instance):
                    lock_path.unlink()
                descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError:
                raise ValueError('This instance is managed by another launcher.') from None
            with os.fdopen(descriptor, 'w') as reservation:
                reservation.write(str(os.getpid()))
            env = os.environ.copy()
            for key in ('PYTHONHOME', 'PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY'):
                env.pop(key, None)
            env.update(PYLAAI_INSTANCE=str(instance), PYLAAI_HUB_MODE='1', PYLAAI_BROWSER_WORKER='1', PYTHONIOENCODING='utf-8')
            state_path = self.store.root / 'logs' / f'runtime_control_{instance}_{uuid.uuid4().hex}.state'
            env['PYLAAI_CONTROL_PATH'] = str(state_path)
            atomic_write(state_path, 'running')
            try:
                process = subprocess.Popen(self.command_factory(instance), cwd=self.store.root, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                    errors='replace', bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except Exception:
                self._remove_lock(instance, os.getpid())
                raise
            atomic_write(lock_path, str(process.pid))
            record = dict(process=process, state='running', state_path=state_path,
                          started_at=time.time(), logs=deque(maxlen=1500), secrets=self._secrets(instance), secret_stamps={})
            self.records[instance] = record
            reader = threading.Thread(target=self._read_output, args=(instance, record), daemon=True)
            record['reader'] = reader
            reader.start()
            return self.status(instance)

    def _remove_lock(self, instance, pid):
        path = self._lock_path(instance)
        try:
            if path.read_text().strip() == str(pid):
                path.unlink()
        except OSError:
            pass

    def _read_output(self, instance, record):
        process = record['process']
        try:
            for line in process.stdout:
                with self.lock:
                    self.remember_secrets(instance, record)
                    for secret in record['secrets']:
                        line = line.replace(secret, '[hidden]')
                    record['logs'].append(line.rstrip())
        finally:
            process.stdout.close()
            process.wait()
            with self.lock:
                self._remove_lock(instance, process.pid)

    def _set_state(self, instance, state):
        with self.lock:
            instance = self.store.instance_id(instance)
            record = self.records.get(instance)
            if not record or record['process'].poll() is not None:
                raise ValueError('This instance is not running in this browser panel.')
            atomic_write(record['state_path'], state)
            record['state'] = state
            return self.status(instance)

    def pause(self, instance):
        return self._set_state(instance, 'paused')

    def resume(self, instance):
        return self._set_state(instance, 'running')

    def stop(self, instance):
        with self.lock:
            record = self.records.get(self.store.instance_id(instance))
            if not record or record['process'].poll() is not None:
                return self.status(instance)
            self._set_state(instance, 'stopped')
            record['state'] = 'stopping'
            record['stop_requested'] = True
            process = record['process']
        # Do not hold the log-reader lock while waiting for worker shutdown.
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False)
            else:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            with self.lock:
                record['logs'].append('Worker did not exit in time and was terminated.')
        record['reader'].join(timeout=2)
        return self.status(instance)

    def _secrets(self, instance):
        result = set()
        for section in ('general', 'telegram', 'discord', 'api'):
            config = self.store.read_config(instance, section)
            result.update(value for key, value in config.items()
                          if SECRET_PATTERN.search(key) and isinstance(value, str) and value)
        return result

    def remember_secrets(self, instance, record=None):
        record = record or self.records.get(self.store.instance_id(instance))
        if not record:
            return
        for section in ('general', 'telegram', 'discord', 'api'):
            path = self.store.config_dir(instance) / SECTIONS[section]
            try:
                stat = path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
                if record['secret_stamps'].get(section) == stamp:
                    continue
                config = self.store.read_config(instance, section)
            except (OSError, ValueError):
                # A legacy worker may briefly truncate a config while refreshing a token.
                continue
            record['secrets'].update(value for key, value in config.items()
                                    if SECRET_PATTERN.search(key) and isinstance(value, str) and value)
            record['secret_stamps'][section] = stamp

    def logs(self, instance):
        with self.lock:
            record = self.records.get(self.store.instance_id(instance))
            lines = list(record['logs']) if record else []
            # Remote libraries can put a bot token into a URL in exception text.
            secrets = self._secrets(instance)
            if record:
                record['secrets'].update(secrets)
                secrets = record['secrets']
            for secret in secrets:
                lines = [line.replace(secret, '[hidden]') for line in lines]
            return lines

    def close(self):
        for instance in list(self.records):
            self.stop(instance)
