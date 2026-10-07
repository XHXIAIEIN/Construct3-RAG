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
import tempfile
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
from src.lookup.schema_layout import SCHEMA_ACE_TYPES, SCHEMA_LOCALES, schema_is_complete


logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"
_BEIJING = timezone(timedelta(hours=8))
# A transient failure (HTTP 5xx, a dropped connection, a timeout) is tried
# again this many times, this many seconds apart; a 4xx is not.
_RETRIES = 2
_RETRY_DELAY = 1.0
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


# The top-level type of each JSON endpoint, and a key it must have, if any.
# A CDN or proxy error page can come with status 200; the shape check keeps it
# out of the cache, which would serve it until the weekly expiry.
_JSON_SHAPES: dict[str, tuple[type, str | None]] = {
    ENDPOINTS["plugin_aces"]:   (dict, None),
    ENDPOINTS["behavior_aces"]: (dict, None),
    ENDPOINTS["effects"]:       (dict, "all"),
    ENDPOINTS["examples"]:      (dict, "projects"),
    ENDPOINTS["plugin_list"]:   (dict, "pluginList"),
    ENDPOINTS["behavior_list"]: (dict, "behaviorList"),
    ENDPOINTS["offline"]:       (dict, "fileList"),
    ENDPOINTS["autocomplete"]:  (dict, None),
    **{ENDPOINTS["lang"].format(locale=locale): (dict, "text") for locale in SCHEMA_LOCALES},
}


def _check_body(path: str, raw: bytes) -> None:
    """Raise ``ValueError`` when ``raw`` is not what the endpoint ``path`` serves."""
    body = _strip_bom(raw)

    def refuse(why: str) -> ValueError:
        return ValueError(f"[CDN] {path}: {why}; the body starts with {body[:80]!r}")

    if path.endswith((".d.ts", ".js")):
        if body.lstrip().startswith(b"<"):
            raise refuse("an HTML page, not a script")
        return
    if not path.endswith(".json"):
        return
    try:
        data = json.loads(body)
    except ValueError:
        raise refuse("not JSON") from None
    kind, key = _JSON_SHAPES.get(path, (object, None))
    if not isinstance(data, kind):
        raise refuse(f"a JSON {type(data).__name__}, not a {kind.__name__}")
    if key is not None and key not in data:
        raise refuse(f"no {key!r} key")


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
    """Fetch URL with browser User-Agent (CDN returns 403 without it).

    Retries an HTTP 5xx, a connection error or a timeout ``_RETRIES`` times;
    raises the last error after that, and a 4xx at once.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == _RETRIES:
                raise
            error: OSError = e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == _RETRIES:
                raise
            error = e
        attempt += 1
        logger.warning(f"[CDN] {url}: {error}; retrying ({attempt}/{_RETRIES})")
        time.sleep(_RETRY_DELAY)


def _write_atomic(path: Path, data: bytes) -> None:
    """Write ``data`` beside ``path``, then move it into place.

    The cache and the .d.ts export skip a file that exists, so a write cut
    short must leave no file at ``path``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    part.replace(path)


def _swap_in(stage: Path, targets: dict[str, Path]) -> None:
    """Move ``stage/{name}`` to each target. The earlier targets go to
    ``stage/earlier/`` first; if any move fails, every target moved so far
    is put back and ``RuntimeError`` is raised."""
    earlier = stage / "earlier"
    earlier.mkdir()
    placed: list[Path] = []
    aside: list[tuple[Path, Path]] = []
    try:
        for name, target in targets.items():
            if target.exists():
                target.rename(earlier / name)
                aside.append((target, earlier / name))
            (stage / name).rename(target)
            placed.append(target)
    except OSError as e:
        for target in placed:
            shutil.rmtree(target)
        for target, old in aside:
            old.rename(target)
        raise RuntimeError(f"[CDN] the export could not be moved into place: {e}; data/ is left as it was") from e


