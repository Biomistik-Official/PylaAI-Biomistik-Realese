"""Bounded JSON transport with an entire-operation deadline and no ambient auth."""
import asyncio
import json

import aiohttp


class HTTPJSONError(RuntimeError):
    def __init__(self):
        super().__init__('JSON service unavailable')


def bounded_json_get(url, timeout=12, headers=None):
    async def read():
        limit = aiohttp.ClientTimeout(total=timeout, connect=min(3, timeout),
                                      sock_read=min(8, timeout))
        async with aiohttp.ClientSession(timeout=limit, trust_env=False) as session:
            async with session.get(url, headers=headers, allow_redirects=False) as response:
                if response.status != 200:
                    return response.status, None
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > 256 * 1024:
                        raise HTTPJSONError()
                return response.status, json.loads(body)
    try:
        return asyncio.run(read())
    except Exception:
        raise HTTPJSONError() from None
