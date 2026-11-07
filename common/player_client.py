"""Public, credential-free HTTPS player client."""
import re
from common.http_json import bounded_json_get, HTTPJSONError


RELAY_URL = 'https://pyla-api.185-251-38-246.sslip.io/v1/players/'


class RelayError(RuntimeError):
    def __init__(self, code='connection'):
        self.code = code
        super().__init__('Player data service: ' + code)


def fetch_relay_player(player_tag, timeout=15):
    tag = str(player_tag).strip().upper().removeprefix('#')
    if not re.fullmatch(r'[0289PYLQGRJCUV]{3,16}', tag):
        raise ValueError('Invalid player tag')
    timeout = max(1, min(int(timeout), 30))
    try:
        status, data = bounded_json_get(RELAY_URL + tag, timeout=timeout)
        if status != 200:
            raise RelayError('tag' if status == 404 else 'rate' if status == 429 else 'connection')
        if (not isinstance(data, dict) or data.get('tag') != '#' + tag
                or not isinstance(data.get('name'), str)
                or not isinstance(data.get('brawlers'), list) or len(data['brawlers']) > 300):
            raise RelayError()
        for row in data['brawlers']:
            if (not isinstance(row, dict) or not isinstance(row.get('name'), str)
                    or type(row.get('trophies')) is not int or row['trophies'] < 0):
                raise RelayError()
        return data
    except RelayError:
        raise
    except (HTTPJSONError, ValueError, TypeError):
        raise RelayError() from None
