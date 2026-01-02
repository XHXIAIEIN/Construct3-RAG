"""
CSV Parser for Construct 3 i18n Translation Terms
Parses zh-CN translation CSV and creates structured term entries
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import csv
import re


@dataclass
class TermEntry:
    """Represents a translation term entry"""
    term_key: str
    path: List[str]
    category: str  # behaviors, plugins, system, etc.
    term_type: str  # action, condition, expression, property, etc.
    zh: str
    en: str
    full_text: str = field(default="")

    def __post_init__(self):
        self.full_text = f"{self.zh} | {self.en}"


class CSVParser:
    """Parse Construct 3 i18n CSV files"""

    # Category mappings
    CATEGORIES = {
        "behaviors": "行为",
        "plugins": "插件",
        "system": "系统",
        "common": "通用",
        "editor": "编辑器",
    }

    # Term type mappings
    TERM_TYPES = {
        "actions": "动作",
        "conditions": "条件",
        "expressions": "表达式",
        "properties": "属性",
        "params": "参数",
        "items": "选项",
    }

    def __init__(self):
        self.entries: List[TermEntry] = []

    def parse_term_key(self, term_key: str) -> Dict[str, Any]:
        """Parse term key into structured components

        Example: text.behaviors.eightdir.actions.stop.list-name
        -> category: behaviors, type: actions, component: eightdir
        """
        parts = term_key.split('.')

        # Default values
        category = "unknown"
        term_type = "unknown"
        component = ""

        if len(parts) >= 2:
            # First part is usually "text"
            if parts[0] == "text" and len(parts) >= 3:
                category = parts[1]  # behaviors, plugins, etc.
                component = parts[2] if len(parts) > 2 else ""

                # Find term type
                for i, part in enumerate(parts):
                    if part in self.TERM_TYPES:
                        term_type = part
                        break

        return {
            "path": parts,
            "category": category,
            "term_type": term_type,
            "component": component
        }

    def parse_line(self, line: str) -> Optional[TermEntry]:
        """Parse a single CSV line"""
        # Handle quoted commas
        parts = []
        current = ""
        in_quotes = False

        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(current.strip('"'))
                current = ""
            else:
                current += char

        if current:
            parts.append(current.strip('"'))

        if len(parts) < 2:
            return None

        term_key = parts[0]
        zh_text = parts[1] if len(parts) > 1 else ""
        en_text = parts[5] if len(parts) > 5 else ""

        # Skip empty entries
        if not term_key or not zh_text:
            return None

        # Parse term key structure
        parsed = self.parse_term_key(term_key)

        return TermEntry(
            term_key=term_key,
            path=parsed["path"],
            category=parsed["category"],
            term_type=parsed["term_type"],
            zh=zh_text,
            en=en_text
        )

    def parse_file(self, csv_path: Path) -> List[TermEntry]:
        """Parse entire CSV file"""
        print(f"Parsing CSV: {csv_path}")

        self.entries = []
        error_count = 0

        with open(csv_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = self.parse_line(line)
                    if entry:
                        self.entries.append(entry)
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:  # Only show first 5 errors
                        print(f"  Warning: Line {line_num}: {e}")

        print(f"  Parsed {len(self.entries)} entries")
        if error_count > 0:
            print(f"  Skipped {error_count} invalid lines")

        return self.entries

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about parsed entries"""
        stats = {
            "total": len(self.entries),
            "by_category": {},
            "by_type": {}
        }

        for entry in self.entries:
            # Count by category
            cat = entry.category
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            # Count by type
            typ = entry.term_type
            stats["by_type"][typ] = stats["by_type"].get(typ, 0) + 1

        return stats

    def search_terms(self, query: str, exact: bool = False) -> List[TermEntry]:
        """Search terms by Chinese or English text"""
        results = []
        query_lower = query.lower()

        for entry in self.entries:
            if exact:
                if query == entry.zh or query.lower() == entry.en.lower():
                    results.append(entry)
            else:
                if query_lower in entry.zh.lower() or query_lower in entry.en.lower():
                    results.append(entry)

        return results

    def get_by_category(self, category: str) -> List[TermEntry]:
        """Get all terms in a category"""
        return [e for e in self.entries if e.category == category]

    def export_for_vectordb(self) -> List[Dict[str, Any]]:
        """Export entries in format suitable for vector database"""
        return [
            {
                "id": f"term_{i}",
                "text": entry.full_text,
                "metadata": {
                    "term_key": entry.term_key,
                    "category": entry.category,
                    "term_type": entry.term_type,
                    "zh": entry.zh,
                    "en": entry.en,
                    "path": "/".join(entry.path)
                }
            }
            for i, entry in enumerate(self.entries)
        ]


def process_terms():
    """Process Construct 3 translation terms"""
    from src.config import SOURCE_DIR, TRANSLATION_CSV

    csv_path = SOURCE_DIR / TRANSLATION_CSV
    parser = CSVParser()

    if csv_path.exists():
        entries = parser.parse_file(csv_path)

        # Print statistics
        stats = parser.get_statistics()
        print(f"\n--- Statistics ---")
        print(f"Total entries: {stats['total']}")

        print("\nBy category:")
        for cat, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

        print("\nBy type:")
        for typ, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
            print(f"  {typ}: {count}")

        return entries
    else:
        print(f"Error: CSV file not found: {csv_path}")
        return []


if __name__ == "__main__":
    entries = process_terms()

    if entries:
        # Preview first few entries
        print("\n--- Sample Entries ---")
        for i, entry in enumerate(entries[:5]):
            print(f"\nEntry {i+1}:")
            print(f"  Key: {entry.term_key}")
            print(f"  Category: {entry.category}, Type: {entry.term_type}")
            print(f"  ZH: {entry.zh}")
            print(f"  EN: {entry.en}")

        # Test search
        print("\n--- Search Test ---")
        parser = CSVParser()
        parser.entries = entries

        results = parser.search_terms("移动")
        print(f"Search '移动': {len(results)} results")
        for r in results[:3]:
            print(f"  {r.zh} -> {r.en}")
