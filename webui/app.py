"""Authenticated loopback API for the fork's browser menus."""
from __future__ import annotations

import hmac
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_from_directory, Response, abort
from werkzeug.exceptions import HTTPException

from webui.devices import scan_devices
from webui.player_api import fetch_player
from webui.runtime import ProcessManager
from webui.storage import ProjectStore, SECTIONS


def create_app(root=None, device_loader=None, player_loader=None):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.update(MAX_CONTENT_LENGTH=1024 * 1024, UI_API_TOKEN=secrets.token_urlsafe(32))
    store = ProjectStore(root)
    manager = ProcessManager(store)
    app.config.update(store=store, runtime_manager=manager)
    device_loader = device_loader or (lambda: scan_devices(root))
    raw_player_loader = player_loader or (lambda instance: fetch_player(root, instance))
    account_locks = {i: threading.RLock() for i in range(1, 100)}

    def player_loader(instance):
        instance = store.instance_id(instance)
        with account_locks[instance]:
            return raw_player_loader(instance)

    @app.before_request
    def protect_local_api():
        try:
            host = urlsplit('//' + request.host)
            if host.hostname not in {'127.0.0.1', 'localhost', '::1'}:
                return jsonify(ok=False, message='Invalid local host.'), 403
            origin = request.headers.get('Origin')
            if origin:
                origin = urlsplit(origin)
                expected_port = host.port or 80
                if (origin.scheme != request.scheme or origin.hostname != host.hostname or
                        (origin.port or (443 if origin.scheme == 'https' else 80)) != expected_port):
                    return jsonify(ok=False, message='Cross-origin request rejected.'), 403
        except ValueError:
            return jsonify(ok=False, message='Invalid local host or origin.'), 403
        if request.path.startswith('/api/'):
            supplied = request.headers.get('X-Pyla-UI-Token', '')
            if not hmac.compare_digest(supplied, app.config['UI_API_TOKEN']):
                return jsonify(ok=False, message='Reload this browser tab to restore your local session.'), 403

    @app.after_request
    def security_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.errorhandler(ValueError)
    def invalid_value(error):
        return jsonify(ok=False, message=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(ok=False, message=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        # Do not send tracebacks or exception text containing credentials to browsers.
        app.logger.error('Local UI request failed (%s).', type(error).__name__)
        return jsonify(ok=False, message='Could not complete this action. Check local files and try again.'), 500

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object.')
        return data

    def instance_info(instance):
        config = store.read_config(instance, 'general')
        return dict(manager.status(instance), emulator=config.get('current_emulator', ''),
                    port=config.get('emulator_port', ''), queue_count=len(store.queue(instance)))

    @app.get('/')
    def index():
        return render_template('index.html', ui_token=app.config['UI_API_TOKEN'])

    @app.get('/api/bootstrap')
    def bootstrap():
        return jsonify(ok=True, brawlers=store.catalog(), catalog=store.catalog_details(), sections=list(SECTIONS),
                       version=store.read_config(1, 'general').get('pyla_version', ''),
                       instances=[instance_info(i) for i in store.instances()])

    @app.get('/assets/brawlers/<name>.png')
    def brawler_portrait(name):
        if name not in store.catalog():
            abort(404)
        folder = root / 'api/assets/brawler_icons'
        if (folder / f'{name}.png').is_file():
            return send_from_directory(folder, f'{name}.png')
        return Response('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" rx="16" fill="#35385d"/><text x="48" y="64" text-anchor="middle" fill="#c9ccff" font-family="sans-serif" font-size="48">?</text></svg>', mimetype='image/svg+xml')

    @app.post('/api/instances/<int:instance>/player')
    def load_account(instance):
        with store.lock:
            manager.assert_editable(instance)
        return jsonify(ok=True, player=player_loader(instance))

    @app.get('/api/instances')
    def get_instances():
        return jsonify(ok=True, instances=[instance_info(i) for i in store.instances()])

    @app.post('/api/instances')
    def create_instance():
        instance = store.create_instance(payload().get('instance'))
        return jsonify(ok=True, instance=instance_info(instance))

    @app.get('/api/devices')
    def devices():
        return jsonify(ok=True, devices=device_loader())

    @app.post('/api/instances/<int:instance>/device')
    def select_device(instance):
        serial = payload().get('serial')
        with store.lock:
            manager.assert_editable(instance)
            selected = next((device for device in device_loader() if device['serial'] == serial), None)
            if not selected:
                raise ValueError('This device is no longer connected. Scan again.')
            store.update_settings(instance, 'general', {'emulator_port': selected['port'], 'current_emulator': selected['emulator']})
            return jsonify(ok=True, instance=instance_info(instance))

    @app.route('/api/instances/<int:instance>/settings/<section>', methods=['GET', 'PUT'])
    def settings(instance, section):
        instance = store.instance_id(instance)
        # A slow account request does not block status polling or other profiles.
        with account_locks[instance], store.lock:
            if request.method == 'PUT':
                manager.assert_editable(instance)
                body = payload()
                manager.remember_secrets(instance)
                store.update_settings(instance, section, body.get('values'), body.get('clear_secrets', []))
            return jsonify(ok=True, fields=store.settings(instance, section))

    @app.route('/api/instances/<int:instance>/queue', methods=['GET', 'PUT'])
    def queue(instance):
        with store.lock:
            if request.method == 'PUT':
                manager.assert_editable(instance)
                store.save_queue(instance, payload().get('queue'))
            return jsonify(ok=True, queue=store.queue(instance))

    def player_rows(instance):
        player = player_loader(instance)
        names = {re.sub('[^a-z0-9]', '', name.lower()): name for name in store.catalog()}
        return [(names[key], int(row.get('trophies', 0))) for row in player.get('brawlers', [])
                if (key := re.sub('[^a-z0-9]', '', row.get('name', '').lower())) in names]

    @app.post('/api/instances/<int:instance>/queue/push-all')
    def push_all(instance):
        target = payload().get('target', 1000)
        if type(target) is not int or not 1 <= target <= 1_000_000:
            raise ValueError('Target must be a positive integer.')
        with store.lock:
            manager.assert_editable(instance)
        rows = [dict(brawler=name, trophies=trophies, push_until=target, type='trophies', automatically_pick=True,
                     selection_method='named_brawler')
                for name, trophies in sorted(player_rows(instance), key=lambda item: item[1]) if trophies < target]
        with store.lock:
            manager.assert_editable(instance)
            return jsonify(ok=True, queue=store.save_queue(instance, rows))

    @app.post('/api/instances/<int:instance>/queue/sync')
    def sync_trophies(instance):
        with store.lock:
            manager.assert_editable(instance)
        trophies = dict(player_rows(instance))
        with store.lock:
            manager.assert_editable(instance)
            rows = store.queue(instance)
            for row in rows:
                if row['brawler'] in trophies:
                    row['trophies'] = trophies[row['brawler']]
            return jsonify(ok=True, queue=store.save_queue(instance, rows))

    @app.get('/api/instances/<int:instance>/playstyles')
    def playstyles(instance):
        return jsonify(ok=True, playstyles=store.playstyles(instance))

    @app.post('/api/instances/<int:instance>/playstyles/activate')
    def activate_playstyle(instance):
        with store.lock:
            manager.assert_editable(instance)
            store.activate_playstyle(instance, payload().get('name'))
        return jsonify(ok=True, playstyles=store.playstyles(instance))

    @app.get('/api/instances/<int:instance>/history')
    def history(instance):
        return jsonify(ok=True, history=store.history(instance))

    @app.get('/api/instances/<int:instance>/logs')
    def logs(instance):
        return jsonify(ok=True, lines=manager.logs(instance))

    @app.post('/api/instances/<int:instance>/runtime/<action>')
    def runtime(instance, action):
        actions = {'start': manager.start, 'pause': manager.pause, 'resume': manager.resume, 'stop': manager.stop}
        if action not in actions:
            raise ValueError('Unknown runtime action.')
        return jsonify(ok=True, instance=actions[action](instance))

    return app
