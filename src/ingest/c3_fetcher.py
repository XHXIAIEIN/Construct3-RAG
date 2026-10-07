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
    offline.json                 — the release's file list, read for its .d.ts paths
    media/autocomplete-data.json — scripting class to member listing
    versions.json                — the current Beta, Stable and LTS releases
    main.js, plugins/allEditorPlugins.js, behaviors/allEditorBehaviors.js
                                 — editor bundles, read for SetIsDeprecated

Every endpoint but versions.json is served per release, in a directory named
after the release with the dot of a patch release written as a dash: r495.2
is ``r495-2/``, r503 is ``r503/``. The root serves whichever release is stable
now, so it is never read for a release's files: a 404 in the release
directory stops the fetch instead of mixing in another release. The cache
stays keyed by the release name, ``{cache_dir}/r495.2/``.

The shared world-object ACEs (``plugins/_common``) are not on any of these
endpoints; ``export_schemas`` reads them from ``common_aces.json`` next to
``src/ingest/common_aces.py``, which explains how that file is produced.
Which addons are deprecated is read from the editor bundles on every export;
``src/ingest/deprecated_addons.py`` explains how.
"""
import json
import logging
import re
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.ingest.common_aces import (
    COMMON_ADDON_ID,
    COMMON_ADDON_NAME,
    build_common_properties,
    check_common_coverage,
    load_common_aces,
    load_common_availability,
)
from src.ingest.deprecated_addons import ADDON_KINDS, deprecated_ids, deprecated_list, extract_deprecation
from src.lookup.schema_layout import SCHEMA_ACE_TYPES, SCHEMA_LOCALES


logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"
_BEIJING = timezone(timedelta(hours=8))
# A release as versions.json names it: r503, r495.2.
_RELEASE_NAME = re.compile(r"r\d+(?:\.\d+)?")

# CDN endpoint paths — update here if Scirra changes URL structure.
# versions.json is at the CDN root; every other path is under the release directory.
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
    "main_js":       "main.js",
    "plugin_js":     "plugins/allEditorPlugins.js",
    "behavior_js":   "behaviors/allEditorBehaviors.js",
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


def _http_get(url: str) -> bytes:
    """Fetch URL with browser User-Agent (CDN returns 403 without it)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _strip_bom(raw: bytes) -> bytes:
    """Remove UTF-8 BOM if present."""
    return raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw


