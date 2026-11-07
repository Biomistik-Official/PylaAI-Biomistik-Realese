# Amethyst tag-only account lookup check

Checked 2026-11-07 at commit `2cbd4da7351dbd42fff822a75eb12aa748902bbc` of [kittenello/Amethyst](https://github.com/kittenello/Amethyst).

The active web UI uses `fetch_brawltracker_player` in [webapp/server.py](https://github.com/kittenello/Amethyst/blob/2cbd4da7351dbd42fff822a75eb12aa748902bbc/webapp/server.py#L167). It downloads the public BrawlTracker profile HTML, parses the player name and brawler cards with regular expressions, and extracts trophies and power. It needs no developer key on the client. Legacy official API helpers still exist in its `utils.py`; those are not the web UI mechanism.

## Live parser checks

The inspected parser and its two text helpers were executed in isolation on complete, live HTML responses using the repository's request headers and verified TLS. No setup executable, bot, remote-control integration or game worker was launched.

| Public tag | Parsed brawlers | Official relay brawlers | Name/total trophies match | Brawler trophies/power differences |
| --- | ---: | ---: | --- | ---: |
| RJC8VGR2P | 75 | 75 | Yes | 0 |
| VLQPVPY | 108 | 108 | Yes | 0 |

These checks establish that its parser worked for these two responses at the time of the check. They do not establish long-term availability or data freshness guarantees.

## Tradeoffs

- BrawlTracker parsing could remove the need to operate a relay/key. The third-party site remains a dependency.
- It matches exact HTML class strings and image attributes; a layout change can break account loading. It has no documented player API contract in the inspected code.
- The downloaded profiles were approximately 0.50 and 0.84 million characters; the JSON relay needs a smaller filtered payload.
- Its full transport fallback includes `verify=False` in `_requests_get_text`. That fallback was not executed or copied into Pyla; disabling certificate checks is unsuitable for our client.
- The parser returns brawler names/trophies/power without official brawler IDs and uses `total_trophies` rather than the official `trophies` field. Adapting it requires field mapping and tests.

The approved relay implementation remains the default. The working Amethyst approach is documented as an alternative, not silently introduced as a second data source.
