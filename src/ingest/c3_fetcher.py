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

    # ── Schema export (compatible with lookup.py / query_expander.py) ───

    def export_schemas(self) -> Path:
        """Generate per-plugin/behavior JSON files from CDN data.

        Creates a directory structure compatible with lookup.py SchemaIndex:
            .cache/c3-cdn/r476/schemas/plugins/sprite.json
            .cache/c3-cdn/r476/schemas/behaviors/platform.json
            ...

        Returns the schemas root directory path.
        """
        schemas_dir = self.cache_dir / "schemas"
        marker = schemas_dir / ".exported"
        if marker.exists() and not _cache_expired(marker):
            return schemas_dir

        aces_data = self.fetch_all_aces()
        en_text = self.fetch_lang("en-US").get("text", {})
        zh_text = self.fetch_lang("zh-CN").get("text", {})

        type_map = {"plugins": "plugin", "behaviors": "behavior"}

        for addon_type, plugin_type in type_map.items():
            out_dir = schemas_dir / addon_type
            out_dir.mkdir(parents=True, exist_ok=True)

            for plugin_id, categories in aces_data.get(addon_type, {}).items():
                pid_lower = plugin_id.lower()
                en_p = en_text.get(addon_type, {}).get(pid_lower, {})
                zh_p = zh_text.get(addon_type, {}).get(pid_lower, {})

                plugin_json = {
                    "id": pid_lower,
                    "originalId": plugin_id,
                    "name_zh": zh_p.get("name", en_p.get("name", plugin_id)),
                    "name_en": en_p.get("name", plugin_id),
                    "description_zh": zh_p.get("description", ""),
                    "description_en": en_p.get("description", ""),
                    "plugin_type": plugin_type,
                    "aceCategories": list(categories.keys()),
                    "conditions": [],
                    "actions": [],
                    "expressions": [],
                    "properties": [],
                }

                for category, ace_types in categories.items():
                    for ace_type_plural, ace_type_key in [
                        ("conditions", "conditions"),
                        ("actions", "actions"),
                        ("expressions", "expressions"),
                    ]:
                        for ace in ace_types.get(ace_type_plural, []):
                            ace_id = ace.get("id", "")
                            en_ace = en_p.get(ace_type_plural, {}).get(ace_id, {})
                            zh_ace = zh_p.get(ace_type_plural, {}).get(ace_id, {})

                            if ace_type_plural == "expressions":
                                name_en = en_ace.get("translated-name", ace_id)
                                name_zh = zh_ace.get("translated-name", name_en)
                            else:
                                name_en = en_ace.get("list-name", ace_id)
                                name_zh = zh_ace.get("list-name", name_en)

                            params = []
                            for p in ace.get("params", []):
                                pid_param = p.get("id", "")
                                en_param = en_ace.get("params", {}).get(pid_param, {})
                                zh_param = zh_ace.get("params", {}).get(pid_param, {})
                                param = {
                                    "id": pid_param,
                                    "type": p.get("type", "any"),
                                    "name_en": en_param.get("name", pid_param),
                                    "name_zh": zh_param.get("name", en_param.get("name", pid_param)),
                                    "desc_en": en_param.get("desc", ""),
                                    "desc_zh": zh_param.get("desc", ""),
                                }
                                if "items" in p:
                                    param["items"] = p["items"]
                                    # Translate combo items
                                    en_items = en_ace.get("params", {}).get(pid_param, {}).get("items", {})
                                    zh_items = zh_ace.get("params", {}).get(pid_param, {}).get("items", {})
                                    if en_items:
                                        param["items_i18n"] = {
                                            k: {"en": en_items.get(k, k), "zh": zh_items.get(k, en_items.get(k, k))}
                                            for k in p["items"]
                                        }
                                params.append(param)

                            entry = {
                                "id": ace_id,
                                "name_zh": name_zh,
                                "name_en": name_en,
                                "description_zh": zh_ace.get("description", ""),
                                "description_en": en_ace.get("description", ""),
                                "display_zh": zh_ace.get("display-text", ""),
                                "display_en": en_ace.get("display-text", ""),
                                "scriptName": ace.get("scriptName", ace.get("expressionName", "")),
                                "category": category,
                                "params": params,
                            }
                            if ace.get("isTrigger"):
                                entry["isTrigger"] = True
                            if ace.get("isAsync"):
                                entry["isAsync"] = True
                            if ace.get("returnType"):
                                entry["returnType"] = ace["returnType"]

                            plugin_json[ace_type_plural].append(entry)

                # Properties from lang
                en_props = en_p.get("properties", {})
                zh_props = zh_p.get("properties", {})
                for prop_id, en_prop in en_props.items():
                    plugin_json["properties"].append({
                        "id": prop_id,
                        "name_en": en_prop.get("name", prop_id),
                        "name_zh": zh_props.get(prop_id, {}).get("name", en_prop.get("name", prop_id)),
                        "description_en": en_prop.get("desc", ""),
                        "description_zh": zh_props.get(prop_id, {}).get("desc", ""),
                    })

                # Write per-plugin file
                out_path = out_dir / f"{pid_lower}.json"
                out_path.write_text(
                    json.dumps(plugin_json, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        # Write marker
        marker.write_text(self.version)
        logger.info(f"[CDN] Exported schemas to {schemas_dir}")
        return schemas_dir

    def fetch_available_locales(self) -> list[str]:
        """Extract available locale codes from the editor's main.js.

        Parses locale patterns like "zh-CN", "ja-JP" from the JavaScript source.
        Results are cached alongside other CDN data.
        """
        import re
        cache_path = self.cache_dir / "_locales.json"
        if cache_path.exists() and not _cache_expired(cache_path):
            return json.loads(cache_path.read_text(encoding="utf-8"))

        url = f"{self.base_url}/{self.version}/main.js"
        logger.info(f"[CDN] Fetching locales from {url}")
        raw = self._http_get(url).decode("utf-8", errors="ignore")
        locales = sorted(set(re.findall(r'"([a-z]{2}-[A-Z]{2})"', raw)))
        if not locales:
            locales = ["en-US"]  # fallback
        cache_path.write_text(json.dumps(locales), encoding="utf-8")
        logger.info(f"[CDN] Found {len(locales)} locales: {', '.join(locales)}")
        return locales

    def export_terms(self) -> list[dict]:
        """Export CDN lang data as term entries for c3_terms indexing.

        Flattens the nested precompiled-zh-CN.json + en-US.json into
        TermEntry-compatible dicts: {term_key, path, category, term_type, zh, en}.
        """
        en_text = self.fetch_lang("en-US").get("text", {})
        zh_text = self.fetch_lang("zh-CN").get("text", {})

        terms = []

        def _flatten(en_obj, zh_obj, path_parts):
            if isinstance(en_obj, str):
                zh_val = zh_obj if isinstance(zh_obj, str) else en_obj
                if en_obj.strip() and zh_val.strip():
                    term_key = "text." + ".".join(path_parts)
                    # Detect category and term_type from path
                    category = path_parts[0] if path_parts else "unknown"
                    term_type = "unknown"
                    for p in path_parts:
                        if p in ("actions", "conditions", "expressions", "properties", "params"):
                            term_type = p
                            break
                    terms.append({
                        "term_key": term_key,
                        "path": ["text"] + list(path_parts),
                        "category": category,
                        "term_type": term_type,
                        "zh": zh_val,
                        "en": en_obj,
                        "full_text": f"{zh_val} | {en_obj}",
                    })
            elif isinstance(en_obj, dict):
                zh_dict = zh_obj if isinstance(zh_obj, dict) else {}
                for k, v in en_obj.items():
                    _flatten(v, zh_dict.get(k, v), list(path_parts) + [k])

        _flatten(en_text, zh_text, [])
        logger.info(f"[CDN] Exported {len(terms)} translation terms")
        return terms

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
