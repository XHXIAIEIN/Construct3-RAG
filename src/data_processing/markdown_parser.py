"""
Markdown Parser for Construct 3 Manual
Parses markdown files with H2-level semantic chunking
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class MarkdownChunk:
    """Represents a semantically chunked markdown section"""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class MarkdownParser:
    """Parse Construct 3 markdown files with H2-level semantic chunking"""

    # Section types for plugin/behavior docs
    SECTION_TYPES = {
        'properties': 'properties',
        'conditions': 'conditions',
        'actions': 'actions',
        'expressions': 'expressions',
        'scripting': 'scripting',
    }

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the parser.

        Args:
            base_dir: Base directory for markdown files. If None, uses config.
        """
        if base_dir is None:
            from src.config import MARKDOWN_DIR
            self.base_dir = MARKDOWN_DIR
        else:
            self.base_dir = Path(base_dir)

        # Load mappings from config
        from src.config import DIR_TO_COLLECTION, COLLECTION_GUIDE, SUBCATEGORY_MAPPING
        self.dir_to_collection = DIR_TO_COLLECTION
        self.default_collection = COLLECTION_GUIDE
        self.subcategory_mapping = SUBCATEGORY_MAPPING

    def detect_collection(self, file_path: Path) -> str:
        """
        Detect collection name from file path using DIR_TO_COLLECTION mapping.

        Args:
            file_path: Path to the markdown file

        Returns:
            Collection name (e.g., 'c3_plugins', 'c3_guide')
        """
        try:
            rel_path = file_path.relative_to(self.base_dir)
            parts = rel_path.parts
        except ValueError:
            parts = file_path.parts

        # Check first directory level for collection mapping
        for part in parts:
            if part in self.dir_to_collection:
                return self.dir_to_collection[part]

        return self.default_collection

    def detect_subcategory(self, file_path: Path) -> Optional[str]:
        """
        Detect subcategory from file path using SUBCATEGORY_MAPPING.

        Args:
            file_path: Path to the markdown file

        Returns:
            Subcategory string or None
        """
        try:
            rel_path = file_path.relative_to(self.base_dir)
            parts = rel_path.parts
        except ValueError:
            return None

        if len(parts) < 1:
            return None

        category = parts[0]  # e.g., 'plugin-reference'

        # Check if this category has subcategory mappings
        if category not in self.subcategory_mapping:
            return None

        category_mapping = self.subcategory_mapping[category]

        # For plugins: check file stem (e.g., 'audio.md' -> 'audio')
        file_stem = file_path.stem

        if file_stem in category_mapping:
            return category_mapping[file_stem]

        # For nested dirs: check subdirectory name
        if len(parts) >= 2:
            subdir = parts[1]
            if subdir in category_mapping:
                return category_mapping[subdir]

        return None

    def parse_frontmatter(self, content: str) -> Tuple[Dict[str, str], str]:
        """
        Extract YAML frontmatter from markdown content.

        Args:
            content: Raw markdown content

        Returns:
            Tuple of (frontmatter dict, remaining content)
        """
        frontmatter = {}
        body = content

        # Check for YAML frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                yaml_content = parts[1].strip()
                body = parts[2].strip()

                # Simple YAML parsing for title and source
                for line in yaml_content.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        frontmatter[key] = value

        return frontmatter, body


    def detect_section_type(self, heading: str) -> Optional[str]:
        """
        Detect section type from H2 heading.

        Args:
            heading: The H2 heading text (without ##)

        Returns:
            Section type or None
        """
        heading_lower = heading.lower().strip()

        for keyword, section_type in self.SECTION_TYPES.items():
            if keyword in heading_lower:
                return section_type

        return None

    def build_breadcrumb(self, file_path: Path) -> str:
        """
        Build navigation breadcrumb from file path.

        Args:
            file_path: Path to the markdown file

        Returns:
            Breadcrumb string like "plugin-reference > audio"
        """
        try:
            rel_path = file_path.relative_to(self.base_dir)
            # Remove .md extension and join with >
            parts = list(rel_path.parts)
            if parts and parts[-1].endswith('.md'):
                parts[-1] = parts[-1][:-3]  # Remove .md
            return ' > '.join(parts)
        except ValueError:
            return file_path.stem

    def get_category(self, file_path: Path) -> str:
        """
        Get top-level category from file path.

        Args:
            file_path: Path to the markdown file

        Returns:
            Category name (first directory level)
        """
        try:
            rel_path = file_path.relative_to(self.base_dir)
            if rel_path.parts:
                return rel_path.parts[0]
        except ValueError:
            pass
        return 'uncategorized'

    def clean_toc_section(self, content: str) -> str:
        """
        Remove the 'On this page' table of contents section.

        Args:
            content: Markdown content

        Returns:
            Content with TOC removed
        """
        # Pattern to match "## On this page" section followed by a list and ---
        pattern = r'## On this page\s*\n(?:- \[.*?\]\(.*?\)\s*\n)*\s*---\s*\n?'
        return re.sub(pattern, '', content, flags=re.IGNORECASE)

    def split_by_h2(self, content: str, base_metadata: Dict[str, Any]) -> List[MarkdownChunk]:
        """
        Split content into chunks at H2 boundaries.

        Args:
            content: Markdown content (without frontmatter)
            base_metadata: Base metadata to include in each chunk

        Returns:
            List of MarkdownChunk objects
        """
        chunks = []

        # Clean TOC section
        content = self.clean_toc_section(content)

        # Extract H1 title for context
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        h1_title = h1_match.group(1).strip() if h1_match else base_metadata.get('title', '')

        # Split by H2 headers
        # Pattern matches ## followed by text, capturing the header and content until next H2 or end
        h2_pattern = r'^##\s+(.+?)$'

        # Find all H2 positions
        h2_matches = list(re.finditer(h2_pattern, content, re.MULTILINE))

        if not h2_matches:
            # No H2 headers, treat entire content as one chunk
            text = content.strip()
            if text:
                chunks.append(MarkdownChunk(
                    text=text,
                    metadata={
                        **base_metadata,
                        'h1_title': h1_title,
                        'h2_heading': '',
                        'section_type': None,
                    }
                ))
            return chunks

        # Get content before first H2 (intro section with H1)
        intro_end = h2_matches[0].start()
        intro_content = content[:intro_end].strip()

        # Process each H2 section
        for i, match in enumerate(h2_matches):
            h2_heading = match.group(1).strip()

            # Skip "On this page" sections that might have been missed
            if h2_heading.lower() == 'on this page':
                continue

            # Get section content
            start = match.start()
            end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(content)
            section_content = content[start:end].strip()

            # Build chunk text with H1 context
            if intro_content:
                # Include H1 title for context
                chunk_text = f"# {h1_title}\n\n{section_content}"
            else:
                chunk_text = section_content

            # Detect section type
            section_type = self.detect_section_type(h2_heading)

            chunks.append(MarkdownChunk(
                text=chunk_text,
                metadata={
                    **base_metadata,
                    'h1_title': h1_title,
                    'h2_heading': h2_heading,
                    'section_type': section_type,
                }
            ))

        return chunks

    def parse_file(self, file_path: Path) -> List[MarkdownChunk]:
        """
        Parse a single markdown file into chunks.

        Args:
            file_path: Path to the markdown file

        Returns:
            List of MarkdownChunk objects
        """
        file_path = Path(file_path)

        if not file_path.exists():
            print(f"Warning: File not found: {file_path}")
            return []

        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []

        # Parse frontmatter
        frontmatter, body = self.parse_frontmatter(content)

        # Build base metadata
        base_metadata = {
            'title': frontmatter.get('title', file_path.stem),
            'source': frontmatter.get('source', ''),
            'collection': self.detect_collection(file_path),
            'category': self.get_category(file_path),
            'subcategory': self.detect_subcategory(file_path),
            'breadcrumb': self.build_breadcrumb(file_path),
            'file_path': str(file_path),
        }

        # Split by H2 sections
        chunks = self.split_by_h2(body, base_metadata)

        return chunks

    def parse_directory(self, dir_path: Optional[Path] = None) -> List[MarkdownChunk]:
        """
        Parse all markdown files in a directory recursively.

        Args:
            dir_path: Directory to parse. If None, uses base_dir.

        Returns:
            List of all MarkdownChunk objects
        """
        if dir_path is None:
            dir_path = self.base_dir
        else:
            dir_path = Path(dir_path)

        all_chunks = []
        md_files = list(dir_path.rglob('*.md'))

        print(f"Found {len(md_files)} markdown files in {dir_path}")

        for file_path in md_files:
            chunks = self.parse_file(file_path)
            all_chunks.extend(chunks)

        print(f"Created {len(all_chunks)} chunks from {len(md_files)} files")
        return all_chunks

    def parse_by_collection(self, collection: str) -> List[MarkdownChunk]:
        """
        Parse markdown files and filter by collection.

        Args:
            collection: Collection name (e.g., 'c3_plugins')

        Returns:
            List of MarkdownChunk objects in the specified collection
        """
        all_chunks = self.parse_directory()
        filtered = [c for c in all_chunks if c.metadata.get('collection') == collection]
        print(f"Filtered to {len(filtered)} chunks in collection '{collection}'")
        return filtered

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the markdown corpus.

        Returns:
            Dictionary with statistics
        """
        all_chunks = self.parse_directory()

        stats = {
            'total_chunks': len(all_chunks),
            'by_collection': {},
            'by_category': {},
            'by_subcategory': {},
            'by_section_type': {},
        }

        for chunk in all_chunks:
            # By collection
            collection = chunk.metadata.get('collection', 'unknown')
            stats['by_collection'][collection] = stats['by_collection'].get(collection, 0) + 1

            # By category
            category = chunk.metadata.get('category', 'unknown')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

            # By subcategory
            subcategory = chunk.metadata.get('subcategory') or 'none'
            stats['by_subcategory'][subcategory] = stats['by_subcategory'].get(subcategory, 0) + 1

            # By section_type
            section_type = chunk.metadata.get('section_type') or 'none'
            stats['by_section_type'][section_type] = stats['by_section_type'].get(section_type, 0) + 1

        return stats


def process_all_markdown():
    """Process all Construct 3 markdown documentation."""
    parser = MarkdownParser()

    # Get stats
    stats = parser.get_stats()

    print("\n=== Markdown Corpus Statistics ===")
    print(f"Total chunks: {stats['total_chunks']}")

    print("\nBy collection:")
    for collection, count in sorted(stats['by_collection'].items()):
        print(f"  {collection}: {count}")

    print("\nBy category:")
    for category, count in sorted(stats['by_category'].items()):
        print(f"  {category}: {count}")

    print("\nBy subcategory:")
    for subcategory, count in sorted(stats['by_subcategory'].items()):
        print(f"  {subcategory}: {count}")

    return parser.parse_directory()


if __name__ == "__main__":
    chunks = process_all_markdown()

    # Preview some chunks
    print("\n--- Sample Chunks ---")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\nChunk {i+1}:")
        print(f"  Title: {chunk.metadata.get('title')}")
        print(f"  Collection: {chunk.metadata.get('collection')}")
        print(f"  Category: {chunk.metadata.get('category')}")
        print(f"  Subcategory: {chunk.metadata.get('subcategory')}")
        print(f"  Breadcrumb: {chunk.metadata.get('breadcrumb')}")
        print(f"  H2: {chunk.metadata.get('h2_heading')}")
        print(f"  Text preview: {chunk.text[:200]}...")
