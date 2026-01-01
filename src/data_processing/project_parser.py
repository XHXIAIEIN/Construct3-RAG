"""
Project Parser for Construct 3 Example Projects
Parses event sheets and converts them to natural language descriptions
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import os


@dataclass
class EventBlock:
    """Represents a parsed event block"""
    project_name: str
    event_sheet: str
    event_type: str
    conditions: List[str]
    actions: List[str]
    natural_text: str
    raw_json: Dict[str, Any] = field(default_factory=dict)


class EventSheetParser:
    """Parse Construct 3 event sheet JSON files"""

    # Common condition ID mappings
    CONDITION_TEMPLATES = {
        "on-start-of-layout": "When the layout starts",
        "on-end-of-layout": "When the layout ends",
        "every-tick": "Every tick",
        "on-key-pressed": "When {key} key is pressed",
        "on-key-released": "When {key} key is released",
        "is-overlapping": "{object} is overlapping {other}",
        "on-collision": "{object} collides with {other}",
        "compare-instance-variable": "{object}.{variable} {comparison} {value}",
        "for-each": "For each {object}",
        "repeat": "Repeat {count} times",
        "is-visible": "{object} is visible",
        "is-between-angles": "{object} angle is between {a} and {b}",
        "trigger-once": "Trigger once while true",
        "on-timer": "On timer {tag}",
        "pick-random-instance": "Pick random {object}",
        "else": "Else",
    }

    # Common action ID mappings
    ACTION_TEMPLATES = {
        "set-position": "Set {object} position to ({x}, {y})",
        "set-x": "Set {object} X to {x}",
        "set-y": "Set {object} Y to {y}",
        "set-visible": "Set {object} {visibility}",
        "set-angle": "Set {object} angle to {angle}",
        "set-opacity": "Set {object} opacity to {opacity}",
        "set-size": "Set {object} size to ({width}, {height})",
        "set-instvar-value": "Set {object}.{variable} to {value}",
        "add-to-instvar": "Add {value} to {object}.{variable}",
        "subtract-from-instvar": "Subtract {value} from {object}.{variable}",
        "spawn-object": "Spawn {object} at ({x}, {y})",
        "create-object": "Create {object} at ({x}, {y})",
        "destroy": "Destroy {object}",
        "go-to-layout": "Go to layout {layout}",
        "restart-layout": "Restart layout",
        "set-text": "Set {object} text to {text}",
        "play-sound": "Play sound {audio}",
        "set-animation": "Set {object} animation to {animation}",
        "start-timer": "Start timer {tag} for {duration}s",
        "stop-timer": "Stop timer {tag}",
        "move-at-angle": "Move {object} at angle {angle} by {distance}",
        "set-enabled": "{behavior} {state}",
        "find-path": "Find path to ({x}, {y})",
        "wait": "Wait {seconds} seconds",
        "scroll-to": "Scroll to {object}",
    }

    def __init__(self):
        self.events: List[EventBlock] = []

    def parse_condition(self, cond: Dict[str, Any]) -> str:
        """Convert condition JSON to natural language"""
        cond_id = cond.get("id", "unknown")
        obj_class = cond.get("objectClass", "")
        params = cond.get("parameters", {})

        # Handle params being a list instead of dict
        if isinstance(params, list):
            if params:
                param_str = ", ".join(str(p) for p in params)
                return f"{obj_class}.{cond_id}({param_str})"
            else:
                return f"{obj_class}.{cond_id}"

        # Check for template (only for dict params)
        if cond_id in self.CONDITION_TEMPLATES:
            template = self.CONDITION_TEMPLATES[cond_id]
            try:
                # Filter out 'object' from params to avoid conflict with explicit arg
                filtered_params = {k: v for k, v in params.items() if k != "object"}
                return template.format(
                    object=obj_class,
                    **filtered_params
                )
            except KeyError:
                pass

        # Fallback to generic format
        if params:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            return f"{obj_class}.{cond_id}({param_str})"
        else:
            return f"{obj_class}.{cond_id}"

    def parse_action(self, action: Dict[str, Any]) -> str:
        """Convert action JSON to natural language"""
        action_id = action.get("id", "unknown")
        obj_class = action.get("objectClass", "")
        params = action.get("parameters", {})

        # Handle params being a list instead of dict
        if isinstance(params, list):
            if params:
                param_str = ", ".join(str(p) for p in params)
                return f"{obj_class}.{action_id}({param_str})"
            else:
                return f"{obj_class}.{action_id}()"

        # Check for template (only for dict params)
        if action_id in self.ACTION_TEMPLATES:
            template = self.ACTION_TEMPLATES[action_id]
            try:
                # Filter out 'object' from params to avoid conflict with explicit arg
                filtered_params = {k: v for k, v in params.items() if k != "object"}
                return template.format(
                    object=obj_class,
                    **filtered_params
                )
            except KeyError:
                pass

        # Fallback to generic format
        if params:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            return f"{obj_class}.{action_id}({param_str})"
        else:
            return f"{obj_class}.{action_id}()"

    def parse_event_block(self, event: Dict[str, Any], project_name: str, sheet_name: str) -> Optional[EventBlock]:
        """Parse a single event block"""
        event_type = event.get("eventType", "")

        if event_type == "comment":
            # Skip comments but we could extract them for context
            return None

        if event_type == "variable":
            # Event variable declaration
            name = event.get("name", "")
            var_type = event.get("type", "")
            initial = event.get("initialValue", "")
            return EventBlock(
                project_name=project_name,
                event_sheet=sheet_name,
                event_type="variable",
                conditions=[],
                actions=[],
                natural_text=f"Declare {var_type} variable '{name}' = {initial}",
                raw_json=event
            )

        if event_type == "block":
            conditions = [self.parse_condition(c) for c in event.get("conditions", [])]
            actions = [self.parse_action(a) for a in event.get("actions", [])]

            # Build natural language description
            cond_text = " AND ".join(conditions) if conditions else "Always"
            action_text = "; ".join(actions) if actions else "No actions"
            natural_text = f"When: {cond_text}\nDo: {action_text}"

            return EventBlock(
                project_name=project_name,
                event_sheet=sheet_name,
                event_type="block",
                conditions=conditions,
                actions=actions,
                natural_text=natural_text,
                raw_json=event
            )

        if event_type == "function":
            # Function declaration
            name = event.get("name", "")
            return EventBlock(
                project_name=project_name,
                event_sheet=sheet_name,
                event_type="function",
                conditions=[],
                actions=[],
                natural_text=f"Function: {name}",
                raw_json=event
            )

        return None

    def parse_event_sheet(self, json_path: Path, project_name: str) -> List[EventBlock]:
        """Parse an event sheet JSON file"""
        blocks = []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  Warning: Failed to parse {json_path}: {e}")
            return blocks

        sheet_name = data.get("name", json_path.stem)
        events = data.get("events", [])

        for event in events:
            block = self.parse_event_block(event, project_name, sheet_name)
            if block:
                blocks.append(block)

            # Parse children (sub-events)
            for child in event.get("children", []):
                child_block = self.parse_event_block(child, project_name, sheet_name)
                if child_block:
                    blocks.append(child_block)

        return blocks

    def parse_project(self, project_dir: Path) -> List[EventBlock]:
        """Parse all event sheets in a project"""
        project_name = project_dir.name
        blocks = []

        event_sheets_dir = project_dir / "eventSheets"
        if not event_sheets_dir.exists():
            return blocks

        for json_file in event_sheets_dir.glob("*.json"):
            sheet_blocks = self.parse_event_sheet(json_file, project_name)
            blocks.extend(sheet_blocks)

        return blocks


class ProjectParser:
    """Parse Construct 3 project files and metadata"""

    def __init__(self):
        self.event_parser = EventSheetParser()
        self.projects: List[Dict[str, Any]] = []

    def parse_c3proj(self, c3proj_path: Path) -> Dict[str, Any]:
        """Parse project.c3proj for metadata"""
        try:
            with open(c3proj_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

        project = data.get("project", {})

        return {
            "name": c3proj_path.parent.name,
            "description": project.get("description", ""),
            "author": project.get("author", ""),
            "version": project.get("version", ""),
            "viewport_width": project.get("viewportWidth", 0),
            "viewport_height": project.get("viewportHeight", 0),
            "plugins_used": list(data.get("usedAddons", [])) if "usedAddons" in data else [],
        }

    def parse_all_projects(self, projects_dir: Path) -> List[Dict[str, Any]]:
        """Parse all projects in the example-projects directory"""
        print(f"Scanning projects in: {projects_dir}")

        self.projects = []
        project_dirs = [d for d in projects_dir.iterdir() if d.is_dir()]

        print(f"Found {len(project_dirs)} projects")

        for i, project_dir in enumerate(project_dirs):
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(project_dirs)} projects...")

            # Find c3proj file
            c3proj_files = list(project_dir.glob("*.c3proj"))
            if not c3proj_files:
                continue

            # Parse project metadata
            metadata = self.parse_c3proj(c3proj_files[0])

            # Parse event sheets
            events = self.event_parser.parse_project(project_dir)

            project_data = {
                **metadata,
                "path": str(project_dir),
                "event_count": len(events),
                "events": events
            }

            self.projects.append(project_data)

        print(f"Parsed {len(self.projects)} projects")
        return self.projects

    def export_for_vectordb(self) -> List[Dict[str, Any]]:
        """Export parsed data for vector database"""
        documents = []

        for project in self.projects:
            # Create project summary document
            doc = {
                "id": f"project_{project['name']}",
                "type": "project",
                "text": f"Project: {project['name']}\n{project.get('description', '')}",
                "metadata": {
                    "name": project["name"],
                    "event_count": project["event_count"],
                    "plugins": project.get("plugins_used", [])
                }
            }
            documents.append(doc)

            # Create event documents
            for i, event in enumerate(project.get("events", [])):
                event_doc = {
                    "id": f"event_{project['name']}_{i}",
                    "type": "event",
                    "text": event.natural_text,
                    "metadata": {
                        "project": project["name"],
                        "event_sheet": event.event_sheet,
                        "event_type": event.event_type,
                        "conditions": event.conditions,
                        "actions": event.actions
                    }
                }
                documents.append(event_doc)

        return documents

    def get_statistics(self) -> Dict[str, Any]:
        """Get parsing statistics"""
        total_events = sum(p["event_count"] for p in self.projects)

        return {
            "total_projects": len(self.projects),
            "total_events": total_events,
            "avg_events_per_project": total_events / len(self.projects) if self.projects else 0
        }


def process_example_projects():
    """Process all Construct 3 example projects"""
    from src.config import EXAMPLE_PROJECTS_DIR

    parser = ProjectParser()

    if EXAMPLE_PROJECTS_DIR.exists():
        projects = parser.parse_all_projects(EXAMPLE_PROJECTS_DIR)

        # Print statistics
        stats = parser.get_statistics()
        print(f"\n--- Statistics ---")
        print(f"Total projects: {stats['total_projects']}")
        print(f"Total events: {stats['total_events']}")
        print(f"Avg events/project: {stats['avg_events_per_project']:.1f}")

        return parser
    else:
        print(f"Error: Directory not found: {EXAMPLE_PROJECTS_DIR}")
        return None


if __name__ == "__main__":
    parser = process_example_projects()

    if parser and parser.projects:
        # Preview first project
        print("\n--- Sample Project ---")
        sample = parser.projects[0]
        print(f"Project: {sample['name']}")
        print(f"Events: {sample['event_count']}")

        if sample.get("events"):
            print("\nFirst few events:")
            for event in sample["events"][:3]:
                print(f"\n[{event.event_type}] {event.event_sheet}")
                print(event.natural_text)
