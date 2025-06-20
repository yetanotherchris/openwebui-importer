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


def detect_format(
    data: Any,
    *,
    validate_schema: bool = False,
    forced_format: Optional[str] = None,
) -> str:
    """Return the detected chat export format.

    When *validate_schema* is ``True`` the data is validated against the
    bundled JSON schemas which can be significantly slower. By default the
    function uses lightweight heuristics. If *forced_format* is provided,
    the function skips detection and optionally validates against the
    corresponding schema.
    """

    if forced_format:
        normalized = forced_format.lower()
        if normalized == "chatgpt":
            if validate_schema and isinstance(data, list):
                validate(instance=data, schema=CHATGPT_SCHEMA)
            return "ChatGPT"
        if normalized == "grok":
            if validate_schema and isinstance(data, dict):
                validate(instance=data, schema=GROK_SCHEMA)
            return "Grok"
        if normalized == "claude":
            if validate_schema and isinstance(data, (list, dict)):
                validate(instance=data, schema=CLAUDE_SCHEMA_EXAMPLE)
            return "Claude"
        raise ValueError(f"Unknown forced format: {forced_format}")

    # First try validating against the ChatGPT schema which expects an array of
    # conversations. Some exports may be a single conversation object, so we
    # only validate when a list is provided.
    if isinstance(data, list):
        if validate_schema:
            try:
                validate(instance=data, schema=CHATGPT_SCHEMA)
                return "ChatGPT"
            except ValidationError:
                pass

        # Heuristic detection for ChatGPT array exports
        if data and isinstance(data[0], dict):
            item = data[0]
            if "mapping" in item:
                return "ChatGPT"
            if "chat_messages" in item and "uuid" not in item:
                return "ChatGPT"
            if (
                ("title" in item or "name" in item)
                and any(k in item for k in ("create_time", "update_time"))
            ):
                return "ChatGPT"

            # Claude array exports contain uuid and chat_messages fields
            if {
                "uuid",
                "chat_messages",
            }.issubset(item.keys()):
                return "Claude"

    # Grok exports are objects; validate against the Grok schema.
    if isinstance(data, dict):
        if validate_schema:
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
            conversations = data.get("conversations")
            if isinstance(conversations, list) and conversations:
                first = conversations[0]
                if isinstance(first, dict) and {"conversation", "responses"}.issubset(first.keys()):
                    return "Claude"
            return "Grok"

        # ChatGPT single conversation heuristic fallback
        if "title" in data and "mapping" in data:
            return "ChatGPT"
        if "name" in data and "chat_messages" in data:
            return "ChatGPT"

    raise ValueError("Unknown export format")


def load_titles(
    path: str,
    *,
    validate_schema: bool = False,
    forced_format: Optional[str] = None,
) -> Tuple[str, List[str]]:
    """Return (format, titles) for the given JSON file.

    If *forced_format* is provided, the file is assumed to be in that format
    and detection is skipped (apart from optional validation).
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fmt = detect_format(data, validate_schema=validate_schema, forced_format=forced_format)

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
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                t = item.get('name') or item.get('title')
                if t:
                    titles.append(t)
        elif isinstance(data, dict):
            meta = data.get('meta', {})
            t = meta.get('title')
            if t:
                titles.append(t)
            if 'conversations' in data and isinstance(data['conversations'], list):
                for conv in data['conversations']:
                    if not isinstance(conv, dict):
                        continue
                    if 'conversation' in conv and isinstance(conv['conversation'], dict):
                        name = conv['conversation'].get('title') or conv['conversation'].get('name')
                        if name:
                            titles.append(name)
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


def load_titles_and_times(
    path: str,
    *,
    validate_schema: bool = False,
    forced_format: Optional[str] = None,
) -> Tuple[str, List[Tuple[str, Optional[datetime]]]]:
    """Return (format, [(title, datetime|None)]) for the given JSON file.

    Providing *forced_format* skips format detection and optionally validates
    the data against the corresponding schema.
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fmt = detect_format(data, validate_schema=validate_schema, forced_format=forced_format)

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
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                add(
                    item.get('name') or item.get('title'),
                    item.get('created_at') or item.get('updated_at'),
                )
        elif isinstance(data, dict):
            meta = data.get('meta', {})
            add(meta.get('title'), meta.get('exported_at'))
            if 'conversations' in data and isinstance(data['conversations'], list):
                for conv in data['conversations']:
                    if not isinstance(conv, dict):
                        continue
                    if 'conversation' in conv and isinstance(conv['conversation'], dict):
                        obj = conv['conversation']
                        add(
                            obj.get('title') or obj.get('name'),
                            obj.get('created_at') or obj.get('updated_at'),
                        )
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
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate input using JSON schemas (slower)",
    )
    parser.add_argument(
        "--format",
        choices=["Grok", "ChatGPT", "Claude"],
        help="Specify the chat export format to skip auto-detection",
    )
    args = parser.parse_args()

    for path in args.files:
        try:
            source, info = load_titles_and_times(
                path,
                validate_schema=args.validate,
                forced_format=args.format,
            )
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
