"""Feature manifest management - read/write ~/.claude/knowledge/_meta/features/."""
import re
from dataclasses import dataclass, field
from pathlib import Path

FEATURES_DIR = Path.home() / ".claude" / "knowledge" / "_meta" / "features"


@dataclass
class Feature:
    ticket_id: str
    description: str
    sessions: list[str] = field(default_factory=list)


def _parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result: dict = {}
    current_list_key = None
    for line in m.group(1).splitlines():
        if re.match(r"^  - (.+)", line) and current_list_key is not None:
            result[current_list_key].append(line[4:].strip())
        elif ": " in line or line.endswith(":"):
            current_list_key = None
            if ": " in line:
                k, v = line.split(": ", 1)
                k = k.strip()
                if v.strip() == "[]":
                    result[k] = []
                    current_list_key = k
                else:
                    result[k] = v.strip()
            else:
                k = line.rstrip(":").strip()
                result[k] = []
                current_list_key = k
    return result


def load_features() -> list[Feature]:
    if not FEATURES_DIR.exists():
        return []
    features = []
    for path in sorted(FEATURES_DIR.glob("*.md")):
        try:
            data = _parse_frontmatter(path.read_text())
            sessions = data.get("sessions", [])
            if not isinstance(sessions, list):
                sessions = []
            features.append(Feature(
                ticket_id=data.get("ticket", path.stem),
                description=data.get("description", ""),
                sessions=sessions,
            ))
        except Exception:
            pass
    return features


def create_feature(ticket_id: str, description: str) -> Path:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FEATURES_DIR / f"{ticket_id}.md"
    if not path.exists():
        path.write_text(
            f"---\n"
            f"ticket: {ticket_id}\n"
            f"description: {description}\n"
            f"sessions: []\n"
            f"---\n\n"
            f"# Feature: {ticket_id}\n\n"
            f"{description}\n"
        )
    return path


def link_session(ticket_id: str, session_name: str) -> bool:
    """Add session_name to the sessions list of the feature manifest."""
    path = FEATURES_DIR / f"{ticket_id}.md"
    if not path.exists():
        return False
    text = path.read_text()
    if f"- {session_name}" in text:
        return True
    if "sessions: []" in text:
        text = text.replace("sessions: []", f"sessions:\n  - {session_name}")
    else:
        text = re.sub(
            r"(sessions:\n(?:  - [^\n]+\n)*)",
            rf"\1  - {session_name}\n",
            text,
        )
    path.write_text(text)
    return True
