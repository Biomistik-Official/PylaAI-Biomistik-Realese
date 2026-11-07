# Player loading by tag

The default `player_source = "relay"` needs only a player tag. The setup wizard sends the tag to the Pyla HTTPS service and loads the public name, owned brawlers, levels and trophies. No game password or developer account is required. This does not log into the game itself.

The endpoint is public. Its address grants profile reads only; it is not an SSH login and contains no server credentials. Source code is public too. A shared secret inside a downloadable application could be extracted and is not used.

## Client settings

Under Integrations -> Brawl Stars API choose **По тегу · без регистрации** (default) or **Свой Brawl Stars API**. Direct mode retains local developer credentials/token handling; only that mode contacts the developer portal. Existing settings without a source default to relay and retain their stored secrets locally. Tags are independent for each profile.

Relay data may be cached for 180 seconds. Short rate limits normally clear within a minute; the daily quota clears at 00:00 UTC. On failure the existing queue/data remains available. No automatic fallback sends stored developer credentials to the relay.

## Operator deployment

Templates: `server/pyla-player-relay.service`, `server/nginx-player-relay.conf` and `server/requirements.txt`. Install Python 3.10+ with venv support.

1. Create non-login system user/group `pyla-relay`. Deploy `server/player_relay.py` as `/opt/pyla-player-relay/player_relay.py` and `common/http_json.py`, `common/__init__.py` under `/opt/pyla-player-relay/common/`. Keep code root-owned.
2. Create a separate venv at `/opt/pyla-player-relay/venv` and install the server requirements there. Game dependencies are not needed.
3. As root, create `/etc/pyla-player-relay.env` with mode 0600 containing `BRAWL_STARS_API_TOKEN=<server-only-token>`. Supply the token through a trusted server-side channel; never put it in Git, command-line arguments, screenshots or client configuration. Whitelist the server egress IP at Supercell.
4. Install the systemd template. Keep **one worker** with four threads; process-local limits require this. systemd creates the private state directory for the persisted quota database.
5. Use a dedicated hostname and valid certificate. Update both the nginx template and `common/player_client.py` if changing the hostname. Bootstrap HTTP ACME validation before enabling the TLS server; test nginx before reload.
6. Enable the service and reload nginx. Verify a tag request, invalid tags/routes, service ownership, secret permissions and existing hosted sites. The Gunicorn port must be reachable only through loopback.

Limits: 30 valid requests/IP per fixed minute; 20 upstream attempts/rolling minute; 2000 upstream attempts/UTC day persisted across restarts; two simultaneous upstream calls. Successful profiles cache for 180s (max 512 entries), not-found profiles for 30s. Upstream failures trigger a short global cooldown (longer for authentication/rate errors). Replies whitelist profile/brawler fields; no cookies, developer credentials, private files or arbitrary upstream fields are forwarded.

Each HTTP operation has a total deadline and 256 KiB decompressed response cap. The transport disables ambient netrc credentials/proxies and redirects. nginx adds connection/rate limits; systemd imposes CPU/memory/process bounds, a read-only system filesystem and home-directory isolation.

## Operations and rollback

Inspect `systemctl status pyla-player-relay` and its journal without printing the environment. Certificate renewals need an nginx reload hook; validate renewal config after hostname changes. The template leaves HTTP ACME challenges available.

To roll back, disable/stop only `pyla-player-relay.service`, remove its own nginx site symlink, test nginx and reload. Existing Money services/configuration are separate. Clients can choose direct mode during a relay outage. A dedicated Supercell key is recommended when independent quota/rotation is needed; replacing the root-only environment file and restarting this service does not require changing the client.