def _strip_bom(raw: bytes) -> bytes:
    """Remove UTF-8 BOM if present."""
    return raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw


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
        # export wrote for an addon or example this one leaves out would reach data/.
        examples_dir = schemas_dir.parent / "examples"
        for stale in (schemas_dir, examples_dir):
            if stale.exists():
                shutil.rmtree(stale)

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
                # zh-CN has no name for _common; keep the value the locale
                # index has always carried (docs/decisions/schema-index-per-locale-split.md).
                fallback_name = COMMON_ADDON_NAME if plugin_id == COMMON_ADDON_ID else plugin_id

                if plugin_id in deprecated[addon_type]:
                    continue
                # Every locale file takes its ACE list from the zh-CN pack
                # (the check below), so an addon the pack lacks would have none.
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
                                        # Merge item labels from lang
                                        l_items = l_param.get("items", {})
                                        if l_items:
                                            param_entry["items"] = l_items
                                        else:
                                            param_entry["items"] = {k: k for k in p["items"]}
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
        all_effects = [item.get("json", item) for item in self.fetch_effects()]
        effects = [data for data in all_effects if not data.get("is-deprecated")]
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
                (out_dir / f"{eid}.json").write_text(
                    json.dumps(fx_json, ensure_ascii=False, indent=2), encoding="utf-8",
                )
                locale_index[lang]["effects"][eid] = {
                    "name": fx_json["name"],
                    "file": f"effects/{eid}.json",
                }

            # Index effects
            if lang == "en-US":
                for data in effects:
                    eid = data.get("id", "")
                    if l_effects.get(eid):
                        index_data["effects"][eid] = {
                            "file": f"effects/{eid}.json",
                            "category": data.get("category", ""),
                        }

        logger.info(f"[CDN] Exported {len(index_data['effects'])} effects")

        # ── Examples (per-language, per-file) ─────────────────────────────
        # A failure stops the export with no marker, like any other endpoint:
        # data/c3-examples is replaced whole, so a skipped export would empty it.
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

        # ── Write _index.json (root + one per locale) ─────────────────────
        (schemas_dir / "_index.json").write_text(
            json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        for lang, data in locale_index.items():
            (schemas_dir / lang / "_index.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )

        # ── Write _deprecated.json (one per locale) ───────────────────────
        retired = deprecated_list(
            aces_data, deprecated,
            [data for data in all_effects if data.get("is-deprecated")],
            lang_texts, self.version,
        )
        for lang, data in retired.items():
            (schemas_dir / lang / "_deprecated.json").write_text(
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
        """Fetch a raw file (text/binary), using local cache if fresh.

        Raises ``ValueError`` and caches nothing when the body is not what the
        endpoint serves (``_check_body``).
        """
        cache_path = self.cache_dir / path.replace("/", "_")
        if not force and cache_path.exists() and not _cache_expired(cache_path):
            return cache_path.read_bytes()
        raw = self._download(path)
        _check_body(path, raw)
        _write_atomic(cache_path, raw)
        return raw

    def export_ts_defs(self) -> Path:
        """Download TypeScript definitions from CDN and save to ts-defs directory.

        Uses offline.json to discover .d.ts file paths, downloads each once
        and caches locally. Adds a small delay between requests to avoid
        overwhelming the CDN.

        Returns the ts-defs output directory path. Raises ``RuntimeError``
        naming every file that failed, after trying them all, and writes no
        marker then: ``export_to_data`` replaces ``data/c3-ts-defs`` whole, so
        a missing file would drop out of the commit. The next run fetches only
        the files still missing.
        """
        ts_dir = self.cache_dir / "ts-defs"
        marker = ts_dir / ".exported"
        if marker.exists() and not _cache_expired(marker):
            return ts_dir

        # Get file list from offline.json
        offline = self.fetch(ENDPOINTS["offline"])
        dts_paths = [f for f in offline.get("fileList", []) if f.endswith(".d.ts")]
        logger.info(f"[CDN] Found {len(dts_paths)} .d.ts files")
        if not dts_paths:
            raise RuntimeError(
                f"[CDN] {ENDPOINTS['offline']} lists no .d.ts file, so data/c3-ts-defs is left as it is"
            )

        fetched = 0
        failed: list[str] = []
        for dts_path in dts_paths:
            out_path = ts_dir / dts_path
            if out_path.exists():
                continue  # already cached
            try:
                _write_atomic(out_path, _strip_bom(self.fetch_raw(dts_path)))
                fetched += 1
                # Throttle: 100ms between requests to be respectful
                if fetched % 10 == 0:
                    time.sleep(1)
                elif fetched > 0:
                    time.sleep(0.1)
            except OSError as e:  # URLError and the 404 FileNotFoundError included
                logger.warning(f"[CDN] Failed to fetch {dts_path}: {e}")
                failed.append(dts_path)

        # Also fetch autocomplete-data.json
        try:
            autocomplete = self.fetch(ENDPOINTS["autocomplete"])
            _write_atomic(
                ts_dir / "autocomplete-data.json",
                json.dumps(autocomplete, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except (OSError, ValueError) as e:
            logger.warning(f"[CDN] Failed to fetch autocomplete-data: {e}")
            failed.append(ENDPOINTS["autocomplete"])

        if failed:
            raise RuntimeError(
                f"[CDN] {len(failed)} ts-defs file(s) failed, so data/c3-ts-defs is left as it is: "
                + ", ".join(failed)
            )
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

        The four targets are built in a staging folder beside ``data_dir`` and
        checked against what the CDN lists: complete schemas, every example
        of the examples list in both locales, both language packs, every
        ``.d.ts`` of ``offline.json`` and the autocomplete listing. Only then
        are they swapped in, and a failed swap puts the earlier ones back.
        Raises ``RuntimeError`` naming what is missing, with ``data_dir`` as
        it was.

        Returns the refreshed target directories keyed by their name.
        """
        schemas_dir = self.export_schemas()
        lang_dir = self.export_lang()
        ts_dir = self.export_ts_defs()
        targets = {name: data_dir / name for name in ("c3-schemas", "c3-examples", "c3-lang", "c3-ts-defs")}

        data_dir.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{data_dir.name}-staging-", dir=data_dir.parent))
        try:
            self._stage(stage, schemas_dir, lang_dir, ts_dir)
            missing = self._missing_from(stage)
            if missing:
                raise RuntimeError(
                    f"[CDN] the {self.version} export is short, so {data_dir} is left as it is: "
                    + ", ".join(missing)
                )
            _swap_in(stage, targets)
        finally:
            try:
                shutil.rmtree(stage)
            except OSError as e:
                logger.warning(f"[CDN] the staging folder {stage} is left behind: {e}; delete it by hand")

        logger.info(f"[CDN] Refreshed {data_dir} from {self.version} exports")
        return targets

    @staticmethod
    def _stage(stage: Path, schemas_dir: Path, lang_dir: Path, ts_dir: Path) -> None:
        """Copy the exports into ``stage`` as data/ lays them out; a missing
        export leaves its folder out, for ``_missing_from`` to name."""
        def hidden(_dir: str, names: list[str]) -> list[str]:
            return [n for n in names if n.startswith(".")]

        for name, source in (("c3-schemas", schemas_dir), ("c3-examples", schemas_dir.parent / "examples"),
                             ("c3-lang", lang_dir)):
            if source.is_dir():
                shutil.copytree(source, stage / name, ignore=hidden)
        # ts-defs: only the interface files and the class listing, not the
        # download bookkeeping the export leaves beside them.
        ts_stage = stage / "c3-ts-defs"
        ts_stage.mkdir()
        for src_file in [*ts_dir.rglob("*.d.ts"), ts_dir / "autocomplete-data.json"]:
            if src_file.is_file():
                dst = ts_stage / src_file.relative_to(ts_dir)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst)

    def _missing_from(self, stage: Path) -> list[str]:
        """What the CDN lists for this release and ``stage`` lacks, as data/ paths."""
        missing: list[str] = []
        if not schema_is_complete(stage / "c3-schemas"):
            missing.append("c3-schemas (incomplete: an addon type is empty, or a file _index.json names is missing or unreadable)")
        example_ids = sorted({ex["id"] for ex in self.fetch_examples() if ex.get("id")})
        expected = [f"c3-examples/{locale}/{eid}.json" for locale in SCHEMA_LOCALES for eid in example_ids]
        expected += [f"c3-lang/{locale}.json" for locale in SCHEMA_LOCALES]
        offline = self.fetch(ENDPOINTS["offline"])
        expected += [f"c3-ts-defs/{f}" for f in offline.get("fileList", []) if f.endswith(".d.ts")]
        expected.append("c3-ts-defs/autocomplete-data.json")
        missing += [rel for rel in expected if not (stage / rel).is_file()]
        return missing

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
        data = self.fetch(ENDPOINTS["effects"])
        return data.get("all", data) if isinstance(data, dict) else data

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
