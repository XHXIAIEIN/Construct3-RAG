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

The shared world-object ACEs (``plugins/_common``) are not on any of these
endpoints; ``export_schemas`` reads them from ``common_aces.json`` next to
``src/ingest/common_aces.py``, which explains how that file is produced.
"""
import json
import logging
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.ingest.common_aces import (
    COMMON_ADDON_ID,
    COMMON_ADDON_NAME,
    check_common_coverage,
    load_common_aces,
)


logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"
_BEIJING = timezone(timedelta(hours=8))

# CDN endpoint paths — update here if Scirra changes URL structure.
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
        version: str | None = None,
        base_url: str = "https://editor.construct.net",
        cache_dir: Path | None = None,
    ):
        if version is None:
            from src.settings import load_settings
            version = load_settings().schema.version
        self.version = version
        self.base_url = base_url.rstrip("/")
        if cache_dir is None:
            from src.settings import load_settings
            cache_dir = load_settings().schema.cache_dir
        self.cache_dir = Path(cache_dir) / self.version
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

        Structure fields from allAces (scriptName, isTrigger, isFakeTrigger,
        isLooping, isInvertible, isCompatibleWithTriggers, isAsync, returnType,
        params[].type) are merged in.

        Directory layout:
            schemas/en-US/plugins/sprite.json
            schemas/zh-CN/plugins/sprite.json
            schemas/en-US/behaviors/platform.json
            schemas/en-US/effects/alphaclamp.json
            schemas/en-US/_index.json   (localized names + file paths)
            schemas/_index.json         (language-neutral: ids, files, counts)

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

        # _common is exported through the same loop as every plugin so its
        # file has the same structural fields. Its definitions come from the
        # committed extract of the editor bundle; a language pack that names
        # a shared ACE the extract lacks stops the export rather than
        # producing untyped parameters.
        en_common = lang_texts["en-US"].get("plugins", {}).get(COMMON_ADDON_ID, {})
        if en_common:
            common_aces = load_common_aces()
            check_common_coverage(common_aces, en_common)
            aces_data["plugins"] = {**aces_data["plugins"], COMMON_ADDON_ID: common_aces}

        type_map = {"plugins": "plugin", "behaviors": "behavior"}
        # The root index is language neutral. Each locale directory gets its
        # own _index.json with display names, so one locale can be read alone.
        index_data: dict = {
            "version": self.version,
            "languages": sorted(lang_texts.keys()),
            "plugins": {}, "behaviors": {}, "effects": {},
        }
        locale_index: dict[str, dict] = {
            lang: {
                "version": self.version,
                "language": lang,
                "plugins": {}, "behaviors": {}, "effects": {},
            }
            for lang in lang_texts
        }

        # ── Plugins & Behaviors ───────────────────────────────────────────
        for addon_type, plugin_type in type_map.items():
            for plugin_id, categories in aces_data.get(addon_type, {}).items():
                pid_lower = plugin_id.lower()
                # zh-CN has no name for _common; keep the value the locale
                # index has always carried (docs/decisions/schema-index-per-locale-split.md).
                fallback_name = COMMON_ADDON_NAME if plugin_id == COMMON_ADDON_ID else plugin_id

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
                        "name": lp.get("name", fallback_name),
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
                                # The editor treats a fake trigger (On collision, On
                                # timer) as a trigger wherever structure is decided:
                                # one per event branch, never inverted, no Else after
                                # it. isTrigger carries that meaning; isFakeTrigger
                                # keeps the CDN's distinction, that the runtime tests
                                # it in sheet order instead of firing it out of band.
                                if ace.get("isTrigger") or ace.get("isFakeTrigger") or ace.get("isFastTrigger"):
                                    entry["isTrigger"] = True
                                if ace.get("isFakeTrigger"):
                                    entry["isFakeTrigger"] = True
                                if ace.get("isLooping"):
                                    entry["isLooping"] = True
                                # Both default to true in the editor, so only the
                                # exceptions are written.
                                if ace.get("isInvertible") is False:
                                    entry["isInvertible"] = False
                                if ace.get("isCompatibleWithTriggers") is False:
                                    entry["isCompatibleWithTriggers"] = False
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
                    locale_index[lang][addon_type][pid_lower] = {
                        "name": plugin_json["name"],
                        "file": f"{addon_type}/{pid_lower}.json",
                    }

                # Index entry (language-neutral). Counts are those of the
                # written file, not of allAces: deprecated ACEs were skipped
                # above, identically for every locale.
                section = "plugins" if plugin_type == "plugin" else "behaviors"
                index_entry: dict = {
                    "file": f"{addon_type}/{pid_lower}.json",
                    "conditions": len(plugin_json["conditions"]),
                    "actions": len(plugin_json["actions"]),
                    "expressions": len(plugin_json["expressions"]),
                }
                if plugin_id != COMMON_ADDON_ID:
                    # The CDN spelling of the id; _common has none.
                    index_entry = {"originalId": plugin_id, **index_entry}
                index_data[section][pid_lower] = index_entry

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
                locale_index[lang]["effects"][eid] = {
                    "name": fx_json["name"],
                    "file": f"effects/{eid}.json",
                }

            # Index effects
            if lang == "en-US":
                for item in effects_raw:
                    data = item.get("json", item)
                    eid = data.get("id", "")
                    if l_effects.get(eid):
                        index_data["effects"][eid] = {
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

        # ── Write _index.json (root + one per locale) ─────────────────────
        (schemas_dir / "_index.json").write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        for lang, data in locale_index.items():
            (schemas_dir / lang / "_index.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )

        marker.write_text(self.version)
        logger.info(f"[CDN] Exported schemas to {schemas_dir}")
        return schemas_dir

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

    def export_to_data(self, data_dir: Path) -> dict[str, Path]:
        """Refresh the committed ``data/`` layout from the exports.

        Runs every export first; each is cached until the weekly expiry, so a
        repeated call copies without fetching. Every target directory is
        replaced whole, so an addon or example that left the CDN also leaves
        the commit. Cache markers (dot-files) stay behind. This is the one
        place that knows how the cache maps onto ``data/``; ``scripts/init.py``
        and the update workflow both call it.

        Returns the refreshed target directories keyed by their name.
        """
        schemas_dir = self.export_schemas()
        lang_dir = self.export_lang()
        ts_dir = self.export_ts_defs()
        targets = {
            "c3-schemas": data_dir / "c3-schemas",
            "c3-examples": data_dir / "c3-examples",
            "c3-lang": data_dir / "c3-lang",
            "c3-ts-defs": data_dir / "c3-ts-defs",
        }

        def _replace(target: Path, source: Path) -> None:
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(
                source,
                target,
                ignore=lambda _dir, names: [n for n in names if n.startswith(".")],
            )

        _replace(targets["c3-schemas"], schemas_dir)
        _replace(targets["c3-examples"], schemas_dir.parent / "examples")
        _replace(targets["c3-lang"], lang_dir)

        # ts-defs: only the interface files and the class listing, not the
        # download bookkeeping the export leaves beside them.
        ts_target = targets["c3-ts-defs"]
        if ts_target.exists():
            shutil.rmtree(ts_target)
        for src_file in ts_dir.rglob("*.d.ts"):
            dst = ts_target / src_file.relative_to(ts_dir)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
        autocomplete = ts_dir / "autocomplete-data.json"
        if autocomplete.exists():
            ts_target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(autocomplete, ts_target / autocomplete.name)

        logger.info(f"[CDN] Refreshed {data_dir} from {self.version} exports")
        return targets

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

    def export_lang(self, locales: tuple[str, ...] = ("en-US", "zh-CN")) -> Path:
        """Save the raw precompiled language packs as readable JSON.

        The CDN serves them minified on one line. Re-serialising with
        indentation and without ASCII escaping puts every string on its own
        line, so two releases can be compared with a plain text diff.

        Returns the output directory containing ``{locale}.json`` files.
        """
        out_dir = self.cache_dir / "lang"
        out_dir.mkdir(parents=True, exist_ok=True)
        for locale in locales:
            data = self.fetch_lang(locale)
            (out_dir / f"{locale}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
        return out_dir

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
