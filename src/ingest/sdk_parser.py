"""
Addon SDK Parser for Construct 3 RAG

Parses the Construct-Addon-SDK code repository to extract structured
documentation about addon templates, ACE definitions, and code patterns.

Data sources:
  - addon.json  → metadata (type, id, name, properties, file structure)
  - aces.json   → ACE definitions (conditions, actions, expressions with params)
  - lang/*.json → display text, descriptions, parameter names
  - *.js / *.ts → runtime implementation code (instance, actions, conditions, etc.)
  - *.fx / *.wgsl → shader source (effects only)
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


def _read_json(path: Path) -> Optional[dict]:
    """Read JSON file, return None on failure. Handles UTF-8 BOM."""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path, max_chars: int = 4000) -> str:
    """Read text file, truncate if too long."""
    try:
        text = path.read_text(encoding="utf-8")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n// ... (truncated)"
        return text
    except OSError:
        return ""


class AddonInfo:
    """Parsed addon sample with all extracted data."""

    def __init__(self, addon_dir: Path):
        self.dir = addon_dir
        self.addon_json: dict = _read_json(addon_dir / "addon.json") or {}
        self.aces_json: dict = _read_json(addon_dir / "aces.json") or {}
        self.lang: dict = {}
        self.code_files: Dict[str, str] = {}

        # Load lang file
        lang_path = addon_dir / "lang" / "en-US.json"
        if lang_path.exists():
            self.lang = _read_json(lang_path) or {}

        # Load key code files
        self._load_code_files()

    @property
    def addon_type(self) -> str:
        return self.addon_json.get("type", "unknown")

    @property
    def addon_id(self) -> str:
        return self.addon_json.get("id", self.dir.name)

    @property
    def addon_name(self) -> str:
        return self.addon_json.get("name", self.dir.name)

    @property
    def description(self) -> str:
        return self.addon_json.get("description", "")

    def _load_code_files(self):
        """Load relevant source files."""
        # Runtime files
        c3rt = self.dir / "c3runtime"
        if c3rt.exists():
            for name in ["instance.js", "actions.js", "conditions.js",
                         "expressions.js", "instance.ts", "actions.ts",
                         "conditions.ts", "expressions.ts"]:
                fp = c3rt / name
                if fp.exists():
                    self.code_files[f"c3runtime/{name}"] = _read_text(fp)

        # Editor-side files
        for name in ["plugin.js", "behavior.js", "plugin.ts", "behavior.ts",
                     "instance.js", "type.js", "instance.ts", "type.ts"]:
            fp = self.dir / name
            if fp.exists():
                self.code_files[name] = _read_text(fp)

        # Shader files (effects)
        for ext in ["*.fx", "*.wgsl"]:
            for fp in self.dir.glob(ext):
                self.code_files[fp.name] = _read_text(fp, max_chars=3000)

        # Theme CSS
        for fp in self.dir.glob("*.css"):
            self.code_files[fp.name] = _read_text(fp, max_chars=3000)

    def get_ace_summary(self) -> str:
        """Build human-readable ACE summary from aces.json + lang."""
        parts = []
        lang_text = self.lang.get("text", {})
        # Navigate to the addon's lang section
        addon_type_key = {
            "plugin": "plugins",
            "behavior": "behaviors",
        }.get(self.addon_type, "plugins")
        addon_id_lower = self.addon_id.lower()
        addon_lang = lang_text.get(addon_type_key, {}).get(addon_id_lower, {})

        for category, aces in self.aces_json.items():
            if category.startswith("$"):
                continue
            for ace_type in ["conditions", "actions", "expressions"]:
                items = aces.get(ace_type, [])
                if not items:
                    continue
                lang_section = addon_lang.get(ace_type, {})
                for item in items:
                    ace_id = item.get("id", "")
                    script_name = item.get("scriptName") or item.get("expressionName", "")
                    lang_entry = lang_section.get(ace_id, {})
                    display = lang_entry.get("display-text", "")
                    desc = lang_entry.get("description", "")
                    params = item.get("params", [])
                    param_strs = []
                    lang_params = lang_entry.get("params", {})
                    for p in params:
                        p_id = p.get("id", "")
                        p_type = p.get("type", "")
                        p_name = lang_params.get(p_id, {}).get("name", p_id)
                        param_strs.append(f"{p_name}: {p_type}")

                    line = f"  [{ace_type[:-1]}] {ace_id}"
                    if script_name:
                        line += f" (script: {script_name})"
                    if display:
                        line += f" — {display}"
                    if desc:
                        line += f" | {desc}"
                    if param_strs:
                        line += f" | params: {', '.join(param_strs)}"
                    parts.append(line)

        return "\n".join(parts) if parts else ""

    def get_properties_summary(self) -> str:
        """Extract addon properties from lang file."""
        lang_text = self.lang.get("text", {})
        addon_type_key = {
            "plugin": "plugins",
            "behavior": "behaviors",
        }.get(self.addon_type, "plugins")
        addon_id_lower = self.addon_id.lower()
        props = lang_text.get(addon_type_key, {}).get(addon_id_lower, {}).get("properties", {})
        if not props:
            return ""
        lines = []
        for prop_id, prop_info in props.items():
            name = prop_info.get("name", prop_id)
            desc = prop_info.get("desc", "")
            lines.append(f"  {name}: {desc}" if desc else f"  {name}")
        return "\n".join(lines)

    def to_overview_doc(self) -> Dict[str, Any]:
        """Generate overview document for vector DB indexing."""
        lines = [
            f"Addon SDK Sample: {self.addon_name}",
            f"Type: {self.addon_type} | ID: {self.addon_id}",
        ]
        if self.description:
            lines.append(f"Description: {self.description}")

        # File structure
        file_list = self.addon_json.get("file-list", [])
        if file_list:
            lines.append(f"Files: {', '.join(file_list)}")

        # SDK version & min construct version
        sdk_ver = self.addon_json.get("sdk-version")
        min_ver = self.addon_json.get("min-construct-version")
        if sdk_ver:
            lines.append(f"SDK version: {sdk_ver}")
        if min_ver:
            lines.append(f"Min Construct version: {min_ver}")

        # Effect-specific metadata
        if self.addon_type == "effect":
            renderers = self.addon_json.get("supported-renderers", [])
            category = self.addon_json.get("category", "")
            params = self.addon_json.get("parameters", [])
            if renderers:
                lines.append(f"Renderers: {', '.join(renderers)}")
            if category:
                lines.append(f"Category: {category}")
            if params:
                param_descs = [f"{p['id']} ({p['type']})" for p in params]
                lines.append(f"Parameters: {', '.join(param_descs)}")
            lines.append(f"Blends background: {self.addon_json.get('blends-background', False)}")

        # Properties
        props = self.get_properties_summary()
        if props:
            lines.append(f"Properties:\n{props}")

        # ACEs
        aces = self.get_ace_summary()
        if aces:
            lines.append(f"ACEs:\n{aces}")

        text = "\n".join(lines)
        return {
            "id": f"sdk_{self.addon_type}_{self.addon_id}",
            "text": text,
            "metadata": {
                "source": f"addon-sdk/{self.addon_type}/{self.dir.name}",
                "addon_type": self.addon_type,
                "addon_id": self.addon_id,
                "addon_name": self.addon_name,
                "doc_type": "sdk-overview",
                "collection": "c3_addon_sdk",
            },
        }

    def to_code_docs(self) -> List[Dict[str, Any]]:
        """Generate per-file code documents for vector DB indexing."""
        docs = []
        for filename, code in self.code_files.items():
            if not code.strip():
                continue
            header = (
                f"Addon SDK Code: {self.addon_name} ({self.addon_type})\n"
                f"File: {filename}\n"
                f"---\n"
            )
            docs.append({
                "id": f"sdk_code_{self.addon_id}_{filename.replace('/', '_')}",
                "text": header + code,
                "metadata": {
                    "source": f"addon-sdk/{self.addon_type}/{self.dir.name}/{filename}",
                    "addon_type": self.addon_type,
                    "addon_id": self.addon_id,
                    "file_name": filename,
                    "doc_type": "sdk-code",
                    "collection": "c3_addon_sdk",
                },
            })
        return docs


def _find_addon_dirs(parent: Path) -> List[Path]:
    """Find directories containing addon.json, searching up to 2 levels deep."""
    results = []
    if not parent.is_dir():
        return results
    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        if (child / "addon.json").exists():
            results.append(child)
        else:
            # Check one level deeper (e.g. wrapperExtensionPlugin/construct-plugin/)
            for grandchild in sorted(child.iterdir()):
                if grandchild.is_dir() and (grandchild / "addon.json").exists():
                    results.append(grandchild)
    return results


def parse_sdk_repo(sdk_dir: Path) -> List[AddonInfo]:
    """Parse all addon samples from the SDK repository."""
    addons = []
    for type_dir_name in ["plugin-sdk", "behavior-sdk", "effect-sdk", "theme-sdk"]:
        type_dir = sdk_dir / type_dir_name
        if not type_dir.exists():
            continue
        for addon_dir in _find_addon_dirs(type_dir):
            addons.append(AddonInfo(addon_dir))
    return addons


def load_sdk_for_vectordb(sdk_dir: Path) -> List[Dict[str, Any]]:
    """Load all SDK samples and return documents ready for vector DB indexing.

    Returns both overview docs and code docs for each addon sample.
    """
    addons = parse_sdk_repo(sdk_dir)
    docs = []
    for addon in addons:
        docs.append(addon.to_overview_doc())
        docs.extend(addon.to_code_docs())

    print(f"  Parsed {len(addons)} addon samples → {len(docs)} documents")
    return docs
