"""
Pyla-Biomistik — EU Proxy Module
Автоматически находит рабочий бесплатный европейский прокси.
Включается через use_eu_proxy = true в cfg/general_config.toml
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Optional

# ──────────────────────────────────────────────────────────
# Внутренний кэш
# ──────────────────────────────────────────────────────────
_proxy_lock = threading.Lock()
_cached_proxy: Optional[str] = None
_proxy_last_fetched: float = 0.0
_PROXY_CACHE_TTL = 3600.0          # Обновлять список раз в час
_proxy_fetch_attempted: bool = False

# Европейские страны для фильтрации прокси
_EU_COUNTRIES = "DE,NL,FR,PL,CZ,AT,BE,SE,FI,DK,NO,SK,HU,RO,BG,HR"

# API для получения списков прокси (с приоритетом)
_PROXY_APIS = [
    # GeoNode — самый надёжный
    (
        "geonode",
        f"https://proxylist.geonode.com/api/proxy-list"
        f"?limit=100&page=1&sort_by=lastChecked&sort_type=desc"
        f"&filterUpTime=70&country={_EU_COUNTRIES}&protocols=http,socks4,socks5",
    ),
    # ProxyScrape — резерв
    (
        "proxyscrape",
        f"https://api.proxyscrape.com/v2/"
        f"?request=getproxies&protocol=http&timeout=5000"
        f"&country={_EU_COUNTRIES}&simplified=true",
    ),
    # Fallback — любые EU HTTP
    (
        "proxyscrape_socks5",
        f"https://api.proxyscrape.com/v2/"
        f"?request=getproxies&protocol=socks5&timeout=5000"
        f"&country={_EU_COUNTRIES}&simplified=true",
    ),
]

# Тестовый URL — проверяем что прокси достаёт Telegram
_TEST_URL = "https://api.telegram.org"
_TEST_TIMEOUT = 6.0


# ──────────────────────────────────────────────────────────
# Чтение конфига
# ──────────────────────────────────────────────────────────

def _is_proxy_enabled() -> bool:
    try:
        from common.utils import load_toml_as_dict
        cfg = load_toml_as_dict("cfg/general_config.toml")
        return bool(cfg.get("use_eu_proxy", False))
    except Exception:
        return False


# ──────────────────────────────────────────────────────────
# Получение списка прокси
# ──────────────────────────────────────────────────────────

def _fetch_geonode(url: str) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
        proxies = []
        for item in data.get("data", []):
            host = item.get("ip", "").strip()
            port = str(item.get("port", "")).strip()
            protocols = item.get("protocols") or ["http"]
            proto = protocols[0] if protocols else "http"
            if host and port:
                proxies.append(f"{proto}://{host}:{port}")
        return proxies
    except Exception:
        return []


def _fetch_proxyscrape(url: str, proto: str = "http") -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            lines = resp.read().decode().strip().splitlines()
        return [f"{proto}://{line.strip()}" for line in lines if line.strip() and ":" in line]
    except Exception:
        return []


def _collect_proxy_candidates() -> list[str]:
    """Собирает список кандидатов из всех источников."""
    seen: set[str] = set()
    result: list[str] = []

    for name, url in _PROXY_APIS:
        if name == "geonode":
            batch = _fetch_geonode(url)
        elif name == "proxyscrape_socks5":
            batch = _fetch_proxyscrape(url, "socks5")
        else:
            batch = _fetch_proxyscrape(url, "http")

        for p in batch:
            if p not in seen:
                seen.add(p)
                result.append(p)

    return result


# ──────────────────────────────────────────────────────────
# Тестирование прокси
# ──────────────────────────────────────────────────────────

def _test_proxy(proxy_url: str, timeout: float = _TEST_TIMEOUT) -> bool:
    """Проверяет, что прокси отвечает и достаёт api.telegram.org."""
    try:
        handler = urllib.request.ProxyHandler(
            {"http": proxy_url, "https": proxy_url}
        )
        opener = urllib.request.build_opener(handler)
        opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        with opener.open(_TEST_URL, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def _find_working_proxy() -> Optional[str]:
    print("[Proxy] Получение списка EU прокси...")
    candidates = _collect_proxy_candidates()

    if not candidates:
        print("[Proxy] Не удалось получить список прокси — работаем без прокси.")
        return None

    test_batch = candidates[:30]
    print(f"[Proxy] Тестирование {len(test_batch)} прокси (ищем рабочий EU)...")

    for proxy in test_batch:
        if _test_proxy(proxy):
            print(f"[Proxy] ✓ Рабочий EU прокси найден: {proxy}")
            return proxy

    print("[Proxy] Ни один прокси не прошёл тест — работаем без прокси.")
    return None


# ──────────────────────────────────────────────────────────
# Публичный API
# ──────────────────────────────────────────────────────────

def get_proxy_url() -> Optional[str]:
    """
    Возвращает рабочий EU прокси URL (строку), или None.
    Прокси включается через use_eu_proxy = true в cfg/general_config.toml.
    Результат кэшируется на 1 час.
    """
    if not _is_proxy_enabled():
        return None

    global _cached_proxy, _proxy_last_fetched, _proxy_fetch_attempted
    now = time.time()

    with _proxy_lock:
        # Вернуть кэш если ещё свежий
        if _proxy_fetch_attempted and now - _proxy_last_fetched < _PROXY_CACHE_TTL:
            return _cached_proxy

        # Найти рабочий прокси
        proxy = _find_working_proxy()
        _cached_proxy = proxy
        _proxy_last_fetched = now
        _proxy_fetch_attempted = True
        return proxy


def get_aiohttp_proxy() -> Optional[str]:
    """
    Возвращает прокси URL в формате для aiohttp.
    socks5:// прокси конвертируются в socks5h:// для корректного DNS.
    """
    proxy = get_proxy_url()
    if proxy and proxy.startswith("socks5://"):
        return proxy.replace("socks5://", "socks5h://", 1)
    return proxy


def get_urllib_proxies() -> dict[str, str]:
    """Возвращает словарь прокси для urllib.request."""
    proxy = get_proxy_url()
    if not proxy:
        return {}
    return {"http": proxy, "https": proxy}


def invalidate_proxy_cache():
    """Сбросить кэш прокси (принудительно найти новый при следующем запросе)."""
    global _proxy_fetch_attempted
    with _proxy_lock:
        _proxy_fetch_attempted = False


def refresh_proxy_async():
    """Обновить прокси в фоновом потоке (не блокирует)."""
    if not _is_proxy_enabled():
        return
    invalidate_proxy_cache()
    threading.Thread(target=get_proxy_url, daemon=True, name="ProxyRefresh").start()