def _write_json(path: Path, data: dict | list) -> None:
    """Write ``data`` as the indented, unescaped UTF-8 JSON every export file uses."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _unwrap(data: dict | list, key: str) -> dict | list:
    """The list or mapping under ``key`` when the CDN wraps it in an object."""
    return data.get(key, data) if isinstance(data, dict) else data


def _replace_tree(target: Path, source: Path) -> None:
    """Replace ``target`` with a copy of ``source``, leaving the dot-files behind."""
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=lambda _dir, names: [n for n in names if n.startswith(".")],
    )


def latest_stable_version(base_url: str = "https://editor.construct.net") -> str:
    """Return the release name of the newest Stable build in versions.json."""
    url = f"{base_url.rstrip('/')}/{ENDPOINTS['versions']}"
    for v in json.loads(_strip_bom(_http_get(url))):
        if v.get("branchName") == "Stable":
            return v["releaseName"]
    raise LookupError(f"{url} lists no Stable release")


def release_directory(version: str) -> str:
    """The CDN directory of a release: ``r495.2`` is served under ``r495-2/``."""
    return version.replace(".", "-")


class C3Fetcher:
    """Fetch and cache Construct 3 CDN data."""

    def __init__(
        self,
        version: str,
        base_url: str = "https://editor.construct.net",
        cache_dir: Path | None = None,
    ):
        # The name labels data/ and keys the cache; r495-2, the directory's
        # spelling, would label the data with a release versions.json never names.
        if not _RELEASE_NAME.fullmatch(version):
            raise ValueError(
                f"release {version!r}: write it as versions.json names it, such as r503 or r495.2"
            )
        self.version = version
        self.base_url = base_url.rstrip("/")
        if cache_dir is None:
            from src.settings import load_settings
            cache_dir = load_settings().schema.cache_dir
        self.cache_dir = Path(cache_dir) / self.version
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _http_get(self, url: str) -> bytes:
        """The one HTTP call of a fetcher, kept as a method so a test can stub it."""
        return _http_get(url)

    def url(self, path: str) -> str:
        """The CDN URL of ``path`` in this release's directory."""
        return f"{self.base_url}/{release_directory(self.version)}/{path}"

    def _download(self, path: str) -> bytes:
        """Fetch ``path`` from this release's directory, never from the root.

        Raises ``FileNotFoundError`` on a 404: the root copy belongs to the
        current stable release, which need not be this one.
        """
        url = self.url(path)
        logger.info(f"[CDN] Fetching {url}")
        try:
            return self._http_get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFoundError(f"{url} returned 404: the CDN has no {path} for {self.version}") from e
            raise

    def fetch_raw(self, path: str, force: bool = False) -> bytes:
        """Fetch a raw file (text/binary), using local cache if fresh."""
        cache_path = self.cache_dir / path.replace("/", "_")
        if not force and cache_path.exists() and not _cache_expired(cache_path):
            return cache_path.read_bytes()
        raw = self._download(path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(raw)
        return raw

    def fetch(self, path: str, force: bool = False) -> dict | list:
        """Fetch a JSON endpoint, using local cache if fresh.

        Args:
            path: Relative path under the release directory (e.g. "plugins/allAces.json")
            force: Skip cache and always fetch from CDN
        """
        return json.loads(_strip_bom(self.fetch_raw(path, force)))

    # ── Schema export (per-language, CDN-native field names) ─────────────

    def export_schemas(self) -> Path:
        """Generate per-language schema files from CDN data.

        Merges allAces.json (structural) + precompiled-{locale}.json (text) into
        per-language files that preserve CDN field names:
          - conditions/actions: list-name, display-text, description
          - expressions: translated-name, description
          - params: name, desc, items, initialValue (object keyed by param id)

        Structure fields from allAces (scriptName, isTrigger, isFakeTrigger,
        isLooping, isInvertible, isCompatibleWithTriggers, isAsync, isDeprecated,
        returnType, isVariadicParameters, params[].type) are merged in.

        Directory layout:
            schemas/en-US/plugins/sprite.json
            schemas/zh-CN/plugins/sprite.json
            schemas/en-US/behaviors/platform.json
            schemas/en-US/effects/alphaclamp.json
            schemas/en-US/_index.json   (localized names + file paths)
            schemas/en-US/_deprecated.json  (what the editor has deprecated)
            schemas/_index.json         (language-neutral: ids, files, counts)

        Returns the schemas root directory path.
        """
        schemas_dir = self.cache_dir / "schemas"
        marker = schemas_dir / ".exported"
        if marker.exists() and not _cache_expired(marker):
            return schemas_dir
        # export_to_data copies the whole directory, so a file an earlier
        # export wrote for an addon this one leaves out would reach data/.
        if schemas_dir.exists():
            shutil.rmtree(schemas_dir)

        aces_data = self.fetch_all_aces()
        lang_texts = {locale: self.fetch_lang(locale).get("text", {}) for locale in SCHEMA_LOCALES}

        # An addon the editor marks deprecated is hidden from its Add object
        # and Add behavior dialogs; it is left out here whether or not the
        # language packs still translate it.
        addon_flags = self.fetch_addon_deprecation()
        deprecated = {
            kind: deprecated_ids(addon_flags[kind], set(aces_data.get(kind, {})), kind)
            for kind in ADDON_KINDS
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
        # Which of them each built-in plugin gets: Text has no set-default-color.
        # A plugin the extract does not know gets no list, and a reader
        # offers it every shared ACE as before.
        common_of = load_common_availability()

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
                if plugin_id in deprecated[addon_type]:
                    continue
                # Every locale file takes its ACE list from the zh-CN pack
                # (the check below), so an addon the pack lacks would have none.
                zh_p = lang_texts["zh-CN"].get(addon_type, {}).get(pid_lower, {})
                if not zh_p:
                    continue
                # zh-CN has no name for _common; keep the value the locale
                # index has always carried (docs/decisions/schema-index-per-locale-split.md).
                fallback_name = COMMON_ADDON_NAME if plugin_id == COMMON_ADDON_ID else plugin_id

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
                    if addon_type == "plugins" and plugin_id in common_of:
                        plugin_json["commonAces"] = common_of[plugin_id]

                    for category, ace_types in categories.items():
                        for ace_type_plural in SCHEMA_ACE_TYPES:
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
                                        # Item labels from lang, else the ids label themselves
                                        param_entry["items"] = l_param.get("items") or {k: k for k in p["items"]}
                                    # The value the editor fills in when the ACE is added:
                                    # Wait's "use time scale" is ticked, "true".
                                    if p.get("initialValue") is not None:
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
                                # A deprecated ACE the zh-CN pack still names is
                                # kept, flagged, so that a reader can avoid it.
                                if ace.get("isDeprecated"):
                                    entry["isDeprecated"] = True
                                if ace.get("returnType"):
                                    entry["returnType"] = ace["returnType"]
                                # A call may pass more arguments than params lists, and
                                # fewer where params names an optional one: Mouse.X("HUD"),
                                # Array.At(x, y), random(a, b), max(a, b, c).
                                if ace.get("isVariadicParameters"):
                                    entry["isVariadicParameters"] = True

                                plugin_json[ace_type_plural].append(entry)

                    # Properties — keep CDN dict structure {prop_id: {name, desc, ...}}.
                    # _common has none of its own: what every world instance
                    # has is the properties bar's text, under ui.bars.
                    plugin_json["properties"] = (
                        build_common_properties(text) if plugin_id == COMMON_ADDON_ID
                        else lp.get("properties", {})
                    )

                    _write_json(out_dir / f"{pid_lower}.json", plugin_json)
                    locale_index[lang][addon_type][pid_lower] = {
                        "name": plugin_json["name"],
                        "file": f"{addon_type}/{pid_lower}.json",
                    }

                # Index entry (language-neutral). Counts are those of the
                # written file, not of allAces: deprecated ACEs were skipped
                # above, identically for every locale.
                index_entry: dict = {
                    "file": f"{addon_type}/{pid_lower}.json",
                    "conditions": len(plugin_json["conditions"]),
                    "actions": len(plugin_json["actions"]),
                    "expressions": len(plugin_json["expressions"]),
                }
                if plugin_id != COMMON_ADDON_ID:
                    # The CDN spelling of the id; _common has none.
                    index_entry = {"originalId": plugin_id, **index_entry}
                index_data[addon_type][pid_lower] = index_entry

        # ── Effects ───────────────────────────────────────────────────────
        # allEffects.json flags the effects the Add effect dialog hides.
        effects: list[dict] = []
        retired_effects: list[dict] = []
        for item in self.fetch_effects():
            data = item.get("json", item)
            (retired_effects if data.get("is-deprecated") else effects).append(data)
        for lang, text in lang_texts.items():
            out_dir = schemas_dir / lang / "effects"
            out_dir.mkdir(parents=True, exist_ok=True)
            l_effects = text.get("effects", {})
            for data in effects:
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
                _write_json(out_dir / f"{eid}.json", fx_json)
                locale_index[lang]["effects"][eid] = {
                    "name": fx_json["name"],
                    "file": f"effects/{eid}.json",
                }
                # The root index lists the effects the en-US pack names.
                if lang == "en-US":
                    index_data["effects"][eid] = {
                        "file": f"effects/{eid}.json",
                        "category": fx_json["category"],
                    }

        logger.info(f"[CDN] Exported {len(index_data['effects'])} effects")

        # ── Examples (per-language, per-file) ─────────────────────────────
        try:
            examples_raw = self.fetch_examples()

            examples_dir = schemas_dir.parent / "examples"
            for lang, text in lang_texts.items():
                out_dir = examples_dir / lang
                out_dir.mkdir(parents=True, exist_ok=True)
                # Per-lang data sources:
                #   - ui.start-page.projects.{id} → {name, description}  (localized title/desc)
                #   - ui.example-browser.filters   → tag label translations
                ui = text.get("ui", {})
                projects = ui.get("start-page", {}).get("projects", {})
                filters = ui.get("example-browser", {}).get("filters", {})
                tmap: dict[str, str] = {
                    k: v
                    for section_key in ("level", "category", "genre", "tag")
                    for k, v in filters.get(section_key, {}).items()
                    if k != "section-title" and isinstance(v, str)
                }
                for ex in examples_raw:
                    eid = ex.get("id", "")
                    if not eid:
                        continue
                    lp = projects.get(eid, {})
                    # Localized name and description from lang
                    entry: dict = {"id": eid, "name": lp.get("name", ex.get("name", eid))}
                    if lp.get("description"):
                        entry["description"] = lp["description"]
                    if ex.get("tags"):
                        entry["tags"] = [tmap.get(t, t) for t in ex["tags"]]
                    if ex.get("used-addons"):
                        entry["used-addons"] = ex["used-addons"]
                    entry["open"] = f"https://editor.construct.net/#open={eid}"
                    _write_json(out_dir / f"{eid}.json", entry)

            index_data["examples"] = len(examples_raw)
            logger.info(f"[CDN] Exported {len(examples_raw)} examples (per-language)")
        except Exception as e:
            logger.warning(f"[CDN] Failed to export examples: {e}")

        # ── Write _index.json (root + one per locale) ─────────────────────
        _write_json(schemas_dir / "_index.json", index_data)
        for lang, data in locale_index.items():
            _write_json(schemas_dir / lang / "_index.json", data)

        # ── Write _deprecated.json (one per locale) ───────────────────────
        retired = deprecated_list(aces_data, deprecated, retired_effects, lang_texts, self.version)
        for lang, data in retired.items():
            _write_json(schemas_dir / lang / "_deprecated.json", data)

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

    def export_ts_defs(self) -> Path:
        """Download TypeScript definitions from CDN and save to ts-defs directory.

        Uses offline.json to discover .d.ts file paths, downloads each once
        and caches locally. Adds a small delay between requests to avoid
        overwhelming the CDN.

        Returns the ts-defs output directory path.
        """
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
                out_path.write_bytes(_strip_bom(self.fetch_raw(dts_path)))
                fetched += 1
                # Throttle: 100ms between requests, a second after every tenth
                time.sleep(1 if fetched % 10 == 0 else 0.1)
            except Exception as e:
                logger.warning(f"[CDN] Failed to fetch {dts_path}: {e}")

        # Also fetch autocomplete-data.json
        try:
            _write_json(ts_dir / "autocomplete-data.json", self.fetch(ENDPOINTS["autocomplete"]))
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

        _replace_tree(targets["c3-schemas"], schemas_dir)
        _replace_tree(targets["c3-examples"], schemas_dir.parent / "examples")
        _replace_tree(targets["c3-lang"], lang_dir)

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

    def export_lang(self, locales: tuple[str, ...] = SCHEMA_LOCALES) -> Path:
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
        return _unwrap(self.fetch(ENDPOINTS["effects"]), "all")

    def fetch_addon_deprecation(self) -> dict[str, dict[str, bool]]:
        """``{"plugins": {id: deprecated}, "behaviors": {...}}`` from the
        editor bundles, for every addon they construct."""
        main_js = self.fetch_raw(ENDPOINTS["main_js"]).decode("utf-8", errors="replace")
        bundles = {"plugins": ENDPOINTS["plugin_js"], "behaviors": ENDPOINTS["behavior_js"]}
        return {
            kind: extract_deprecation(main_js, self.fetch_raw(path).decode("utf-8", errors="replace"), kind)
            for kind, path in bundles.items()
        }

    def fetch_examples(self) -> list:
        """Fetch example project metadata list."""
        return _unwrap(self.fetch(ENDPOINTS["examples"]), "projects")

    def fetch_plugin_list(self) -> dict:
        """Fetch plugin ID → path mapping."""
        return _unwrap(self.fetch(ENDPOINTS["plugin_list"]), "pluginList")

    def fetch_behavior_list(self) -> dict:
        """Fetch behavior ID → path mapping."""
        return _unwrap(self.fetch(ENDPOINTS["behavior_list"]), "behaviorList")
