import argparse
import json
import os
from jsonschema import validate, ValidationError

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schemas")

with open(os.path.join(SCHEMA_DIR, "chatgpt-schema.json"), "r", encoding="utf-8") as f:
    CHATGPT_SCHEMA = json.load(f)

with open(os.path.join(SCHEMA_DIR, "grok-schema.json"), "r", encoding="utf-8") as f:
    GROK_SCHEMA = json.load(f)

with open(os.path.join(SCHEMA_DIR, "claude-schema.json"), "r", encoding="utf-8") as f:
    CLAUDE_SCHEMA_EXAMPLE = json.load(f)
from datetime import datetime
from typing import Any, List, Tuple, Optional


def ordinal(n: int) -> str:
    """Return an ordinal string for the given integer."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_human_date(dt: datetime) -> str:
    """Return a human-readable date like 'Mon 23rd June 2025'."""
    weekday = dt.strftime("%a")
    day = ordinal(dt.day)
    month = dt.strftime("%B")
    year = dt.year
    return f"{weekday} {day} {month} {year}"


def detect_format(data: Any) -> str:
    """Return the detected chat export format using bundled JSON schemas."""

    # First try validating against the ChatGPT schema which expects an array of
    # conversations. Some exports may be a single conversation object, so we
    # only validate when a list is provided.
    if isinstance(data, list):
        try:
            validate(instance=data, schema=CHATGPT_SCHEMA)
            return "ChatGPT"
        except ValidationError:
            pass

    # Grok exports are objects; validate against the Grok schema.
    if isinstance(data, dict):
        try:
            validate(instance=data, schema=GROK_SCHEMA)
            return "Grok"
        except ValidationError:
            pass

        # Claude currently ships with an example file instead of a formal JSON
        # schema. Detect it by checking for the keys we see in that example.
        if "meta" in data and "chats" in data:
            return "Claude"

        if "conversations" in data:
            return "Grok"

        # ChatGPT single conversation heuristic fallback
        if "title" in data and "mapping" in data:
            return "ChatGPT"
        if "name" in data and "chat_messages" in data:
            return "ChatGPT"

    raise ValueError("Unknown export format")


def load_titles(path: str) -> Tuple[str, List[str]]:
    """Return (format, titles) for the given JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fmt = detect_format(data)

    titles: List[str] = []
    if fmt == 'ChatGPT':
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                t = item.get('title') or item.get('name')
                if t:
                    titles.append(t)
        elif isinstance(data, dict):
            t = data.get('title') or data.get('name')
            if t:
                titles.append(t)
    elif fmt == 'Claude':
        meta = data.get('meta', {}) if isinstance(data, dict) else {}
        t = meta.get('title')
        if t:
            titles.append(t)
    elif fmt == 'Grok':
        if 'conversations' in data and isinstance(data['conversations'], list):
            for conv in data['conversations']:
                if not isinstance(conv, dict):
                    continue
                if 'conversation' in conv and isinstance(conv['conversation'], dict):
                    t = conv['conversation'].get('title')
                    if t:
                        titles.append(t)
                elif 'title' in conv:
                    t = conv['title']
                    if t:
                        titles.append(t)
        else:
            t = data.get('title')
            if t:
                titles.append(t)

    return fmt, titles


def load_titles_and_times(path: str) -> Tuple[str, List[Tuple[str, Optional[datetime]]]]:
    """Return (format, [(title, datetime|None)]) for the given JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fmt = detect_format(data)

    results: List[Tuple[str, Optional[datetime]]] = []

    def add(title: Optional[str], ts: Optional[Any]) -> None:
        if not title:
            return
        dt: Optional[datetime] = None
        if ts is not None:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts)
                elif isinstance(ts, str):
                    dt = datetime.fromisoformat(ts)
            except Exception:
                dt = None
        results.append((title, dt))

    if fmt == 'ChatGPT':
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                add(item.get('title') or item.get('name'), item.get('create_time') or item.get('update_time'))
        elif isinstance(data, dict):
            add(data.get('title') or data.get('name'), data.get('create_time') or data.get('update_time'))
    elif fmt == 'Claude':
        meta = data.get('meta', {}) if isinstance(data, dict) else {}
        add(meta.get('title'), meta.get('exported_at'))
    elif fmt == 'Grok':
        if 'conversations' in data and isinstance(data['conversations'], list):
            for conv in data['conversations']:
                if not isinstance(conv, dict):
                    continue
                if 'conversation' in conv and isinstance(conv['conversation'], dict):
                    obj = conv['conversation']
                    title = obj.get('title')
                    ts = obj.get('create_time') or obj.get('modify_time')
                else:
                    title = conv.get('title')
                    ts = conv.get('create_time') or conv.get('modify_time')
                add(title, ts)
        else:
            add(data.get('title'), data.get('create_time') or data.get('modify_time'))

    return fmt, results


def main() -> None:
    parser = argparse.ArgumentParser(description="List chat titles from export files")
    parser.add_argument("files", nargs="+", help="Chat export JSON files")
    parser.add_argument(
        "--no-dates",
        action="store_true",
        help="Only print titles without their timestamps",
    )
    args = parser.parse_args()

    for path in args.files:
        try:
            source, info = load_titles_and_times(path)
        except Exception as e:
            print(f"{path}: failed to parse - {e}")
            continue

        print(f"{path} ({source}):")

        def sort_key(item: Tuple[str, Optional[datetime]]) -> Tuple[float, str]:
            title, ts = item
            ts_value = ts.timestamp() if ts is not None else float('-inf')
            # negative ts_value gives descending order when using ascending sort
            return (-ts_value, title)

        for title, ts in sorted(info, key=sort_key):
            if args.no_dates or ts is None:
                print(f'  - "{title}"')
            else:
                date_str = format_human_date(ts)
                print(f'  - {date_str}: "{title}"')


if __name__ == '__main__':
    main()
