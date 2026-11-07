"""Read-only player relay. Run ONE Gunicorn worker so admission state is shared."""
from collections import OrderedDict, deque
import ipaddress
import os
import re
import sqlite3
import threading
import time

from flask import Flask, jsonify, request
from common.http_json import bounded_json_get
from werkzeug.exceptions import HTTPException


TAG = re.compile(r'#[0289PYLQGRJCUV]{3,16}\Z')


class UpstreamError(Exception):
    def __init__(self, status):
        self.status = status


def normalize_tag(value):
    tag = '#' + str(value).strip().upper().lstrip('#')
    if not TAG.fullmatch(tag):
        raise ValueError('Invalid tag')
    return tag


def public_player(data, tag):
    """Explicit whitelist; never forward arbitrary upstream fields."""
    if not isinstance(data, dict) or data.get('tag') != tag:
        raise ValueError('Invalid profile')
    if not isinstance(data.get('name'), str) or len(data['name']) > 256:
        raise ValueError('Invalid name')
    brawlers = data.get('brawlers')
    if not isinstance(brawlers, list) or len(brawlers) > 300:
        raise ValueError('Invalid brawlers')
    def numbers(source, target, names):
        for key in names:
            if key in source:
                value = source[key]
                if type(value) is not int or not 0 <= value <= 10**10:
                    raise ValueError('Invalid number')
                target[key] = value
    result = {'tag': tag, 'name': data['name'], 'brawlers': []}
    numbers(data, result, ('trophies', 'highestTrophies', 'expLevel',
                          '3vs3Victories', 'soloVictories', 'duoVictories'))
    for row in brawlers:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or len(row['name']) > 128:
            raise ValueError('Invalid brawler')
        if any(key not in row for key in ('id', 'power', 'trophies')):
            raise ValueError('Missing brawler fields')
        item = {'name': row['name']}
        numbers(row, item, ('id', 'power', 'rank', 'trophies', 'highestTrophies'))
        result['brawlers'].append(item)
    return result


def fetch_upstream(token, tag):
    status, data = bounded_json_get(
        'https://api.brawlstars.com/v1/players/%23' + tag[1:], timeout=12,
        headers={'Authorization': 'Bearer ' + token})
    if status != 200:
        raise UpstreamError(status)
    return data


def create_app(token, fetch=None, clock=None, budget_path=':memory:'):
    if not token or '\n' in token or '\r' in token:
        raise ValueError('Upstream credential is required')
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 1024
    clock = clock or time.time
    fetch = fetch or (lambda tag: fetch_upstream(token, tag))
    lock = threading.Lock()
    cache, clients, attempts, pending = OrderedDict(), {}, deque(), set()
    state = {'cooldown': 0}
    budget = sqlite3.connect(budget_path, check_same_thread=False)
    app.extensions['relay_budget'] = budget
    budget.execute('CREATE TABLE IF NOT EXISTS budget(day INTEGER PRIMARY KEY, count INTEGER NOT NULL)')
    budget.commit()

    def reply(payload, status, retry_after=60):
        response = jsonify(payload)
        response.status_code = status
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if status in (429, 503):
            response.headers['Retry-After'] = str(retry_after)
        return response

    @app.errorhandler(Exception)
    def failure(error):
        status = error.code if isinstance(error, HTTPException) else 503
        return reply({'error': 'not_found' if status == 404 else
                      'method_not_allowed' if status == 405 else 'unavailable'}, status)

    @app.route('/v1/players/<tag>', methods=['GET'], provide_automatic_options=False)
    def player(tag):
        # Only the loopback nginx hop may supply a client address.
        if request.method != 'GET' or request.args or request.content_length or request.headers.get('Transfer-Encoding'):
            return reply({'error': 'invalid_request'}, 400)
        try:
            tag = normalize_tag(tag)
        except ValueError:
            return reply({'error': 'invalid_tag'}, 400)
        now = clock()
        with lock:
            # Fixed windows and bounded client table keep untrusted IP cardinality bounded.
            window = int(now // 60)
            for ip in list(clients):
                if clients[ip][0] != window:
                    del clients[ip]
            ip = request.remote_addr or 'unknown'
            if ip == '127.0.0.1' and request.headers.get('X-Real-IP'):
                try:
                    ip = str(ipaddress.ip_address(request.headers['X-Real-IP']))
                except ValueError:
                    return reply({'error': 'invalid_request'}, 400)
            if ip not in clients and len(clients) >= 4096:
                return reply({'error': 'rate_limited'}, 429)
            count = clients.get(ip, (window, 0))[1]
            if count >= 30:
                return reply({'error': 'rate_limited'}, 429)
            clients[ip] = (window, count + 1)
            hit = cache.get(tag)
            if hit and hit[0] > now:
                cache.move_to_end(tag)
                return reply(hit[1], hit[2])
            if now < state['cooldown']:
                return reply({'error': 'unavailable'}, 503)
            if tag in pending or len(pending) >= 2:
                return reply({'error': 'busy'}, 503)
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= 20:
                return reply({'error': 'rate_limited'}, 429)
            day = int(now // 86400)
            try:
                with budget:
                    budget.execute('DELETE FROM budget WHERE day != ?', (day,))
                    budget.execute('INSERT OR IGNORE INTO budget(day, count) VALUES (?, 0)', (day,))
                    used = budget.execute('SELECT count FROM budget WHERE day = ?', (day,)).fetchone()[0]
                    if used >= 2000:
                        return reply({'error': 'daily_limit'}, 429, max(1, int((day + 1) * 86400 - now)))
                    budget.execute('UPDATE budget SET count = count + 1 WHERE day = ?', (day,))
            except sqlite3.Error:
                return reply({'error': 'unavailable'}, 503)
            attempts.append(now)
            pending.add(tag)
        try:
            payload, status, ttl = public_player(fetch(tag), tag), 200, 180
        except UpstreamError as error:
            payload, status, ttl = {'error': 'not_found'}, 404, 30
            if error.status != 404:
                payload, status, ttl = {'error': 'unavailable'}, 503, 0
                with lock:
                    state['cooldown'] = max(state['cooldown'], clock() +
                                            (300 if error.status in (401, 403) else 60))
        except Exception:
            payload, status, ttl = {'error': 'unavailable'}, 503, 0
            with lock:
                state['cooldown'] = max(state['cooldown'], clock() + 3)
        with lock:
            if ttl:
                cache[tag] = (clock() + ttl, payload, status)
                cache.move_to_end(tag)
                while len(cache) > 512:
                    cache.popitem(last=False)
            pending.discard(tag)
        return reply(payload, status)

    return app


def application():
    return create_app(os.environ['BRAWL_STARS_API_TOKEN'],
                      budget_path=os.environ.get('RELAY_BUDGET_PATH', '/var/lib/pyla-player-relay/budget.sqlite'))
