"""
Sitemap Parser for Construct 3 Manual Structure
Parses manual-1.xml to extract document hierarchy
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse
import re


@dataclass
class ManualPage:
    """Represents a manual page entry"""
    url: str
    path: str  # URL path
    section: str  # Main section
    subsection: str  # Subsection
    title: str  # Page title (extracted from URL)
    depth: int  # Hierarchy depth


class SitemapParser:
    """Parse Construct 3 manual sitemap"""

    # Known main sections in the manual
    MAIN_SECTIONS = [
        "overview",
        "interface",
        "project-structure",
        "plugin-reference",
        "behavior-reference",
        "scripting",
        "system-reference",
        "tips-and-guides",
        "addon-sdk",
    ]

    def __init__(self):
        self.pages: List[ManualPage] = []
        self.structure: Dict[str, Any] = {}

    def parse_url_path(self, url: str) -> Dict[str, str]:
        """Extract structured information from URL"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        parts = path.split('/')

        # Extract section hierarchy
        result = {
            "path": path,
            "parts": parts,
            "depth": len(parts)
        }

        # Find manual-specific sections
        # Expected format: en/make-games/manuals/construct-3/section/subsection/...
        if "manuals/construct-3" in path:
            idx = parts.index("construct-3") if "construct-3" in parts else -1
            if idx >= 0 and idx + 1 < len(parts):
                result["section"] = parts[idx + 1]
                if idx + 2 < len(parts):
                    result["subsection"] = parts[idx + 2]
                if idx + 3 < len(parts):
                    result["page"] = parts[idx + 3]

        # Extract title from last part of URL
        if parts:
            title = parts[-1].replace('-', ' ').title()
            result["title"] = title

        return result

    def parse_file(self, xml_path: Path) -> List[ManualPage]:
        """Parse sitemap XML file"""
        print(f"Parsing sitemap: {xml_path}")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Handle XML namespace
        namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

        # Find all URL entries
        urls = root.findall('.//sm:url/sm:loc', namespace)
        if not urls:
            # Try without namespace
            urls = root.findall('.//url/loc')
            if not urls:
                urls = root.findall('.//loc')

        self.pages = []

        for url_elem in urls:
            url = url_elem.text.strip() if url_elem.text else ""
            if not url:
                continue

            parsed = self.parse_url_path(url)

            page = ManualPage(
                url=url,
                path=parsed.get("path", ""),
                section=parsed.get("section", "unknown"),
                subsection=parsed.get("subsection", ""),
                title=parsed.get("title", ""),
                depth=parsed.get("depth", 0)
            )
            self.pages.append(page)

        print(f"  Found {len(self.pages)} pages")
        return self.pages

    def build_hierarchy(self) -> Dict[str, Any]:
        """Build hierarchical structure from pages"""
        self.structure = {}

        for page in self.pages:
            section = page.section
            subsection = page.subsection or "_root"

            if section not in self.structure:
                self.structure[section] = {"_pages": [], "_subsections": {}}

            if subsection == "_root":
                self.structure[section]["_pages"].append(page)
            else:
                if subsection not in self.structure[section]["_subsections"]:
                    self.structure[section]["_subsections"][subsection] = []
                self.structure[section]["_subsections"][subsection].append(page)

        return self.structure

    def export_toc(self) -> str:
        """Export table of contents as markdown"""
        self.build_hierarchy()

        lines = ["# Construct 3 Manual - Table of Contents\n"]

        for section, data in sorted(self.structure.items()):
            # Section header
            section_title = section.replace('-', ' ').title()
            lines.append(f"\n## {section_title}\n")

            # Root pages
            for page in data["_pages"]:
                lines.append(f"- [{page.title}]({page.url})")

            # Subsections
            for subsection, pages in sorted(data["_subsections"].items()):
                subsection_title = subsection.replace('-', ' ').title()
                lines.append(f"\n### {subsection_title}\n")
                for page in pages:
                    lines.append(f"- [{page.title}]({page.url})")

        return "\n".join(lines)

    def export_json(self) -> List[Dict[str, Any]]:
        """Export pages as JSON-compatible structure"""
        return [
            {
                "url": page.url,
                "path": page.path,
                "section": page.section,
                "subsection": page.subsection,
                "title": page.title,
                "depth": page.depth
            }
            for page in self.pages
        ]

    def get_sections_summary(self) -> Dict[str, int]:
        """Get count of pages per section"""
        summary = {}
        for page in self.pages:
            section = page.section
            summary[section] = summary.get(section, 0) + 1
        return summary


def process_sitemap():
    """Process the Construct 3 manual sitemap"""
    from src.config import DATA_DIR

    sitemap_path = DATA_DIR / "manual-1.xml"

    if not sitemap_path.exists():
        print(f"Sitemap not found: {sitemap_path}")
        print("Please save manual-1.xml to the mate/ directory")
        return None

    parser = SitemapParser()
    pages = parser.parse_file(sitemap_path)

    # Print summary
    print(f"\n--- Section Summary ---")
    summary = parser.get_sections_summary()
    for section, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {section}: {count} pages")

    # Export table of contents
    toc = parser.export_toc()
    toc_path = DATA_DIR.parent / "doc" / "design" / "manual-toc.md"
    toc_path.parent.mkdir(parents=True, exist_ok=True)
    with open(toc_path, 'w', encoding='utf-8') as f:
        f.write(toc)
    print(f"\nTable of contents saved to: {toc_path}")

    return pages


if __name__ == "__main__":
    pages = process_sitemap()

    if pages:
        print("\n--- Sample Pages ---")
        for page in pages[:10]:
            print(f"  [{page.section}] {page.title}: {page.url}")
