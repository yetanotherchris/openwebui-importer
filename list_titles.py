import json
import sys
from typing import Any, List, Tuple


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


def main():
    if len(sys.argv) < 2:
        print('Usage: python list_titles.py <export.json> [more.json ...]')
        sys.exit(1)

    for path in sys.argv[1:]:
        try:
            source, titles = load_titles(path)
        except Exception as e:
            print(f"{path}: failed to parse - {e}")
            continue
        print(f"{path} ({source}):")
        for title in titles:
            print(f"  - {title}")


if __name__ == '__main__':
    main()
