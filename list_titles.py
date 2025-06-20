import json
import sys
from datetime import datetime
from typing import Any, List, Tuple, Optional


def ordinal(n: int) -> str:
    """Return an ordinal string for the given integer."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def detect_format(data: Any) -> str:
    """Return the detected chat export format."""
    if isinstance(data, list):
        return 'ChatGPT'

    if isinstance(data, dict):
        if 'meta' in data and 'chats' in data:
            return 'Claude'
        if 'conversations' in data:
            return 'Grok'
        if 'title' in data and 'mapping' in data:
            return 'Grok'
        if 'name' in data and 'chat_messages' in data:
            return 'ChatGPT'

    raise ValueError('Unknown export format')


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


def main():
    if len(sys.argv) < 2:
        print('Usage: python list_titles.py <export.json> [more.json ...]')
        sys.exit(1)

    files: List[Tuple[str, str, List[Tuple[str, Optional[datetime]]]]] = []

    for path in sys.argv[1:]:
        try:
            source, info = load_titles_and_times(path)
        except Exception as e:
            print(f"{path}: failed to parse - {e}")
            continue
        files.append((path, source, info))
        print(f"{path} ({source}):")
        for title, _ in sorted(info, key=lambda x: x[0]):
            print(f"  - {title}")

    answer = input("Show chat timestamps? [y/N]: ").strip().lower()
    if answer.startswith('y'):
        for path, source, info in files:
            print(f"{path} ({source}) timestamps:")
            for title, ts in sorted(info, key=lambda x: x[0]):
                if ts is None:
                    print(f"  - {title}: n/a")
                else:
                    print(f"  - {title}: {ts.isoformat(sep=' ', timespec='seconds')}")


if __name__ == '__main__':
    main()
