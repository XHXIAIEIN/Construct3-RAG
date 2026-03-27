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
import urllib.error
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
    "offline":       "offline.json",
    "autocomplete":  "media/autocomplete-data.json",
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
            try:
                raw = self._http_get(url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # Patch versions (e.g. r476.2) don't have their own CDN
                    # directory; fall back to the root path (latest stable).
                    fallback_url = f"{self.base_url}/{path}"
                    logger.warning(f"[CDN] 404 for {url}, falling back to {fallback_url}")
                    raw = self._http_get(fallback_url)
                else:
                    raise
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

    # ── Schema export (per-language, CDN-native field names) ─────────────

    def export_schemas(self) -> Path:
        """Generate per-language schema files from CDN data.

        Merges allAces.json (structural) + precompiled-{locale}.json (text) into
        per-language files that preserve CDN field names:
          - conditions/actions: list-name, display-text, description
          - expressions: translated-name, description
          - params: name, desc, items (object keyed by param id)

        Structure fields from allAces (scriptName, isTrigger, isAsync, returnType,
        params[].type) are merged in.

        Directory layout:
            schemas/en/plugins/sprite.json
            schemas/zh/plugins/sprite.json
            schemas/en/behaviors/platform.json
            schemas/en/effects/alphaclamp.json
            schemas/en/editor/index.json
            schemas/_index.json   (language-neutral)

        Returns the schemas root directory path.
        """
        schemas_dir = self.cache_dir / "schemas"
        marker = schemas_dir / ".exported"
        if marker.exists() and not _cache_expired(marker):
            return schemas_dir

        aces_data = self.fetch_all_aces()
        lang_texts = {
            "en-US": self.fetch_lang("en-US").get("text", {}),
            "zh-CN": self.fetch_lang("zh-CN").get("text", {}),
        }

        type_map = {"plugins": "plugin", "behaviors": "behavior"}
        all_locales = self.fetch_available_locales()
        index_data: dict = {
            "version": self.version,
            "languages": sorted(lang_texts.keys()),
            "supported_languages": all_locales,
            "plugins": {}, "behaviors": {}, "effects": {},
        }

        # ── Plugins & Behaviors ───────────────────────────────────────────
        for addon_type, plugin_type in type_map.items():
            for plugin_id, categories in aces_data.get(addon_type, {}).items():
                pid_lower = plugin_id.lower()

                # Skip deprecated addons (absent from zh-CN lang)
                zh_p = lang_texts["zh-CN"].get(addon_type, {}).get(pid_lower, {})
                if not zh_p:
                    continue

                for lang, text in lang_texts.items():
                    lp = text.get(addon_type, {}).get(pid_lower, {})
                    out_dir = schemas_dir / lang / addon_type
                    out_dir.mkdir(parents=True, exist_ok=True)

                    plugin_json = {
                        "id": pid_lower,
                        "name": lp.get("name", plugin_id),
                        "description": lp.get("description", ""),
                        "type": plugin_type,
                        "aceCategories": lp.get("aceCategories", {}),
                        "conditions": [],
                        "actions": [],
                        "expressions": [],
                        "properties": {},
                    }

                    for category, ace_types in categories.items():
                        for ace_type_plural in ("conditions", "actions", "expressions"):
                            for ace in ace_types.get(ace_type_plural, []):
                                ace_id = ace.get("id", "")

                                # Skip deprecated ACEs (absent from zh-CN)
                                if not zh_p.get(ace_type_plural, {}).get(ace_id):
                                    continue

                                l_ace = lp.get(ace_type_plural, {}).get(ace_id, {})

                                # Merge params: type from allAces + name/desc from lang
                                params: dict = {}
                                for p in ace.get("params", []):
                                    pid_param = p.get("id", "")
                                    l_param = l_ace.get("params", {}).get(pid_param, {})
                                    param_entry: dict = {
                                        "type": p.get("type", "any"),
                                        "name": l_param.get("name", pid_param),
                                        "desc": l_param.get("desc", ""),
                                    }
                                    if "items" in p:
                                        # Merge item labels from lang
                                        l_items = l_param.get("items", {})
                                        if l_items:
                                            param_entry["items"] = l_items
                                        else:
                                            param_entry["items"] = {k: k for k in p["items"]}
                                        if p.get("initialValue"):
                                            param_entry["initialValue"] = p["initialValue"]
                                    params[pid_param] = param_entry

                                entry: dict = {
                                    "id": ace_id,
                                    "scriptName": ace.get("scriptName", ace.get("expressionName", "")),
                                    "category": category,
                                }
                                # Use CDN-native field names
                                if ace_type_plural == "expressions":
                                    entry["translated-name"] = l_ace.get("translated-name", ace_id)
                                else:
                                    entry["list-name"] = l_ace.get("list-name", ace_id)
                                    entry["display-text"] = l_ace.get("display-text", "")
                                entry["description"] = l_ace.get("description", "")
                                if params:
                                    entry["params"] = params
                                if ace.get("isTrigger"):
                                    entry["isTrigger"] = True
                                if ace.get("isAsync"):
                                    entry["isAsync"] = True
                                if ace.get("returnType"):
                                    entry["returnType"] = ace["returnType"]

                                plugin_json[ace_type_plural].append(entry)

                    # Properties — keep CDN dict structure {prop_id: {name, desc, ...}}
                    plugin_json["properties"] = lp.get("properties", {})

                    out_path = out_dir / f"{pid_lower}.json"
                    out_path.write_text(
                        json.dumps(plugin_json, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                # Index entry (language-neutral)
                en_p = lang_texts["en-US"].get(addon_type, {}).get(pid_lower, {})
                section = "plugins" if plugin_type == "plugin" else "behaviors"
                c_count = sum(len(at.get("conditions", [])) for at in categories.values())
                a_count = sum(len(at.get("actions", [])) for at in categories.values())
                e_count = sum(len(at.get("expressions", [])) for at in categories.values())
                index_data[section][pid_lower] = {
                    "originalId": plugin_id,
                    "name_en": en_p.get("name", plugin_id),
                    "name_zh": zh_p.get("name", en_p.get("name", plugin_id)),
                    "file": f"{addon_type}/{pid_lower}.json",
                    "conditions": c_count,
                    "actions": a_count,
                    "expressions": e_count,
                }

        # ── _common (shared ACEs for World instances) ─────────────────────
        en_common = lang_texts["en-US"].get("plugins", {}).get("_common", {})
        zh_common = lang_texts["zh-CN"].get("plugins", {}).get("_common", {})
        if en_common:
            for lang in ("en-US", "zh-CN"):
                lc = lang_texts[lang].get("plugins", {}).get("_common", {})
                common_json: dict = {
                    "id": "_common",
                    "name": lc.get("name", "Common"),
                    "description": lc.get("description", ""),
                    "type": "plugin",
                    "aceCategories": lc.get("aceCategories", {}),
                    "conditions": [],
                    "actions": [],
                    "expressions": [],
                    "properties": lc.get("properties", {}),
                }
                for ace_type_plural in ("conditions", "actions", "expressions"):
                    en_aces = en_common.get(ace_type_plural, {})
                    zh_aces = zh_common.get(ace_type_plural, {})
                    l_aces = lc.get(ace_type_plural, {})
                    for ace_id in en_aces:
                        if not zh_aces.get(ace_id):
                            continue
                        l_ace = l_aces.get(ace_id, en_aces[ace_id])
                        # Build params from lang (allAces doesn't include _common)
                        params = {}
                        for pid_param, l_param in l_ace.get("params", {}).items():
                            params[pid_param] = {
                                "type": "object",
                                "name": l_param.get("name", pid_param),
                                "desc": l_param.get("desc", ""),
                            }
                        entry: dict = {
                            "id": ace_id,
                            "scriptName": ace_id,
                            "category": "common",
                        }
                        if ace_type_plural == "expressions":
                            entry["translated-name"] = l_ace.get("translated-name", ace_id)
                        else:
                            entry["list-name"] = l_ace.get("list-name", ace_id)
                            entry["display-text"] = l_ace.get("display-text", "")
                        entry["description"] = l_ace.get("description", "")
                        if params:
                            entry["params"] = params
                        common_json[ace_type_plural].append(entry)

                out_dir = schemas_dir / lang / "plugins"
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "_common.json").write_text(
                    json.dumps(common_json, ensure_ascii=False, indent=2), encoding="utf-8",
                )

            c_count = len(common_json["conditions"])
            a_count = len(common_json["actions"])
            e_count = len(common_json["expressions"])
            logger.info(f"[CDN] Exported _common: {c_count}C {a_count}A {e_count}E")
            index_data["plugins"]["_common"] = {
                "name_en": en_common.get("name", "Common"),
                "name_zh": zh_common.get("name", "公共"),
                "file": "plugins/_common.json",
                "conditions": c_count, "actions": a_count, "expressions": e_count,
            }

        # ── Effects ───────────────────────────────────────────────────────
        effects_raw = self.fetch_effects()
        for lang, text in lang_texts.items():
            out_dir = schemas_dir / lang / "effects"
            out_dir.mkdir(parents=True, exist_ok=True)
            l_effects = text.get("effects", {})
            for item in effects_raw:
                data = item.get("json", item)
                eid = data.get("id", "")
                l_fx = l_effects.get(eid, {})
                if not l_fx:
                    continue
                # Merge structural (allEffects) + text (lang)
                fx_json: dict = {
                    "id": eid,
                    "name": l_fx.get("name", eid),
                    "description": l_fx.get("description", ""),
                    "category": data.get("category", ""),
                    "blends-background": data.get("blends-background", False),
                    "cross-sampling": data.get("cross-sampling", False),
                    "animated": data.get("animated", False),
                    "parameters": [],
                }
                for p in data.get("parameters", []):
                    pid_param = p.get("id", "")
                    l_param = l_fx.get("parameters", {}).get(pid_param, {})
                    fx_json["parameters"].append({
                        "id": pid_param,
                        "type": p.get("type", "float"),
                        "name": l_param.get("name", pid_param),
                        "desc": l_param.get("desc", ""),
                    })
                (out_dir / f"{eid}.json").write_text(
                    json.dumps(fx_json, ensure_ascii=False, indent=2), encoding="utf-8",
                )

            # Index effects
            if lang == "en-US":
                for item in effects_raw:
                    data = item.get("json", item)
                    eid = data.get("id", "")
                    en_fx = l_effects.get(eid, {})
                    zh_fx = lang_texts["zh-CN"].get("effects", {}).get(eid, {})
                    if en_fx:
                        index_data["effects"][eid] = {
                            "name_en": en_fx.get("name", eid),
                            "name_zh": zh_fx.get("name", en_fx.get("name", eid)),
                            "file": f"effects/{eid}.json",
                            "category": data.get("category", ""),
                        }

        logger.info(f"[CDN] Exported {len(index_data['effects'])} effects")

        # ── Examples (per-language, per-file) ─────────────────────────────
        try:
            examples_raw = self.fetch_examples()

            # Per-lang data sources:
            #   - ui.start-page.projects.{id} → {name, description}  (localized title/desc)
            #   - ui.example-browser.filters   → tag label translations
            lang_projects: dict[str, dict] = {}
            tag_maps: dict[str, dict[str, str]] = {}
            for lang, text in lang_texts.items():
                lang_projects[lang] = text.get("ui", {}).get("start-page", {}).get("projects", {})
                filters = text.get("ui", {}).get("example-browser", {}).get("filters", {})
                tmap: dict[str, str] = {}
                for section_key in ("level", "category", "genre", "tag"):
                    section = filters.get(section_key, {})
                    for k, v in section.items():
                        if k != "section-title" and isinstance(v, str):
                            tmap[k] = v
                tag_maps[lang] = tmap

            examples_dir = schemas_dir.parent / "examples"
            for lang in lang_texts:
                out_dir = examples_dir / lang
                out_dir.mkdir(parents=True, exist_ok=True)
                tmap = tag_maps.get(lang, {})
                projects = lang_projects.get(lang, {})
                for ex in examples_raw:
                    eid = ex.get("id", "")
                    if not eid:
                        continue
                    lp = projects.get(eid, {})
                    entry: dict = {"id": eid}
                    # Localized name and description from lang
                    entry["name"] = lp.get("name", ex.get("name", eid))
                    if lp.get("description"):
                        entry["description"] = lp["description"]
                    if ex.get("tags"):
                        entry["tags"] = [tmap.get(t, t) for t in ex["tags"]]
                    if ex.get("used-addons"):
                        entry["used-addons"] = ex["used-addons"]
                    entry["open"] = f"https://editor.construct.net/#open={eid}"
                    (out_dir / f"{eid}.json").write_text(
                        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8",
                    )

            index_data["examples"] = len(examples_raw)
            logger.info(f"[CDN] Exported {len(examples_raw)} examples (per-language)")
        except Exception as e:
            logger.warning(f"[CDN] Failed to export examples: {e}")

        # ── Write _index.json ─────────────────────────────────────────────
        (schemas_dir / "_index.json").write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8",
        )

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

    def fetch_raw(self, path: str, force: bool = False) -> bytes:
        """Fetch a raw file (text/binary), using local cache if fresh."""
        cache_path = self.cache_dir / path.replace("/", "_")
        if not force and cache_path.exists() and not _cache_expired(cache_path):
            return cache_path.read_bytes()
        url = f"{self.base_url}/{self.version}/{path}"
        logger.info(f"[CDN] Fetching {url}")
        try:
            raw = self._http_get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                fallback_url = f"{self.base_url}/{path}"
                logger.warning(f"[CDN] 404 for {url}, falling back to {fallback_url}")
                raw = self._http_get(fallback_url)
            else:
                raise
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(raw)
        return raw

    def export_ts_defs(self) -> Path:
        """Download TypeScript definitions from CDN and save to ts-defs directory.

        Uses offline.json to discover .d.ts file paths, downloads each once
        and caches locally. Adds a small delay between requests to avoid
        overwhelming the CDN.

        Returns the ts-defs output directory path.
        """
        import time

        ts_dir = self.cache_dir / "ts-defs"
        marker = ts_dir / ".exported"
        if marker.exists() and not _cache_expired(marker):
            return ts_dir

        # Get file list from offline.json
        offline = self.fetch(ENDPOINTS["offline"])
        dts_paths = [f for f in offline.get("fileList", []) if f.endswith(".d.ts")]
        logger.info(f"[CDN] Found {len(dts_paths)} .d.ts files")

        fetched = 0
        for dts_path in dts_paths:
            out_path = ts_dir / dts_path
            if out_path.exists():
                continue  # already cached
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                raw = self.fetch_raw(dts_path)
                # Strip BOM
                raw = self._strip_bom(raw)
                out_path.write_bytes(raw)
                fetched += 1
                # Throttle: 100ms between requests to be respectful
                if fetched % 10 == 0:
                    time.sleep(1)
                elif fetched > 0:
                    time.sleep(0.1)
            except Exception as e:
                logger.warning(f"[CDN] Failed to fetch {dts_path}: {e}")

        # Also fetch autocomplete-data.json
        try:
            autocomplete = self.fetch(ENDPOINTS["autocomplete"])
            (ts_dir / "autocomplete-data.json").write_text(
                json.dumps(autocomplete, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[CDN] Failed to fetch autocomplete-data: {e}")

        marker.write_text(self.version)
        logger.info(f"[CDN] Exported {fetched} new .d.ts files to {ts_dir}")
        return ts_dir

    def ensure_ready(self) -> None:
        """Ensure CDN data is fetched and exported. Safe to call multiple times.

        Called automatically on first use in api.py and indexer.py.
        Fetches all required CDN endpoints and exports schemas for lookup.py.
        """
        self.export_schemas()
        logger.info(f"[CDN] Ready: {self.version}")

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
