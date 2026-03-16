"""Fetch Construct 3 data from official CDN with local caching.

Cache expires every Wednesday 08:00 Beijing time (UTC+8), aligned with
Scirra's typical Tuesday-evening (UK time) release schedule. Within one
cache period, each file is fetched from CDN at most once.

Endpoints:
    plugins/allAces.json         — all plugin ACE definitions
    behaviors/allAces.json       — all behavior ACE definitions
    effects/allEffects.json      — all effects + shader code
    loader/lang/precompiled-{locale}.json — bilingual names/descriptions
    media/example-project-data.json      — example project metadata
    plugins/pluginList.json      — plugin ID → path mapping
    behaviors/behaviorList.json  — behavior ID → path mapping
    versions.json                — all release versions
"""
import json
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"
_BEIJING = timezone(timedelta(hours=8))

# CDN endpoint paths — update here if Scirra changes URL structure.
# See data/c3-cdn-samples/ for expected response schemas.
ENDPOINTS = {
    "versions":      "versions.json",
    "plugin_aces":   "plugins/allAces.json",
    "behavior_aces": "behaviors/allAces.json",
    "effects":       "effects/allEffects.json",
    "lang":          "loader/lang/precompiled-{locale}.json",
    "examples":      "media/example-project-data.json",
    "plugin_list":   "plugins/pluginList.json",
    "behavior_list": "behaviors/behaviorList.json",
}


def _cache_expired(cache_path: Path) -> bool:
    """Check if cache file is from before the most recent Wednesday 08:00 Beijing time.

    Scirra (UK-based) releases updates on Tuesday evenings.
    Wednesday 08:00 CST = Wednesday 00:00 UTC, giving them a full evening.
    """
    if not cache_path.exists():
        return True
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=_BEIJING)
    now = datetime.now(_BEIJING)
    # Find the most recent Wednesday 08:00 Beijing time (weekday 2 = Wednesday)
    days_since_wed = (now.weekday() - 2) % 7
    last_wed = now.replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=days_since_wed)
    if last_wed > now:
        last_wed -= timedelta(days=7)
    return mtime < last_wed


class C3Fetcher:
    """Fetch and cache Construct 3 CDN data."""

    def __init__(
        self,
        version: str = "r476",
        base_url: str = "https://editor.construct.net",
        cache_dir: Path | None = None,
    ):
        self.version = version
        self.base_url = base_url.rstrip("/")
        if cache_dir is None:
            from src.config import C3_CACHE_DIR
            cache_dir = C3_CACHE_DIR
        self.cache_dir = Path(cache_dir) / version
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _http_get(self, url: str) -> bytes:
        """Fetch URL with browser User-Agent (CDN returns 403 without it)."""
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    @staticmethod
    def _strip_bom(raw: bytes) -> bytes:
        """Remove UTF-8 BOM if present."""
        return raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw

    def fetch(self, path: str, force: bool = False) -> dict | list:
        """Fetch a JSON endpoint, using local cache if fresh.

        Args:
            path: Relative path under the version URL (e.g. "plugins/allAces.json")
            force: Skip cache and always fetch from CDN
        """
        cache_path = self.cache_dir / path.replace("/", "_")
        if not force and cache_path.exists() and not _cache_expired(cache_path):
            raw = cache_path.read_bytes()
        else:
            url = f"{self.base_url}/{self.version}/{path}"
            logger.info(f"[CDN] Fetching {url}")
            raw = self._http_get(url)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(raw)
        return json.loads(self._strip_bom(raw))

    def get_latest_stable_version(self) -> str:
        """Query versions.json for the latest stable release name."""
        url = f"{self.base_url}/versions.json"
        raw = self._http_get(url)
        versions = json.loads(self._strip_bom(raw))
        for v in versions:
            if v.get("branchName") == "Stable":
                return v["releaseName"]
        return self.version

    # ── Convenience methods ──────────────────────────────────────────────

    def fetch_all_aces(self) -> dict:
        """Return {"plugins": {...}, "behaviors": {...}} ACE definitions."""
        return {
            "plugins": self.fetch(ENDPOINTS["plugin_aces"]),
            "behaviors": self.fetch(ENDPOINTS["behavior_aces"]),
        }

    def fetch_lang(self, locale: str = "en-US") -> dict:
        """Fetch precompiled language file (en-US or zh-CN)."""
        return self.fetch(ENDPOINTS["lang"].format(locale=locale))

    def fetch_effects(self) -> list:
        """Fetch all effect definitions."""
        data = self.fetch(ENDPOINTS["effects"])
        return data.get("all", data) if isinstance(data, dict) else data

    def fetch_examples(self) -> list:
        """Fetch example project metadata list."""
        data = self.fetch(ENDPOINTS["examples"])
        return data.get("projects", data) if isinstance(data, dict) else data

    def fetch_plugin_list(self) -> dict:
        """Fetch plugin ID → path mapping."""
        data = self.fetch(ENDPOINTS["plugin_list"])
        return data.get("pluginList", data) if isinstance(data, dict) else data

    def fetch_behavior_list(self) -> dict:
        """Fetch behavior ID → path mapping."""
        data = self.fetch(ENDPOINTS["behavior_list"])
        return data.get("behaviorList", data) if isinstance(data, dict) else data
